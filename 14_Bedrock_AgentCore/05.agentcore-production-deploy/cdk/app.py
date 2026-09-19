#!/usr/bin/env python3
"""CDK app — staged classroom deploys: -c stage=1 .. -c stage=10"""

from __future__ import annotations

import os

import aws_cdk as cdk

from lauki_support_stack import LaukiSupportStack

app = cdk.App()

stage = int(app.node.try_get_context("stage") or os.environ.get("CDK_STAGE") or "10")
runtime_arn = (
    app.node.try_get_context("supportRuntimeArn")
    or os.environ.get("SUPPORT_RUNTIME_ARN")
    or ""
).strip()
budget_alert_email = (
    app.node.try_get_context("budgetAlertEmail")
    or os.environ.get("BUDGET_ALERT_EMAIL")
    or ""
).strip()
budget_limit_usd = float(
    app.node.try_get_context("budgetLimitUsd")
    or os.environ.get("BUDGET_LIMIT_USD")
    or "15"
)
github_repo = (
    app.node.try_get_context("githubRepo")
    or os.environ.get("GITHUB_REPO")
    or "nursnaaz/zero-to-genai-engineer"
).strip()
github_oidc_provider_arn = (
    app.node.try_get_context("githubOidcProviderArn")
    or os.environ.get("GITHUB_OIDC_PROVIDER_ARN")
    or ""
).strip()

if stage >= 10 and not runtime_arn:
    raise SystemExit(
        "Stage 10 needs the AgentCore Runtime ARN.\n"
        "  export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...\n"
        "  npx cdk deploy -c stage=10 -c supportRuntimeArn=$SUPPORT_RUNTIME_ARN"
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
    stage=stage,
    support_runtime_arn=runtime_arn,
    budget_alert_email=budget_alert_email,
    budget_limit_usd=budget_limit_usd,
    github_repo=github_repo,
    github_oidc_provider_arn=github_oidc_provider_arn,
    env=env,
    description=f"Lauki Support classroom stack (stage {stage}/12)",
)

app.synth()
