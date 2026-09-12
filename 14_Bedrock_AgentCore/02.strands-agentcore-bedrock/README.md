# Bedrock AgentCore — Strands Support Copilot (from scratch)

Parent index: [`14_Bedrock_AgentCore/README.md`](../README.md).

**Use case:** Lauki Support Copilot — one Strands agent with FAQ tools, then
Memory → Gateway → Identity → flagship + Streamlit.

This lab is **self-contained**. Start with an empty AgentCore console. Create
**your own** Memory, Gateway, and Identity. Do **not** paste a classmate’s ids.

Harness (Code Interpreter / Browser) is **not** in this lab — that stays in
[`01.langraph-agentcore-bedrock`](../01.langraph-agentcore-bedrock/).
Sibling: [`03.crewai-agentcore-bedrock`](../03.crewai-agentcore-bedrock/).

---

## What you will build (order matters)

| Step | What you create | Where |
|---|---|---|
| 0 | Local Python env + `.env` | This folder |
| 1 | AgentCore **Memory** | AWS Console → `us-east-1` |
| 2 | Cognito M2M + **Gateway** (+ Lambda tools) | Script → `us-west-2` |
| 3 | AgentCore **Identity** OAuth provider | AWS Console → `us-east-1` |
| 4 | Demo 1 Runtime agent | `agentcore deploy` → `us-east-1` |
| 5 | Demo 2 Memory agent + IAM grant | `us-east-1` |
| 6 | Demo 3 Gateway agent | `us-east-1` Runtime calling west-2 Gateway |
| 7 | Demo 4 Identity agent | `us-east-1` |
| 8 | Demo 5 Flagship + Streamlit | `us-east-1` |

Stop after any demo if you only need that concept. Demos 2–5 need Step 1.
Demos 3–5 need Step 2. Demos 4–5 need Step 3.

---

## Regions (read once — do not “simplify”)

| Resource | Region | Why |
|---|---|---|
| Memory (`MEMORY_ID`) | **`us-east-1`** | Memory ids are region-scoped |
| All Runtime agents | **`us-east-1`** | Must match Memory |
| Gateway + Cognito | **`us-west-2`** | Created here by the script |
| Identity provider | **`us-east-1`** | Looked up by east-1 Runtimes |

Always pass `--env AWS_REGION=us-east-1` on **deploy**. If you omit it, Memory
clients may default to west-2 and fail against your east-1 Memory id.

---

## Step 0 — Laptop setup

You need:

- AWS account access to **Bedrock AgentCore** (Memory, Runtime, Gateway, Identity)
- An **OpenAI API key** (this lab uses OpenAI on Runtime, not Bedrock model access)
- Python **3.11–3.13** (3.14 is not supported)

```bash
cd 02.strands-agentcore-bedrock

uv sync --python 3.11
cp .env.example .env
```

Edit `.env` and set **only** this for now:

```bash
OPENAI_API_KEY=sk-...
AWS_REGION=us-east-1
# MEMORY_ID=   ← leave empty until Step 1
```

```bash
source .venv/bin/activate
export AWS_PROFILE=<your-profile>   # or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
alias agentcore='.venv/bin/agentcore'
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
set -a && source .env && set +a

aws sts get-caller-identity
test ${#OPENAI_API_KEY} -gt 20 && echo "OPENAI OK"
```

### Deploy rules (every agent in this lab)

- Prefer **`agentcore deploy`** (old name was `launch`).
- Runtime **ignores** your local `.env`. Pass every secret with `--env` at deploy.
- Use **`--disable-memory`** on configure so the toolkit does not create a second,
  unused STM Memory. You will use the Memory id you create in Step 1.
- Packaging default is **`direct_code_deploy`** (no Docker required).

---

## Step 1 — Create AgentCore Memory (your id)

Nothing is pre-created for you. Create Memory yourself:

1. Open AWS Console → switch region to **`us-east-1`**
2. Go to **Amazon Bedrock → AgentCore → Memory → Create**
3. Create a Memory (any clear name, e.g. `strands-support-memory`)
4. Copy the **Memory ID** from the console

Put it in `.env`:

```bash
MEMORY_ID=<paste-your-memory-id-here>
```

Reload:

```bash
set -a && source .env && set +a
test ${#MEMORY_ID} -ge 12 && echo "MEMORY_ID OK: $MEMORY_ID"
```

You need this for Demos 2–5.

---

## Step 2 — Create Gateway + Cognito (script in this folder)

Creates Cognito M2M client + AgentCore Gateway + optional Lambda tools
(`get_weather`, `get_time`), and writes **`gateway-credentials.json`** in **this**
folder (gitignored — never commit it).

```bash
# Gateway lives in us-west-2 (Runtime stays us-east-1)
export AWS_REGION=us-west-2

.venv/bin/python scripts/create_mcp_gateway.py \
  --name lauki-demo-gateway \
  --region us-west-2 \
  --with-lambda-target
```

Confirm the file exists:

```bash
test -f gateway-credentials.json && echo "gateway-credentials.json OK"
```

Mint a token and load URL (do this again whenever tokens expire — ~1 hour):

```bash
export AWS_REGION=us-east-1   # back to Runtime region for the rest of the lab

export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"
echo "GATEWAY_URL=$GATEWAY_URL"
test -n "$GATEWAY_TOKEN" && echo "GATEWAY_TOKEN OK"
```

Optional smoke test (expect tools including `get_weather` / `get_time`):

```bash
.venv/bin/python - <<'PY'
import httpx, json, subprocess
creds = json.load(open("gateway-credentials.json"))
url = creds["gateway"]["gatewayUrl"]
token = subprocess.check_output([".venv/bin/python", "scripts/get_gateway_token.py"], text=True).strip()
r = httpx.post(
    url,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    },
    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    timeout=60,
)
print(r.status_code, r.text[:800])
PY
```

You need Step 2 for Demos 3–5.

---

## Step 3 — Create Identity provider (Console)

Needed for Demos 4–5. Identity asks Cognito for a Gateway JWT at runtime
(instead of only baking `GATEWAY_TOKEN`).

Print the values you will paste into the console:

```bash
.venv/bin/python - <<'PY'
import json
c = json.load(open("gateway-credentials.json"))["cognito"]
print("token_endpoint:", c["token_endpoint"])
print("client_id:     ", c["client_id"])
print("client_secret: ", c["client_secret"])
print("scope:         ", c["scope"])
print("discovery_url: ", c.get("discovery_url", ""))
PY
```

Then in AWS Console (**region `us-east-1`**):

1. **Amazon Bedrock → AgentCore → Identity → OAuth2 credential providers**
2. Create a **Custom OAuth2** provider (client credentials / M2M)
3. Name it exactly: **`gateway-cognito-m2m`**
4. Use the `token_endpoint`, `client_id`, `client_secret`, and `scope` printed above
5. Scopes must include: **`lauki-demo-gateway/invoke`** (or whatever `scope` your
   credentials file shows if you used a different `--name`)

If Identity fails later, demos still accept a `GATEWAY_TOKEN` fallback (re-mint + redeploy).

---

## Demo map

| # | File | Agent name (`-n` / `-a`) | Needs |
|---|---|---|---|
| 1 | `strands_agent.py` | `strands_agent` | OpenAI |
| 2 | `strands_agent_memory.py` | `strands_agent_memory` | + Step 1 Memory + IAM grant |
| 3 | `strands_agent_gateway.py` | `strands_agent_gateway` | + Step 2 Gateway |
| 4 | `strands_agent_identity.py` | `strands_agent_identity` | + Step 3 Identity |
| 5 | `strands_support_copilot.py` | `strands_support_copilot` | Full stack + Streamlit |

After **your** first deploy of each agent, discover **your** ARN:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
data = yaml.safe_load(Path(".bedrock_agentcore.yaml").read_text())
for name, cfg in (data.get("agents") or {}).items():
    arn = (cfg.get("bedrock_agentcore") or {}).get("agent_arn")
    print(f"{name}: {arn}")
PY
```

Do **not** copy someone else’s Runtime ARN into Streamlit.

---

## Demo 1 — Runtime only

FAQ tools only. No Memory / Gateway required.

```bash
export AWS_REGION=us-east-1
set -a && source .env && set +a

agentcore configure -e strands_agent.py -n strands_agent \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a strands_agent \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --auto-update-on-conflict

agentcore invoke -a strands_agent \
  '{"prompt":"How do I activate a new SIM?"}'
```

Ask topics that exist in `lauki_qna.csv` (activate SIM, eSIM, plans, roaming, …).

---

## Demo 2 — Memory

```bash
agentcore configure -e strands_agent_memory.py -n strands_agent_memory \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a strands_agent_memory \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --auto-update-on-conflict

# Required once per Runtime role (or re-run after new agents appear)
.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a strands_agent_memory \
  '{"prompt":"My name is Mohamed and I like concise answers","actor_id":"mohamed","thread_id":"demo-1"}'
agentcore invoke -a strands_agent_memory \
  '{"prompt":"What is my name and preference?","actor_id":"mohamed","thread_id":"demo-1"}'
```

Same `actor_id` + `thread_id` → recall.  
Without the IAM grant, Strands Memory returns **500** (`AccessDeniedException` on `ListEvents`).

---

## Demo 3 — Gateway

```bash
# Refresh token if older than ~1 hour
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e strands_agent_gateway.py -n strands_agent_gateway \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a strands_agent_gateway \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a strands_agent_gateway \
  '{"prompt":"How do I activate a new SIM?","actor_id":"mohamed","thread_id":"gw-1"}'
```

---

## Demo 4 — Identity

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e strands_agent_identity.py -n strands_agent_identity \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a strands_agent_identity \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a strands_agent_identity \
  '{"prompt":"How do I activate a new SIM?","actor_id":"mohamed","thread_id":"id-1"}'
```

If you used a different Gateway `--name`, set `IDENTITY_SCOPES` to the `scope`
value from your `gateway-credentials.json` (and match the Identity console scopes).

---

## Demo 5 — Flagship + Streamlit

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e strands_support_copilot.py -n strands_support_copilot \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a strands_support_copilot \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a strands_support_copilot \
  '{"prompt":"Does Lauki support eSIM?","actor_id":"mohamed","thread_id":"flag-1"}'

# YOUR ARN from .bedrock_agentcore.yaml (not a classmate's)
export SUPPORT_RUNTIME_ARN="$(.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
print(yaml.safe_load(Path(".bedrock_agentcore.yaml").read_text())["agents"]["strands_support_copilot"]["bedrock_agentcore"]["agent_arn"])
PY
)"
echo "$SUPPORT_RUNTIME_ARN"

# Keep AWS credentials exported — Streamlit uses boto3
streamlit run streamlit_support_app.py
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Memory 500 / `ListEvents` AccessDenied | Run `scripts/grant_runtime_memory_permissions.py --all-from-config` after deploy |
| Memory region errors | Memory + Runtime must be `us-east-1`; pass `--env AWS_REGION=us-east-1` |
| Bedrock model / Error 002 | Pass `--env OPENAI_API_KEY=...` at **deploy** |
| No `gateway-credentials.json` | Run Step 2 `create_mcp_gateway.py` |
| Gateway 401 | Re-mint token and **redeploy** (token is baked into Runtime env) |
| Identity fails | Check provider name `gateway-cognito-m2m` + scopes; keep `GATEWAY_TOKEN` fallback |
| Wrong agent on invoke | Always `agentcore invoke -a <agent_name> ...` |
| FAQ useless answers | Ask activate / eSIM / plans (see `lauki_qna.csv`) |
| Python 3.14 install errors | `uv sync --python 3.11` |

---

## Scripts in this folder

| Script | Purpose |
|---|---|
| `scripts/create_mcp_gateway.py` | Create Cognito + Gateway (+ Lambda); write `gateway-credentials.json` |
| `scripts/create_lambda_gateway_target.py` | Attach Lambda tools to an existing Gateway |
| `scripts/get_gateway_token.py` | Mint Cognito M2M JWT |
| `scripts/grant_runtime_memory_permissions.py` | IAM: Memory APIs + Identity token APIs on Runtime roles |

---

## Contrast

| | LangGraph (01) | Strands (02) |
|---|---|---|
| Agent style | Graphs | Single `Agent` + tools |
| Packaging | Container or direct | Direct code deploy |
| Flagship | Research graph | Support Copilot |
