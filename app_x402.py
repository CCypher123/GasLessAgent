# app_x402.py
import base64
import json
import ast
from decimal import Decimal

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chain_utils import get_web3, get_relayer_account, get_token_address
from erc20_utils import human_to_token_amount
from sign.eip3009_meta import relay_two_auth, human_to_atomic, relayer_account

app = FastAPI(title="x402 Relay Demo (Sepolia / USDC)")

# ==== x402 配置 ====
X402_VERSION = 1
SCHEME = "eip3009-2auth"          # 自定义的 scheme：用两份 EIP-3009 授权完成 A->B + A->Service          # 自定义的 scheme，含义：用 txHash + 普通转账来证明已付款
NETWORK = "eip155:11155111"         # Sepolia 的 CAIP-2 network id
BASE_FEE = Decimal("0.01")          # 手续费
MAX_TIMEOUT_SECONDS = 60            # 承诺多快完成代办


class RelayBody(BaseModel):
    """
    用户希望我们帮他做的事：帮 user 给 to_address 转 amount 个 Token。
    （user_address 只是用来校验付款是否真的是这个人付的）
    """
    user_address: str
    to_address: str
    amount: str


def build_payment_required_response(resource_url: str, amount_human: str) -> dict:
    w3 = get_web3()
    relayer = get_relayer_account(w3)
    token_addr = get_token_address()

    amount_dec = Decimal(amount_human)
    main_amount_atomic = human_to_token_amount(w3, token_addr, amount_dec)
    fee_amount_atomic = human_to_token_amount(w3, token_addr, BASE_FEE)

    total_required_atomic = main_amount_atomic + fee_amount_atomic

    payment_req = {
        "scheme": SCHEME,
        "network": NETWORK,
        # 这里 maxAmountRequired 可以理解为：需要从 A 地址扣掉的总 token 数量
        "maxAmountRequired": str(total_required_atomic),
        "resource": resource_url,
        "description": (
            "Provide two EIP-3009 authorizations: "
            "main(A->to_address, amount) and fee(A->service, BASE_FEE). "
            "Relayer pays gas and broadcasts meta-txs."
        ),
        "mimeType": "application/json",
        # payTo 可以理解为服务费的接收方
        "payTo": relayer.address,
        "maxTimeoutSeconds": MAX_TIMEOUT_SECONDS,
        "asset": token_addr,
        "extra": {
            "name": "USDC",
            "version": "1",
            "mainAmountAtomic": str(main_amount_atomic),
            "feeAtomic": str(fee_amount_atomic),
            "serviceAddress": relayer.address,
        },
    }

    return {
        "x402Version": X402_VERSION,
        "accepts": [payment_req],
        "error": "",
    }


@app.get("/")
def root():
    return {"msg": "x402-style relay server running"}


@app.post("/relay")
async def relay_endpoint(
    request: Request,
    body: RelayBody,
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
):
    """
    这是一个符合 x402 流程的受保护资源（EIP-3009 版本）：
    - 如果没有 X-PAYMENT 头 → 返回 402 + PaymentRequiredResponse
    - 如果有 X-PAYMENT 头 → 解码 payload，校验两份授权 → 播两笔 meta-tx → 返回 200
    """
    w3 = get_web3()
    relayer = get_relayer_account(w3)
    token_addr = get_token_address()

    resource_url = str(request.url)

    # 没有 X-PAYMENT 头：告诉你「需要两份 EIP-3009 授权」
    if x_payment is None:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        return JSONResponse(status_code=402, content=pay_resp)

    # 有 X-PAYMENT 头：解码并检查 PaymentPayload
    try:
        decoded = base64.b64decode(x_payment).decode("utf-8")
    except Exception as e:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = f"X-PAYMENT base64 decode failed: {e}"
        return JSONResponse(status_code=402, content=pay_resp)

    # 调试：看看到底收到什么
    print("X-PAYMENT decoded raw:", repr(decoded))

    # 尝试 1：当作标准 JSON 解析
    try:
        payment_payload = json.loads(decoded)
    except Exception as e1:
        # 尝试 2：当作 Python 字面量解析（兼容一些奇怪的引号/转义）
        try:
            payment_payload = ast.literal_eval(decoded)
        except Exception as e2:
            pay_resp = build_payment_required_response(resource_url, body.amount)
            pay_resp["error"] = f"Invalid X-PAYMENT header (json+literal_eval failed): {e2}"
            return JSONResponse(status_code=402, content=pay_resp)

    # 基本字段校验
    if payment_payload.get("x402Version") != X402_VERSION:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "Unsupported x402Version"
        return JSONResponse(status_code=402, content=pay_resp)

    if payment_payload.get("scheme") != SCHEME or payment_payload.get("network") != NETWORK:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "Unsupported scheme or network"
        return JSONResponse(status_code=402, content=pay_resp)

    payload_inner = payment_payload.get("payload", {}) or {}
    auth_main = payload_inner.get("auth_main")
    auth_fee = payload_inner.get("auth_fee")

    if not isinstance(auth_main, dict) or not isinstance(auth_fee, dict):
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "Missing auth_main or auth_fee in payment payload"
        return JSONResponse(status_code=402, content=pay_resp)

    # ==== 业务一致性检查（可选但推荐） ====
    # 1) 确认授权的 from = body.user_address
    user_addr_lower = body.user_address.lower()
    if auth_main.get("from", "").lower() != user_addr_lower:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "auth_main.from != body.user_address"
        return JSONResponse(status_code=402, content=pay_resp)
    if auth_fee.get("from", "").lower() != user_addr_lower:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "auth_fee.from != body.user_address"
        return JSONResponse(status_code=402, content=pay_resp)

    # 2) 确认授权的 to（主转账给 body.to_address，手续费给 relayer）
    if auth_main.get("to", "").lower() != body.to_address.lower():
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "auth_main.to != body.to_address"
        return JSONResponse(status_code=402, content=pay_resp)
    if auth_fee.get("to", "").lower() != relayer.address.lower():
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "auth_fee.to != relayer.address"
        return JSONResponse(status_code=402, content=pay_resp)

    # 3) 确认 value 金额正确（金额 = amount, 手续费 = BASE_FEE）
    amount_dec = Decimal(body.amount)
    main_amount_atomic = human_to_token_amount(w3, token_addr, amount_dec)
    fee_amount_atomic = human_to_token_amount(w3, token_addr, BASE_FEE)

    if str(auth_main.get("value")) != str(main_amount_atomic):
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "auth_main.value != expected amount"
        return JSONResponse(status_code=402, content=pay_resp)
    if str(auth_fee.get("value")) != str(fee_amount_atomic):
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "auth_fee.value != expected fee"
        return JSONResponse(status_code=402, content=pay_resp)

    # ==== 授权校验通过 → relayer 播两笔 meta-tx ====
    try:
        tx_result = relay_two_auth(auth_main, auth_fee)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "msg": "Relay meta-tx failed on-chain",
                "error": str(e),
            },
        )

    # 构造 X-PAYMENT-RESPONSE（也是 base64(JSON)）
    settlement = {
        "x402Version": X402_VERSION,
        "scheme": SCHEME,
        "network": NETWORK,
        "relayTxMain": tx_result["tx_main"],
        "relayTxFee": tx_result["tx_fee"],
    }
    settlement_b64 = base64.b64encode(json.dumps(settlement).encode("utf-8")).decode("ascii")

    headers = {
        "X-PAYMENT-RESPONSE": settlement_b64,
    }

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "message": "Authorizations accepted and meta-txs sent",
            "relayTxMain": tx_result["tx_main"],
            "relayTxFee": tx_result["tx_fee"],
        },
        headers=headers,
    )