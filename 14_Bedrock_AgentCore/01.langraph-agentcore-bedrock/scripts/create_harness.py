#!/usr/bin/env python3
"""
Create a managed AgentCore Harness (Demo 6) via the control-plane API.

True Harness = AWS runs the agent loop (no langraph_*.py).

This account often lacks Bedrock model access, so the default model is OpenAI
(gpt-4o-mini) via an AgentCore API-key credential provider. Set OPENAI_API_KEY
in .env (or the environment) before running.

Usage:
  export AWS_PROFILE=inceptez
  .venv/bin/python scripts/create_harness.py

Then:
  export HARNESS_ARN=...   # printed by this script
  .venv/bin/python invoke_harness_client.py "What is 2+2? Use code interpreter."
"""

from __future__ import annotations

import argparse
import json
import os
import time

import boto3
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ROLE = (
    "arn:aws:iam::899736802567:role/"
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-79b0307c3f"
)
API_KEY_PROVIDER_NAME = "openai-harness-key"  # must match [a-zA-Z0-9-.]+


def ensure_openai_api_key_provider(ctrl, region: str, account: str) -> str:
    """Return credential provider ARN for OpenAI; create if missing."""
    arn = (
        f"arn:aws:bedrock-agentcore:{region}:{account}:"
        f"token-vault/default/apikeycredentialprovider/{API_KEY_PROVIDER_NAME}"
    )
    try:
        ctrl.get_api_key_credential_provider(name=API_KEY_PROVIDER_NAME)
        print(f"Using existing API key provider: {API_KEY_PROVIDER_NAME}")
        return arn
    except Exception:  # noqa: BLE001
        pass

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY is required to create the harness model credential provider."
        )
    print(f"Creating API key provider {API_KEY_PROVIDER_NAME!r} ...")
    ctrl.create_api_key_credential_provider(
        name=API_KEY_PROVIDER_NAME,
        apiKey=api_key,
    )
    return arn


def ensure_role_can_read_api_keys(role_name: str) -> None:
    iam = boto3.client("iam")
    doc = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "IdentityApiKeyAny",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetResourceApiKey",
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    "secretsmanager:GetSecretValue",
                ],
                "Resource": "*",
            }
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="HarnessOpenAIApiKeyAccess",
        PolicyDocument=json.dumps(doc),
    )
    print("Ensured IAM policy HarnessOpenAIApiKeyAccess on execution role")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="lauki_harness_demo")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--execution-role-arn", default=DEFAULT_ROLE)
    p.add_argument("--openai-model", default="gpt-4o-mini")
    p.add_argument("--wait-seconds", type=int, default=180)
    args = p.parse_args()

    sts = boto3.client("sts")
    account = sts.get_caller_identity()["Account"]
    ctrl = boto3.client("bedrock-agentcore-control", region_name=args.region)

    role_name = args.execution_role_arn.split("/")[-1]
    ensure_role_can_read_api_keys(role_name)
    api_key_arn = ensure_openai_api_key_provider(ctrl, args.region, account)

    print(f"Creating harness {args.name!r} in {args.region} ...")
    try:
        resp = ctrl.create_harness(
            harnessName=args.name,
            executionRoleArn=args.execution_role_arn,
            model={
                "openAiModelConfig": {
                    "modelId": args.openai_model,
                    "apiKeyArn": api_key_arn,
                    "temperature": 0.2,
                    "maxTokens": 2048,
                }
            },
            systemPrompt=[
                {
                    "text": (
                        "You are a helpful demo agent. When asked to compute or run "
                        "code, use the code interpreter tool and report the exact stdout."
                    )
                }
            ],
            tools=[
                {
                    "type": "agentcore_code_interpreter",
                    "name": "code_interpreter",
                    "config": {"agentCoreCodeInterpreter": {}},
                }
            ],
            maxIterations=8,
            timeoutSeconds=120,
        )
        harness_id = resp["harness"]["harnessId"]
    except Exception as exc:  # noqa: BLE001
        # If name already exists, list and reuse
        if "Conflict" not in type(exc).__name__ and "Conflict" not in str(exc):
            raise
        print(f"Create conflict ({exc}); looking up existing harness ...")
        listed = ctrl.list_harnesses().get("harnesses") or []
        match = next((h for h in listed if h.get("harnessName") == args.name), None)
        if not match:
            raise
        harness_id = match["harnessId"]

    print(f"harnessId={harness_id}")
    deadline = time.time() + args.wait_seconds
    harness = {}
    while time.time() < deadline:
        harness = ctrl.get_harness(harnessId=harness_id)["harness"]
        status = harness["status"]
        print(f"  status={status}")
        if status in ("READY", "CREATE_FAILED", "FAILED", "DELETED"):
            break
        time.sleep(8)

    harness_arn = harness.get("arn") or (
        f"arn:aws:bedrock-agentcore:{args.region}:{account}:harness/{harness_id}"
    )
    print(
        json.dumps(
            {
                "harnessId": harness_id,
                "harnessArn": harness_arn,
                "status": harness.get("status"),
            },
            indent=2,
        )
    )
    if harness.get("status") != "READY":
        raise SystemExit("Harness did not become READY.")

    print("\n# Export and invoke (use HARNESS_ARN — not Runtime ARN):")
    print(f'export HARNESS_ARN="{harness_arn}"')
    print(
        '.venv/bin/python invoke_harness_client.py '
        '"What is 2+2? Use code interpreter."'
    )


if __name__ == "__main__":
    main()
