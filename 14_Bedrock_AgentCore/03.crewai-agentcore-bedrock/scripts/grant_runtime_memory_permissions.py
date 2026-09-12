#!/usr/bin/env python3
"""
Grant AgentCore Memory (+ optional Identity token) permissions on Runtime roles.

Strands Memory demos fail without ListEvents/CreateEvent on MEMORY_ID.
Identity demos need GetResourceOauth2Token for @requires_access_token.

Usage:
  .venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config
  .venv/bin/python scripts/grant_runtime_memory_permissions.py \\
    --role-name AmazonBedrockAgentCoreSDKRuntime-us-east-1-XXXX
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3
import yaml

POLICY_NAME = "AgentCoreMemoryAndIdentityAccess"
ROOT = Path(__file__).resolve().parents[1]


def build_policy(account: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "MemoryReadWrite",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:ListActors",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:ListMemoryRecords",
                    "bedrock-agentcore:ListSessions",
                    "bedrock-agentcore:DeleteEvent",
                    "bedrock-agentcore:DeleteMemoryRecord",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:us-east-1:{account}:memory/*",
                    f"arn:aws:bedrock-agentcore:us-west-2:{account}:memory/*",
                ],
            },
            {
                "Sid": "IdentityTokenAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetResourceApiKey",
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                "Resource": "*",
            },
        ],
    }


def role_names_from_config() -> list[str]:
    cfg = ROOT / ".bedrock_agentcore.yaml"
    if not cfg.is_file():
        return []
    data = yaml.safe_load(cfg.read_text()) or {}
    names = []
    for _, agent in (data.get("agents") or {}).items():
        role = ((agent.get("aws") or {}).get("execution_role") or "")
        if role.startswith("arn:aws:iam::"):
            names.append(role.rsplit("/", 1)[-1])
    return sorted(set(names))


def grant(role_name: str, account: str) -> None:
    iam = boto3.client("iam")
    doc = build_policy(account)
    print(f"Putting {POLICY_NAME} on {role_name} ...")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=POLICY_NAME,
        PolicyDocument=json.dumps(doc),
    )
    print("  OK")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--role-name", default=None)
    p.add_argument("--all-from-config", action="store_true")
    p.add_argument("--account", default=None)
    args = p.parse_args()

    account = args.account or boto3.client("sts").get_caller_identity()["Account"]
    roles: list[str] = []
    if args.all_from_config:
        roles = role_names_from_config()
    if args.role_name:
        roles.append(args.role_name)
    roles = sorted(set(roles))
    if not roles:
        raise SystemExit("Pass --role-name or --all-from-config")

    for role in roles:
        grant(role, account)
    print("Done. Re-invoke agents (IAM is immediate; no redeploy needed).")


if __name__ == "__main__":
    main()
