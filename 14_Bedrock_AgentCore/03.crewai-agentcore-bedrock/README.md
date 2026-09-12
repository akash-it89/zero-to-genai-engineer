# Bedrock AgentCore — CrewAI Competitor Brief (from scratch)

Parent index: [`14_Bedrock_AgentCore/README.md`](../README.md).

**Use case:** Competitor Brief Crew — Researcher → Analyst → Writer, then
Memory → Gateway → Identity → flagship + Streamlit.

This lab is **self-contained**. Start with an empty AgentCore console. Create
**your own** Memory, Gateway, and Identity. Do **not** paste a classmate’s ids.

Harness stays in [`01.langraph-agentcore-bedrock`](../01.langraph-agentcore-bedrock/).
Sibling: [`02.strands-agentcore-bedrock`](../02.strands-agentcore-bedrock/).

---

## What you will build (order matters)

| Step | What you create | Where |
|---|---|---|
| 0 | Local Python env + `.env` | This folder |
| 1 | AgentCore **Memory** | AWS Console → `us-east-1` |
| 2 | Cognito M2M + **Gateway** (+ Lambda tools) | Script → `us-west-2` |
| 3 | AgentCore **Identity** OAuth provider | AWS Console → `us-east-1` |
| 4 | Demo 1 Runtime crew | Container deploy → `us-east-1` |
| 5 | Demo 2 Memory crew + IAM grant | `us-east-1` |
| 6 | Demo 3 Gateway crew | `us-east-1` Runtime calling west-2 Gateway |
| 7 | Demo 4 Identity crew | `us-east-1` |
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

Always pass `--env AWS_REGION=us-east-1` on **deploy**.

---

## Step 0 — Laptop setup

You need:

- AWS account access to **Bedrock AgentCore** (Memory, Runtime, Gateway, Identity)
- An **OpenAI API key**
- Python **3.11–3.13** (CrewAI / chroma break on 3.14)

```bash
cd 03.crewai-agentcore-bedrock

# --extra local = AgentCore CLI toolkit + Streamlit (kept out of Runtime image)
uv sync --python 3.11 --extra local
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
export AWS_PROFILE=<your-profile>   # or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
alias agentcore='.venv/bin/agentcore'
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
set -a && source .env && set +a

aws sts get-caller-identity
test ${#OPENAI_API_KEY} -gt 20 && echo "OPENAI OK"
```

### Packaging rule (every CrewAI agent)

CrewAI exceeds the **250MB `direct_code_deploy`** limit. **Always** use container
+ the slim Runtime requirements file:

```bash
agentcore configure -e <file.py> -n <agent_name> \
  --deployment-type container \
  --disable-memory \
  --non-interactive \
  --region us-east-1 \
  --requirements-file requirements-runtime.txt
```

Then **`agentcore deploy`** with `--env` vars (Runtime ignores local `.env`).

`--disable-memory` on configure = do not create toolkit STM. You will use the
Memory id from Step 1 via `--env MEMORY_ID=...`.

---

## Step 1 — Create AgentCore Memory (your id)

Nothing is pre-created for you. Create Memory yourself:

1. Open AWS Console → switch region to **`us-east-1`**
2. Go to **Amazon Bedrock → AgentCore → Memory → Create**
3. Create a Memory (any clear name, e.g. `crewai-brief-memory`)
4. Copy the **Memory ID**

Put it in `.env`:

```bash
MEMORY_ID=<paste-your-memory-id-here>
```

```bash
set -a && source .env && set +a
test ${#MEMORY_ID} -ge 12 && echo "MEMORY_ID OK: $MEMORY_ID"
```

Needed for Demos 2–5.

---

## Step 2 — Create Gateway + Cognito (script in this folder)

```bash
export AWS_REGION=us-west-2

.venv/bin/python scripts/create_mcp_gateway.py \
  --name lauki-demo-gateway \
  --region us-west-2 \
  --with-lambda-target
```

```bash
test -f gateway-credentials.json && echo "gateway-credentials.json OK"
```

Mint token + URL (repeat when the token expires — ~1 hour):

```bash
export AWS_REGION=us-east-1

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

Optional smoke test:

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

Needed for Demos 3–5.

---

## Step 3 — Create Identity provider (Console)

Needed for Demos 4–5.

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

AWS Console (**region `us-east-1`**):

1. **Amazon Bedrock → AgentCore → Identity → OAuth2 credential providers**
2. Create **Custom OAuth2** (client credentials / M2M)
3. Name exactly: **`gateway-cognito-m2m`**
4. Paste `token_endpoint`, `client_id`, `client_secret`, and `scope` from above
5. Scopes must include **`lauki-demo-gateway/invoke`** (or your file’s `scope` if
   you used a different Gateway `--name`)

Demos keep `GATEWAY_TOKEN` as a fallback if Identity fails.

---

## Demo map

| # | File | Agent name | Needs |
|---|---|---|---|
| 1 | `crewai_agent.py` | `crewai_agent` | OpenAI |
| 2 | `crewai_agent_memory.py` | `crewai_agent_memory` | + Step 1 + IAM grant |
| 3 | `crewai_agent_gateway.py` | `crewai_agent_gateway` | + Step 2 |
| 4 | `crewai_agent_identity.py` | `crewai_agent_identity` | + Step 3 |
| 5 | `crewai_competitor_brief.py` | `crewai_competitor_brief` | Full stack + Streamlit |

Discover **your** ARNs after deploy (never paste a shared lab ARN):

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

---

## Demo 1 — Runtime only

```bash
export AWS_REGION=us-east-1
set -a && source .env && set +a

agentcore configure -e crewai_agent.py -n crewai_agent \
  --deployment-type container --disable-memory --non-interactive \
  --region us-east-1 --requirements-file requirements-runtime.txt

agentcore deploy -a crewai_agent \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env CREWAI_DISABLE_TELEMETRY=true \
  --auto-update-on-conflict

agentcore invoke -a crewai_agent \
  '{"prompt":"Summarize Amazon Bedrock AgentCore in 5 short bullets"}'
```

---

## Demo 2 — Memory

```bash
agentcore configure -e crewai_agent_memory.py -n crewai_agent_memory \
  --deployment-type container --disable-memory --non-interactive \
  --region us-east-1 --requirements-file requirements-runtime.txt

agentcore deploy -a crewai_agent_memory \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env CREWAI_DISABLE_TELEMETRY=true \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a crewai_agent_memory \
  '{"prompt":"I prefer concise bullet briefs","actor_id":"mohamed","thread_id":"brief-1"}'
agentcore invoke -a crewai_agent_memory \
  '{"prompt":"Compare Strands vs LangGraph on AgentCore","actor_id":"mohamed","thread_id":"brief-1"}'
```

---

## Demo 3 — Gateway

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e crewai_agent_gateway.py -n crewai_agent_gateway \
  --deployment-type container --disable-memory --non-interactive \
  --region us-east-1 --requirements-file requirements-runtime.txt

agentcore deploy -a crewai_agent_gateway \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --env CREWAI_DISABLE_TELEMETRY=true \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a crewai_agent_gateway \
  '{"prompt":"What is the weather in Seattle if tools allow? Then 3 bullets on AgentCore.","actor_id":"mohamed","thread_id":"gw-1"}'
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

agentcore configure -e crewai_agent_identity.py -n crewai_agent_identity \
  --deployment-type container --disable-memory --non-interactive \
  --region us-east-1 --requirements-file requirements-runtime.txt

agentcore deploy -a crewai_agent_identity \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --env CREWAI_DISABLE_TELEMETRY=true \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a crewai_agent_identity \
  '{"prompt":"Give 5 bullets on AgentCore.","actor_id":"mohamed","thread_id":"id-1"}'
```

---

## Demo 5 — Flagship + Streamlit

Expect **30–90s** per brief (3 LLM stages).

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e crewai_competitor_brief.py -n crewai_competitor_brief \
  --deployment-type container --disable-memory --non-interactive \
  --region us-east-1 --requirements-file requirements-runtime.txt

agentcore deploy -a crewai_competitor_brief \
  --env AWS_REGION=us-east-1 \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --env CREWAI_DISABLE_TELEMETRY=true \
  --auto-update-on-conflict

.venv/bin/python scripts/grant_runtime_memory_permissions.py --all-from-config

agentcore invoke -a crewai_competitor_brief \
  '{"prompt":"Bedrock AgentCore vs running agents yourself","actor_id":"mohamed","thread_id":"brief-flag-1"}'

export CREW_RUNTIME_ARN="$(.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
print(yaml.safe_load(Path(".bedrock_agentcore.yaml").read_text())["agents"]["crewai_competitor_brief"]["bedrock_agentcore"]["agent_arn"])
PY
)"
echo "$CREW_RUNTIME_ARN"

streamlit run streamlit_crew_app.py
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Package > 250MB / direct deploy fails | `--deployment-type container` + `requirements-runtime.txt` |
| `Cannot change deployment type` | `agentcore destroy -a <name>` then reconfigure |
| Memory AccessDenied / ListEvents | `scripts/grant_runtime_memory_permissions.py --all-from-config` |
| No `gateway-credentials.json` | Run Step 2 |
| Gateway 401 | Re-mint `GATEWAY_TOKEN` and **redeploy** |
| Identity fails | Provider name + scopes; keep `GATEWAY_TOKEN` fallback |
| Python 3.14 errors | `uv sync --python 3.11 --extra local` |
| Wrong agent | Always `invoke -a <name>` |

---

## Scripts in this folder

| Script | Purpose |
|---|---|
| `scripts/create_mcp_gateway.py` | Create Cognito + Gateway (+ Lambda); write `gateway-credentials.json` |
| `scripts/create_lambda_gateway_target.py` | Attach Lambda tools to an existing Gateway |
| `scripts/get_gateway_token.py` | Mint Cognito M2M JWT |
| `scripts/grant_runtime_memory_permissions.py` | IAM: Memory + Identity token APIs on Runtime roles |

---

## Contrast

| | LangGraph (01) | Strands (02) | CrewAI (03) |
|---|---|---|---|
| Shape | Graphs | Single agent | Multi-agent crew |
| Deploy | Container or direct | Direct code OK | **Container required** |
| Flagship | Research graph | Support Copilot | Competitor Brief |
