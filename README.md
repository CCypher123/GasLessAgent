# GasLessAgent – x402 + EIP-3009 Gasless Transfer Demo

一个基于 **Ethereum / Sepolia** 的 gasless 转账 Demo。  
用户只需要 **签名两份授权**，不需要自己付 gas，由服务端 Relayer 代为广播交易并支付 gas。

项目同时演示了：

- 如何用 **EIP-3009 (transferWithAuthorization)** 做 meta-transaction
- 如何用 **x402 风格的 402 / X-PAYMENT 头** 做“用户先付费 / 授权，再访问受保护资源”
- 如何用 **大模型（LLM）+ LangChain / LangGraph** 做一个 Web3 助手，引导用户完成 gasless 转账流程

---

## 目录结构

```text
GasLessAgent/
├── llm/
│   ├── agent.py        # LLM 入口：创建带工具的 agent，管理多轮对话
│   └── llm_tools.py    # x402_relay 工具（调用 /relay 接口）
│
├── sign/
│   ├── eip3009_abi.py  # EIP-3009 相关 ABI 定义
│   └── eip3009_meta.py # EIP-3009 授权构造与 meta-tx 播放逻辑
│
├── app_x402.py         # x402 网关服务：/relay 受保护资源（主入口）
├── gasless_api.py      # 开发调试用 API（签名 demo、直接 relay 等）
├── chain_utils.py      # Web3 初始化与链上通用工具
├── erc20_utils.py      # ERC-20 / USDC 相关工具函数
├── chat_ui.py          # 简单的聊天界面（本地跑 LLM + 工具）
└── properties.env      # 配置文件（RPC、私钥、USDC 地址、OpenAI Key 等）
```
## 快速开始
```text
pip install -r requirements.txt
```
新增并编辑 `properties.env` 文件，配置 RPC、私钥、OpenAI Key 等：
```bash
#以太坊Sepolia测试网RPC URL（Alchemy）,请替换为你自己的API Key
RPC_URL_SEPOLIA=https://eth-sepolia.g.alchemy.com/v2/your-api-key
#钱包1-服务端Relayer账户私钥
RELAYER_PRIVATE_KEY=
#钱包2-模拟用户账户私钥-仅在纯后端无前端进行模拟签名时候使用，正常无需配置
USER_PRIVATE_KEY=
#USDC合约地址-以太坊Sepolia测试网
TOKEN_ADDRESS=0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238
TOKEN_NAME=USDC
CHAIN_ID=11155111

OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-nano

#langSmith链路监控配置
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=GasLessAgent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
```
运行 `app_x402.py` 启动 x402 网关：
```bash
uvicorn app_x402:app --reload --port 8000
```
（可选）运行 `chat_ui.py` 启动最简demo聊天界面：
```bash
python chat_ui.py
```
（可选）启动开发辅助 API（用于本地签名调试）：
```bash
uvicorn gasless_api:app --reload --port 8001
```
## 前端所需工作
1.构造两份授权（使用钱包签名 EIP-712）：
 - auth_main：A → B，本金
 - auth_fee：A → Service，手续费 
```text
    "auth_main": {
      "from": "",
      "to": "",
      "value": "",
      "validAfter": "",
      "validBefore": "",
      "nonce": "",
      "v": ,
      "r": "",
      "s": ""
    },
    "auth_fee": {
      "from": "",
      "to": "",
      "value": "",
      "validAfter": "",
      "validBefore": "",
      "nonce": "",
      "v": ,
      "r": "",
      "s": ""
    }
```
2.构造聊天界面，并美化/屏蔽传入以上参数的记录