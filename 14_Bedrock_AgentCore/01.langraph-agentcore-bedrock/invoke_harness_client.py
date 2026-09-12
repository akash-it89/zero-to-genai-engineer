"""
Client: invoke a managed AgentCore Harness (Demo 6).

Harness runtimes cannot use InvokeAgentRuntime — AWS requires InvokeHarness
with the **Harness ARN** (not the Runtime ARN).

Env:
  HARNESS_ARN   — preferred: arn:...:harness/lauki_harness_demo-...
  HARNESS_ID    — optional alternative: lauki_harness_demo-rk1Voq8Z3T
  AWS_REGION    — default derived from ARN / us-east-1
  PROMPT        — optional; else pass as CLI arg

Usage:
  export AWS_PROFILE=inceptez
  export HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:899736802567:harness/lauki_harness_demo-rk1Voq8Z3T"
  .venv/bin/python invoke_harness_client.py "What is 2+2? Use code interpreter."
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid

import boto3
from dotenv import load_dotenv

load_dotenv()

_PLACEHOLDER = re.compile(r"PASTE_|YOUR_|REPLACE_|xxx|TODO", re.I)
_HARNESS_ARN_RE = re.compile(
    r"^arn:aws:bedrock-agentcore:([a-z0-9-]+):\d{12}:harness/[A-Za-z0-9._-]+$"
)


def _region_from_arn(arn: str) -> str | None:
    m = re.match(r"^arn:aws:bedrock-agentcore:([a-z0-9-]+):", arn)
    return m.group(1) if m else None


def _resolve_harness_arn() -> str:
    arn = (os.getenv("HARNESS_ARN") or "").strip()
    # Back-compat: older docs used HARNESS_RUNTIME_ARN — reject it clearly
    runtime_arn = (os.getenv("HARNESS_RUNTIME_ARN") or "").strip()
    harness_id = (os.getenv("HARNESS_ID") or "").strip()

    if runtime_arn and ":runtime/" in runtime_arn and not arn:
        raise SystemExit(
            "HARNESS_RUNTIME_ARN is set, but managed Harnesses cannot be invoked "
            "via InvokeAgentRuntime.\n"
            "Use the Harness ARN instead:\n"
            "  export HARNESS_ARN=\"arn:aws:bedrock-agentcore:REGION:ACCOUNT:harness/ID\"\n"
            "Get it with:\n"
            "  aws bedrock-agentcore-control list-harnesses --region us-east-1"
        )

    if not arn and harness_id:
        region = os.getenv("AWS_REGION") or "us-east-1"
        account = boto3.client("sts").get_caller_identity()["Account"]
        arn = f"arn:aws:bedrock-agentcore:{region}:{account}:harness/{harness_id}"

    if not arn:
        raise SystemExit(
            "Set HARNESS_ARN to your Harness ARN (not Runtime ARN, not PASTE_HERE).\n"
            "Example:\n"
            "  export HARNESS_ARN="
            '"arn:aws:bedrock-agentcore:us-east-1:899736802567:harness/lauki_harness_demo-rk1Voq8Z3T"'
        )

    if _PLACEHOLDER.search(arn):
        raise SystemExit(
            f"HARNESS_ARN still looks like a placeholder:\n  {arn}\n"
            "Create one with: .venv/bin/python scripts/create_harness.py\n"
            "Or: aws bedrock-agentcore-control list-harnesses --region us-east-1"
        )
    if not _HARNESS_ARN_RE.match(arn):
        raise SystemExit(
            f"HARNESS_ARN must look like ...:harness/NAME-id (got):\n  {arn}"
        )
    return arn


def _print_stream(stream) -> None:
    """Consume InvokeHarness event stream and print useful chunks."""
    final_texts: list[str] = []
    for event in stream:
        # Typical keys vary by SDK version — print compactly
        if not isinstance(event, dict):
            print(event)
            continue
        # Common shapes: message / contentBlockDelta / error / result
        if "error" in event:
            print("ERROR:", json.dumps(event["error"], default=str))
            continue
        if "message" in event:
            msg = event["message"]
            print(json.dumps(msg, default=str))
            content = msg.get("content") if isinstance(msg, dict) else None
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("text"):
                        final_texts.append(block["text"])
            continue
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta") or {}
            text = delta.get("text")
            if text:
                print(text, end="", flush=True)
                final_texts.append(text)
            continue
        if "result" in event:
            print(json.dumps(event["result"], default=str, indent=2))
            continue
        # Fallback dump
        keys = list(event.keys())
        if keys == ["ResponseMetadata"]:
            continue
        print(json.dumps(event, default=str)[:2000])
    if final_texts and not any("contentBlockDelta" in str(x) for x in []):
        # If we only collected deltas, ensure newline
        if final_texts:
            print()


def main() -> None:
    arn = _resolve_harness_arn()
    prompt = (
        " ".join(sys.argv[1:]).strip()
        or os.getenv("PROMPT", "Hello from AgentCore Harness client")
    )
    region = os.getenv("AWS_REGION") or _region_from_arn(arn) or "us-east-1"
    session_id = str(uuid.uuid4())

    client = boto3.client("bedrock-agentcore", region_name=region)
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    print(f"Invoking harness: {arn}")
    print(f"region={region}")
    print(f"session_id={session_id}")
    print(f"prompt={prompt}")
    print("-" * 60)

    response = client.invoke_harness(
        harnessArn=arn,
        runtimeSessionId=session_id,
        messages=messages,
        qualifier="DEFAULT",
    )
    stream = response.get("stream")
    if stream is None:
        print(response)
        return
    _print_stream(stream)


if __name__ == "__main__":
    main()
