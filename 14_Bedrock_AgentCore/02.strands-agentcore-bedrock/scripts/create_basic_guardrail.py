#!/usr/bin/env python3
"""
Create a basic Bedrock Guardrail for the Strands Support Copilot demo.

  .venv/bin/python scripts/create_basic_guardrail.py
  # prints GUARDRAIL_ID + GUARDRAIL_VERSION for .env / agentcore deploy
"""

from __future__ import annotations

import argparse
import json

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="lauki-support-guardrail")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    client = boto3.client("bedrock", region_name=args.region)
    created = client.create_guardrail(
        name=args.name,
        description="Basic classroom Guardrail for Strands Support Copilot",
        blockedInputMessaging=(
            "I can't help with that request. Please ask about Lauki plans, "
            "activation, eSIM, or other product support."
        ),
        blockedOutputsMessaging=(
            "I can't share that content. Please ask a Lauki product support question."
        ),
        contentPolicyConfig={
            "filtersConfig": [
                {"type": "HATE", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                {"type": "INSULTS", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                {"type": "SEXUAL", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                {"type": "VIOLENCE", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                {"type": "MISCONDUCT", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                {"type": "PROMPT_ATTACK", "inputStrength": "MEDIUM", "outputStrength": "NONE"},
            ]
        },
        topicPolicyConfig={
            "topicsConfig": [
                {
                    "name": "Illegal activity advice",
                    "definition": (
                        "Requests for help committing crimes, fraud, hacking, "
                        "or acquiring illegal goods/services."
                    ),
                    "examples": [
                        "How do I hack a phone",
                        "Help me create fake KYC documents",
                    ],
                    "type": "DENY",
                }
            ]
        },
    )
    gid = created["guardrailId"]
    versioned = client.create_guardrail_version(
        guardrailIdentifier=gid,
        description="v1 classroom baseline",
    )
    out = {
        "GUARDRAIL_ID": gid,
        "GUARDRAIL_VERSION": versioned["version"],
        "GUARDRAIL_ARN": created["guardrailArn"],
        "region": args.region,
    }
    print(json.dumps(out, indent=2))
    print("\nAdd to deploy:")
    print(f'  --env USE_BEDROCK=true \\')
    print(f'  --env GUARDRAIL_ID={gid} \\')
    print(f'  --env GUARDRAIL_VERSION={versioned["version"]}')


if __name__ == "__main__":
    main()
