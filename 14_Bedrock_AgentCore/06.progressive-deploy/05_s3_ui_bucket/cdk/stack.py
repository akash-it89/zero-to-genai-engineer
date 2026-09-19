from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_cognito as cognito
from aws_cdk import custom_resources as cr
from aws_cdk import aws_s3 as s3
from constructs import Construct

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "DemoUser1!"

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
        CfnOutput(self, "DeployStep", value="5")
        CfnOutput(
            self,
            "StepHint",
            value="Private S3 bucket for UI",
        )
        CfnOutput(self, "StackName", value=construct_id)

        ssm.StringParameter(
            self,
            "StageMarker",
            parameter_name=f"/lauki-support/{_safe}/deploy-stage",
            string_value="5",
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


        create_user = cr.AwsCustomResource(
            self,
            "CreateDemoUser",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminCreateUser",
                parameters={
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": DEMO_USERNAME,
                    "TemporaryPassword": DEMO_PASSWORD,
                    "MessageAction": "SUPPRESS",
                    "UserAttributes": [
                        {"Name": "email", "Value": "demo@example.com"},
                        {"Name": "email_verified", "Value": "true"},
                    ],
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"demo-user-{DEMO_USERNAME}"
                ),
                ignore_error_codes_matching="UsernameExistsException",
            ),
            on_update=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminCreateUser",
                parameters={
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": DEMO_USERNAME,
                    "TemporaryPassword": DEMO_PASSWORD,
                    "MessageAction": "SUPPRESS",
                    "UserAttributes": [
                        {"Name": "email", "Value": "demo@example.com"},
                        {"Name": "email_verified", "Value": "true"},
                    ],
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"demo-user-{DEMO_USERNAME}"
                ),
                ignore_error_codes_matching="UsernameExistsException",
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )
        set_password = cr.AwsCustomResource(
            self,
            "SetDemoPassword",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminSetUserPassword",
                parameters={
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": DEMO_USERNAME,
                    "Password": DEMO_PASSWORD,
                    "Permanent": True,
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"demo-password-{DEMO_USERNAME}"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminSetUserPassword",
                parameters={
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": DEMO_USERNAME,
                    "Password": DEMO_PASSWORD,
                    "Permanent": True,
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"demo-password-{DEMO_USERNAME}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )
        set_password.node.add_dependency(create_user)
        CfnOutput(self, "DemoUsername", value=DEMO_USERNAME)
        CfnOutput(self, "DemoPassword", value=DEMO_PASSWORD)


        ui_bucket = s3.Bucket(
            self,
            "UiBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        CfnOutput(self, "UiBucketName", value=ui_bucket.bucket_name)
