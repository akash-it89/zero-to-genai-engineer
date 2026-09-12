"""
Local Streamlit UI for the CrewAI Competitor Brief Runtime.

    export CREW_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/crewai_competitor_brief-XXXX"
    export AWS_PROFILE=inceptez
    export AWS_REGION=us-east-1
    streamlit run streamlit_crew_app.py
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
DEFAULT_ARN = os.getenv("CREW_RUNTIME_ARN", "").strip()


def region_from_arn(arn: str) -> str:
    m = re.match(r"^arn:aws:bedrock-agentcore:([a-z0-9-]+):", arn or "")
    return m.group(1) if m else os.getenv("AWS_REGION", "us-east-1")


def invoke_runtime(*, arn: str, prompt: str, actor_id: str, thread_id: str, session_id: str) -> dict:
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
        return data if isinstance(data, dict) else {"result": str(data)}
    except json.JSONDecodeError:
        return {"result": str(raw)}


st.set_page_config(page_title="Competitor Brief Crew", page_icon="🧭", layout="centered")
st.title("Competitor Brief Crew")
st.caption("CrewAI · Researcher → Analyst → Writer on AgentCore Runtime")

with st.sidebar:
    arn = st.text_input("Runtime ARN", value=DEFAULT_ARN)
    actor_id = st.text_input("actor_id", value="streamlit-user")
    st.markdown("**Pipeline**")
    st.markdown("1. Researcher  \n2. Analyst  \n3. Writer")
    if st.button("New session"):
        st.session_state.runtime_session_id = str(uuid.uuid4())
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.history = []
        st.rerun()

if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = str(uuid.uuid4())
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []

for item in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(item["topic"])
    with st.chat_message("assistant"):
        st.markdown(item["result"])

topic = st.chat_input("Topic for competitor brief (e.g. AgentCore vs DIY agents)")
if topic:
    with st.chat_message("user"):
        st.markdown(topic)
    with st.chat_message("assistant"):
        if not arn.strip():
            answer = "Set CREW_RUNTIME_ARN in the sidebar first."
            stages = []
        else:
            with st.spinner("Crew running on AgentCore (may take 30–90s)…"):
                try:
                    data = invoke_runtime(
                        arn=arn.strip(),
                        prompt=topic.strip(),
                        actor_id=actor_id.strip() or "streamlit-user",
                        thread_id=st.session_state.thread_id,
                        session_id=st.session_state.runtime_session_id,
                    )
                    answer = str(data.get("result") or data)
                    stages = data.get("stages") or ["researcher", "analyst", "writer"]
                except Exception as exc:  # noqa: BLE001
                    answer = f"Invoke failed: {exc}"
                    stages = []
        if stages:
            st.info("Stages: " + " → ".join(stages))
        st.markdown(answer)
    st.session_state.history.append({"topic": topic, "result": answer})
