#!/usr/bin/env bash
# Deploy FastAPI → App Runner, React → S3 + CloudFront.
# Usage (from 05.agentcore-production-deploy):
#   export AWS_PROFILE=<your-profile> AWS_REGION=us-east-1
#   export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...:runtime/strands_support_copilot-XXXX
#   bash scripts/deploy_aws.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
# Use whatever profile/credentials are already configured. Do not assume a named profile.
# Example: export AWS_PROFILE=my-lab-profile

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [ -z "${SUPPORT_RUNTIME_ARN:-}" ]; then
  echo "ERROR: Set SUPPORT_RUNTIME_ARN to YOUR AgentCore Runtime ARN before deploying." >&2
  echo "  Example:" >&2
  echo "    export SUPPORT_RUNTIME_ARN=\$(... from 02.strands-agentcore-bedrock/.bedrock_agentcore.yaml ...)" >&2
  exit 1
fi
RUNTIME_ARN="$SUPPORT_RUNTIME_ARN"

# Sanity: Runtime account should match the caller account for same-account IAM.
RUNTIME_ACCOUNT="$(python3 - <<PY
arn = "${RUNTIME_ARN}"
parts = arn.split(":")
print(parts[4] if len(parts) > 4 else "")
PY
)"
if [ -n "$RUNTIME_ACCOUNT" ] && [ "$RUNTIME_ACCOUNT" != "$ACCOUNT" ]; then
  echo "WARNING: Runtime account ($RUNTIME_ACCOUNT) != caller account ($ACCOUNT)."
  echo "  Cross-account invoke needs a Runtime resource policy (see README)."
fi

ECR_REPO="lauki-support-api"
SERVICE_NAME="lauki-support-api"
UI_BUCKET="lauki-support-react-ui-${ACCOUNT}"
INSTANCE_ROLE="AppRunnerLaukiSupportInstanceRole"
ECR_ACCESS_ROLE="AppRunnerECRAccessRole"
PREFIX="lauki-support"

echo "==> Identity: $(aws sts get-caller-identity --query Arn --output text)"
echo "==> Runtime:  $RUNTIME_ARN"

# --- IAM: App Runner instance role (InvokeAgentRuntime) ---
if ! aws iam get-role --role-name "$INSTANCE_ROLE" >/dev/null 2>&1; then
  echo "==> Creating instance role $INSTANCE_ROLE"
  aws iam create-role \
    --role-name "$INSTANCE_ROLE" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{
        "Effect":"Allow",
        "Principal":{"Service":"tasks.apprunner.amazonaws.com"},
        "Action":"sts:AssumeRole"
      }]
    }' >/dev/null
fi

aws iam put-role-policy \
  --role-name "$INSTANCE_ROLE" \
  --policy-name InvokeAgentCore \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Action\":[
        \"bedrock-agentcore:InvokeAgentRuntime\",
        \"bedrock-agentcore:InvokeAgentRuntimeForUser\"
      ],
      \"Resource\":[
        \"${RUNTIME_ARN}\",
        \"${RUNTIME_ARN}/runtime-endpoint/DEFAULT\"
      ]
    }]
  }"

INSTANCE_ROLE_ARN="$(aws iam get-role --role-name "$INSTANCE_ROLE" --query Role.Arn --output text)"

# --- IAM: App Runner ECR access role ---
if ! aws iam get-role --role-name "$ECR_ACCESS_ROLE" >/dev/null 2>&1; then
  echo "==> Creating ECR access role $ECR_ACCESS_ROLE"
  aws iam create-role \
    --role-name "$ECR_ACCESS_ROLE" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{
        "Effect":"Allow",
        "Principal":{"Service":"build.apprunner.amazonaws.com"},
        "Action":"sts:AssumeRole"
      }]
    }' >/dev/null
  aws iam attach-role-policy \
    --role-name "$ECR_ACCESS_ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
fi
ECR_ACCESS_ROLE_ARN="$(aws iam get-role --role-name "$ECR_ACCESS_ROLE" --query Role.Arn --output text)"

# IAM propagation
sleep 8

# --- ECR ---
if ! aws ecr describe-repositories --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  echo "==> Creating ECR repo $ECR_REPO"
  aws ecr create-repository --repository-name "$ECR_REPO" >/dev/null
fi
ECR_URI="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
IMAGE_TAG="latest"
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

echo "==> Building + pushing $IMAGE_URI"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build --platform linux/amd64 -t "$ECR_REPO:$IMAGE_TAG" "$ROOT/api"
docker tag "$ECR_REPO:$IMAGE_TAG" "$IMAGE_URI"
docker push "$IMAGE_URI"

# --- App Runner ---
EXISTING="$(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" --output text || true)"

SOURCE_CONFIG=$(python3 - <<PY
import json
print(json.dumps({
  "AuthenticationConfiguration": {
    "AccessRoleArn": "${ECR_ACCESS_ROLE_ARN}"
  },
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE_URI}",
    "ImageRepositoryType": "ECR",
    "ImageConfiguration": {
      "Port": "8000",
      "RuntimeEnvironmentVariables": {
        "SUPPORT_RUNTIME_ARN": "${RUNTIME_ARN}",
        "AWS_REGION": "${AWS_REGION}",
        "CORS_ORIGINS": "*"
      }
    }
  },
  "AutoDeploymentsEnabled": False
}))
PY
)

INSTANCE_CONFIG='{"Cpu":"1024","Memory":"2048","InstanceRoleArn":"'"${INSTANCE_ROLE_ARN}"'"}'
HEALTH='{"Protocol":"HTTP","Path":"/health","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}'

if [ -z "$EXISTING" ] || [ "$EXISTING" = "None" ]; then
  echo "==> Creating App Runner service $SERVICE_NAME"
  CREATE_OUT=$(aws apprunner create-service \
    --service-name "$SERVICE_NAME" \
    --source-configuration "$SOURCE_CONFIG" \
    --instance-configuration "$INSTANCE_CONFIG" \
    --health-check-configuration "$HEALTH" \
    --output json)
  SERVICE_ARN=$(echo "$CREATE_OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Service"]["ServiceArn"])')
else
  SERVICE_ARN="$EXISTING"
  echo "==> Updating App Runner service $SERVICE_ARN"
  aws apprunner update-service \
    --service-arn "$SERVICE_ARN" \
    --source-configuration "$SOURCE_CONFIG" \
    --instance-configuration "$INSTANCE_CONFIG" \
    --health-check-configuration "$HEALTH" >/dev/null
fi

echo "==> Waiting for App Runner RUNNING..."
for i in $(seq 1 60); do
  STATUS=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --query 'Service.Status' --output text)
  URL=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --query 'Service.ServiceUrl' --output text)
  echo "  [$i] status=$STATUS url=$URL"
  if [ "$STATUS" = "RUNNING" ]; then
    break
  fi
  if [ "$STATUS" = "CREATE_FAILED" ] || [ "$STATUS" = "DELETE_FAILED" ]; then
    echo "App Runner failed: $STATUS" >&2
    exit 1
  fi
  sleep 15
done

API_URL="https://${URL}"
echo "==> API URL: $API_URL"
curl -sf "${API_URL}/health" && echo " (health ok)" || echo " (health not ready yet — wait a minute)"

# --- React build ---
echo "==> Building React with VITE_API_BASE=$API_URL"
cd "$ROOT/web"
npm install --silent
VITE_API_BASE="$API_URL" npm run build

# --- S3 static hosting ---
if ! aws s3api head-bucket --bucket "$UI_BUCKET" 2>/dev/null; then
  echo "==> Creating bucket $UI_BUCKET"
  aws s3 mb "s3://${UI_BUCKET}" --region "$AWS_REGION"
fi

aws s3api put-public-access-block \
  --bucket "$UI_BUCKET" \
  --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false

aws s3 website "s3://${UI_BUCKET}" --index-document index.html --error-document index.html

aws s3api put-bucket-policy --bucket "$UI_BUCKET" --policy "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{
    \"Sid\":\"PublicReadGetObject\",
    \"Effect\":\"Allow\",
    \"Principal\":\"*\",
    \"Action\":\"s3:GetObject\",
    \"Resource\":\"arn:aws:s3:::${UI_BUCKET}/*\"
  }]
}"

aws s3 sync dist/ "s3://${UI_BUCKET}/" --delete \
  --cache-control "public,max-age=60"

WEBSITE="http://${UI_BUCKET}.s3-website-${AWS_REGION}.amazonaws.com"

# --- CloudFront (HTTPS) ---
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='${PREFIX}-ui'].Id" --output text 2>/dev/null || true)

ORIGIN_DOMAIN="${UI_BUCKET}.s3-website-${AWS_REGION}.amazonaws.com"

if [ -z "$DIST_ID" ] || [ "$DIST_ID" = "None" ]; then
  echo "==> Creating CloudFront distribution"
  CALLER="$(date +%s)"
  DIST_OUT=$(aws cloudfront create-distribution --distribution-config "{
    \"CallerReference\":\"${CALLER}\",
    \"Comment\":\"${PREFIX}-ui\",
    \"Enabled\":true,
    \"DefaultRootObject\":\"index.html\",
    \"Origins\":{
      \"Quantity\":1,
      \"Items\":[{
        \"Id\":\"s3-website\",
        \"DomainName\":\"${ORIGIN_DOMAIN}\",
        \"CustomOriginConfig\":{
          \"HTTPPort\":80,
          \"HTTPSPort\":443,
          \"OriginProtocolPolicy\":\"http-only\"
        }
      }]
    },
    \"DefaultCacheBehavior\":{
      \"TargetOriginId\":\"s3-website\",
      \"ViewerProtocolPolicy\":\"redirect-to-https\",
    \"AllowedMethods\":{
      \"Quantity\":2,
      \"Items\":[\"GET\",\"HEAD\"],
      \"CachedMethods\":{\"Quantity\":2,\"Items\":[\"GET\",\"HEAD\"]}
    },
    \"ForwardedValues\":{\"QueryString\":false,\"Cookies\":{\"Forward\":\"none\"}},
    \"MinTTL\":0,
    \"DefaultTTL\":60,
    \"MaxTTL\":300,
    \"Compress\":true
  },
    \"CustomErrorResponses\":{
      \"Quantity\":2,
      \"Items\":[
        {\"ErrorCode\":403,\"ResponsePagePath\":\"/index.html\",\"ResponseCode\":\"200\",\"ErrorCachingMinTTL\":0},
        {\"ErrorCode\":404,\"ResponsePagePath\":\"/index.html\",\"ResponseCode\":\"200\",\"ErrorCachingMinTTL\":0}
      ]
    }
  }" --output json)
  DIST_ID=$(echo "$DIST_OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Distribution"]["Id"])')
  CF_DOMAIN=$(echo "$DIST_OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Distribution"]["DomainName"])')
else
  CF_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)
  echo "==> Invalidating CloudFront $DIST_ID"
  aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null
fi

UI_HTTPS="https://${CF_DOMAIN}"

cat > "$ROOT/deploy-urls.txt" <<EOF
API_URL=${API_URL}
UI_S3_WEBSITE=${WEBSITE}
UI_CLOUDFRONT=${UI_HTTPS}
RUNTIME_ARN=${RUNTIME_ARN}
ACCOUNT=${ACCOUNT}
SERVICE_ARN=${SERVICE_ARN}
BUCKET=${UI_BUCKET}
DIST_ID=${DIST_ID}
EOF

echo ""
echo "========================================"
echo " Deploy complete"
echo " API:  $API_URL"
echo " UI:   $UI_HTTPS"
echo " S3:   $WEBSITE"
echo " (CloudFront can take 5–15 min to go live)"
echo " Saved: deploy-urls.txt"
echo "========================================"
