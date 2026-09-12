#!/usr/bin/env python3
"""
Pre-flight checks before a live class (trainer account).

Usage:
  export AWS_PROFILE=inceptez
  export AWS_REGION=us-east-1
  set -a && source .env && set +a
  .venv/bin/python scripts/preflight_class.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import boto3
import httpx

ROOT = Path(__file__).resolve().parents[1]
CREDS = ROOT / "gateway-credentials.json"

RUNTIME_IDS = [
    "langraph_agent-eXAuqCCubY",
    "langraph_agent_memory-Ozmjjm40aH",
    "langraph_agent_gateway-xZYKDfD5rE",
    "langraph_agent_harness_tools-1YMFVrFv5B",
    "langgraph_research_agent-oii60EHhFt",
    "langgraph_research_graph-ZsDIkv2WYd",
]
HARNESS_ID = "lauki_harness_demo-rk1Voq8Z3T"
MEMORY_ID = os.getenv("MEMORY_ID") or "memorybot-w6GzC7D97L"


def ok(msg: str) -> None:
    print(f"✅ {msg}")


def bad(msg: str) -> None:
    print(f"❌ {msg}")


def warn(msg: str) -> None:
    print(f"⚠️  {msg}")


def main() -> int:
    profile = os.getenv("AWS_PROFILE")
    region = os.getenv("AWS_REGION") or "us-east-1"
    fails = 0

    print(f"profile={profile!r} region={region!r}")
    if not profile:
        bad("AWS_PROFILE not set")
        fails += 1

    if not os.getenv("OPENAI_API_KEY"):
        bad("OPENAI_API_KEY missing (source .env)")
        fails += 1
    else:
        ok("OPENAI_API_KEY present")

    session = boto3.Session(profile_name=profile, region_name=region)
    sts = session.client("sts")
    try:
        ident = sts.get_caller_identity()
        ok(f"sts account={ident.get('Account')}")
    except Exception as exc:  # noqa: BLE001
        bad(f"sts failed: {exc}")
        fails += 1
        return fails

    ctrl = session.client("bedrock-agentcore-control", region_name="us-east-1")
    try:
        mems = ctrl.list_memories().get("memories") or []
        ids = [m.get("id") for m in mems]
        if MEMORY_ID in ids:
            ok(f"Memory ACTIVE/listed: {MEMORY_ID}")
        else:
            bad(f"Memory {MEMORY_ID} not listed in us-east-1 (found {ids[:5]})")
            fails += 1
    except Exception as exc:  # noqa: BLE001
        bad(f"list_memories: {exc}")
        fails += 1

    if not CREDS.exists():
        bad("gateway-credentials.json missing — run scripts/create_mcp_gateway.py")
        fails += 1
    else:
        creds = json.loads(CREDS.read_text())
        url = creds["gateway"]["gatewayUrl"]
        ok(f"gateway credentials present ({creds.get('region')})")
        try:
            token = subprocess.check_output(
                [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/get_gateway_token.py")],
                text=True,
                cwd=str(ROOT),
            ).strip()
            r = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                timeout=60,
            )
            if r.status_code == 200 and "get_weather" in r.text:
                ok("Gateway MCP tools/list OK (get_weather present)")
            else:
                bad(f"Gateway MCP unexpected: HTTP {r.status_code} body={r.text[:200]}")
                fails += 1
        except Exception as exc:  # noqa: BLE001
            bad(f"Gateway token/MCP failed: {exc}")
            fails += 1

    for rid in RUNTIME_IDS:
        try:
            st = ctrl.get_agent_runtime(agentRuntimeId=rid)["status"]
            if st == "READY":
                ok(f"Runtime {rid} READY")
            else:
                bad(f"Runtime {rid} status={st}")
                fails += 1
        except Exception as exc:  # noqa: BLE001
            bad(f"Runtime {rid}: {exc}")
            fails += 1

    try:
        h = ctrl.get_harness(harnessId=HARNESS_ID)["harness"]
        st = h.get("status")
        if st == "READY":
            ok(f"Harness {HARNESS_ID} READY")
        else:
            bad(f"Harness status={st}")
            fails += 1
    except Exception as exc:  # noqa: BLE001
        bad(f"Harness: {exc}")
        fails += 1

    # Identity provider
    try:
        providers = (
            session.client("bedrock-agentcore-control", region_name="us-east-1")
            .list_oauth2_credential_providers()
            .get("credentialProviders")
            or []
        )
        names = [p.get("name") for p in providers]
        if "gateway-cognito-m2m" in names:
            ok("Identity provider gateway-cognito-m2m (us-east-1)")
        else:
            warn(f"Identity provider missing in us-east-1 (have {names}) — use GATEWAY_TOKEN fallback")
    except Exception as exc:  # noqa: BLE001
        warn(f"Identity list failed: {exc}")

    print("---")
    if fails:
        bad(f"{fails} blocking issue(s) — fix before class")
    else:
        ok("Pre-flight passed — warm Streamlit + one graph 'hi' before students join")
    return fails


if __name__ == "__main__":
    sys.exit(main())
