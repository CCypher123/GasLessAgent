# verify_payment.py
from web3 import Web3
from chain_utils import get_web3
from erc20_utils import get_erc20_contract, human_to_token_amount

# 预计算 Transfer 事件的 topic0
TRANSFER_TOPIC0 = Web3.keccak(text="Transfer(address,address,uint256)").hex()

def verify_token_payment(
    tx_hash: str,
    user_address: str,
    service_address: str,
    token_address: str,
    required_amount_human: str | float,
) -> bool:
    """
    校验：这笔 tx 是否为 user -> service 的 token transfer
    且转账数量 >= required_amount_human
    """
    w3 = get_web3()
    user = Web3.to_checksum_address(user_address)
    service = Web3.to_checksum_address(service_address)
    token_addr = Web3.to_checksum_address(token_address)

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        print("get_transaction_receipt error:", e)
        return False

    # 1. 交易是否成功
    if receipt.status != 1:
        print("Tx failed, status != 1")
        return False

    # 2. 是否 token 合约上的 Transfer 事件
    # 计算 required_amount_int
    required_amount_int = human_to_token_amount(w3, token_addr, required_amount_human)

    token = get_erc20_contract(w3, token_addr)

    # 遍历 logs 找 Transfer 事件
    paid_amount = 0
    matched = False

    for log in receipt.logs:
        # 必须是这个 token 合约的 log
        if log.address.lower() != token_addr.lower():
            continue

        # 必须是 Transfer 事件
        if log.topics[0].hex() != TRANSFER_TOPIC0:
            continue

        # topics[1] = from, topics[2] = to
        from_addr = "0x" + log.topics[1].hex()[-40:]
        to_addr = "0x" + log.topics[2].hex()[-40:]

        from_addr = Web3.to_checksum_address(from_addr)
        to_addr = Web3.to_checksum_address(to_addr)

        # 我们只关注 user -> service 的转账
        if from_addr != user or to_addr != service:
            continue

        # data 里是 uint256 value
        value_int = Web3.to_int(log.data)

        paid_amount += value_int
        matched = True

    if not matched:
        print("No matching Transfer(user -> service) found in logs")
        return False

    if paid_amount < required_amount_int:
        print(f"Paid {paid_amount}, required {required_amount_int}")
        return False

    print("Payment verified OK")
    return True

