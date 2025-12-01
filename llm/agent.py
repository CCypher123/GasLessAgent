# llm_agent.py
import json
import os
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_tools import x402_relay_tool
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

# 当前文件 llm/chat.py -> parents[1] 就是 project_root
BASE_DIR = Path(__file__).resolve().parents[1]
env_path = BASE_DIR / "properties.env"

# 调试一下（可以先打印看看）
print("ENV PATH:", env_path, "exists:", env_path.exists())

load_dotenv(env_path)


SYSTEM_PROMPT = """
你是一个 Web3 助手，可以通过工具 x402_relay 代用户在链上发起代币转账。
使用说明：
1）当用户请求“帮我转账”时，你可以调用 x402_relay 工具，
   在第一次调用时不要填写 payment_tx_hash（让它为 null 或不传）。
   工具会返回 http_status 和 data。
2）如果 http_status/ data.status 是 402，
   说明需要用户先付费。你需要用自然语言告诉用户：
   - 使用哪个网络（network）
   - 使用哪个代币（asset 地址）
   - 转多少代币（required_fee 对应的人类数量，你可以简单说明不需要非常精确）
   - 转给哪个地址（payTo）
   然后请用户用钱包完成转账，并把交易哈希 txHash 发给你。
   不要在没有 txHash 的情况下再次调用工具。
3）当用户提供 txHash 后，
   你在第二次调用 x402_relay 时，带上 payment_tx_hash 字段，
   工具成功返回 status=200 时，向用户说明：
   - 代办的转账已发送
   - relayTx 的哈希
4）如果工具返回错误信息或 http_status 非 200/402，
   请把错误简要解释给用户。
"""
llm = ChatOpenAI(
        model="gpt-5-nano",
    )
checkpointer = MemorySaver()  # 自动按 thread_id 存历史

agent = create_agent(llm, tools=[x402_relay_tool],
                     checkpointer=checkpointer,
                     system_prompt=SYSTEM_PROMPT,
                     )

def chat_once(user_input: str):

    result = agent.invoke({
        "messages": [
            HumanMessage(content=user_input)
        ]
    })
    return result

def chat(session_id: str, user_input: str) -> str:
    """
    session_id: 对话线程 id（比如用钱包地址、用户 id 等）
    user_input: 当前这一轮用户说的话
    返回：这一轮模型的自然语言回复
    """
    config = {"configurable": {"thread_id": session_id}}

    # 直接用 invoke 拿“最终状态”
    result = agent.invoke(
        {"messages": [("user", user_input)]},
        config=config,
    )

    # LangGraph state 里，messages 是完整对话（包含这轮）
    messages = result["messages"]
    last = messages[-1]
    # last 通常就是最后一条 assistant 消息
    return last.content if getattr(last, "content", None) else ""

