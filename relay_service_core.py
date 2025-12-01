# relay_service_core.py
from web3 import Web3
from chain_utils import get_web3, get_relayer_account, get_token_address
from erc20_utils import get_erc20_contract, human_to_token_amount
from verify_payment import verify_token_payment
from relay_token import relay_token_transfer


def handle_paid_and_relay(
    payment_tx_hash: str,
    user_address: str,
    relay_to_address: str,
    relay_amount_human: str | float,
    required_fee_human: str | float = "0.2",
):
    """
    整体流程：
    1. 校验 payment_tx_hash 是否为 user 向 service 地址支付 required_fee 的转账
    2. 如果验证通过，则用 relayer 帮他向 relay_to_address 转 relay_amount_human 代币
    """
    w3 = get_web3()
    relayer = get_relayer_account(w3)
    token_addr = get_token_address()

    service_address = relayer.address  # 简化：服务费就收在 relayer 钱包里
    print("[DEBUG] user_address   =", user_address)
    print("[DEBUG] service_address=", service_address)
    print("[DEBUG] token_addr     =", token_addr)
    print("[DEBUG] payment_tx_hash=", payment_tx_hash)
    # 1. 先验证用户支付
    ok = verify_token_payment(
        tx_hash=payment_tx_hash,
        user_address=user_address,
        service_address=service_address,
        token_address=token_addr,
        required_amount_human=required_fee_human,
    )
    if not ok:
        return {
            "ok": False,
            "step": "verify_payment",
            "msg": "Payment verification failed",
        }

    # 2. 通过则代办转账
    relay_tx_hash, status = relay_token_transfer(relay_to_address, relay_amount_human)
    if status != 1:
        return {
            "ok": False,
            "step": "relay_transfer",
            "msg": "Relay transfer failed on-chain",
            "relay_tx": relay_tx_hash,
        }

    return {
        "ok": True,
        "step": "done",
        "msg": "Payment verified and relay tx sent",
        "relay_tx": relay_tx_hash,
        "service_address": service_address,
    }