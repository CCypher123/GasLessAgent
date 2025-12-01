# gasless_api.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from sign.eip3009_meta import (
    user_account,
    relayer_account,
    human_to_atomic,
    build_transfer_authorization,
    relay_two_auth,
)

app = FastAPI()


class BuildAuthDemoRequest(BaseModel):
    from_addr: Optional[str] = None   # 不传就用 user_account
    to_addr: str                      # B
    amount: str                       # 本金（人类单位）
    fee: str = "0.01"                 # 手续费（人类单位）


@app.post("/build_auth_demo")
def build_auth_demo(req: BuildAuthDemoRequest):
    """
    开发阶段使用：后端帮你“模拟前端签名”，
    返回两份授权 auth_main / auth_fee（以后前端钱包会自己生成同款结构）。
    """
    from_addr = req.from_addr or user_account.address
    to_main = req.to_addr
    to_service = relayer_account.address

    amount_atomic = human_to_atomic(req.amount)
    fee_atomic = human_to_atomic(req.fee)

    # A -> B
    auth_main = build_transfer_authorization(
        from_addr=from_addr,
        to_addr=to_main,
        value_atomic=amount_atomic,
    )

    # A -> Service
    auth_fee = build_transfer_authorization(
        from_addr=from_addr,
        to_addr=to_service,
        value_atomic=fee_atomic,
    )

    return {
        "code": 0,
        "data": {
            "from": from_addr,
            "to_main": to_main,
            "to_service": to_service,
            "amount": req.amount,
            "fee": req.fee,
            "auth_main": auth_main,
            "auth_fee": auth_fee,
        },
    }

class AuthPayload(BaseModel):
    from_: str
    to: str
    value: str
    validAfter: str
    validBefore: str
    nonce: str
    v: int
    r: str
    s: str

    def to_dict(self) -> dict:
        return {
            "from": self.from_,
            "to": self.to,
            "value": self.value,
            "validAfter": self.validAfter,
            "validBefore": self.validBefore,
            "nonce": self.nonce,
            "v": self.v,
            "r": self.r,
            "s": self.s,
        }


class RelayWithAuthRequest(BaseModel):
    auth_main: AuthPayload   # A -> B
    auth_fee: AuthPayload    # A -> Service


@app.post("/relay_with_auth")
def relay_with_auth(req: RelayWithAuthRequest):
    """
    通用接口：前端/LLM/x402 都可以直接调用。
    要求：调用方已经做好两份授权签名（auth_main / auth_fee）。
    本接口只负责用 relayer 播两笔 meta-tx。
    """
    auth_main = req.auth_main.to_dict()
    auth_fee = req.auth_fee.to_dict()

    try:
        result = relay_two_auth(auth_main, auth_fee)
        return {
            "code": 0,
            "data": result,
        }
    except Exception as e:
        return {
            "code": 1,
            "error": str(e),
        }