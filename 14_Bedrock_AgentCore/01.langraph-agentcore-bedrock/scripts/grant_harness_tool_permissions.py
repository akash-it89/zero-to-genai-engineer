#!/usr/bin/env python3
"""
Grant AgentCore Code Interpreter + Browser permissions to a Runtime execution role.

Demo 5 (langraph_agent_harness_tools) needs these on the Runtime role.
Without them you get:
  AccessDeniedException ... StartCodeInterpreterSession ... aws.codeinterpreter.v1

Usage:
  .venv/bin/python scripts/grant_harness_tool_permissions.py
  .venv/bin/python scripts/grant_harness_tool_permissions.py \
    --role-name AmazonBedrockAgentCoreSDKRuntime-us-east-1-79b0307c3f \
    --region us-east-1
"""

from __future__ import annotations

import argparse
import json

import boto3

DEFAULT_ROLE = "AmazonBedrockAgentCoreSDKRuntime-us-east-1-79b0307c3f"
POLICY_NAME = "AgentCoreHarnessToolsAccess"


def build_policy(account: str, region: str) -> dict:
    # Narrow ARNs for system tools (`:aws:code-interpreter/*`) often still 403
    # on StartCodeInterpreterSession — use Resource "*" for the demo role.
    _ = region  # kept for CLI compatibility / future narrowing
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CodeInterpreterAndBrowser",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:StartCodeInterpreterSession",
                    "bedrock-agentcore:InvokeCodeInterpreter",
                    "bedrock-agentcore:StopCodeInterpreterSession",
                    "bedrock-agentcore:GetCodeInterpreter",
                    "bedrock-agentcore:GetCodeInterpreterSession",
                    "bedrock-agentcore:ListCodeInterpreters",
                    "bedrock-agentcore:ListCodeInterpreterSessions",
                    "bedrock-agentcore:CreateCodeInterpreter",
                    "bedrock-agentcore:DeleteCodeInterpreter",
                    "bedrock-agentcore:StartBrowserSession",
                    "bedrock-agentcore:UpdateBrowserStream",
                    "bedrock-agentcore:StopBrowserSession",
                    "bedrock-agentcore:GetBrowserSession",
                    "bedrock-agentcore:GetBrowser",
                    "bedrock-agentcore:ListBrowsers",
                    "bedrock-agentcore:ListBrowserSessions",
                    "bedrock-agentcore:ConnectBrowserAutomationStream",
                    "bedrock-agentcore:ConnectBrowserLiveViewStream",
                ],
                "Resource": "*",
            },
            {
                "Sid": "MemoryCrossRegionReadWrite",
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
                # Allow Memory in common demo regions (Memory IDs are region-scoped)
                "Resource": [
                    f"arn:aws:bedrock-agentcore:us-east-1:{account}:memory/*",
                    f"arn:aws:bedrock-agentcore:us-west-2:{account}:memory/*",
                ],
            },
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--role-name", default=DEFAULT_ROLE)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--account", default=None)
    args = p.parse_args()

    sts = boto3.client("sts")
    account = args.account or sts.get_caller_identity()["Account"]
    iam = boto3.client("iam")
    doc = build_policy(account, args.region)

    print(f"Putting inline policy {POLICY_NAME} on role {args.role_name} ...")
    iam.put_role_policy(
        RoleName=args.role_name,
        PolicyName=POLICY_NAME,
        PolicyDocument=json.dumps(doc),
    )
    print("✅ Done. Re-invoke the agent (no relaunch required for IAM):")
    print(
        '  agentcore invoke -a langraph_agent_harness_tools '
        '\'{"prompt":"Run python: print(sum(range(10)))","actor_id":"demo","thread_id":"h1"}\''
    )


if __name__ == "__main__":
    main()
