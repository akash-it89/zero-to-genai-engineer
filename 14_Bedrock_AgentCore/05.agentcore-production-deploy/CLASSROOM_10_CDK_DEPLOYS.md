# 10 CDK deploy stages — grow the stack step by step

This guide walks you through **10 CloudFormation updates** using the single
[`cdk/`](./cdk/) app and stage flags (`-c stage=N`).

Each stage ends with something you can **see or curl** so you know the new
layer works before you add the next one.

> Prefer learning from **full code folders** instead? Use
> [`06.progressive-deploy/`](../06.progressive-deploy/) — each folder is a complete snapshot
> of the app at that moment (recommended for most students).

---

## Before you start

```bash
cd 05.agentcore-production-deploy

export AWS_PROFILE=<your-profile>   # YOUR AWS account
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1

aws sts get-caller-identity         # confirm Account id
docker info >/dev/null              # Docker must be running (stages 7+)
```

**Prerequisite for stage 10 only:** you already deployed the AgentCore Runtime
from lab 02 and have **your** `SUPPORT_RUNTIME_ARN`.

Demo Cognito user (created at stage 4): **`demo` / `DemoUser1!`**

---

## How to deploy a stage

```bash
bash cdk/deploy.sh N     # N = 1 .. 10
```

Or from `cdk/`:

```bash
cd cdk && source .venv/bin/activate
npx cdk deploy -c stage=N --require-approval never
```

Stage **10** also needs:

```bash
export SUPPORT_RUNTIME_ARN='arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX'
bash cdk/deploy.sh 10
```

Read outputs anytime:

```bash
aws cloudformation describe-stacks \
  --stack-name LaukiSupportStack \
  --query "Stacks[0].Outputs" \
  --output table
```

---

## Stage 1 — Prove CDK works

**Goal:** Create the smallest CloudFormation stack so you see CDK → CloudFormation is real.

```bash
bash cdk/deploy.sh 1
```

**Verify:** Outputs include `DeployStage = 1` (or `DeployStep`) and a stage hint.  
Console → **CloudFormation** → `LaukiSupportStack` exists.

**Still missing:** Identity, UI, API, chat.

---

## Stage 2 — Cognito User Pool

**Goal:** Add an identity store for usernames and passwords (before any chat API).

```bash
bash cdk/deploy.sh 2
```

**Verify:** Output `UserPoolId`.  
Console → **Cognito → User pools** → open the new pool.

**Still missing:** An app client the React SPA can call.

---

## Stage 3 — SPA App Client

**Goal:** Register a public Cognito app client (no client secret) for username/password login.

```bash
bash cdk/deploy.sh 3
```

**Verify:** Output `UserPoolClientId`.  
Pool → **App integration → App clients** → `lauki-support-spa`.

**Still missing:** A user account to sign in with.

---

## Stage 4 — Demo user

**Goal:** Create the shared class login `demo` / `DemoUser1!`.

```bash
bash cdk/deploy.sh 4
```

**Verify:** Outputs `DemoUsername` / `DemoPassword`.  
Cognito → **Users** → `demo` (Confirmed).

**Still missing:** A place to host the website files.

---

## Stage 5 — Private S3 for the UI

**Goal:** Create a **private** S3 bucket for React assets (not public-read).

```bash
bash cdk/deploy.sh 5
```

**Verify:** Output `UiBucketName`.  
S3 console → bucket exists → **Block Public Access** is ON.

**Still missing:** A public HTTPS URL in front of the bucket.

---

## Stage 6 — CloudFront + placeholder page

**Goal:** Get a real HTTPS URL. No React yet — just proof the CDN works.

```bash
bash cdk/deploy.sh 6
```

**Verify:** Open `CloudFrontUrl` in the browser → placeholder “Stage 6” page.

**Still missing:** React login UI wired to Cognito.

---

## Stage 7 — React login UI (chat locked)

**Goal:** Sign in with Cognito from the browser. Chat stays off until stage 10.

```bash
bash cdk/deploy.sh 7
```

**Verify:**
1. Open the same `CloudFrontUrl` → login form  
2. Sign in as `demo` / `DemoUser1!`  
3. Welcome message appears; composer shows **chat off**  
4. Open `/config.json` → `chatEnabled: false`, `stage: 7`

**Still missing:** A backend API.

---

## Stage 8 — FastAPI on App Runner (`/health`)

**Goal:** Deploy the API container. Auth is still off so `/health` is easy to curl.

```bash
bash cdk/deploy.sh 8
```

**Verify:**

```bash
AR=$(aws cloudformation describe-stacks --stack-name LaukiSupportStack \
  --query "Stacks[0].Outputs[?OutputKey=='AppRunnerUrl'].OutputValue" --output text)
CF=$(aws cloudformation describe-stacks --stack-name LaukiSupportStack \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" --output text)

curl -sS "$AR/health"; echo
curl -sS "$CF/health"; echo
```

Login still works; chat is still locked.

**Still missing:** JWT protection on API routes.

---

## Stage 9 — Lock the API with Cognito JWT

**Goal:** `/api/me` requires a Bearer ID token. Unauthenticated calls fail with **401**.

```bash
bash cdk/deploy.sh 9
```

**Verify:**

```bash
CF=$(aws cloudformation describe-stacks --stack-name LaukiSupportStack \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" --output text)

curl -sS -o /dev/null -w "%{http_code}\n" "$CF/api/me"   # expect 401

# After browser login, copy ID token from DevTools → Application → sessionStorage → lauki_id_token
# curl -sS -H "Authorization: Bearer $ID_TOKEN" "$CF/api/me"
```

`/health` can stay public; `/api/me` is protected.

**Still missing:** AgentCore chat (`/api/chat`).

---

## Stage 10 — AgentCore chat (full demo)

**Goal:** Wire your Runtime ARN + IAM. React turns `chatEnabled` on. Ask a real support question.

```bash
export SUPPORT_RUNTIME_ARN='arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX'
bash cdk/deploy.sh 10
```

**Verify:**
1. Open `CloudFrontUrl` → sign in  
2. Chips show `stage 10`, `chat on`  
3. Ask: *How do I activate a new SIM?* → grounded answer  

Architecture diagrams (optional):  
[`06.progressive-deploy/10_agentcore_chat/architecture/`](../06.progressive-deploy/10_agentcore_chat/architecture/)

---

## Stage map (quick reference)

| Stage | What appears | How you prove it |
|------:|--------------|------------------|
| 1 | SSM stage marker | Stack outputs |
| 2 | Cognito User Pool | `UserPoolId` |
| 3 | SPA app client | `UserPoolClientId` |
| 4 | Demo user | Cognito user `demo` |
| 5 | Private S3 UI bucket | `UiBucketName` |
| 6 | CloudFront + placeholder | Open HTTPS URL |
| 7 | React login (`chat` off) | Sign in; composer locked |
| 8 | App Runner `/health` | `curl …/health` |
| 9 | Cognito JWT on API | `/api/me` → 401 without token |
| 10 | AgentCore chat | Ask about SIM / eSIM |

Docker is required from stage **7** (React build) and **8** (API image).

---

## Suggested pace

| Stages | Rough time | What you should remember |
|------:|------------|--------------------------|
| 1–4 | ~15–20 min | Cognito exists before UI |
| 5–7 | ~20–25 min | HTTPS UI + login, no bot |
| 8–9 | ~20–25 min | API health → JWT lock |
| 10 | ~15–20 min | Full AgentCore chat |

---

## If you already have a full stack

Jumping from an old full deploy to `stage=1` may try to **delete** Cognito/API/UI. Prefer either:

1. **Destroy once**, then walk 1→10 cleanly:  
   `cd cdk && npx cdk destroy …`, then `bash cdk/deploy.sh 1` …
2. Or start at the stage that matches what is already live (compatible construct IDs).

For a **fresh account**, always start at stage 1.

---

## One-liner (optional)

```bash
for n in 1 2 3 4 5 6 7 8 9; do bash cdk/deploy.sh $n; done
SUPPORT_RUNTIME_ARN=arn:... bash cdk/deploy.sh 10
```

Between deploys, open the **CloudFront URL** (from stage 6) or curl **health** (from stage 8) so you see the system grow.
