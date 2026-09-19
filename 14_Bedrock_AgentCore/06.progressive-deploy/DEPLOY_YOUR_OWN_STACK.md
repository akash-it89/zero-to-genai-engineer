# Deploy your own stack (steps 01 → 10)

One CloudFormation stack, updated 10 times. Pick a **new stack name** so you do
not overwrite a classmate’s stack (or an older `LaukiSupportStack` you want to keep).

---

## Setup (run once)

```bash
cd 14_Bedrock_AgentCore/06.progressive-deploy

export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1

# ★ Your stack name (change this if you redeploy in parallel)
export STACK_NAME=LaukiSupportStudent1

# Only required for step 10 — YOUR Runtime ARN from lab 02
export SUPPORT_RUNTIME_ARN='arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX'

aws sts get-caller-identity
docker info >/dev/null
```

Never paste someone else’s Runtime ARN or CloudFront URL into your homework.

---

## Deploy 01 → 10 (same `STACK_NAME` every time)

```bash
cd 01_empty_cdk && bash deploy.sh
cd ../02_cognito_pool && bash deploy.sh
cd ../03_cognito_client && bash deploy.sh
cd ../04_demo_user && bash deploy.sh
cd ../05_s3_ui_bucket && bash deploy.sh
cd ../06_cloudfront && bash deploy.sh
cd ../07_react_login && bash deploy.sh
cd ../08_apprunner_health && bash deploy.sh
cd ../09_jwt_lock && bash deploy.sh
cd ../10_agentcore_chat && bash deploy.sh
```

---

## After any step — read outputs

```bash
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' --output table
```

---

## After step 06+ — open the UI

```bash
CF=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" --output text)
echo "$CF"
# open "$CF"   # macOS; or paste the URL in your browser
```

Login (from step 04): **`demo` / `DemoUser1!`**

---

## One-liner loop (optional)

```bash
for d in 01_empty_cdk 02_cognito_pool 03_cognito_client 04_demo_user 05_s3_ui_bucket \
         06_cloudfront 07_react_login 08_apprunner_health 09_jwt_lock 10_agentcore_chat
do
  echo "======== $d → stack $STACK_NAME ========"
  (cd "$d" && bash deploy.sh)
done

aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' --output table
```

---

## Destroy this named stack later

```bash
cd 10_agentcore_chat/cdk
source .venv/bin/activate
npx cdk destroy "$STACK_NAME" \
  -c stackName="$STACK_NAME" \
  -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" \
  --force
```

This does **not** delete AgentCore Runtime / Memory / Gateway / Guardrail from lab 02.
Clean those up separately when you are finished with the lab.
