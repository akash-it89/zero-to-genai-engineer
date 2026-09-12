# Strands Support Copilot — Deploy Frontend + Backend on AWS (your account)

Parent index: [`../README.md`](../README.md)  
Agent Runtime lab (required first): [`../02.strands-agentcore-bedrock`](../02.strands-agentcore-bedrock/)

This guide is written so **anyone** can deploy the full stack in **their own AWS
account** — AgentCore Runtime → FastAPI on App Runner → React on S3 + CloudFront —
without copying trainer ARNs, buckets, or profiles.

**Honest scope:** this README + lab 02 together are the full path. Lab **05** alone
cannot create the agent brain — you must finish lab **02** Runtime first, then
come back here for the web UI hosting (CDK recommended).

---

## Absolute beginners — set up AWS on your laptop (do this once)

If you have never used the AWS CLI:

1. Create an AWS account (or get a classroom account from your trainer).
2. In the console (top right) note your **12-digit Account ID**.
3. Create an IAM user (or use the one your trainer gave you) with programmatic access.
   Classroom shortcut: attach **`AdministratorAccess`** so CDK/App Runner/IAM do not fail mid-deploy.
4. Create an **access key** for that user (Console → IAM → Users → Security credentials).
5. Install [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
6. Configure a named profile (example name `my-lab`):

```bash
aws configure --profile my-lab
# AWS Access Key ID:     <paste>
# AWS Secret Access Key: <paste>
# Default region name:   us-east-1
# Default output format: json

export AWS_PROFILE=my-lab
export AWS_REGION=us-east-1
aws sts get-caller-identity
# Must print YOUR Account id and user/role ARN — not a classmate’s
```

7. In the console, open region **`us-east-1`** and confirm you can see
   **Amazon Bedrock → AgentCore** (Memory / Runtime). If AgentCore is missing,
   your account/region may not have the service enabled — ask your trainer.
8. Install **Docker Desktop** and leave it **running** (CDK builds the API image
   and bundles the React app inside containers).
9. Install **Node.js 18+** and **Python 3.10–3.13** (`python3 --version`).
   Avoid Python 3.14 for lab 02 / `uv` installs.

Also install lab-02 tooling when you get there (`uv`, OpenAI API key). See lab 02 README Step 0.

---

## What you are deploying

```
Browser
  │  HTTPS  (one CloudFront URL)
  ▼
CloudFront
  ├─ /*           → S3 (React)         ← no AWS keys in the browser
  └─ /api/*, /health → App Runner API  ← IAM Instance Role invokes AgentCore
  │
  ▼
AgentCore Runtime (strands_support_copilot)
  + Memory + Gateway + Identity
  + Bedrock Guardrail (ApplyGuardrail)
  + OpenAI LLM (typical classroom accounts block Bedrock model Error 002)
```

| Piece | Runs where | Holds secrets? |
|---|---|---|
| React UI | S3 + CloudFront (or local Vite) | **No** — same-origin `/api` via CloudFront |
| FastAPI | App Runner container (or local uvicorn) | **No OpenAI key** — only AWS IAM to invoke Runtime |
| Agent Runtime | Bedrock AgentCore | Yes — `OPENAI_API_KEY`, Gateway token, Memory id (baked at `agentcore deploy`) |

---

## Prerequisites

### Tools on your laptop

| Tool | Why | Check |
|---|---|---|
| AWS CLI v2 | Deploy + identity checks | `aws --version` |
| Configured AWS profile | Credentials for *your* account | `aws sts get-caller-identity` |
| Docker Desktop (running) | Build API image + CDK React bundling | `docker info` |
| Node.js 18+ / npm | Local React / `npx cdk@2` | `node -v` |
| Python 3.10–3.13 | Lab 02 Runtime + CDK app | `python3 --version` |
| `uv` (recommended) | Lab 02 package install | `uv --version` |
| OpenAI API key | Runtime LLM (when Bedrock models blocked) | key starts with `sk-` |

### AWS permissions (same account)

Your IAM user/role needs enough access to:

- **CloudFormation** + **CDK bootstrap** (SSM param `/cdk-bootstrap/...`, staging S3/ECR)
- **Bedrock AgentCore** — Runtime, Memory, Gateway, Identity
- **Bedrock Guardrails** — `CreateGuardrail`, `CreateGuardrailVersion`, `ApplyGuardrail`
- **IAM** — create roles + policies (App Runner + CDK custom resources)
- **ECR** — push/pull images
- **App Runner** — create/update service
- **S3** + **CloudFront** — UI hosting
- **Lambda** — CDK `BucketDeployment` helper
- **Cognito** + **Lambda** — Gateway from lab 02

Classroom tip: **`AdministratorAccess`** avoids mid-deploy IAM surprises.

### Secrets you must provide

| Secret | Used by | Where you set it |
|---|---|---|
| OpenAI API key | Agent Runtime only | `--env OPENAI_API_KEY=...` on `agentcore deploy` |
| AWS credentials | Your CLI; App Runner uses an **instance role** in the cloud | `AWS_PROFILE` — **same account as the Runtime** |

Never put AWS keys or OpenAI keys in the React app.

### Cost / region notes (read before deploying)

| Item | Typical note |
|---|---|
| Region for Runtime / Memory / Guardrail / App Runner / CDK | **`us-east-1`** |
| Gateway + Cognito (lab 02 script) | Usually **`us-west-2`** — follow lab 02 |
| Ongoing cost drivers | App Runner (always-on), CloudFront, AgentCore invokes, OpenAI tokens, small S3/ECR |
| First CDK deploy | Often **10–20 minutes**; bootstrap once per account/region |
| Tear down | [Cleanup](#9-cleanup--stop-charges) — CDK destroy does **not** delete AgentCore Runtime |

Exact dollars vary by account; treat App Runner as the main “left it on overnight” cost.

---

## Folder map (this lab)

```
05.strands-support-react-aws/
├── README.md                 ← this file
├── cdk/                      ← ★ production: one `cdk deploy`
│   ├── app.py
│   ├── lauki_support_stack.py
│   ├── cdk.json
│   ├── requirements.txt
│   ├── deploy.sh
│   └── README.md
├── scripts/deploy_aws.sh     ← alternative bash deploy (no CDK)
├── api/
│   ├── Dockerfile
│   ├── main.py               ← POST /api/chat → InvokeAgentRuntime
│   └── requirements.txt
└── web/
    ├── package.json
    ├── vite.config.js
    ├── amplify.yml           ← optional Amplify Hosting
    └── src/App.jsx           ← empty VITE_API_BASE = same-origin /api
```

---

## End-to-end checklist (do in order)

| # | Phase | Outcome |
|---|---|---|
| 0 | [AWS laptop setup](#absolute-beginners--set-up-aws-on-your-laptop-do-this-once) | `sts get-caller-identity` works |
| 1 | [Lab 02 backend](#1-backend--agentcore-runtime-lab-02) | Memory, Gateway, Identity in **your** account |
| 2 | [Guardrail](#2-create-a-bedrock-guardrail) | Your `GUARDRAIL_ID` / `VERSION` |
| 3 | [Deploy Runtime](#3-deploy-strands_support_copilot-runtime) | Your `SUPPORT_RUNTIME_ARN` |
| 4 | [Smoke-test Runtime](#4-smoke-test-the-runtime) | CLI invoke returns FAQ-style answer |
| 5 | **[CDK production deploy](#6-production-deploy-with-cdk-recommended)** | One CloudFront URL for UI + API |
| 6 | *(Optional)* [Local API + React](#5-optional-run-api--react-locally) | Debug before / without cloud UI |
| 7 | *(Optional)* [Bash deploy](#7-alternative-bash-deploy-scriptsdeploy_awssh) | Same idea without CDK |
| 8 | [Verify](#8-verify-production) | Browser chat works |
| 9 | [Cleanup](#9-cleanup--stop-charges) | Stop App Runner / CF charges when done |

Do **not** paste a classmate’s Runtime ARN, Memory id, or Gateway credentials.

---

## 1) Backend — AgentCore Runtime (lab 02)

**You cannot skip this.** Lab 05 only hosts a UI/API in front of a Runtime that
already exists.

Complete **Steps 0 → 3** and **Demo 5** in:

[`../02.strands-agentcore-bedrock/README.md`](../02.strands-agentcore-bedrock/README.md)

That lab walks you through (in order):

0. Local `.venv` + `.env` (`OPENAI_API_KEY`, `AWS_REGION=us-east-1`)
1. Create **Memory** in console (`us-east-1`) → `MEMORY_ID`
2. Run `scripts/create_mcp_gateway.py` → `gateway-credentials.json` (often `us-west-2`)
3. Create **Identity** OAuth provider in console (`us-east-1`) named like `gateway-cognito-m2m`
4. Deploy demos culminating in **`strands_support_copilot`**

Minimum checks before continuing here:

```bash
cd ../02.strands-agentcore-bedrock
source .venv/bin/activate
export AWS_PROFILE=<your-profile>   # YOUR account
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity         # note Account = AAAAAAAAAAAA

set -a && source .env && set +a
# .env must contain at least:
#   OPENAI_API_KEY=sk-...
#   MEMORY_ID=<your memory id from console>
# and gateway-credentials.json from scripts/create_mcp_gateway.py
test -f gateway-credentials.json && echo "gateway OK"
test ${#MEMORY_ID} -ge 12 && echo "MEMORY_ID OK"
test ${#OPENAI_API_KEY} -gt 20 && echo "OPENAI OK"
```

Identity provider name used by the flagship agent (lab 02 default):
`gateway-cognito-m2m` with scope `lauki-demo-gateway/invoke`.

---

## 2) Create a Bedrock Guardrail

From lab 02 (same AWS credentials / `us-east-1`):

```bash
cd ../02.strands-agentcore-bedrock
source .venv/bin/activate
export AWS_REGION=us-east-1

.venv/bin/python scripts/create_basic_guardrail.py
```

Example output:

```json
{
  "GUARDRAIL_ID": "xxxxxxxxxxxx",
  "GUARDRAIL_VERSION": "1",
  "GUARDRAIL_ARN": "arn:aws:bedrock:us-east-1:ACCOUNT:guardrail/...",
  "region": "us-east-1"
}
```

Export them:

```bash
export GUARDRAIL_ID=xxxxxxxxxxxx          # YOUR id
export GUARDRAIL_VERSION=1
```

After Runtime deploy, lab 02’s
`scripts/grant_runtime_memory_permissions.py --all-from-config` also grants
`bedrock:ApplyGuardrail` on the Runtime role. If chat works but Guardrail never
blocks, re-run that grant script and redeploy the Runtime with the Guardrail env vars.

---

## 3) Deploy `strands_support_copilot` Runtime

Still in lab 02:

```bash
cd ../02.strands-agentcore-bedrock
source .venv/bin/activate
set -a && source .env && set +a
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
alias agentcore='.venv/bin/agentcore'
export AGENTCORE_SUPPRESS_RECOMMENDATION=1

export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e strands_support_copilot.py -n strands_support_copilot \
  --disable-memory --non-interactive --region us-east-1

# USE_BEDROCK=false → OpenAI generation + ApplyGuardrail (works when Bedrock models are blocked)
agentcore deploy -a strands_support_copilot \
  --env AWS_REGION=us-east-1 \
  --env USE_BEDROCK=false \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env GUARDRAIL_ID="$GUARDRAIL_ID" \
  --env GUARDRAIL_VERSION="$GUARDRAIL_VERSION" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config
```

Capture **your** ARN (never hardcode someone else’s):

```bash
export SUPPORT_RUNTIME_ARN="$(.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
print(yaml.safe_load(Path(".bedrock_agentcore.yaml").read_text())
      ["agents"]["strands_support_copilot"]["bedrock_agentcore"]["agent_arn"])
PY
)"
echo "$SUPPORT_RUNTIME_ARN"
# Expected shape:
# arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXXXXXX
```

Persist it for later shells:

```bash
# optional: add to a gitignored file in THIS lab
cd ../05.strands-support-react-aws
echo "SUPPORT_RUNTIME_ARN=$SUPPORT_RUNTIME_ARN" >> .env.deploy
echo "AWS_REGION=us-east-1" >> .env.deploy
```

---

## 4) Smoke-test the Runtime

```bash
cd ../02.strands-agentcore-bedrock
agentcore invoke -a strands_support_copilot \
  '{"prompt":"Does Lauki support eSIM?","actor_id":"deployer","thread_id":"smoke-1"}'
```

You should get a product-support style answer. Then try a blocked topic (fraud /
fake KYC) and confirm the Guardrail intervenes.

---

## 5) Optional — run API + React locally

Use this to debug before paying for App Runner / CloudFront.

### 5a — API (port 8000)

```bash
cd 05.strands-support-react-aws

python3 -m venv .venv-api
source .venv-api/bin/activate
pip install -r api/requirements.txt

# Load YOUR runtime ARN (from step 3) — or: set -a && source .env.deploy && set +a
export SUPPORT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX"
export AWS_REGION=us-east-1
export AWS_PROFILE=<your-profile>   # MUST be the same account as the Runtime

# Confirm identity BEFORE starting uvicorn
aws sts get-caller-identity
# Account in the ARN must match SUPPORT_RUNTIME_ARN's account id

uvicorn api.main:app --reload --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}
```

Chat smoke:

```bash
curl -s -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What is an eSIM?","actor_id":"local-user"}'
```

### 5b — React (port 5173)

In a **second** terminal:

```bash
cd 05.strands-support-react-aws/web
npm install
npm run dev
```

Open http://127.0.0.1:5173  

Vite proxies `/api` → `http://127.0.0.1:8000` (see `web/vite.config.js`).  
Do **not** set `VITE_API_BASE` for local proxy mode.

### Common local failures

| Error | Cause | Fix |
|---|---|---|
| `Address already in use` on :8000 | Old uvicorn still running | `lsof -iTCP:8000 -sTCP:LISTEN` then `kill -9 <pid>` |
| `AccessDenied… no resource-based policy` | Credentials are a **different** AWS account than the Runtime | Use same-account profile, **or** attach Runtime + endpoint resource policies (see [Cross-account](#cross-account-invoke-advanced)) |
| `Unsupported payload type: StreamingBody` | Outdated `api/main.py` | Pull latest; decoder must `.read()` StreamingBody |
| Wrong user in error ARN | `AWS_PROFILE` unset; `[default]` is another account | Always `export AWS_PROFILE=...` and re-check `sts get-caller-identity` |

---

## 6) Production deploy with CDK (recommended)

This is the **production** path: one CloudFormation stack creates App Runner
(API image), a private S3 bucket (React), IAM roles, and a **single CloudFront
URL** that serves the UI and proxies `/api/*` + `/health` to App Runner.

```
https://dxxxx.cloudfront.net/          → React (S3)
https://dxxxx.cloudfront.net/api/chat  → FastAPI (App Runner)
https://dxxxx.cloudfront.net/health    → FastAPI health
```

Because CloudFront is same-origin, React builds with **`VITE_API_BASE=""`** —
no chicken-and-egg App Runner URL at build time.

### 6a — One-liner (after Runtime ARN exists)

```bash
cd 05.strands-support-react-aws

export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
# Important: env access keys override profiles — clear them if set
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# If you saved step 3:
#   set -a && source .env.deploy && set +a
export SUPPORT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX"

# Docker Desktop must be running
docker info >/dev/null

bash cdk/deploy.sh
```

What `cdk/deploy.sh` does for you:

1. Creates `cdk/.venv` and installs `aws-cdk-lib`
2. `cdk bootstrap` once for `aws://ACCOUNT/us-east-1` (CDK staging bucket/ECR/roles)
3. `cdk deploy` — builds API Docker image, bundles React, creates the stack

Equivalent explicit commands:

```bash
cd cdk
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
npx cdk@2 bootstrap "aws://${CDK_DEFAULT_ACCOUNT}/${CDK_DEFAULT_REGION}"
npx cdk@2 deploy -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" --require-approval never
```

First deploy usually takes **10–20 minutes**. When it finishes, CDK prints:

| Output | Meaning |
|---|---|
| **`CloudFrontUrl`** | ★ Open this in the browser (production UI) |
| `AppRunnerUrl` | Direct API (also via CloudFront `/api`) |
| `SupportRuntimeArn` | Echo of the ARN you passed |
| `UiBucketName` | Private S3 bucket for static assets |

Re-read outputs later **without** redeploying:

```bash
aws cloudformation describe-stacks \
  --stack-name LaukiSupportStack \
  --query "Stacks[0].Outputs" \
  --output table
```

Or save on next deploy:

```bash
cd cdk
npx cdk@2 deploy -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" \
  --outputs-file ../cdk-outputs.json --require-approval never
cat ../cdk-outputs.json
```

### 6b — What the CDK stack creates

| Resource | Construct / name |
|---|---|
| Docker image → ECR (CDK assets) | `ApiImage` from `../api` (`linux/amd64`) |
| App Runner service | `lauki-support-api-cdk` |
| Instance role | InvokeAgentRuntime on Runtime + `/runtime-endpoint/DEFAULT` |
| ECR access role | App Runner pull from asset repo |
| S3 bucket | Private + OAC (not a public website) |
| CloudFront | comment `lauki-support-ui-cdk` — UI + `/api/*` + `/health` |
| BucketDeployment | `npm ci && npm run build` in Node 20 container |

Stack code: [`cdk/lauki_support_stack.py`](cdk/lauki_support_stack.py).

### 6c — Update / destroy

```bash
# Ship a code change (api/ or web/)
bash cdk/deploy.sh

# Tear down hosting (does NOT delete AgentCore Runtime / Memory / Guardrail)
cd cdk
npx cdk@2 destroy -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" --force
```

### 6d — CDK troubleshooting

| Symptom | Fix |
|---|---|
| `Missing Runtime ARN` | Pass `-c supportRuntimeArn=...` or `export SUPPORT_RUNTIME_ARN=...` |
| `No module named aws_cdk` | From `cdk/`: `.venv/bin/pip install -r requirements.txt` (cdk.json uses `.venv/bin/python3`) |
| Docker daemon errors | Start Docker Desktop; re-run `docker info` |
| App Runner unhealthy | Wait 2–5 min after CREATE; `curl AppRunnerUrl/health` |
| Chat `AccessDenied` | Confirm Runtime ARN account == deploy account; stack already grants Runtime + endpoint |
| Bootstrap / CFN permission errors | Need broader IAM (or AdminAccess) for first bootstrap |
| Node “untested version” warning | Harmless; `deploy.sh` sets `JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1` |

---

## 7) Alternative — bash deploy (`scripts/deploy_aws.sh`)

Use this if you do not want CDK. It creates a **public S3 website** + separate
App Runner URL (React is built with `VITE_API_BASE=https://…apprunner.com`).

```bash
cd 05.strands-support-react-aws
export AWS_PROFILE=<your-profile> AWS_REGION=us-east-1
export SUPPORT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX"
bash scripts/deploy_aws.sh
cat deploy-urls.txt   # gitignored — your API_URL / UI_CLOUDFRONT / UI_S3_WEBSITE
```

| Resource | Name / pattern |
|---|---|
| ECR repository | `lauki-support-api` |
| App Runner service | `lauki-support-api` |
| App Runner instance role | `AppRunnerLaukiSupportInstanceRole` |
| App Runner ECR access role | `AppRunnerECRAccessRole` |
| S3 bucket | `lauki-support-react-ui-<ACCOUNT_ID>` (public website) |
| CloudFront comment | `lauki-support-ui` |

Optional: host only the React app on Amplify using `web/amplify.yml` and build env
`VITE_API_BASE=https://YOUR-APPRUNNER-HOST`.

---

## 8) Verify production

### After CDK

```bash
# Paste CloudFrontUrl from cdk deploy output (or describe-stacks)
CF_URL="https://dxxxx.cloudfront.net"

curl -s "$CF_URL/health"
# {"status":"ok"}

curl -s -X POST "$CF_URL/api/chat" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"How do I activate a SIM?","actor_id":"prod-user"}'

# macOS: open "$CF_URL"   |   Linux: xdg-open "$CF_URL"   |   or paste into a browser
```

Footer chip should say **`same-origin / local proxy`** (empty `VITE_API_BASE`).

### After bash deploy

```bash
source <(grep -E '^(API_URL|UI_)' deploy-urls.txt | sed 's/^/export /')
curl -s "$API_URL/health"
# Prefer UI_CLOUDFRONT (HTTPS). UI_S3_WEBSITE is HTTP-only and works immediately.
```

---

## Architecture details (why this shape)

1. **Browser never calls AgentCore directly** — `InvokeAgentRuntime` needs AWS
   credentials; putting keys in React would leak them.
2. **FastAPI is a thin proxy** — `api/main.py` builds the payload, calls
   `bedrock-agentcore.invoke_agent_runtime`, and decodes `StreamingBody`.
3. **CDK same-origin CloudFront** — UI and `/api` share one HTTPS host so
   `VITE_API_BASE` can be empty (recommended production shape).
4. **Bash deploy uses separate hosts** — React is built with
   `VITE_API_BASE=https://…apprunner.com` (fine for demos).
5. **App Runner Instance Role** replaces your laptop’s `AWS_PROFILE` in the cloud.

---

## Cross-account invoke (advanced)

Prefer **same-account** deploy (Runtime account == App Runner / laptop account).

If the caller is in account **B** and the Runtime is in account **A**, account
**A** must attach a **resource-based policy** on **both**:

- `arn:aws:bedrock-agentcore:REGION:A:runtime/NAME`
- `arn:aws:bedrock-agentcore:REGION:A:runtime/NAME/runtime-endpoint/DEFAULT`

```bash
RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_A:runtime/strands_support_copilot-XXXX"
ENDPOINT_ARN="${RUNTIME_ARN}/runtime-endpoint/DEFAULT"
CALLER_PRINCIPAL="arn:aws:iam::ACCOUNT_B:user/YOUR_USER"   # or role ARN / account root

for ARN in "$RUNTIME_ARN" "$ENDPOINT_ARN"; do
  aws bedrock-agentcore-control put-resource-policy \
    --resource-arn "$ARN" \
    --region us-east-1 \
    --policy "{
      \"Version\":\"2012-10-17\",
      \"Statement\":[{
        \"Sid\":\"AllowCrossAccountInvoke\",
        \"Effect\":\"Allow\",
        \"Principal\":{\"AWS\":[\"${CALLER_PRINCIPAL}\"]},
        \"Action\":[
          \"bedrock-agentcore:InvokeAgentRuntime\",
          \"bedrock-agentcore:InvokeAgentRuntimeForUser\"
        ],
        \"Resource\":\"${ARN}\"
      }]
    }"
done
```

Account **B** still needs an **identity** policy allowing the same actions on
those ARNs. `PutResourcePolicy` requires `Resource` to equal `--resource-arn`
exactly (no multi-ARN arrays in one call).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `deploy_aws.sh` / CDK: `Set SUPPORT_RUNTIME_ARN` | Export ARN from lab 02 `.bedrock_agentcore.yaml` |
| App Runner `CREATE_FAILED` | App Runner console events; image must be `linux/amd64` |
| App Runner healthy but chat `AccessDenied` | Wrong account credentials **or** missing endpoint ARN on role |
| CORS errors (bash deploy, separate hosts) | Set `CORS_ORIGINS` on App Runner to your UI origin (or `*`) |
| Bash UI calls wrong host / localhost | Rebuild with `VITE_API_BASE=https://YOUR-APPRUNNER` (CDK path should not need this) |
| CloudFront 403 / old UI | Wait for Deployed; invalidate `/*` after S3 sync |
| Guardrail not applied | Redeploy Runtime with Guardrail envs; re-run `grant_runtime_memory_permissions.py` |
| Bedrock model Error 002 | Keep `USE_BEDROCK=false` + `OPENAI_API_KEY` on Runtime deploy |
| Gateway 401 from Runtime | Re-mint `GATEWAY_TOKEN` and **redeploy** Runtime (token is env-baked) |
| Docker build fails on Apple Silicon | Use `--platform linux/amd64` (CDK + bash scripts already do) |

---

## 9) Cleanup — stop charges

### Prefer CDK destroy (if you used CDK)

```bash
cd 05.strands-support-react-aws/cdk
export SUPPORT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/..."
npx cdk@2 destroy -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" --force
```

### Bash-deploy resources

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

ARN=$(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='lauki-support-api'].ServiceArn" --output text)
[ -n "$ARN" ] && [ "$ARN" != "None" ] && aws apprunner delete-service --service-arn "$ARN"

aws ecr delete-repository --repository-name lauki-support-api --force 2>/dev/null || true

BUCKET=lauki-support-react-ui-$ACCOUNT
aws s3 rm "s3://$BUCKET" --recursive 2>/dev/null || true
aws s3 rb "s3://$BUCKET" 2>/dev/null || true

aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='lauki-support-ui'].[Id,DomainName,Status]" \
  --output table
# Disable + delete the distribution in console (CloudFront deletes are multi-step)
```

### Always (lab 02 leftovers — not removed by CDK destroy)

Delete when the class is over: AgentCore **Runtime**, **Memory**, **Gateway**,
**Identity** provider, **Guardrail**, Cognito app client — from the AWS console
or lab 02 / `agentcore` tooling. Leaving App Runner + Runtime running is what
usually burns classroom credits.

---

## Why OpenAI + ApplyGuardrail?

Many classroom accounts return:

`Error 002: Access to Bedrock models is not allowed`

So the Runtime uses **OpenAI** for generation and still enforces safety with
`bedrock:ApplyGuardrail` on input/output. If Bedrock model access is enabled in
your account, you can redeploy with `USE_BEDROCK=true` and a Nova/Claude model id
(see lab 02 agent code).

---

## Where your URLs live (after a successful deploy)

| Deploy path | Where to find URLs |
|---|---|
| **CDK (recommended)** | Terminal outputs `CloudFrontUrl` / `AppRunnerUrl`, or `aws cloudformation describe-stacks --stack-name LaukiSupportStack` |
| **Bash** | `deploy-urls.txt` in this folder (gitignored) |

Do **not** use another student’s CloudFront or Runtime ARN — they are account-scoped.
