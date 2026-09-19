from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

class LaukiSupportStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Unique per STACK_NAME so parallel classroom stacks do not collide
        _safe = "".join(
            ch.lower() if ch.isalnum() else "-" for ch in construct_id
        ).strip("-")[:24]
        CfnOutput(self, "DeployStep", value="1")
        CfnOutput(
            self,
            "StepHint",
            value="Empty CDK stack (SSM marker)",
        )
        CfnOutput(self, "StackName", value=construct_id)

        ssm.StringParameter(
            self,
            "StageMarker",
            parameter_name=f"/lauki-support/{_safe}/deploy-stage",
            string_value="1",
            description="Classroom step folder",
        )
