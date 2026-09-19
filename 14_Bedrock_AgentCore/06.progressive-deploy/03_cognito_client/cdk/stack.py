from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_cognito as cognito
from constructs import Construct

class LaukiSupportStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        region = Stack.of(self).region

        # Unique per STACK_NAME so parallel classroom stacks do not collide
        _safe = "".join(
            ch.lower() if ch.isalnum() else "-" for ch in construct_id
        ).strip("-")[:24]
        CfnOutput(self, "DeployStep", value="3")
        CfnOutput(
            self,
            "StepHint",
            value="Cognito SPA app client",
        )
        CfnOutput(self, "StackName", value=construct_id)

        ssm.StringParameter(
            self,
            "StageMarker",
            parameter_name=f"/lauki-support/{_safe}/deploy-stage",
            string_value="3",
            description="Classroom step folder",
        )


        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"lauki-users-{_safe}",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)


        user_pool_client = user_pool.add_client(
            "SpaClient",
            user_pool_client_name="lauki-support-spa",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            generate_secret=False,
            prevent_user_existence_errors=True,
        )
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
