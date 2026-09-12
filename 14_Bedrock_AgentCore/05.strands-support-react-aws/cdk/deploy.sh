#!/usr/bin/env bash
# One-shot production deploy via CDK.
#
#   export AWS_PROFILE=<your-profile>
#   export AWS_REGION=us-east-1
#   export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/strands_support_copilot-XXXX
#   bash cdk/deploy.sh
#
# Or:
#   bash cdk/deploy.sh -c supportRuntimeArn=arn:...

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export CDK_DEFAULT_REGION="$AWS_REGION"
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

if [ -z "${SUPPORT_RUNTIME_ARN:-}" ] && [[ "$*" != *supportRuntimeArn* ]]; then
  echo "ERROR: set SUPPORT_RUNTIME_ARN or pass -c supportRuntimeArn=..." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

echo "==> Account=$CDK_DEFAULT_ACCOUNT Region=$AWS_REGION"
aws sts get-caller-identity

# Bootstrap once per account/region (safe to re-run)
npx --yes cdk@2 bootstrap "aws://${CDK_DEFAULT_ACCOUNT}/${AWS_REGION}"

ARGS=("$@")
if [ -n "${SUPPORT_RUNTIME_ARN:-}" ] && [[ "$*" != *supportRuntimeArn* ]]; then
  ARGS+=(-c "supportRuntimeArn=${SUPPORT_RUNTIME_ARN}")
fi

echo "==> cdk deploy ${ARGS[*]}"
npx --yes cdk@2 deploy --require-approval never "${ARGS[@]}"
