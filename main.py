# main.py (全能版)
import json
import re
import uvicorn
import random
from decimal import Decimal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 引入原本 app_x402.py 里的工具链
# 确保 chain_utils.py 和 sign/ 文件夹在同一级目录
from chain_utils import get_web3, get_relayer_account, get_token_address
from erc20_utils import human_to_token_amount
from sign.eip3009_meta import relay_two_auth

# ================= 配置 =================
TOKEN_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238" # Sepolia USDC
CHAIN_ID = 11155111
BASE_FEE = Decimal("0.01") # 固定收 0.01 USDC 服务费
MAX_UINT256 = "115792089237316195423570985008687907853269984665640564039457584007913129639935"
# =======================================

app = FastAPI(title="x402 Merged Agent")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    thread_id: str
    message: str

def random_nonce():
    """生成 32 字节的随机 Nonce"""
    return "0x" + "".join([random.choice("0123456789abcdef") for _ in range(64)])

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    msg = req.message
    print(f"🔹 收到消息: {msg[:60]}...")

    # ==========================================================
    # 场景 A: 处理签名结果 -> 直接上链
    # (逻辑来自原 app_x402.py)
    # ==========================================================
    if "[System:Signed]" in msg:
        try:
            # 1. 解析前端传来的签名数据
            json_payload = msg.split("[System:Signed]")[1].strip()
            signed_data = json.loads(json_payload)
            
            auth_main = signed_data.get('auth_main')
            auth_fee = signed_data.get('auth_fee')

            if not auth_main or not auth_fee:
                return {"reply": "❌ 错误: 签名数据缺失。"}

            print("📡 正在验证签名并广播交易...")

            # 2. 调用工具链直接上链 (不再需要 Base64 解码和 HTTP 请求)
            # relay_two_auth 函数在 sign/eip3009_meta.py 中
            tx_result = relay_two_auth(auth_main, auth_fee)
            
            tx_main = tx_result["tx_main"]
            tx_fee = tx_result["tx_fee"]

            return {"reply": f"""
### 🎉 交易成功上链！

无需 Gas 费，交易已由 Relayer 完成：

1. **主转账**: [`{tx_main[:12]}...`](https://sepolia.etherscan.io/tx/{tx_main})
2. **服务费**: [`{tx_fee[:12]}...`](https://sepolia.etherscan.io/tx/{tx_fee})
"""}

        except Exception as e:
            print(f"❌ 上链失败: {e}")
            # 捕获 Web3 报错 (如 Meta-tx failed)
            return {"reply": f"❌ **上链失败**\n原因: `{str(e)}`\n(可能是余额不足 0.02 USDC 或签名版本号不对)"}

    # ==========================================================
    # 场景 B: 解析意图 -> 生成签名请求
    # (逻辑来自原 api.py，但不再请求外部，直接计算)
    # ==========================================================
    
    # 正则提取：给 0x... 转 10
    target_match = re.search(r"(0x[a-fA-F0-9]{40})", msg)
    amount_match = re.search(r"(\d+(\.\d+)?)", msg)
    my_addr_match = re.search(r"My Wallet Address is (0x[a-fA-F0-9]{40})", msg)

    if target_match and amount_match and my_addr_match:
        user_addr = my_addr_match.group(1)
        
        # 寻找目标地址（排除自己）
        all_addrs = re.findall(r"(0x[a-fA-F0-9]{40})", msg)
        to_addr = next((a for a in all_addrs if a.lower() != user_addr.lower()), user_addr)

        # 提取金额
        try:
            amount_str = re.search(r"转\s*(\d+(\.\d+)?)", msg).group(1)
        except:
            amount_str = amount_match.group(1)

        print(f"🔍 解析: {user_addr} -> {to_addr} | Amount: {amount_str}")

        try:
            # 1. 获取链上数据 (用于计算精度)
            w3 = get_web3()
            # 获取 Relayer 地址 (收款服务费的人)
            relayer_account = get_relayer_account(w3)
            service_addr = relayer_account.address

            # 2. 计算原子单位 (Atomic Amount)
            # 例如 1 USDC -> 1000000
            amount_dec = Decimal(amount_str)
            main_atomic = human_to_token_amount(w3, TOKEN_ADDRESS, amount_dec)
            fee_atomic = human_to_token_amount(w3, TOKEN_ADDRESS, BASE_FEE)

            # 3. 构造前端需要的 JSON (Batch Sign)
            response_json = {
                "action": "batch_sign_auth",
                "tasks": [
                    {
                        "id": "auth_main",
                        "label": f"1. 签署转账本金 ({amount_str} USDC)",
                        "domain": { 
                            "name": "USDC", 
                            "version": "2", # ✅ 确保是 Sepolia 的 v2
                            "chainId": CHAIN_ID, 
                            "verifyingContract": TOKEN_ADDRESS 
                        },
                        "types": {
                            "TransferWithAuthorization": [
                                {"name": "from", "type": "address"},
                                {"name": "to", "type": "address"},
                                {"name": "value", "type": "uint256"},
                                {"name": "validAfter", "type": "uint256"},
                                {"name": "validBefore", "type": "uint256"},
                                {"name": "nonce", "type": "bytes32"}, 
                            ]
                        },
                        "message": {
                            "from": user_addr,
                            "to": to_addr,
                            "value": str(main_atomic),
                            "validAfter": 0,
                            "validBefore": MAX_UINT256, # ✅ 确保是十进制字符串
                            "nonce": random_nonce()
                        }
                    },
                    {
                        "id": "auth_fee",
                        "label": "2. 签署代付服务费 (0.01 USDC)",
                        "domain": { 
                            "name": "USDC", 
                            "version": "2", # ✅ 确保是 Sepolia 的 v2
                            "chainId": CHAIN_ID, 
                            "verifyingContract": TOKEN_ADDRESS 
                        },
                        "types": {
                            "TransferWithAuthorization": [
                                {"name": "from", "type": "address"},
                                {"name": "to", "type": "address"},
                                {"name": "value", "type": "uint256"},
                                {"name": "validAfter", "type": "uint256"},
                                {"name": "validBefore", "type": "uint256"},
                                {"name": "nonce", "type": "bytes32"},
                            ]
                        },
                        "message": {
                            "from": user_addr,
                            "to": service_addr,
                            "value": str(fee_atomic),
                            "validAfter": 0,
                            "validBefore": MAX_UINT256, # ✅ 确保是十进制字符串
                            "nonce": random_nonce()
                        }
                    }
                ]
            }

            return {"reply": f"""### 🧾 订单确认

已准备好代付交易：

- **转账**: {amount_str} USDC
- **目标**: `{to_addr[:6]}...{to_addr[-4:]}`
- **服务费**: 0.01 USDC

请点击下方按钮签名。

```json
{json.dumps(response_json, indent=2)}
"""
}
        except Exception as e:
            return {"reply": f"❌ 构建交易失败: {str(e)}"}

    return {"reply": "你好，我是 x402 助手。请说“给 0x... 转 1 USDC”。"}

if __name__ == "__main__":
    print("🚀 Merged Server 正在启动 (Port: 9000)...")
    uvicorn.run(app, host="0.0.0.0", port=9000)