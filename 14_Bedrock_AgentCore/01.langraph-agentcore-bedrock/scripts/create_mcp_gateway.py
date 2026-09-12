#!/usr/bin/env python3
"""
Create AgentCore MCP Gateway + Cognito M2M authorizer, and SAVE credentials.

IMPORTANT: create_mcp_gateway() alone discards the Cognito client_secret.
This script creates Cognito first, writes gateway-credentials.json, then creates
the gateway. Without that file you cannot mint GATEWAY_TOKEN later.

Usage (always use project venv):
  .venv/bin/python scripts/create_mcp_gateway.py --name lauki-demo-gateway --region us-west-2
  .venv/bin/python scripts/create_mcp_gateway.py --name lauki-demo-gateway --region us-west-2 --with-lambda-target
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
except ModuleNotFoundError:
    print(
        "Missing bedrock_agentcore_starter_toolkit.\n"
        "Run:  .venv/bin/python scripts/create_mcp_gateway.py ...\n"
        "Or:   uv run python scripts/create_mcp_gateway.py ...\n"
        "Or:   uv sync",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

ROOT = Path(__file__).resolve().parents[1]
CREDS_PATH = ROOT / "gateway-credentials.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create AgentCore MCP Gateway + Cognito")
    parser.add_argument("--name", default="lauki-demo-gateway")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument(
        "--with-lambda-target",
        action="store_true",
        help="Also attach the default demo Lambda target (get_weather / get_time)",
    )
    parser.add_argument(
        "--credentials-out",
        default=str(CREDS_PATH),
        help="Where to save Cognito + gateway credentials JSON",
    )
    args = parser.parse_args()
    out = Path(args.credentials_out)

    client = GatewayClient(region_name=args.region)

    print("=" * 64)
    print("Step 1/3 — Create Cognito User Pool + M2M app client (client_credentials)")
    print("=" * 64)
    cognito = client.create_oauth_authorizer_with_cognito(args.name)
    client_info = cognito["client_info"]
    authorizer_config = cognito["authorizer_config"]
    print(json.dumps({**client_info, "client_secret": "***REDACTED***"}, indent=2))

    print("\n" + "=" * 64)
    print("Step 2/3 — Create MCP Gateway using that Cognito JWT authorizer")
    print("=" * 64)
    gateway = client.create_mcp_gateway(
        name=args.name,
        authorizer_config=authorizer_config,
        enable_observability=False,  # avoid X-Ray trace destination failures on fresh accounts
    )
    print(
        json.dumps(
            {
                "gatewayArn": gateway.get("gatewayArn"),
                "gatewayId": gateway.get("gatewayId"),
                "gatewayUrl": gateway.get("gatewayUrl"),
                "roleArn": gateway.get("roleArn"),
                "status": gateway.get("status"),
            },
            indent=2,
            default=str,
        )
    )

    target = None
    if args.with_lambda_target:
        print("\n" + "=" * 64)
        print("Step 3/3 — Attach default Lambda MCP target (get_weather, get_time)")
        print("=" * 64)
        target = client.create_mcp_gateway_target(
            gateway=gateway,
            name=f"{args.name}-lambda",
            target_type="lambda",
        )
        print(
            json.dumps(
                {
                    "targetId": target.get("targetId"),
                    "name": target.get("name"),
                    "status": target.get("status"),
                },
                indent=2,
                default=str,
            )
        )
    else:
        print("\n(Skipping Lambda target — pass --with-lambda-target to create one)")

    bundle = {
        "region": args.region,
        "gateway": {
            "gatewayArn": gateway.get("gatewayArn"),
            "gatewayId": gateway.get("gatewayId"),
            "gatewayUrl": gateway.get("gatewayUrl"),
            "roleArn": gateway.get("roleArn"),
            "name": gateway.get("name") or args.name,
        },
        "cognito": {
            "user_pool_id": client_info["user_pool_id"],
            "client_id": client_info["client_id"],
            "client_secret": client_info["client_secret"],
            "domain_prefix": client_info["domain_prefix"],
            "token_endpoint": client_info["token_endpoint"],
            "scope": client_info["scope"],
            "discovery_url": authorizer_config["customJWTAuthorizer"]["discoveryUrl"],
        },
        "target": {
            "targetId": (target or {}).get("targetId"),
            "name": (target or {}).get("name"),
        }
        if target
        else None,
    }
    out.write_text(json.dumps(bundle, indent=2) + "\n")
    print(f"\n✅ Saved credentials → {out}")
    print("   (gitignored — do NOT commit client_secret)")

    print(
        f"""
================================================================================
NEXT STEPS
================================================================================
1) Mint a bearer token (reads {out.name}):
     .venv/bin/python scripts/get_gateway_token.py

2) Launch the gateway agent:
     export GATEWAY_URL="{gateway.get("gatewayUrl")}"
     export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
     agentcore configure -e langraph_agent_gateway.py -n langraph_agent_gateway
     agentcore launch \\
       --env OPENAI_API_KEY="$OPENAI_API_KEY" \\
       --env MEMORY_ID=memorybot-w6GzC7D97L \\
       --env GATEWAY_URL="$GATEWAY_URL" \\
       --env GATEWAY_TOKEN="$GATEWAY_TOKEN"

3) Invoke:
     agentcore invoke -a langraph_agent_gateway \\
       '{{"prompt":"What is the weather in Chennai?","actor_id":"demo","thread_id":"gw-1"}}'
================================================================================
"""
    )


if __name__ == "__main__":
    main()
