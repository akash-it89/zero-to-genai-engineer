#!/usr/bin/env python3
"""CDK app entry — Lauki Support Copilot (API + React) on AWS."""

from __future__ import annotations

import os

import aws_cdk as cdk

from lauki_support_stack import LaukiSupportStack


app = cdk.App()

runtime_arn = (
    app.node.try_get_context("supportRuntimeArn")
    or os.environ.get("SUPPORT_RUNTIME_ARN")
    or ""
).strip()

if not runtime_arn:
    raise SystemExit(
        "Missing Runtime ARN.\n"
        "  cdk deploy -c supportRuntimeArn=arn:aws:bedrock-agentcore:...\n"
        "  or: export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:..."
    )

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or "us-east-1",
)

LaukiSupportStack(
    app,
    "LaukiSupportStack",
    support_runtime_arn=runtime_arn,
    env=env,
    description="Lauki Support: App Runner API + S3/CloudFront React → AgentCore Runtime",
)

app.synth()
