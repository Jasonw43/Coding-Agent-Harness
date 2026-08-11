"""Streamlit demo console for Streamlit Community Cloud (free tier)."""

from __future__ import annotations

import time

import streamlit as st

from cah.web.hf_console import DemoConsole

console = DemoConsole()

st.set_page_config(page_title="cah 审批台", layout="wide")
st.title("cah 审批台（demo 模式）")
st.caption("mock LLM + 只读沙箱：启动演示后观察 agent 尝试危险动作并等待人工审批。")

if "run_id" not in st.session_state:
    st.session_state.run_id = ""

if st.button("启动演示运行"):
    st.session_state.run_id = console.start_demo()
    time.sleep(2)  # give the demo thread time to submit the approval
    st.success(f"demo 已启动：{st.session_state.run_id}（如下表仍为空，点『刷新』）")

if st.button("刷新"):
    st.rerun()

st.subheader("待审批动作")
pending = console.pending()
if pending:
    st.table(
        [
            {"action_id": p["action_id"], "reason": p["reason"], "token": p["token"]}
            for p in pending
        ]
    )
else:
    st.write("（无）")

st.subheader("审批")
aid = st.text_input("action id", key="aid")
tok = st.text_input("token", key="tok")
col1, col2 = st.columns(2)
if col1.button("批准") and aid and tok:
    st.info(console.decide(aid, tok, "approve"))
if col2.button("拒绝") and aid and tok:
    st.info(console.decide(aid, tok, "reject"))

st.subheader("运行事件流")
run_id = st.session_state.run_id
st.code(console.events_text(run_id) if run_id else "（尚未启动）")
