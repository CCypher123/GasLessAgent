# relay_token.py
from web3 import Web3
from chain_utils import get_web3, get_relayer_account, get_token_address
from erc20_utils import get_erc20_contract, human_to_token_amount

def relay_token_transfer(to_address: str, amount_human: str | float):
    """
    用 relayer 钱包帮用户发一笔 ERC20 转账（你出 gas）
    - to_address: 收款地址
    - amount_human: "0.5" 之类的人类可读数量（代币单位）
    """
    w3 = get_web3()
    relayer = get_relayer_account(w3)
    token_addr = get_token_address()
    token = get_erc20_contract(w3, token_addr)

    to = Web3.to_checksum_address(to_address)
    amount_int = human_to_token_amount(w3, token_addr, amount_human)

    # 构造交易
    tx = token.functions.transfer(to, amount_int).build_transaction(
        {
            "from": relayer.address,
            "nonce": w3.eth.get_transaction_count(relayer.address),
            "chainId": w3.eth.chain_id,
            # gas 粗估一个值，Sepolia 宽裕一点没问题
            "gas": 150000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
        }
    )

    signed = relayer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("Sent token tx:", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Token tx status:", receipt.status)

    return tx_hash.hex(), receipt.status

if __name__ == "__main__":
    to = ""
    tx_hash, status = relay_token_transfer(to, "0.2")
    print("Done:", tx_hash, status)