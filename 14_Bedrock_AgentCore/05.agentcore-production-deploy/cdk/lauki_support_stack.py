#!/usr/bin/env python3
"""
Staged classroom stack — grow with repeated `cdk deploy -c stage=N`.

  stage 1  Empty CDK stack (prove deploy works)
  stage 2  Cognito User Pool
  stage 3  Cognito App Client
  stage 4  Demo user (demo / DemoUser1!)
  stage 5  S3 bucket for UI
  stage 6  CloudFront + placeholder HTML
  stage 7  React login UI + config.json (signed-in welcome; no bot yet)
  stage 8  App Runner FastAPI /health (+ CF /health + /api/*)
  stage 9  JWT lock on API (/api/me) + Cognito env on App Runner
  stage 10 AgentCore /api/chat + React chat enabled
  stage 11 App Runner auto scaling config + monthly cost budget alarm
  stage 12 GitHub Actions OIDC deploy role (CI can `cdk deploy`, not a laptop)

Requires SUPPORT_RUNTIME_ARN only for stage >= 10.
Stage 11's budget alarm is skipped unless you pass -c budgetAlertEmail=...
Stage 12 imports an existing GitHub OIDC provider if you pass
-c githubOidcProviderArn=... (most AWS accounts only allow one per URL);
otherwise it creates a new one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apprunner as apprunner
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_ssm as ssm
from aws_cdk import custom_resources as cr
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
WEB_DIR = ROOT / "web"

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "DemoUser1!"


class LaukiSupportStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: int,
        support_runtime_arn: str = "",
        budget_alert_email: str = "",
        budget_limit_usd: float = 15.0,
        github_repo: str = "nursnaaz/zero-to-genai-engineer",
        github_oidc_provider_arn: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if stage < 1 or stage > 12:
            raise ValueError("stage must be 1..12")

        region = Stack.of(self).region

        CfnOutput(self, "DeployStage", value=str(stage))
        CfnOutput(
            self,
            "StageHint",
            value={
                1: "Empty stack — CDK works",
                2: "Cognito User Pool created",
                3: "Cognito App Client created",
                4: "Demo user ready (demo / DemoUser1!)",
                5: "S3 UI bucket created",
                6: "CloudFront placeholder site",
                7: "React login UI live — no chat API yet",
                8: "App Runner /health live (same-origin via CF)",
                9: "API JWT lock (/api/me) live",
                10: "Full chat via AgentCore",
                11: "Auto scaling + cost budget alarm live",
                12: "GitHub Actions can deploy this stack via OIDC",
            }[stage],
        )

        user_pool = None
        user_pool_client = None
        ui_bucket = None
        distribution = None
        api_service = None

        # Stage 1 needs at least one resource (CFN rejects empty stacks)
        ssm.StringParameter(
            self,
            "StageMarker",
            parameter_name="/lauki-support/deploy-stage",
            string_value=str(stage),
            description="Classroom CDK stage (1-10)",
        )

        # ----- Stage 2+: Cognito User Pool -----
        if stage >= 2:
            user_pool = cognito.UserPool(
                self,
                "UserPool",
                user_pool_name="lauki-support-users",
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

        # ----- Stage 3+: App Client (SPA) -----
        if stage >= 3 and user_pool is not None:
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
            CfnOutput(
                self, "UserPoolClientId", value=user_pool_client.user_pool_client_id
            )

        # ----- Stage 4+: Demo user -----
        if stage >= 4 and user_pool is not None:
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

        # ----- Stage 5+: S3 UI bucket -----
        if stage >= 5:
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

        # ----- Stage 8+ BEFORE CloudFront so we can attach /api behaviors -----
        if stage >= 8:
            api_image = ecr_assets.DockerImageAsset(
                self,
                "ApiImage",
                directory=str(API_DIR),
                platform=ecr_assets.Platform.LINUX_AMD64,
                asset_name="lauki-support-api",
            )
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

            instance_role = iam.Role(
                self,
                "AppRunnerInstanceRole",
                assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
            )

            env_vars = [
                apprunner.CfnService.KeyValuePairProperty(
                    name="AWS_REGION", value=region
                ),
                apprunner.CfnService.KeyValuePairProperty(
                    name="CORS_ORIGINS", value="*"
                ),
            ]

            if stage >= 9 and user_pool is not None and user_pool_client is not None:
                env_vars.extend(
                    [
                        apprunner.CfnService.KeyValuePairProperty(
                            name="COGNITO_REGION", value=region
                        ),
                        apprunner.CfnService.KeyValuePairProperty(
                            name="COGNITO_USER_POOL_ID",
                            value=user_pool.user_pool_id,
                        ),
                        apprunner.CfnService.KeyValuePairProperty(
                            name="COGNITO_CLIENT_ID",
                            value=user_pool_client.user_pool_client_id,
                        ),
                        apprunner.CfnService.KeyValuePairProperty(
                            name="AUTH_DISABLED", value="false"
                        ),
                    ]
                )
            else:
                env_vars.append(
                    apprunner.CfnService.KeyValuePairProperty(
                        name="AUTH_DISABLED", value="true"
                    )
                )

            if stage >= 10:
                if not support_runtime_arn:
                    raise ValueError(
                        "stage 10 requires support_runtime_arn / SUPPORT_RUNTIME_ARN"
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
                env_vars.append(
                    apprunner.CfnService.KeyValuePairProperty(
                        name="SUPPORT_RUNTIME_ARN",
                        value=support_runtime_arn,
                    )
                )
                CfnOutput(self, "SupportRuntimeArn", value=support_runtime_arn)

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
                            runtime_environment_variables=env_vars,
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
            CfnOutput(
                self,
                "AppRunnerUrl",
                value=f"https://{api_service.attr_service_url}",
            )

        # ----- Stage 6+: CloudFront (S3 UI; + App Runner from stage 8) -----
        if stage >= 6 and ui_bucket is not None:
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
            if api_service is not None:
                api_origin = origins.HttpOrigin(
                    api_service.attr_service_url,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                )
                api_behavior = cloudfront.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                )
                additional["/api/*"] = api_behavior
                additional["/health"] = api_behavior

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

            if stage == 6:
                placeholder = s3deploy.Source.data(
                    "index.html",
                    """<!doctype html><html><head><meta charset="utf-8"/>
<title>Lauki — Stage 6</title></head>
<body style="font-family:sans-serif;background:#0b1220;color:#e8eefc;padding:2rem">
<h1>CDK Stage 6</h1>
<p>CloudFront + S3 are live. Next: React Cognito login UI.</p>
</body></html>""",
                )
                s3deploy.BucketDeployment(
                    self,
                    "DeployPlaceholder",
                    sources=[placeholder],
                    destination_bucket=ui_bucket,
                    distribution=distribution,
                    distribution_paths=["/*"],
                )

        # ----- Stage 7+: React UI (+ config.json; chat from stage 10) -----
        if stage >= 7 and ui_bucket is not None and distribution is not None:
            chat_enabled = stage >= 10
            auth_required = (
                user_pool is not None and user_pool_client is not None
            )
            config: dict[str, Any] = {
                "stage": stage,
                "authRequired": auth_required,
                "chatEnabled": chat_enabled,
                "region": region,
                "apiBase": "",
            }
            if auth_required and user_pool is not None and user_pool_client is not None:
                config["userPoolId"] = user_pool.user_pool_id
                config["clientId"] = user_pool_client.user_pool_client_id

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

        # ----- Stage 11: App Runner auto scaling + a monthly cost budget -----
        if stage >= 11 and api_service is not None:
            # min_size keeps one warm instance (no cold start on the first
            # request); max_size is a hard ceiling so a traffic burst in
            # class can't turn into a runaway bill; max_concurrency is how
            # many in-flight requests one instance takes before App Runner
            # starts a new one.
            min_size, max_size, max_concurrency = 1, 3, 25
            autoscaling = apprunner.CfnAutoScalingConfiguration(
                self,
                "ApiAutoScaling",
                auto_scaling_configuration_name=f"lauki-support-s{stage}",
                min_size=min_size,
                max_size=max_size,
                max_concurrency=max_concurrency,
            )
            api_service.auto_scaling_configuration_arn = (
                autoscaling.attr_auto_scaling_configuration_arn
            )
            CfnOutput(
                self,
                "AutoScalingLimits",
                value=f"min={min_size} max={max_size} concurrency={max_concurrency} (edit in stack.py)",
            )

            # Budgets supports an EMAIL subscriber directly — no SNS topic
            # or topic policy needed, which keeps this safe to run live.
            if budget_alert_email:
                budgets.CfnBudget(
                    self,
                    "MonthlyCostBudget",
                    budget=budgets.CfnBudget.BudgetDataProperty(
                        budget_type="COST",
                        time_unit="MONTHLY",
                        budget_limit=budgets.CfnBudget.SpendProperty(
                            amount=budget_limit_usd, unit="USD"
                        ),
                    ),
                    notifications_with_subscribers=[
                        budgets.CfnBudget.NotificationWithSubscribersProperty(
                            notification=budgets.CfnBudget.NotificationProperty(
                                notification_type="ACTUAL",
                                comparison_operator="GREATER_THAN",
                                threshold=80,
                                threshold_type="PERCENTAGE",
                            ),
                            subscribers=[
                                budgets.CfnBudget.SubscriberProperty(
                                    subscription_type="EMAIL",
                                    address=budget_alert_email,
                                )
                            ],
                        )
                    ],
                )
                CfnOutput(
                    self,
                    "BudgetAlert",
                    value=f"${budget_limit_usd}/mo, alert at 80% -> {budget_alert_email}",
                )

        # ----- Stage 12: let GitHub Actions deploy this stack via OIDC -----
        # (no long-lived AWS keys stored in the repo — same "no secrets in
        # the browser" idea from the Cognito/App Runner design, applied to
        # the pipeline instead of the UI.)
        if stage >= 12:
            if github_oidc_provider_arn:
                oidc_provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                    self, "GithubOidcProvider", github_oidc_provider_arn
                )
            else:
                oidc_provider = iam.OpenIdConnectProvider(
                    self,
                    "GithubOidcProvider",
                    url="https://token.actions.githubusercontent.com",
                    client_ids=["sts.amazonaws.com"],
                )

            deploy_role = iam.Role(
                self,
                "GithubActionsDeployRole",
                assumed_by=iam.WebIdentityPrincipal(
                    oidc_provider.open_id_connect_provider_arn,
                    conditions={
                        "StringEquals": {
                            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                        },
                        "StringLike": {
                            "token.actions.githubusercontent.com:sub": f"repo:{github_repo}:*"
                        },
                    },
                ),
                # Classroom scope: broad enough to deploy this whole stack.
                # Tighten to a scoped CDK-deploy policy once the pipeline is
                # proven — see OPS_DAY_RUNBOOK.md.
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "AdministratorAccess"
                    )
                ],
                max_session_duration=Duration.hours(1),
            )
            CfnOutput(self, "GithubActionsDeployRoleArn", value=deploy_role.role_arn)
