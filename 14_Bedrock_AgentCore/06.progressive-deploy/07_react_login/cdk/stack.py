from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_cognito as cognito
from aws_cdk import custom_resources as cr
from aws_cdk import aws_s3 as s3
from aws_cdk import Duration
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

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
        CfnOutput(self, "DeployStep", value="7")
        CfnOutput(
            self,
            "StepHint",
            value="React Cognito login (chat locked)",
        )
        CfnOutput(self, "StackName", value=construct_id)

        ssm.StringParameter(
            self,
            "StageMarker",
            parameter_name=f"/lauki-support/{_safe}/deploy-stage",
            string_value="7",
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


        oac = cloudfront.S3OriginAccessControl(
            self,
            "UiOac",
            signing=cloudfront.Signing.SIGV4_ALWAYS,
        )
        s3_origin = origins.S3BucketOrigin.with_origin_access_control(
            ui_bucket,
            origin_access_control=oac,
        )
        additional: dict[str, cloudfront.BehaviorOptions] = {}

        distribution = cloudfront.Distribution(
            self,
            "UiDistribution",
            comment="lauki-support-ui-cdk",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                compress=True,
            ),
            additional_behaviors=additional or None,
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
        )
        CfnOutput(
            self,
            "CloudFrontUrl",
            value=f"https://{distribution.distribution_domain_name}",
        )


        chat_enabled = False
        config = {
            "step": 7,
            "stage": 7,
            "authRequired": True,
            "chatEnabled": chat_enabled,
            "region": region,
            "apiBase": "",
            "userPoolId": user_pool.user_pool_id,
            "clientId": user_pool_client.user_pool_client_id,
        }
        web_asset = s3deploy.Source.asset(
            str(WEB_DIR),
            exclude=["node_modules", "dist", ".git"],
            bundling=cdk.BundlingOptions(
                image=cdk.DockerImage.from_registry(
                    "public.ecr.aws/docker/library/node:20-alpine"
                ),
                user="root",
                environment={"VITE_API_BASE": ""},
                command=[
                    "sh",
                    "-c",
                    "npm ci && npm run build && cp -r dist/. /asset-output/",
                ],
            ),
        )
        cognito_config = s3deploy.Source.json_data("config.json", config)
        s3deploy.BucketDeployment(
            self,
            "DeployUi",
            sources=[web_asset, cognito_config],
            destination_bucket=ui_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            memory_limit=1024,
        )
