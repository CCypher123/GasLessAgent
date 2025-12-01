# eip3009_meta.py
import os
import time
import uuid
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_typed_data

from sign.eip3009_abi import EIP3009_ABI

BASE_DIR = Path(__file__).resolve().parents[1]
env_path = BASE_DIR / "properties.env"

print("ENV PATH:", env_path, "exists:", env_path.exists())

load_dotenv(env_path)

RPC_URL = os.getenv("RPC_URL_SEPOLIA")
TOKEN_ADDRESS = os.getenv("TOKEN_ADDRESS")
CHAIN_ID = int(os.getenv("CHAIN_ID", "11155111"))

USER_PRIVATE_KEY = os.getenv("USER_PRIVATE_KEY")        # A：用户
RELAYER_PRIVATE_KEY = os.getenv("RELAYER_PRIVATE_KEY")  # Service：代播+收手续费

w3 = Web3(Web3.HTTPProvider(RPC_URL))
user_account = Account.from_key(USER_PRIVATE_KEY)
relayer_account = Account.from_key(RELAYER_PRIVATE_KEY)

token = w3.eth.contract(
    address=Web3.to_checksum_address(TOKEN_ADDRESS),
    abi=EIP3009_ABI,
)

try:
    DECIMALS = token.functions.decimals().call()
except Exception:
    DECIMALS = 6  # USDC 风格

TOKEN_NAME = os.getenv("TOKEN_NAME", "USD Coin")
TOKEN_VERSION = os.getenv("TOKEN_VERSION", "2")


def human_to_atomic(human: str | Decimal) -> int:
    if not isinstance(human, Decimal):
        human = Decimal(str(human))
    return int(human * (Decimal(10) ** DECIMALS))


def random_nonce_bytes32() -> bytes:
    return uuid.uuid4().bytes


def build_transfer_authorization(
    from_addr: str,
    to_addr: str,
    value_atomic: int,
    valid_for_seconds: int = 3600,
) -> dict:
    """
    构造一份 TransferWithAuthorization 的 EIP-712 授权，并用【用户私钥】签名。
    当前阶段：用于后端模拟“前端签名”。
    未来：前端自己实现同样结构的签名即可，无需改后端 relay 逻辑。
    """
    now = int(time.time())
    valid_after = 0
    valid_before = now + valid_for_seconds

    raw_nonce = random_nonce_bytes32()
    nonce = raw_nonce.rjust(32, b"\x00")  # pad 到 32 bytes

    domain = {
        "name": TOKEN_NAME,
        "version": TOKEN_VERSION,
        "chainId": CHAIN_ID,
        "verifyingContract": Web3.to_checksum_address(TOKEN_ADDRESS),
    }

    types = {
        "EIP712Domain": [
            {"name": "name",              "type": "string"},
            {"name": "version",           "type": "string"},
            {"name": "chainId",           "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "TransferWithAuthorization": [
            {"name": "from",        "type": "address"},
            {"name": "to",          "type": "address"},
            {"name": "value",       "type": "uint256"},
            {"name": "validAfter",  "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce",       "type": "bytes32"},
        ],
    }

    message = {
        "from": Web3.to_checksum_address(from_addr),
        "to": Web3.to_checksum_address(to_addr),
        "value": int(value_atomic),
        "validAfter": int(valid_after),
        "validBefore": int(valid_before),
        "nonce": nonce,
    }

    signable = encode_typed_data(
        # domain_data=domain,
        # message_types=types,
        # message_data=message,
        full_message={
            "types": types,
            "primaryType": "TransferWithAuthorization",
            "domain": domain,
            "message": message
        }
    )
    signed = user_account.sign_message(signable)

    v = signed.v
    r = signed.r
    s = signed.s

    # 这里返回“前端未来要给你”的 payload 结构
    return {
        "from": message["from"],
        "to": message["to"],
        "value": str(message["value"]),
        "validAfter": str(message["validAfter"]),
        "validBefore": str(message["validBefore"]),
        "nonce": Web3.to_hex(message["nonce"]),
        "v": v,
        "r": Web3.to_hex(r),
        "s": Web3.to_hex(s),
    }

def relay_with_authorization(auth: dict) -> str:
    """
    只负责：用 relayer 私钥调用 transferWithAuthorization。
    auth: 必须包含 from/to/value/validAfter/validBefore/nonce/v/r/s 字段
    返回 tx_hash(hex)
    """
    from_addr = auth["from"]
    to_addr = auth["to"]
    value = int(auth["value"])
    valid_after = int(auth["validAfter"])
    valid_before = int(auth["validBefore"])
    nonce = Web3.to_bytes(hexstr=auth["nonce"])
    v = int(auth["v"])
    r = Web3.to_bytes(hexstr=auth["r"])
    s = Web3.to_bytes(hexstr=auth["s"])

    tx = token.functions.transferWithAuthorization(
        Web3.to_checksum_address(from_addr),
        Web3.to_checksum_address(to_addr),
        value,
        valid_after,
        valid_before,
        nonce,
        v, r, s,
    ).build_transaction(
        {
            "from": relayer_account.address,
            "nonce": w3.eth.get_transaction_count(relayer_account.address),
            "chainId": CHAIN_ID,
            "gas": 200_000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
        }
    )

    signed = relayer_account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("Sent meta-tx:", tx_hash.hex())
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Status:", receipt.status)
    if receipt.status != 1:
        raise RuntimeError("Meta-tx failed")
    return tx_hash.hex()

def relay_two_auth(auth_main: dict, auth_fee: dict) -> dict:
    """
    播两笔 meta-tx：
    1) auth_main: A -> B（本金）
    2) auth_fee:  A -> Service（手续费）
    """
    tx_main = relay_with_authorization(auth_main)
    tx_fee = relay_with_authorization(auth_fee)
    return {"tx_main": tx_main, "tx_fee": tx_fee}
