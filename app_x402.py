# app_x402.py
import base64
import json
from decimal import Decimal

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chain_utils import get_web3, get_relayer_account, get_token_address
from erc20_utils import human_to_token_amount
from verify_payment import verify_token_payment
from relay_token import relay_token_transfer

app = FastAPI(title="x402 Relay Demo (Sepolia / USDC)")

# ==== x402 配置 ====
X402_VERSION = 1
SCHEME = "simple-transfer"          # 自定义的 scheme，含义：用 txHash + 普通转账来证明已付款
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

    # 总共需要用户转过来的数量 = 本金 + 手续费
    total_required_human = (Decimal(amount_human) + BASE_FEE)
    max_amount_atomic = str(human_to_token_amount(w3, token_addr, total_required_human))

    payment_req = {
        "scheme": SCHEME,
        "network": NETWORK,
        "maxAmountRequired": max_amount_atomic,
        "resource": resource_url,
        "description": "Pay amount+fee, relayer forwards amount and keeps fee",
        "mimeType": "application/json",
        "payTo": relayer.address,
        "maxTimeoutSeconds": MAX_TIMEOUT_SECONDS,
        "asset": token_addr,
        "extra": {
            "name": "USDC",
            "version": "1"
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
    这是一个符合 x402 流程的受保护资源：
    - 如果没有 X-PAYMENT 头 → 返回 402 + PaymentRequiredResponse
    - 如果有 X-PAYMENT 头 → 解码 payload，链上校验付款 → 代办转账 → 返回 200 + 业务结果
    """
    w3 = get_web3()
    relayer = get_relayer_account(w3)
    token_addr = get_token_address()

    resource_url = str(request.url)

    # 没有 X-PAYMENT 头：告诉你「要付多少钱、付给谁」
    # app_x402.py 里 /relay 端点
    if x_payment is None:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        return JSONResponse(status_code=402, content=pay_resp)

    # 有 X-PAYMENT 头：解码并检查 PaymentPayload
    try:
        decoded = base64.b64decode(x_payment).decode("utf-8")
        payment_payload = json.loads(decoded)
    except Exception as e:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = f"Invalid X-PAYMENT header: {e}"
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
    tx_hash = payload_inner.get("txHash")
    payer = payload_inner.get("from")

    if not tx_hash or not payer:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "Missing txHash or from in payment payload"
        return JSONResponse(status_code=402, content=pay_resp)

    # 用链上逻辑校验：payer -> relayer 是否真的付了 REQUIRED_FEE
    total_required_human = (Decimal(body.amount) + BASE_FEE)

    ok = verify_token_payment(
        tx_hash=tx_hash,
        user_address=payer,
        service_address=relayer.address,
        token_address=token_addr,
        required_amount_human=str(total_required_human),
    )
    if not ok:
        pay_resp = build_payment_required_response(resource_url, body.amount)
        pay_resp["error"] = "On-chain payment verification failed. Please check your transaction and txHash"
        return JSONResponse(status_code=402, content=pay_resp)

    # 付款校验通过 → relayer 代办转账
    relay_tx_hash, status = relay_token_transfer(body.to_address, body.amount)
    if status != 1:
        raise HTTPException(
            status_code=500,
            detail={
                "msg": "Relay transfer failed on-chain",
                "relay_tx": relay_tx_hash,
            },
        )

    # 构造 X-PAYMENT-RESPONSE（也是 base64(JSON)）
    settlement = {
        "x402Version": X402_VERSION,
        "scheme": SCHEME,
        "network": NETWORK,
        "paidTxHash": tx_hash,
        "relayTxHash": relay_tx_hash,
    }
    settlement_b64 = base64.b64encode(json.dumps(settlement).encode("utf-8")).decode("ascii")

    headers = {
        "X-PAYMENT-RESPONSE": settlement_b64,
    }

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "message": "Payment verified and relay tx sent",
            "relayTx": relay_tx_hash,
        },
        headers=headers,
    )