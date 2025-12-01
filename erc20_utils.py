# erc20_utils.py
from web3 import Web3
from decimal import Decimal
from chain_utils import get_web3, get_token_address

# 最小 ERC20 ABI，只要 transfer / decimals / balanceOf
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    # 事件 Transfer
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "_from", "type": "address"},
            {"indexed": True, "name": "_to", "type": "address"},
            {"indexed": False, "name": "_value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]

def get_erc20_contract(w3: Web3, token_addr: str = None):
    if token_addr is None:
        token_addr = get_token_address()
    token_addr = Web3.to_checksum_address(token_addr)
    return w3.eth.contract(address=token_addr, abi=ERC20_ABI)

def human_to_token_amount(w3: Web3, token_addr: str, amount_human: str | float | Decimal) -> int:
    """
    把“人类读得懂的数量”（如 "0.2" USDC）转成最小单位的整数（如 200000）
    """
    contract = get_erc20_contract(w3, token_addr)
    decimals = contract.functions.decimals().call()

    # 用 Decimal 避免浮点误差
    amt = Decimal(str(amount_human))
    scaled = amt * (Decimal(10) ** decimals)
    return int(scaled)