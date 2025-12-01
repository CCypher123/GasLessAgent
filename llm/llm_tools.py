# llm_tools.py
import os
import base64
import json
import requests
from typing import Optional
from langchain.tools import tool

X402_SERVER_URL = os.getenv("X402_SERVER_URL", "http://127.0.0.1:8000/relay")

@tool("x402_relay")
def x402_relay_tool(
    user_address: str,
    to_address: str,
    amount: str,
    payment_tx_hash: Optional[str] = None,
) -> str:
    """
    通过 x402 受保护的 /relay 接口，代用户在链上转账（由服务端代付 gas）。
    使用方式：
    - 第一步：不提供 payment_tx_hash，调用后会返回 status=402 和支付要求。
      你应该把这个信息转述给用户，提醒 TA 用钱包完成支付，并让 TA 提供 txHash。
    - 第二步：当用户提供 txHash 后，再次调用本工具，并把 payment_tx_hash 填上。
      如果成功，会返回 status=200 和 relayTx。
    """
    body = {
        "user_address": user_address,
        "to_address": to_address,
        "amount": amount,
    }

    headers = {}
    if payment_tx_hash:
        # 构造 PaymentPayload（和 app_x402.py 对应）
        payment_payload = {
            "x402Version": 1,
            "scheme": "simple-transfer",
            "network": "eip155:11155111",
            "payload": {
                "txHash": payment_tx_hash,
                "from": user_address,
            },
        }
        b64 = base64.b64encode(json.dumps(payment_payload).encode("utf-8")).decode("ascii")
        headers["X-PAYMENT"] = b64

    resp = requests.post(X402_SERVER_URL, json=body, headers=headers)
    # 直接把后端 JSON + status_code 包一层返回，让大模型自己看 status 决定说什么
    try:
        data = resp.json()
    except Exception:
        return f"Request failed with status {resp.status_code}, body: {resp.text}"

    return json.dumps(
        {
            "http_status": resp.status_code,
            "data": data,
        },
        ensure_ascii=False,
    )