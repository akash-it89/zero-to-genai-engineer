# CDK — Lauki Support (production)

Parent guide: [`../README.md`](../README.md)

Deploys **App Runner (FastAPI) + private S3 + CloudFront** in one stack so the
browser uses a single HTTPS origin (`/api` proxied to App Runner).

## Quick start

```bash
# From repo lab root 05.strands-support-react-aws/
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/strands_support_copilot-XXXX

bash cdk/deploy.sh
```

Open the **`CloudFrontUrl`** output when deploy finishes.

## Manual

```bash
cd cdk
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
npx cdk@2 bootstrap "aws://${CDK_DEFAULT_ACCOUNT}/${CDK_DEFAULT_REGION}"
npx cdk@2 deploy -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" --require-approval never
```

## Destroy

```bash
npx cdk@2 destroy -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" --force
```

Does **not** delete AgentCore Runtime / Memory / Gateway / Guardrail (those stay
in lab 02 until you remove them separately).
