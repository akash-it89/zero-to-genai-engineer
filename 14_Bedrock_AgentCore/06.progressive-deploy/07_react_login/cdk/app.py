#!/usr/bin/env python3
from __future__ import annotations

import os
import aws_cdk as cdk
from stack import LaukiSupportStack

app = cdk.App()
stack_name = (
    app.node.try_get_context("stackName")
    or os.environ.get("STACK_NAME")
    or "LaukiSupportStack"
)
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or "us-east-1",
)

LaukiSupportStack(
    app,
    stack_name,
    env=env,
)
app.synth()
