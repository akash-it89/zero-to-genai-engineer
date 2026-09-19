# Verification checklist — classroom steps 01 → 10

Use this after each deploy (or at the end) to confirm **your** stack works.
Replace `STACK_NAME` / URLs with your outputs — do not copy another student’s.

```bash
export STACK_NAME="${STACK_NAME:-LaukiSupportStack}"
export AWS_REGION=us-east-1
```

| Step | Folder | Pass when you can prove… |
|-----:|--------|--------------------------|
| 01 | `01_empty_cdk` | Stack exists; `DeployStep` / stage output = `1` |
| 02 | `02_cognito_pool` | `UserPoolId` output; pool visible in Cognito console |
| 03 | `03_cognito_client` | `UserPoolClientId`; SPA client on the pool |
| 04 | `04_demo_user` | Cognito user `demo` is Confirmed |
| 05 | `05_s3_ui_bucket` | `UiBucketName`; Block Public Access ON |
| 06 | `06_cloudfront` | `CloudFrontUrl` serves the placeholder page |
| 07 | `07_react_login` | Login works; `chatEnabled: false` in `/config.json` |
| 08 | `08_apprunner_health` | `curl CloudFrontUrl/health` (and App Runner `/health`) → ok |
| 09 | `09_jwt_lock` | `/api/me` → **401** without token; **200** with ID token |
| 10 | `10_agentcore_chat` | `chatEnabled: true`; chat answers a SIM / eSIM question |

## UI / API by step

| Step | Browser (CloudFront) | Backend |
|-----:|----------------------|---------|
| 01–05 | No public site yet | Cognito / S3 growing in console |
| 06 | Static placeholder page | S3 + CloudFront only |
| 07 | React **sign-in**; chat composer **locked** | Cognito only (no API) |
| 08 | Same React (chat still off) | FastAPI **/health** open |
| 09 | Same React | **/api/me** requires JWT |
| 10 | Chat **on** | **/api/chat** → AgentCore |

## Handy commands

```bash
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' --output table

CF=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" --output text)

curl -sS "$CF/health"; echo
curl -sS "$CF/config.json"; echo
curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$CF/api/chat" \
  -H 'Content-Type: application/json' -d '{"prompt":"hi"}'   # expect 401 until logged in
```

Login after step 04: **`demo` / `DemoUser1!`**

Detailed explanations: [`STEP_BY_STEP.md`](./STEP_BY_STEP.md)
