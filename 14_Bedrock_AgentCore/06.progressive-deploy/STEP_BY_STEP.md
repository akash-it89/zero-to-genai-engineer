# Progressive Deploy — detailed learning guide (01 → 10)

**Who this is for:** you (the student).  
**Pattern:** one CloudFormation stack, updated 10 times. Folders grow code; AWS grows resources.

**Architecture to keep in mind:**

```
Browser (React)
    │  Cognito login → ID token (JWT)
    ▼
CloudFront (HTTPS)
    ├── static UI from private S3
    └── /api/*, /health → App Runner (FastAPI)
              │  IAM
              ▼
         AgentCore Runtime (Strands support agent)
```

**One sentence for the whole lab:**

> The browser never holds AWS keys. Cognito proves *who you are*. FastAPI uses *IAM* to call AgentCore. CDK is how we build that path in AWS, one layer at a time.

---

## How to use this guide

For every step:

1. Open folder `0N_...` and `0N+1_...` side-by-side  
2. Read **Purpose** (why this layer exists)  
3. Check **What AWS creates** (console or stack outputs)  
4. Deploy → prove it with the **Verify** checklist  
5. Read **What's still MISSING?** (sets up the next folder)

```bash
export STACK_NAME=LaukiSupportClassA   # or your class name
# … then bash deploy.sh inside each folder
```

---

# STEP 01 — `01_empty_cdk`

### Purpose (why)

Students often think “CDK = magic deploy of the whole app.”  
We start with the **smallest possible stack** so they see: CDK only creates CloudFormation. Nothing else exists yet.

### What it does (technically)

| Piece | Role |
|--------|------|
| `cdk/app.py` | Entry point: creates a CDK `App` and one `Stack` |
| `cdk/stack.py` | Defines resources as Python objects |
| SSM Parameter `/lauki-support/<stack>/deploy-stage = 1` | Dummy resource (CloudFormation rejects a truly empty stack) |
| Outputs `DeployStep`, `StepHint`, `StackName` | Visible proof in the console |

**Analogy:** Pouring a concrete foundation with a date stamp on it — no walls yet, but the building site exists.

### What AWS creates

- 1 CloudFormation stack (`STACK_NAME`)
- 1 SSM String Parameter
- Stack outputs

### Verify

```bash
cd 06.progressive-deploy/01_empty_cdk && bash deploy.sh
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs' --output table
aws ssm get-parameter --name "/lauki-support/$(echo $STACK_NAME | tr '[:upper:]' '[:lower:]' | tr '_' '-' | cut -c1-24)/deploy-stage"
```

Console: **CloudFormation → Stacks → your stack → Resources** (almost empty).

### Key idea

> “CDK is not the app. CDK is a compiler that turns Python into CloudFormation. Until we add Cognito, S3, and API code, there is nothing for users to click.”

### What's MISSING?

Identity. We cannot log anyone in.

---

# STEP 02 — `02_cognito_pool`

### Purpose (why)

Before chat, hosting, or APIs — we need a place that stores **usernames and passwords**.  
That place is **Amazon Cognito User Pool**.

### What it does (technically)

Adds `cognito.UserPool`:

| Setting | Meaning |
|---------|----------------------|
| `self_sign_up_enabled=False` | Users are created by the stack (demo account), not public signup |
| `sign_in_aliases` username + email | Users can sign in with either |
| Password policy (upper/lower/digit/symbol) | Matches our demo password `DemoUser1!` |
| `removal_policy=DESTROY` | Safe for lab teardown |

**Analogy:** Opening a membership desk at a gym — the desk exists, but no membership cards and no front door yet.

### What AWS creates

- Cognito User Pool (`lauki-users-<stack>`)
- Output `UserPoolId` (looks like `us-east-1_xxxxx`)

### Verify

Console → **Cognito → User pools** → open the new pool → Users tab is empty.

### Key idea

> “A User Pool is your identity database. Passwords are hashed by Cognito. Our React app will never store passwords in S3 or in the API.”

### What's MISSING?

An **app client**. Browsers need a client ID to talk to Cognito. Also: no users yet.

---

# STEP 03 — `03_cognito_client`

### Purpose (why)

Cognito won’t accept login from a random website. You register an **App Client** that represents the React SPA.

### What it does (technically)

`user_pool.add_client("SpaClient", ...)`:

| Setting | Why it matters |
|---------|----------------|
| `generate_secret=False` | Public SPA — secrets in browsers would leak |
| `user_password=True` | Allows `USER_PASSWORD_AUTH` (username + password → tokens) |
| `user_srp=True` | Also allows SRP (more secure; our demo uses password auth for simplicity) |
| `prevent_user_existence_errors=True` | Don’t reveal whether a username exists |

**Tokens you’ll mention later:**

- **ID token** — who the user is (JWT) → we send this to FastAPI  
- **Access token** — used for Cognito APIs / OAuth scopes  
- **Refresh token** — get new tokens without re-typing password  

**Analogy:** Printing membership cards for the gym app — the desk (pool) already existed; now the app has a registered card design (client ID).

### What AWS creates

- App client on the pool  
- Output `UserPoolClientId`

### Verify

Pool → **App integration → App clients** → `lauki-support-spa`.

### Key idea

> “Client ID is public — like a shop’s door number. It is not a password. The password still belongs only to the user and Cognito.”

### What's MISSING?

An actual user to log in as.

---

# STEP 04 — `04_demo_user`

### Purpose (why)

You need a **shared login** for the lab that always works: `demo` / `DemoUser1!`.  
We create that user with CDK custom resources (Lambda-backed AWS API calls).

### What it does (technically)

Two `AwsCustomResource`s:

1. **`adminCreateUser`** — creates `demo`, suppresses welcome email  
2. **`adminSetUserPassword`** — sets permanent password (skips “force change on first login”)

Outputs: `DemoUsername`, `DemoPassword`.

**Analogy:** Creating one sample member account so everyone in the lab can practice the same login.

### What AWS creates

- Cognito user `demo` (Confirmed)  
- Still **no website**

### Verify

Cognito → Users → `demo` → status Confirmed.

Optional:

```bash
aws cognito-idp admin-get-user --user-pool-id <UserPoolId> --username demo
```

### Key idea

> “In production you would not print passwords in CloudFormation outputs. For this lab, we trade production-hardening for a reliable live demo.”

### What's MISSING?

A place to host the UI files (HTML/JS/CSS).

---

# STEP 05 — `05_s3_ui_bucket`

### Purpose (why)

Static websites need object storage. We use **private S3** — not a public website bucket — because later CloudFront will be the only public door.

### What it does (technically)

`s3.Bucket` with:

| Setting | Meaning |
|---------|---------|
| `BLOCK_ALL` public access | Nobody browses the bucket URL directly |
| `S3_MANAGED` encryption | Data encrypted at rest |
| `enforce_ssl=True` | HTTPS only for S3 API access |
| `auto_delete_objects` + `DESTROY` | Easy lab cleanup |

**Analogy:** A locked warehouse for website files. Customers don’t walk into the warehouse — they use the front door (CloudFront) next.

### What AWS creates

- Private S3 bucket  
- Output `UiBucketName`

### Verify

S3 console → bucket exists → empty (or nearly). Permissions: Block Public Access ON.

### Key idea

> “If the bucket is public, anyone can scrape your JS and configs. Private bucket + CloudFront Origin Access Control is the modern pattern.”

### What's MISSING?

HTTPS CDN in front of the bucket. You still have no URL to open.

---

# STEP 06 — `06_cloudfront`

### Purpose (why)

Users need a **global HTTPS URL**. CloudFront is the CDN that:

1. Serves files from private S3 (via OAC)  
2. Later (step 08+) also routes `/api/*` to App Runner  

### What it does (technically)

| Piece | Role |
|--------|------|
| `S3OriginAccessControl` (OAC) | CloudFront signs requests to private S3 |
| `Distribution` default behavior | Serve `index.html` from S3 |
| Error 403/404 → `/index.html` | SPA-friendly (React Router later) |
| `BucketDeployment` placeholder HTML | Proves CDN works **before** React |

**Analogy:** Opening the mall front door with a temporary “Under Construction” poster. The warehouse is still locked; only the door (CloudFront) is public.

### What AWS creates

- CloudFront distribution  
- Placeholder `index.html` in S3  
- Output `CloudFrontUrl` (`https://dxxxx.cloudfront.net`)

### Verify

Open `CloudFrontUrl` in the browser → “Classroom Step 06” page.

```bash
curl -fsS "$CF/"
```

### Key idea

> “From this moment AWS feels real — a public URL. You still have no login UI and no backend.”

### What's MISSING?

React login UI wired to Cognito.

---

# STEP 07 — `07_react_login`

### Purpose (why)

Prove **browser authentication** end-to-end **without** the bot yet.  
If login is broken, chat will look “broken” for the wrong reason. We isolate identity first.

### What it does (technically)

**New folder content:** `web/` (React + Vite)

| File | Role |
|------|------|
| `auth.js` | Cognito `USER_PASSWORD_AUTH` via `amazon-cognito-identity-js` |
| `App.jsx` | Login form; after login shows welcome; **composer locked** if `chatEnabled=false` |
| `config.json` (deployed to S3) | Runtime config: `userPoolId`, `clientId`, `chatEnabled: false` |

**CDK adds:**

- Docker-bundled `npm ci && npm run build`  
- Upload `dist/` + `config.json` to S3  
- Invalidate CloudFront  

**Flow:**

```
User types demo / DemoUser1!
  → Cognito returns ID token
  → stored in sessionStorage
  → UI shows “welcome” but chat stays off
```

**Analogy:** Security desk checks your ID and says “You’re in the building, but the support bot room opens later.”

### What AWS creates / updates

- Same CloudFront URL now serves React  
- `config.json` with Cognito IDs  

### Verify

1. Open CloudFront URL → login form  
2. Sign in as `demo` / `DemoUser1!`  
3. Show chip **chat off** / locked composer  
4. Open `/config.json` → `chatEnabled: false`

### Key idea

> “Notice: still no AWS keys in the browser. Cognito gave us a JWT. The API does not exist yet, so we refuse to pretend chat works.”

### What's MISSING?

A backend that can answer `/health` and later `/api/chat`.

---

# STEP 08 — `08_apprunner_health`

### Purpose (why)

Introduce the **API layer** as a tiny FastAPI service.  
First prove the container is alive (`/health`) with auth **disabled** — easier to debug.

### What it does (technically)

**New folder content:** `api/`

| Piece | Role |
|--------|------|
| `main.py` | Only `GET /health` → `{"status":"ok","auth":"disabled"}` |
| `Dockerfile` | Container image for App Runner |
| CDK `DockerImageAsset` | Builds image, pushes to ECR |
| `CfnService` App Runner | Runs container on AWS (no EC2 management) |
| CloudFront behaviors `/health`, `/api/*` | Same-origin path from the UI domain to the API |

**Env on App Runner:** `AUTH_DISABLED=true`

**Analogy:** Opening a clinic reception phone line that only says “We’re open” — no patient records yet.

### Architecture now

```
Browser → CloudFront → S3 (React)
                    └→ App Runner /health
```

### Verify

```bash
AR=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='AppRunnerUrl'].OutputValue" --output text)
CF=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" --output text)
curl -fsS "$AR/health"; echo
curl -fsS "$CF/health"; echo
```

Both should return ok. UI login still works; chat still locked.

### Key idea

> “App Runner is ‘managed containers.’ We give Docker; AWS runs it. CloudFront can front both static files and API paths so the browser stays on one origin.”

### What's MISSING?

Protecting API routes with the Cognito JWT from step 07.

---

# STEP 09 — `09_jwt_lock`

### Purpose (why)

Anyone who guesses the App Runner URL could call the API.  
We lock sensitive routes: **no valid Cognito ID token → 401**.

### What it does (technically)

**API grows:**

| Piece | Role |
|--------|------|
| `HTTPBearer` | Read `Authorization: Bearer <token>` |
| `PyJWKClient` | Download Cognito JWKS (public keys) |
| `jwt.decode` | Verify signature, issuer, expiry |
| Audience check | ID token `aud` must match app client ID |
| `GET /api/me` | Returns username from token claims |

**App Runner env now:**

- `COGNITO_USER_POOL_ID`  
- `COGNITO_CLIENT_ID`  
- `AUTH_DISABLED=false`  

**Analogy:** Reception still says “We’re open” (`/health`), but the records room (`/api/me`) checks your membership badge (JWT).

### Flow to draw

```
React login → ID token
     │
     ▼
GET /api/me
Authorization: Bearer eyJhbGciOi...
     │
     ▼
FastAPI verifies JWT with Cognito public keys
     │
     ├─ invalid/missing → 401
     └─ valid → {"username":"demo", ...}
```

### Verify

```bash
curl -sS -o /dev/null -w "%{http_code}\n" "$CF/api/me"   # 401

# Get token (or copy from browser sessionStorage lauki_id_token)
TOKEN=$(aws cognito-idp initiate-auth --client-id <ClientId> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=demo,PASSWORD='DemoUser1!' \
  --query 'AuthenticationResult.IdToken' --output text)
curl -fsS -H "Authorization: Bearer $TOKEN" "$CF/api/me"; echo
```

Health may show `"auth":"cognito"`.

### Key idea

> “JWT verification uses Cognito’s public keys — the API does not need the user’s password. That’s the whole point of tokens.”

### What's MISSING?

Calling AgentCore to answer real support questions (`/api/chat`).

---

# STEP 10 — `10_agentcore_chat`

### Purpose (why)

Connect the authenticated API to the **already-built Strands AgentCore Runtime** (from earlier labs).  
Turn on the React chat composer.

### What it does (technically)

**API (full):**

| Piece | Role |
|--------|------|
| `POST /api/chat` | Requires JWT (same `require_user`) |
| `boto3` `bedrock-agentcore` | `invoke_agent_runtime` |
| Payload | `{prompt, actor_id, thread_id}` |
| Response | Agent text → `{result, ...}` |

**IAM on App Runner instance role:**

- `bedrock-agentcore:InvokeAgentRuntime`  
- on Runtime ARN **and** `.../runtime-endpoint/DEFAULT`

**Env:** `SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...`

**React / config:**

- `chatEnabled: true`  
- Composer unlocked  
- Sends `Authorization: Bearer <id_token>` with each chat request  

**Analogy:** The membership badge opens the records room **and** the specialist doctor (AgentCore) finally picks up the phone.

### End-to-end path (follow this path)

```
1. User logs in (Cognito) → ID token
2. User asks “How do I activate a new SIM?”
3. React POST /api/chat + Bearer token
4. FastAPI verifies JWT
5. FastAPI calls AgentCore with IAM (no keys in browser)
6. Strands agent uses Memory / Gateway / Guardrails (lab 02)
7. Answer returns to UI
```

### Verify

1. Open CloudFront URL  
2. Login `demo` / `DemoUser1!`  
3. Confirm `chat on`  
4. Ask: *How do I activate a new SIM?*  
5. Show grounded support answer  

Optional API proof:

```bash
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"How do I activate a new SIM?","actor_id":"demo","thread_id":"class-demo-thread-001234567890"}' \
  "$CF/api/chat"
```

### Key idea

> “This is production-shaped GenAI: identity at the edge, thin API with IAM, agent runtime in the middle, UI with no secrets. CDK made each layer visible so you can learn each layer — not because production always needs 10 deploys.”

### What's MISSING? (tease next modules)

Observability, stronger auth (Hosted UI / OAuth), custom domains, CI/CD, evals — later in the curriculum.

---

## Quick delta table

| Step | New capability | How you prove it |
|-----:|----------------|------------------------|
| 01 | CDK/CloudFormation works | Stack + SSM |
| 02 | Identity store | Cognito pool |
| 03 | SPA can request tokens | App client ID |
| 04 | Shared login | User `demo` |
| 05 | Private UI storage | S3 bucket |
| 06 | Public HTTPS | Placeholder page |
| 07 | Browser login | React sign-in, chat locked |
| 08 | Backend alive | `/health` 200 |
| 09 | API auth | `/api/me` 401 → 200 |
| 10 | Full agent chat | SIM question answered |

---

## FAQ

**Q: Why not put AWS keys in React?**  
A: Anyone can view page source. Keys would be stolen in minutes.

**Q: Why FastAPI in the middle?**  
A: Browsers can’t use IAM the way servers can. The API holds the IAM role; the browser only holds a Cognito JWT.

**Q: Why 10 deploys instead of one?**  
A: Learning. At work you’d often ship one stack; here each deploy is a checkpoint so you understand the stack.

**Q: Is Gateway Cognito the same as this Cognito?**  
A: No. Lab 02 Gateway Cognito is **M2M** for tools. This pool is **human login** for the website.

**Q: What is AgentCore Runtime?**  
A: Managed host for your Strands agent — invoke it with an ARN, like calling a serverless agent endpoint.

---

## Best files to open at each step

| Step | File to study |
|-----:|---------------|
| 01 | `cdk/stack.py` (SSM only) |
| 02 | `cdk/stack.py` (`UserPool`) |
| 03 | `cdk/stack.py` (`SpaClient`) |
| 04 | `cdk/stack.py` (custom resources) |
| 05 | `cdk/stack.py` (`UiBucket`) |
| 06 | `cdk/stack.py` (CloudFront + placeholder) |
| 07 | `web/src/App.jsx` + `web/src/auth.js` |
| 08 | `api/main.py` (health only) |
| 09 | `api/main.py` (`require_user`, `/api/me`) |
| 10 | `api/main.py` (`/api/chat`) + IAM in `stack.py` |

Deploy commands: [`DEPLOY_YOUR_OWN_STACK.md`](./DEPLOY_YOUR_OWN_STACK.md)  
Folder overview: [`README.md`](./README.md)
