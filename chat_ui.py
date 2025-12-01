# chat_ui.py
import streamlit as st
import uuid

from llm.agent import chat

st.set_page_config(page_title="x402 Web3 Chat")

st.title("x402 Web3 助手 Demo")

# 1. 初始化 session_state
if "thread_id" not in st.session_state:
    # 用一个随机的 uuid 作为这次会话的 thread_id
    st.session_state["thread_id"] = str(uuid.uuid4())
    print(st.session_state["thread_id"])

if "messages" not in st.session_state:
    # 存放前端展示用的对话历史
    st.session_state["messages"] = []
    # 系统欢迎语
    st.session_state["messages"].append({
        "role": "assistant",
        "content": "你好，我是基于 x402 的 Web3 转账助手。\n你可以直接说：\
“我的地址是 0x...，帮我给 0x... 转 0.1 USDC”，我会帮你完成收费和代付流程。"
    })

# 2. 渲染历史消息
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 3. 接收用户新输入
user_input = st.chat_input("请输入你的问题或指令...")

if user_input:
    # 3.1 先把用户消息加到历史里
    st.session_state["messages"].append({
        "role": "user",
        "content": user_input
    })
    with st.chat_message("user"):
        st.markdown(user_input)

    # 3.2 调用后端 LLM agent
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                reply = chat(st.session_state["thread_id"], user_input)
            except Exception as e:
                reply = f"调用后端出错了：{e}"

            st.markdown(reply)

    # 3.3 把助手回复也写入历史
    st.session_state["messages"].append({
        "role": "assistant",
        "content": reply
    })