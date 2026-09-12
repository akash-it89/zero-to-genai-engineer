# Bedrock AgentCore — LangGraph Demo Suite (from scratch)

Parent index: [`14_Bedrock_AgentCore/README.md`](../README.md).

**Use case:** LangGraph / LangChain agents on AgentCore — Runtime → Memory →
Gateway → Identity → Harness tools → managed Harness → Research + Streamlit.

This lab is **self-contained**. Start with an empty AgentCore console. Create
**your own** Memory, Gateway, and Identity. Do **not** paste a classmate’s
`MEMORY_ID` or Runtime ARN.

Sibling labs (same AgentCore arc, different frameworks):

- [`02.strands-agentcore-bedrock`](../02.strands-agentcore-bedrock/) — Strands Support Copilot  
- [`03.crewai-agentcore-bedrock`](../03.crewai-agentcore-bedrock/) — CrewAI Competitor Brief  

> **Student rule:** always use this project’s `.venv` (`uv sync` first). Prefer
> **`agentcore deploy`** (old name: `launch`).

---

## What you will build (order matters)

| Step | What you create | Where |
|---|---|---|
| 0 | Local Python env + `.env` | This folder |
| 1 | AgentCore **Memory** | AWS Console → `us-east-1` |
| 2 | Cognito M2M + **Gateway** (+ Lambda tools) | Script → `us-west-2` |
| 3 | AgentCore **Identity** OAuth provider | AWS Console → `us-east-1` |
| 4 | Demo 1 Runtime | `us-east-1` |
| 5 | Demo 2 Memory | `us-east-1` |
| 6 | Demo 3 Gateway | Runtime east-1 → Gateway west-2 |
| 7 | Demo 4 Identity | `us-east-1` |
| 8 | Demo 5 Harness-style tools (your code) | + IAM grant |
| 9 | Demo 6 Managed Harness | `scripts/create_harness.py` |
| 10 | Demo 7 Research + Streamlit | Flagship |

Demos 2–7 need Step 1. Demos 3–4 and 7 need Step 2. Demos 4 and 7 need Step 3.

---

## Regions (read once — do not “simplify”)

| Resource | Region | Why |
|---|---|---|
| Memory (`MEMORY_ID`) | **`us-east-1`** | Memory ids are region-scoped |
| All Runtime agents + Harness | **`us-east-1`** | Must match Memory / Browser / Code Interpreter |
| Gateway + Cognito | **`us-west-2`** | Created by the script below |
| Identity provider | **`us-east-1`** | Looked up by east-1 Runtimes |

Always pass `--env AWS_REGION=us-east-1` on **deploy**.

---

## Step 0 — Laptop setup

You need:

- AWS account access to Bedrock AgentCore (Runtime, Memory, Gateway, Identity, Code Interpreter, Browser, Harness)
- AWS CLI v2 + credentials (`AWS_PROFILE` or access keys)
- Python **3.11–3.13** and [`uv`](https://docs.astral.sh/uv/)
- An **OpenAI API key** (demos use OpenAI so Bedrock model quotas do not block you)
- Optional: `TAVILY_API_KEY` for better `web_search`

```bash
cd 01.langraph-agentcore-bedrock

uv sync --python 3.11
cp .env.example .env
```

Edit `.env` — set **only** this for now:

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

`agentcore` has **no `--profile` flag** — always export `AWS_PROFILE` (or keys) first.

### Deploy rules

- Prefer **`agentcore deploy`** (formerly `launch`).
- Runtime **ignores** local `.env` — pass secrets with `--env` at deploy.
- Use **`--disable-memory`** on configure so toolkit STM is not confused with your Step 1 Memory.
- After Memory / Browser / Code Interpreter agents exist, grant IAM (Demo 5 script also covers Memory APIs).

---

## Step 1 — Create AgentCore Memory (your id)

1. AWS Console → region **`us-east-1`**
2. **Amazon Bedrock → AgentCore → Memory → Create**
3. Name e.g. `langgraph-lab-memory` → copy the **Memory ID**

```bash
# Put in .env:
# MEMORY_ID=<paste-your-memory-id-here>
set -a && source .env && set +a
test ${#MEMORY_ID} -ge 12 && echo "MEMORY_ID OK: $MEMORY_ID"
```

---

## Step 2 — Create Gateway + Cognito (this folder)

Creates Cognito M2M + Gateway + Lambda tools (`get_weather`, `get_time`) and writes
**`gateway-credentials.json`** here (gitignored).

```bash
export AWS_REGION=us-west-2

.venv/bin/python scripts/create_mcp_gateway.py \
  --name lauki-demo-gateway \
  --region us-west-2 \
  --with-lambda-target

test -f gateway-credentials.json && echo "gateway-credentials.json OK"
```

Mint token + URL (repeat when token expires — ~1 hour):

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
```

Optional smoke test (expect `get_weather` / `get_time`):

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

---

## Step 3 — Create Identity provider (Console)

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
4. Paste `token_endpoint`, `client_id`, `client_secret`, `scope` from above
5. Scopes must include **`lauki-demo-gateway/invoke`** (or your file’s `scope`)

Keep `GATEWAY_TOKEN` as a deploy fallback if Identity fails.

---

## Demo map

| # | File | Agent name | Needs |
|---|---|---|---|
| 1 | `langraph_agent.py` | `langraph_agent` | OpenAI |
| 2 | `langraph_agent_memory.py` | `langraph_agent_memory` | + Step 1 |
| 3 | `langraph_agent_gateway.py` | `langraph_agent_gateway` | + Step 2 |
| 4 | `langraph_agent_identity.py` | `langraph_agent_identity` | + Step 3 |
| 5 | `langraph_agent_harness_tools.py` | `langraph_agent_harness_tools` | + IAM grant |
| 6 | `invoke_harness_client.py` | *(client only)* | `HARNESS_ARN` from `create_harness.py` |
| 7a | `langgraph_research_agentcore.py` | `langgraph_research_agent` | Full stack |
| 7b | `langgraph_research_graph_agentcore.py` | `langgraph_research_graph` | Full stack + Browser |
| — | `streamlit_research_app.py` | *(local UI)* | **Your** `RESEARCH_RUNTIME_ARN` |

Discover **your** ARNs after deploy:

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

agentcore configure -e langraph_agent.py -n langraph_agent \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a langraph_agent \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env AWS_REGION=us-east-1 \
  --auto-update-on-conflict

agentcore invoke -a langraph_agent \
  '{"prompt":"What plans do Lauki Phones offer?"}'
```

---

## Demo 2 — Runtime + Memory

```bash
agentcore configure -e langraph_agent_memory.py -n langraph_agent_memory \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a langraph_agent_memory \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --auto-update-on-conflict

# Grant Memory APIs on this Runtime role (also used for Demo 5 Browser/CI)
.venv/bin/python - <<'PY'
from pathlib import Path
from bedrock_agentcore_starter_toolkit.utils.runtime.config import load_config
a = load_config(Path(".bedrock_agentcore.yaml")).agents["langraph_agent_memory"]
print(a.aws.execution_role.split("/")[-1])
PY
.venv/bin/python scripts/grant_harness_tool_permissions.py \
  --role-name <role-name-from-above> \
  --region us-east-1

agentcore invoke -a langraph_agent_memory \
  '{"prompt":"My name is Mohamed","actor_id":"mohamed","thread_id":"demo-1"}'
agentcore invoke -a langraph_agent_memory \
  '{"prompt":"What is my name?","actor_id":"mohamed","thread_id":"demo-1"}'
```

Same `actor_id` + `thread_id` → recall.

---

## Demo 3 — Gateway (baked Cognito JWT)

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e langraph_agent_gateway.py -n langraph_agent_gateway \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a langraph_agent_gateway \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

agentcore invoke -a langraph_agent_gateway \
  '{"prompt":"What is the weather in Chennai?","actor_id":"demo","thread_id":"gw-1"}'
```

Expected: mock Lambda weather (e.g. `72°F / Sunny`), not live meteorology.
Token ~1h — on Gateway `401`, re-mint and **redeploy**.

---

## Demo 4 — Identity

Identity mints the Gateway JWT at runtime. Still pass `GATEWAY_TOKEN` as fallback.

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

agentcore configure -e langraph_agent_identity.py -n langraph_agent_identity \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a langraph_agent_identity \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

agentcore invoke -a langraph_agent_identity \
  '{"prompt":"What is the weather in Chennai?","actor_id":"demo","thread_id":"id-1"}'
```

Always pass `IDENTITY_PROVIDER_NAME=gateway-cognito-m2m` explicitly (code defaults differ if unset).

---

## Demo 5 — Harness-style tools on Runtime (your code)

Code Interpreter + Browser called from **your** LangGraph agent — not the managed Harness product.

```bash
agentcore configure -e langraph_agent_harness_tools.py -n langraph_agent_harness_tools \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a langraph_agent_harness_tools \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --auto-update-on-conflict

.venv/bin/python - <<'PY'
from pathlib import Path
from bedrock_agentcore_starter_toolkit.utils.runtime.config import load_config
a = load_config(Path(".bedrock_agentcore.yaml")).agents["langraph_agent_harness_tools"]
print(a.aws.execution_role.split("/")[-1])
PY
.venv/bin/python scripts/grant_harness_tool_permissions.py \
  --role-name <role-name-from-above> \
  --region us-east-1

agentcore invoke -a langraph_agent_harness_tools \
  '{"prompt":"Run python: print(sum(range(10)))","actor_id":"demo","thread_id":"h1"}'
```

Expected: tool `run_python_code` → stdout **`45`**.

---

## Demo 6 — True Harness (managed loop, no agent Python)

| | Demo 5 | Demo 6 |
|---|---|---|
| Who runs the loop? | Your LangGraph on Runtime | AWS-managed Harness |
| Deploy `langraph_*.py`? | Yes | **No** |
| Invoke | `agentcore invoke` / Runtime ARN | `invoke_harness_client.py` / **`…:harness/…`** |

```bash
.venv/bin/python scripts/create_harness.py

# Use the Harness ARN printed by the script (YOUR account):
export HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:harness/<harness-id>"
.venv/bin/python invoke_harness_client.py "What is 2+2? Use code interpreter."
```

Do **not** pass a Runtime ARN (`…:runtime/…`) to this client.

---

## Demo 7 — Research agent + Streamlit

### Two research entrypoints

| File | Pattern | Agent name |
|---|---|---|
| `langgraph_research_graph_agentcore.py` | Explicit `StateGraph` + `browse_url` | `langgraph_research_graph` (**recommended**) |
| `langgraph_research_agentcore.py` | `create_agent` | `langgraph_research_agent` |

### Dockerfile CMD (critical)

CodeBuild uses the **project root `Dockerfile`**. `CMD` must match the agent you deploy:

| Deploying | Required `CMD` module |
|---|---|
| `langgraph_research_graph` | `langgraph_research_graph_agentcore` |
| `langgraph_research_agent` | `langgraph_research_agentcore` |

Wrong `CMD` → wrong agent starts even if `deploy -a` succeeded. Fix `CMD`, then redeploy.

### Deploy StateGraph research agent (recommended)

```bash
export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])
PY
)"

# Confirm Dockerfile CMD → langgraph_research_graph_agentcore before CodeBuild

agentcore configure -e langgraph_research_graph_agentcore.py -n langgraph_research_graph \
  --disable-memory --non-interactive --region us-east-1

agentcore deploy -a langgraph_research_graph \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  --auto-update-on-conflict

.venv/bin/python - <<'PY'
from pathlib import Path
from bedrock_agentcore_starter_toolkit.utils.runtime.config import load_config
a = load_config(Path(".bedrock_agentcore.yaml")).agents["langgraph_research_graph"]
print(a.aws.execution_role.split("/")[-1])
PY
.venv/bin/python scripts/grant_harness_tool_permissions.py \
  --role-name <role-name-from-above> \
  --region us-east-1

agentcore invoke -a langgraph_research_graph \
  '{"prompt":"What is AgentCore Memory? Use search_docs.","actor_id":"demo","thread_id":"g1"}'
```

### Streamlit UI

```bash
export RESEARCH_RUNTIME_ARN="$(.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
print(yaml.safe_load(Path(".bedrock_agentcore.yaml").read_text())["agents"]["langgraph_research_graph"]["bedrock_agentcore"]["agent_arn"])
PY
)"
echo "$RESEARCH_RUNTIME_ARN"

.venv/bin/streamlit run streamlit_research_app.py --server.port 8502 --server.address 0.0.0.0
```

Open **http://127.0.0.1:8502**. Always use **your** ARN — never a shared lab default.

UI notes: sticky `runtimeSessionId` per chat (New session rotates it); passes `runtimeUserId` for Identity.

---

## Destroy / cleanup

```bash
agentcore destroy -a <agent_name> --dry-run
agentcore destroy -a <agent_name> --force
```

Gateway / Cognito / Lambda / Identity / Memory / Harness are **separate** — delete in Console when done.

```bash
aws bedrock-agentcore-control delete-harness \
  --harness-id <harness-id> \
  --region us-east-1
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'bedrock_agentcore…'` | `uv sync`; use `.venv/bin/python` |
| Memory errors | Memory + `--env AWS_REGION=us-east-1`; run grant script on role |
| Gateway `401` | Re-mint token + **redeploy** |
| Demo 5 AccessDenied CI/Browser | `grant_harness_tool_permissions.py` on **that** role |
| Demo 6 rejects Runtime ARN | Use `HARNESS_ARN` (`…:harness/…`) |
| Identity never engages | Provider name + scopes; `GATEWAY_TOKEN` fallback |
| Wrong agent after deploy | Fix root `Dockerfile` `CMD` + redeploy |
| Streamlit wrong account | Set `RESEARCH_RUNTIME_ARN` from **your** yaml |
| Bedrock model quota | Pass `OPENAI_API_KEY` at deploy |

---

## Scripts in this folder

| Script | Purpose |
|---|---|
| `scripts/create_mcp_gateway.py` | Cognito + Gateway (+ Lambda) → `gateway-credentials.json` |
| `scripts/get_gateway_token.py` | Mint Cognito M2M JWT |
| `scripts/create_lambda_gateway_target.py` | Attach Lambda tools to existing Gateway |
| `scripts/grant_harness_tool_permissions.py` | Code Interpreter + Browser + Memory IAM |
| `scripts/create_harness.py` | Managed Harness + OpenAI API-key provider |
| `scripts/preflight_class.py` | Trainer-only health check (optional) |

---

## Contrast with sibling labs

| | LangGraph (01) | Strands (02) | CrewAI (03) |
|---|---|---|---|
| Shape | Graphs / `create_agent` | Single agent + tools | Multi-agent crew |
| Extra | Harness + Research UI | Support Copilot | Competitor Brief |
| Packaging | Usually container/CodeBuild | Direct code OK | **Container + `requirements-runtime.txt` required** |
| Bootstrap | Steps 0–3 in **this** README | Same pattern in 02 | Same pattern in 03 |
