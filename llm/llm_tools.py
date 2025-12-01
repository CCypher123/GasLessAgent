# llm_tools.py
import os
import base64
import json
import requests
from typing import Optional
from langchain.tools import tool

X402_SERVER_URL = os.getenv("X402_SERVER_URL", "http://127.0.0.1:8000/relay")

X402_VERSION = 1
SCHEME = "eip3009-2auth"
NETWORK = "eip155:11155111"

@tool("x402_relay")
def x402_relay_tool(
    user_address: str,
    to_address: str,
    amount: str,
    payload_json: Optional[str] = None,
) -> str:
    """
    通过 x402 受保护的 /relay 接口，代用户在链上发起 gasless 代币转账（EIP-3009 两份授权）。

    使用方式（两步）：
    1）第一次调用：不要提供 payload_json。
       - 工具会直接 POST /relay（没有 X-PAYMENT），收到 402 和 PaymentRequiredResponse。
       - 你应该把里面的 network / asset / amount / fee / serviceAddress 解释给用户，
         提醒 TA 使用自己的签名接口生成两份授权（auth_main / auth_fee），
         然后只需把「包含 auth_main 和 auth_fee 的 JSON」发给你，例如：
         {
           "auth_main": { ... },
           "auth_fee": { ... }
         }

    2）第二次调用：当用户提供了 payload_json（只包含 auth_main/auth_fee）时，
       - 工具会在内部包装成完整的 X-PAYMENT JSON：
         {
           "x402Version": 1,
           "scheme": "eip3009-2auth",
           "network": "eip155:11155111",
           "payload": <payload_json 解析出来的 dict>
         }
       - 再 base64 编码后放入 X-PAYMENT 头，请求 /relay。
    """
    body = {
        "user_address": user_address,
        "to_address": to_address,
        "amount": amount,
    }

    headers = {}

    if payload_json:
        try:
            inner = json.loads(payload_json)  # 这里预期是 {"auth_main": {...}, "auth_fee": {...}}
        except Exception as e:
            return json.dumps(
                {
                    "http_status": 0,
                    "data": {
                        "error": f"payload_json 不是合法 JSON: {e}",
                        "raw": payload_json,
                    },
                },
                ensure_ascii=False,
            )

        full_payload = {
            "x402Version": X402_VERSION,
            "scheme": SCHEME,
            "network": NETWORK,
            "payload": inner,
        }
        json_str = json.dumps(full_payload)
        b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
        headers["X-PAYMENT"] = b64

    try:
        resp = requests.post(X402_SERVER_URL, json=body, headers=headers, timeout=30)
    except Exception as e:
        return json.dumps(
            {
                "http_status": 0,
                "data": {
                    "error": f"Request to x402 server failed: {e}",
                },
            },
            ensure_ascii=False,
        )

    try:
        data = resp.json()
    except Exception:
        return json.dumps(
            {
                "http_status": resp.status_code,
                "data": {
                    "error": "Non-JSON response from x402 server",
                    "raw": resp.text,
                },
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "http_status": resp.status_code,
            "data": data,
        },
        ensure_ascii=False,
    )