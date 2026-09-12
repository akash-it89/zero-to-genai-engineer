#!/usr/bin/env python3
"""
Attach a default Lambda MCP target to an existing AgentCore Gateway.

Usage:
  .venv/bin/python scripts/create_lambda_gateway_target.py \
    --gateway-arn arn:aws:bedrock-agentcore:us-west-2:899736802567:gateway/lauki-demo-gateway-kp97tedwof \
    --gateway-url https://lauki-demo-gateway-kp97tedwof.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp \
    --role-arn arn:aws:iam::899736802567:role/AgentCoreGatewayExecutionRole \
    --region us-west-2
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
except ModuleNotFoundError:
    print("Use .venv/bin/python ...", file=sys.stderr)
    raise SystemExit(1) from None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gateway-arn", required=True)
    p.add_argument("--gateway-url", required=True)
    p.add_argument("--role-arn", required=True)
    p.add_argument("--region", default="us-west-2")
    p.add_argument("--name", default="lauki-lambda-target")
    args = p.parse_args()

    client = GatewayClient(region_name=args.region)
    gateway = {
        "gatewayArn": args.gateway_arn,
        "gatewayUrl": args.gateway_url,
        "roleArn": args.role_arn,
        # toolkit also looks for these keys in some paths
        "gatewayId": args.gateway_arn.split("/")[-1],
    }
    print(f"Creating lambda target on {args.gateway_arn} ...")
    target = client.create_mcp_gateway_target(
        gateway=gateway,
        name=args.name,
        target_type="lambda",
    )
    print(json.dumps(target, indent=2, default=str))
    print("\nDone. Fetch a token and list MCP tools next.")


if __name__ == "__main__":
    main()
