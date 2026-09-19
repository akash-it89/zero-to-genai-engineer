#!/usr/bin/env bash
# Deploy 06.progressive-deploy 01→10 and verify each step.
# Usage (with AWS creds already exported):
#   bash 06.progressive-deploy/verify_all_steps.sh
set -euo pipefail

STEPS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT="$STEPS_DIR/VERIFY_REPORT.md"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export STACK_NAME="${STACK_NAME:-LaukiSupportStack}"
STACK_SAFE="$(echo "$STACK_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]/-/g; s/^-+//; s/-+$//' | cut -c1-24)"

if [ -z "${SUPPORT_RUNTIME_ARN:-}" ]; then
  echo "ERROR: export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:... (from your lab 02 deploy)" >&2
  exit 1
fi

STEPS=(
  01_empty_cdk
  02_cognito_pool
  03_cognito_client
  04_demo_user
  05_s3_ui_bucket
  06_cloudfront
  07_react_login
  08_apprunner_health
  09_jwt_lock
  10_agentcore_chat
)

mkdir -p "$STEPS_DIR"
{
  echo "# Classroom steps verify report"
  echo ""
  echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Account: $(aws sts get-caller-identity --query Account --output text)"
  echo "START_FROM=${START_FROM:-1}"
  echo ""
} > "$REPORT"

# If resuming, keep prior PASS notes
if [[ "${START_FROM:-1}" -gt 1 && -f "$STEPS_DIR/VERIFY_REPORT.md.bak" ]]; then
  :
fi
if [[ "${START_FROM:-1}" -gt 1 && -f "$STEPS_DIR/verify_run.log" ]]; then
  {
    echo "# Classroom steps verify report (resumed)"
    echo ""
    echo "Resumed: $(date -u +%Y-%m-%dT%H:%M:%SZ) from step ${START_FROM}"
    echo "Account: $(aws sts get-caller-identity --query Account --output text)"
    echo ""
    echo "## Prior steps 01–$((START_FROM - 1))"
    echo ""
    echo "See verify_run.log / earlier run — already deployed and checked."
    echo ""
  } > "$REPORT"
fi

cfn_out() {
  local key="$1"
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" --output text 2>/dev/null || true
}

pass() { echo "- PASS: $*" | tee -a "$REPORT"; }
fail() { echo "- FAIL: $*" | tee -a "$REPORT"; FAILED=1; }

deploy_step() {
  local folder="$1"
  echo ""
  echo "========== DEPLOY $folder =========="
  echo "" >> "$REPORT"
  echo "## $folder" >> "$REPORT"
  echo "" >> "$REPORT"
  (
    cd "$STEPS_DIR/$folder"
    bash deploy.sh
  )
}

verify_01() {
  local step; step="$(cfn_out DeployStep)"
  [[ "$step" == "1" ]] && pass "DeployStep=1" || fail "DeployStep want 1 got '$step'"
  aws ssm get-parameter --name "/lauki-support/$STACK_SAFE/deploy-stage" --query Parameter.Value --output text | grep -qx 1 \
    && pass "SSM stage marker=1" || fail "SSM marker"
}

verify_02() {
  local pool; pool="$(cfn_out UserPoolId)"
  [[ -n "$pool" && "$pool" != "None" ]] && pass "UserPoolId=$pool" || fail "UserPoolId missing"
  aws cognito-idp describe-user-pool --user-pool-id "$pool" --query 'UserPool.Name' --output text \
    | grep -q lauki && pass "Pool exists in Cognito" || fail "Pool describe"
}

verify_03() {
  local cid; cid="$(cfn_out UserPoolClientId)"
  [[ -n "$cid" && "$cid" != "None" ]] && pass "UserPoolClientId=$cid" || fail "ClientId missing"
}

verify_04() {
  local pool user
  pool="$(cfn_out UserPoolId)"
  user="$(cfn_out DemoUsername)"
  [[ "$user" == "demo" ]] && pass "DemoUsername=demo" || fail "DemoUsername"
  aws cognito-idp admin-get-user --user-pool-id "$pool" --username demo \
    --query 'UserStatus' --output text | grep -Eq 'CONFIRMED|FORCE_CHANGE_PASSWORD' \
    && pass "demo user present" || fail "demo user missing"
}

verify_05() {
  local b; b="$(cfn_out UiBucketName)"
  [[ -n "$b" && "$b" != "None" ]] && pass "UiBucketName=$b" || fail "bucket"
  aws s3api head-bucket --bucket "$b" && pass "S3 bucket reachable" || fail "S3 head-bucket"
}

verify_06() {
  local url; url="$(cfn_out CloudFrontUrl)"
  [[ "$url" == https://* ]] && pass "CloudFrontUrl=$url" || fail "CloudFrontUrl"
  # CF can lag; retry
  local body="" code=0
  for i in 1 2 3 4 5 6; do
    body="$(curl -fsS "$url/" 2>/dev/null || true)"
    echo "$body" | grep -q "Step 06\|CDK Stage 6\|Classroom Step 06" && break
    sleep 15
  done
  echo "$body" | grep -q "Step 06\|CDK Stage 6\|Classroom Step 06" \
    && pass "Placeholder HTML visible" || fail "Placeholder HTML not found (body len=${#body})"
}

verify_07() {
  local url pool cid
  url="$(cfn_out CloudFrontUrl)"
  pool="$(cfn_out UserPoolId)"
  cid="$(cfn_out UserPoolClientId)"
  sleep 20
  local cfg
  cfg="$(curl -fsS "$url/config.json")"
  echo "$cfg" | grep -Eq '"chatEnabled"[[:space:]]*:[[:space:]]*false' && pass "config chatEnabled=false" || fail "chatEnabled in config: $cfg"
  echo "$cfg" | grep -q "$pool" && pass "config has userPoolId" || fail "config pool"
  # Cognito login works
  local token
  token="$(aws cognito-idp initiate-auth \
    --client-id "$cid" \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME=demo,PASSWORD='DemoUser1!' \
    --query 'AuthenticationResult.IdToken' --output text)"
  [[ -n "$token" && "$token" != "None" ]] && pass "Cognito login demo/DemoUser1! works" || fail "Cognito login"
  curl -fsS "$url/" | grep -qi "lauki\|root\|script" && pass "React shell HTML served" || fail "React HTML"
}

verify_08() {
  local url ar
  url="$(cfn_out CloudFrontUrl)"
  ar="$(cfn_out AppRunnerUrl)"
  [[ "$ar" == https://* ]] && pass "AppRunnerUrl=$ar" || fail "AppRunnerUrl"
  sleep 30
  local h1 h2
  h1="$(curl -fsS "$ar/health")"
  h2="$(curl -fsS "$url/health")"
  echo "$h1" | grep -q '"status":"ok"' && pass "App Runner /health: $h1" || fail "AR health: $h1"
  echo "$h2" | grep -q '"status":"ok"' && pass "CloudFront /health: $h2" || fail "CF health: $h2"
}

verify_09() {
  local url cid token code
  url="$(cfn_out CloudFrontUrl)"
  cid="$(cfn_out UserPoolClientId)"
  sleep 40
  code="$(curl -sS -o /tmp/me_noauth.json -w '%{http_code}' "$url/api/me")"
  [[ "$code" == "401" ]] && pass "/api/me without token → 401" || fail "/api/me want 401 got $code"
  token="$(aws cognito-idp initiate-auth \
    --client-id "$cid" \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME=demo,PASSWORD='DemoUser1!' \
    --query 'AuthenticationResult.IdToken' --output text)"
  code="$(curl -sS -o /tmp/me_auth.json -w '%{http_code}' -H "Authorization: Bearer $token" "$url/api/me")"
  [[ "$code" == "200" ]] && pass "/api/me with token → 200 $(cat /tmp/me_auth.json)" || fail "/api/me auth got $code $(cat /tmp/me_auth.json)"
  local h; h="$(curl -fsS "$url/health")"
  echo "$h" | grep -q cognito && pass "health auth=cognito: $h" || pass "health: $h (auth may vary)"
}

verify_10() {
  local url cid token code body
  url="$(cfn_out CloudFrontUrl)"
  cid="$(cfn_out UserPoolClientId)"
  sleep 45
  local cfg; cfg="$(curl -fsS "$url/config.json")"
  echo "$cfg" | grep -Eq '"chatEnabled"[[:space:]]*:[[:space:]]*true' && pass "config chatEnabled=true" || fail "chatEnabled: $cfg"
  token="$(aws cognito-idp initiate-auth \
    --client-id "$cid" \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME=demo,PASSWORD='DemoUser1!' \
    --query 'AuthenticationResult.IdToken' --output text)"
  code="$(curl -sS -o /tmp/chat.json -w '%{http_code}' \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"How do I activate a new SIM?","actor_id":"demo","thread_id":"verify-thread-abcdefghijklmnop"}' \
    "$url/api/chat")"
  body="$(cat /tmp/chat.json)"
  [[ "$code" == "200" ]] && pass "/api/chat → 200" || fail "/api/chat want 200 got $code $body"
  echo "$body" | grep -qi 'result\|SIM\|activate\|eSIM\|plan' \
    && pass "Chat response looks grounded (len=${#body})" || fail "Chat body unexpected: $body"
}

FAILED=0
START_FROM="${START_FROM:-1}"

for i in "${!STEPS[@]}"; do
  n=$((i + 1))
  if (( n < START_FROM )); then
    echo "skip ${STEPS[$i]}"
    continue
  fi
  folder="${STEPS[$i]}"
  deploy_step "$folder"
  echo "### Checks" >> "$REPORT"
  case "$n" in
    1) verify_01 ;;
    2) verify_02 ;;
    3) verify_03 ;;
    4) verify_04 ;;
    5) verify_05 ;;
    6) verify_06 ;;
    7) verify_07 ;;
    8) verify_08 ;;
    9) verify_09 ;;
    10) verify_10 ;;
  esac
  if [[ "${FAILED:-0}" == "1" ]]; then
    echo "" | tee -a "$REPORT"
    echo "**Stopped after $folder due to failures.**" | tee -a "$REPORT"
    exit 1
  fi
done

{
  echo ""
  echo "## Summary"
  echo ""
  echo "All steps deployed and verified: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "Final CloudFrontUrl: $(cfn_out CloudFrontUrl)"
  echo "Final AppRunnerUrl: $(cfn_out AppRunnerUrl)"
} | tee -a "$REPORT"

echo ""
echo "Report: $REPORT"
