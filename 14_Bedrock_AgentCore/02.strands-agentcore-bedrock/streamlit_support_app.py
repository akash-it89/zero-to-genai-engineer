"""
Local Streamlit UI for the Strands Support Copilot Runtime.

    export SUPPORT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/strands_support_copilot-XXXX"
    export AWS_PROFILE=inceptez
    export AWS_REGION=us-east-1
    streamlit run streamlit_support_app.py
"""

from __future__ import annotations

import json
import os
import re
import uuid

import boto3
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ARN = os.getenv("SUPPORT_RUNTIME_ARN", "").strip()


def region_from_arn(arn: str) -> str:
    m = re.match(r"^arn:aws:bedrock-agentcore:([a-z0-9-]+):", arn or "")
    return m.group(1) if m else os.getenv("AWS_REGION", "us-east-1")


def invoke_runtime(*, arn: str, prompt: str, actor_id: str, thread_id: str, session_id: str) -> str:
    region = region_from_arn(arn)
    client = boto3.client("bedrock-agentcore", region_name=region)
    if len(session_id) < 33:
        session_id = f"{session_id}-{uuid.uuid4().hex}"[:64]
    payload = json.dumps(
        {"prompt": prompt, "actor_id": actor_id, "thread_id": thread_id}
    ).encode("utf-8")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        runtimeUserId=(actor_id or "streamlit-user")[:128],
        payload=payload,
        qualifier="DEFAULT",
    )
    body = response.get("response") or response.get("body")
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return str(data.get("result") or data)
        return str(data)
    except json.JSONDecodeError:
        return str(raw)


st.set_page_config(page_title="Lauki Support Copilot (Strands)", page_icon="📱", layout="centered")
st.title("Lauki Support Copilot")
st.caption("Strands agent on Bedrock AgentCore Runtime + Memory")

with st.sidebar:
    arn = st.text_input("Runtime ARN", value=DEFAULT_ARN)
    actor_id = st.text_input("actor_id", value="streamlit-user")
    if st.button("New chat session"):
        st.session_state.runtime_session_id = str(uuid.uuid4())
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = str(uuid.uuid4())
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask about Lauki activation, eSIM, plans, roaming…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        if not arn.strip():
            answer = "Set SUPPORT_RUNTIME_ARN (sidebar) first."
        else:
            with st.spinner("Invoking AgentCore Runtime…"):
                try:
                    answer = invoke_runtime(
                        arn=arn.strip(),
                        prompt=prompt.strip(),
                        actor_id=actor_id.strip() or "streamlit-user",
                        thread_id=st.session_state.thread_id,
                        session_id=st.session_state.runtime_session_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    answer = f"Invoke failed: {exc}"
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
