# chain_utils.py
from web3 import Web3
from dotenv import load_dotenv
import os
load_dotenv("properties.env")


def get_web3():
    rpc_url = os.getenv("RPC_URL_SEPOLIA")
    if not rpc_url:
        raise RuntimeError("RPC_URL_SEPOLIA not set in .env")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("Web3 not connected, check RPC_URL_SEPOLIA")
    return w3

def get_relayer_account(w3: Web3):
    private_key = os.getenv("RELAYER_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("RELAYER_PRIVATE_KEY not set in .env")

    account = w3.eth.account.from_key(private_key)
    return account

def get_token_address():
    addr = os.getenv("TOKEN_ADDRESS")
    if not addr:
        raise RuntimeError("TOKEN_ADDRESS not set in .env")
    return addr