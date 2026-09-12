"""
Production stack: React (S3) + FastAPI (App Runner) behind one CloudFront URL.

Same-origin routing means the UI calls `/api/chat` with empty VITE_API_BASE —
no chicken-and-egg App Runner URL at React build time.
"""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apprunner as apprunner
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
WEB_DIR = ROOT / "web"


class LaukiSupportStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        support_runtime_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = Stack.of(self).region

        # --- API container image (linux/amd64 for App Runner) ---
        api_image = ecr_assets.DockerImageAsset(
            self,
            "ApiImage",
            directory=str(API_DIR),
            platform=ecr_assets.Platform.LINUX_AMD64,
            asset_name="lauki-support-api",
        )

        # --- App Runner: pull from ECR ---
        ecr_access_role = iam.Role(
            self,
            "AppRunnerEcrAccessRole",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSAppRunnerServicePolicyForECRAccess"
                )
            ],
        )
        api_image.repository.grant_pull(ecr_access_role)

        # --- App Runner: invoke AgentCore ---
        instance_role = iam.Role(
            self,
            "AppRunnerInstanceRole",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
        )
        endpoint_arn = f"{support_runtime_arn}/runtime-endpoint/DEFAULT"
        instance_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=[support_runtime_arn, endpoint_arn],
            )
        )

        # CloudFront domain is unknown at synth for CORS — allow all origins in demo;
        # traffic is same-origin through CloudFront in production UI path.
        api_service = apprunner.CfnService(
            self,
            "ApiService",
            service_name="lauki-support-api-cdk",
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=ecr_access_role.role_arn,
                ),
                auto_deployments_enabled=False,
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_identifier=api_image.image_uri,
                    image_repository_type="ECR",
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="8000",
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(
                                name="SUPPORT_RUNTIME_ARN",
                                value=support_runtime_arn,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="AWS_REGION",
                                value=region,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="CORS_ORIGINS",
                                value="*",
                            ),
                        ],
                    ),
                ),
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu="1024",
                memory="2048",
                instance_role_arn=instance_role.role_arn,
            ),
            health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(
                protocol="HTTP",
                path="/health",
                interval=10,
                timeout=5,
                healthy_threshold=1,
                unhealthy_threshold=5,
            ),
        )
        api_service.node.add_dependency(ecr_access_role)
        api_service.node.add_dependency(instance_role)

        # --- Static UI bucket ---
        ui_bucket = s3.Bucket(
            self,
            "UiBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- CloudFront: UI + /api + /health → App Runner (same site) ---
        # ServiceUrl is hostname without scheme (e.g. xxx.us-east-1.awsapprunner.com)
        api_origin = origins.HttpOrigin(
            api_service.attr_service_url,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
            read_timeout=Duration.seconds(120),
            keepalive_timeout=Duration.seconds(60),
        )

        oac = cloudfront.S3OriginAccessControl(
            self,
            "UiOac",
            signing=cloudfront.Signing.SIGV4_ALWAYS,
        )
        s3_origin = origins.S3BucketOrigin.with_origin_access_control(
            ui_bucket,
            origin_access_control=oac,
        )

        api_behavior = cloudfront.BehaviorOptions(
            origin=api_origin,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            compress=True,
        )

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
            additional_behaviors={
                "/api/*": api_behavior,
                "/health": api_behavior,
            },
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

        # --- Build React with empty VITE_API_BASE (same-origin via CloudFront) ---
        s3deploy.BucketDeployment(
            self,
            "DeployUi",
            sources=[
                s3deploy.Source.asset(
                    str(WEB_DIR),
                    exclude=[
                        "node_modules",
                        "dist",
                        ".git",
                    ],
                    bundling=cdk.BundlingOptions(
                        image=cdk.DockerImage.from_registry("public.ecr.aws/docker/library/node:20-alpine"),
                        user="root",
                        environment={"VITE_API_BASE": ""},
                        command=[
                            "sh",
                            "-c",
                            "npm ci && npm run build && cp -r dist/. /asset-output/",
                        ],
                    ),
                )
            ],
            destination_bucket=ui_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            memory_limit=1024,
        )

        CfnOutput(self, "SupportRuntimeArn", value=support_runtime_arn)
        CfnOutput(
            self,
            "AppRunnerUrl",
            value=f"https://{api_service.attr_service_url}",
            description="Direct API URL (also reachable via CloudFront /api)",
        )
        CfnOutput(
            self,
            "CloudFrontUrl",
            value=f"https://{distribution.distribution_domain_name}",
            description="Production UI — open this in the browser",
        )
        CfnOutput(self, "UiBucketName", value=ui_bucket.bucket_name)
