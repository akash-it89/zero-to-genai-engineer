"""
Thin API in front of AgentCore Runtime (React must not hold AWS keys).

  export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
  export AWS_REGION=us-east-1
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import boto3
from botocore.eventstream import EventStream
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Strands Support Copilot API", version="0.1.0")

# Amplify / local Vite origins — tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    actor_id: str = "web-user"
    thread_id: str | None = None


class ChatResponse(BaseModel):
    result: str
    actor_id: str
    thread_id: str
    runtime_arn: str


def _region_from_arn(arn: str) -> str:
    parts = arn.split(":")
    return parts[3] if len(parts) > 3 else (os.getenv("AWS_REGION") or "us-east-1")


def _decode_payload(raw: Any) -> dict:
    # boto3 often returns botocore.response.StreamingBody — read() → bytes
    if hasattr(raw, "read") and not isinstance(raw, (bytes, bytearray, str)):
        raw = raw.read()
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text) if text.strip() else {}
    if isinstance(raw, str):
        return json.loads(raw) if raw.strip() else {}
    if isinstance(raw, EventStream):
        chunks: list[bytes] = []
        for event in raw:
            if "chunk" in event and "bytes" in event["chunk"]:
                chunks.append(event["chunk"]["bytes"])
        return json.loads(b"".join(chunks).decode("utf-8"))
    raise TypeError(f"Unsupported payload type: {type(raw)}")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    arn = (os.getenv("SUPPORT_RUNTIME_ARN") or "").strip()
    if not arn:
        raise HTTPException(
            status_code=500,
            detail="SUPPORT_RUNTIME_ARN is not set on the API server",
        )
    thread_id = (body.thread_id or str(uuid.uuid4())).strip()
    # AgentCore requires runtimeSessionId length >= 33
    session_id = thread_id if len(thread_id) >= 33 else f"{thread_id}-{uuid.uuid4().hex}"[:64]
    region = os.getenv("AWS_REGION") or _region_from_arn(arn)
    client = boto3.client("bedrock-agentcore", region_name=region)

    payload = {
        "prompt": body.prompt,
        "actor_id": body.actor_id,
        "thread_id": thread_id,
    }
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=session_id[:100],
            payload=json.dumps(payload).encode("utf-8"),
            qualifier="DEFAULT",
            runtimeUserId=(body.actor_id or "web-user")[:128],
        )
        data = _decode_payload(
            resp.get("response") or resp.get("body") or resp.get("payload") or b"{}"
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result = data.get("result") or data.get("output") or data.get("message") or str(data)
    if not isinstance(result, str):
        result = json.dumps(result)
    return ChatResponse(
        result=result,
        actor_id=body.actor_id,
        thread_id=thread_id,
        runtime_arn=arn,
    )
