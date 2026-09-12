# Bedrock AgentCore — LangGraph Demo Suite

Hands-on demos for **Amazon Bedrock AgentCore** using LangGraph / LangChain agents.

Each Runtime demo is a Python entrypoint you `configure → launch → invoke`.
Shared helpers live in `_shared.py`. Managed Harness (Demo 6) is invoked with a
**client script**, not `agentcore invoke`.

> **Student rule:** always use this project’s `.venv` (`uv sync` first). Never rely
> on system `python` / `pip` for AgentCore toolkit imports.

---

## Table of contents

1. [What you get](#1-what-you-get)
2. [Prerequisites](#2-prerequisites)
3. [Regions (read this first)](#3-regions-read-this-first)
4. [One-time project setup](#4-one-time-project-setup)
5. [Demo map](#5-demo-map)
6. [Demo 1 — Runtime only](#6-demo-1--runtime-only)
7. [Demo 2 — Runtime + Memory](#7-demo-2--runtime--memory)
8. [Demo 3 — Runtime + Memory + Gateway (MCP) + Cognito](#8-demo-3--runtime--memory--gateway-mcp--cognito)
9. [Demo 4 — Runtime + Memory + Gateway + Identity](#9-demo-4--runtime--memory--gateway--identity)
10. [Demo 5 — Harness-style tools on Runtime](#10-demo-5--harness-style-tools-on-runtime)
11. [Demo 6 — True Harness (managed)](#11-demo-6--true-harness-managed-loop-no-agent-python)
12. [Demo 7 — Research agent + Streamlit](#12-demo-7--research-agent--streamlit)
13. [Dockerfile CMD warning](#13-dockerfile-cmd-warning)
14. [Destroy / cleanup](#14-destroy--cleanup)
15. [Troubleshooting](#15-troubleshooting)
16. [File reference](#16-file-reference)
17. [Cold-start checklist](#17-cold-start-checklist)
18. [What can still fail (AWS reality)](#18-what-can-still-fail-aws-reality)

---

## 1) What you get

| Capability | How this repo demos it |
|---|---|
| **Runtime** | Your Python agent packaged as a container, hosted by AgentCore |
| **Memory** | `AgentCoreMemorySaver` + `AgentCoreMemoryStore` via `MEMORY_ID` |
| **Gateway** | MCP HTTPS front for Lambda tools (`get_weather`, `get_time`) |
| **Cognito (JWT)** | M2M app client; secrets saved in `gateway-credentials.json` (gitignored) |
| **Identity** | `@requires_access_token` → OAuth token for Gateway (provider `gateway-cognito-m2m`) |
| **Harness tools** | Code Interpreter + Browser called from **your** Runtime code (Demo 5) |
| **Harness (managed)** | AWS-owned loop via `scripts/create_harness.py` + `invoke_harness_client.py` (Demo 6) |
| **Research + Streamlit** | RAG + tools + optional Browser; SSE chat UI (Demo 7) |

---

## 2) Prerequisites

- AWS account with permission to use Bedrock AgentCore (Runtime, Memory, Gateway, Identity, Code Interpreter, Browser, Harness as needed)
- AWS CLI v2 + a named profile (`aws configure --profile <name>`)
- Python **3.11+** and [`uv`](https://docs.astral.sh/uv/)
- AgentCore starter toolkit CLI (`agentcore`) — prefer the **project binary**:
  `.venv/bin/agentcore` (or `uv run agentcore`) after `uv sync`, so CLI version
  matches this repo’s toolkit
- OpenAI API key (these demos default to OpenAI so Bedrock model quotas do not block you)
- Optional: `TAVILY_API_KEY` for higher-quality `web_search` (otherwise DuckDuckGo via `ddgs`)

**CLI note:** `agentcore` has **no `--profile` flag**. Always:

```bash
export AWS_PROFILE=<your-profile>   # example used in this lab: inceptez
export AWS_REGION=us-east-1         # Runtime + Memory region (see §3)
aws sts get-caller-identity         # must succeed before configure/launch

# Prefer the venv CLI (avoids a stale global install):
alias agentcore='.venv/bin/agentcore'   # optional, for this shell
# or prefix every command:  .venv/bin/agentcore ...
```

Always run helpers with the project venv:

```bash
.venv/bin/python scripts/...
# or
uv run python scripts/...
```

In the rest of this README, every `agentcore …` command means:

```bash
.venv/bin/agentcore …
```

(unless you created the shell alias shown above).

---

## 3) Regions (read this first)

This lab intentionally uses **two regions**. Do not “simplify” them or Memory / Gateway break.

| Resource | Region | Why |
|---|---|---|
| AgentCore **Memory** (`MEMORY_ID`) | **`us-east-1`** | Memory IDs are region-scoped |
| All **Runtime** agents in this repo | **`us-east-1`** | Matches Memory + Code Interpreter / Browser sessions |
| **Gateway + Cognito** | **`us-west-2`** | Existing lab Gateway URL is west-2; Runtime calls it by full HTTPS URL |

Rules that prevent 90% of student failures:

1. For every `agentcore configure` / `agentcore launch` of a **Runtime** agent, use **`AWS_REGION=us-east-1`** (or `agentcore configure ... -r us-east-1`).
2. Pass **`--env AWS_REGION=us-east-1`** on launch so `_shared.py` Memory / Code Interpreter / Browser clients use east-1 (`REGION = os.getenv("AWS_REGION") or "us-west-2"` — if you omit this, Memory defaults to west-2 and **fails** against an east-1 Memory ID).
3. Create / call the Gateway with **`us-west-2`**. The Gateway URL is absolute; cross-region calls from an east-1 Runtime are fine.

---

## 4) One-time project setup

```bash
cd 01.langraph-agentcore-bedrock

uv sync

cp .env.example .env
# Edit .env — set at least OPENAI_API_KEY and MEMORY_ID

set -a && source .env && set +a
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
aws sts get-caller-identity
```

### 4.1 Create AgentCore Memory (required for Demos 2–5 and 7)

Console: **Amazon Bedrock → AgentCore → Memory → Create**, region **`us-east-1`**.

Or use an existing Memory ID. Put it in `.env`:

```bash
MEMORY_ID=<your-memory-id>    # lab example: memorybot-w6GzC7D97L (us-east-1)
```

The Runtime **execution role** must allow AgentCore Memory APIs on that Memory.
`scripts/grant_harness_tool_permissions.py` also attaches a Memory statement for
`us-east-1` and `us-west-2` when you run it for Demo 5 / Browser.

### 4.2 Secrets file

| File | Commit? | Purpose |
|---|---|---|
| `.env` | **Never** | Local keys (`OPENAI_API_KEY`, `MEMORY_ID`, …) |
| `gateway-credentials.json` | **Never** | Cognito client secret + Gateway URL (created by script) |
| `.env.example` | Yes | Template only |

`.env` is **not** copied into the Runtime container. Every secret the cloud agent
needs must be passed with `agentcore launch ... --env KEY=VALUE`.

---

## 5) Demo map

| # | Entrypoint | Agent name (`-n` / `-a`) | Needs |
|---|---|---|---|
| 1 | `langraph_agent.py` | `langraph_agent` | `OPENAI_API_KEY` |
| 2 | `langraph_agent_memory.py` | `langraph_agent_memory` | + `MEMORY_ID` + `AWS_REGION=us-east-1` |
| 3 | `langraph_agent_gateway.py` | `langraph_agent_gateway` | + Gateway URL + `GATEWAY_TOKEN` |
| 4 | `langraph_agent_identity.py` | `langraph_agent_identity` | + Identity provider (no baked token required) |
| 5 | `langraph_agent_harness_tools.py` | `langraph_agent_harness_tools` | + Code Interpreter / Browser IAM |
| 6 | `invoke_harness_client.py` | *(client only)* | `HARNESS_ARN` (`…:harness/…`) |
| 7a | `langgraph_research_agentcore.py` | `langgraph_research_agent` | Research stack (`create_agent`) |
| 7b | `langgraph_research_graph_agentcore.py` | `langgraph_research_graph` | Explicit `StateGraph` + `browse_url` |
| — | `research_create_agent_agentcore.py` | *(library / preserved copy)* | Tools shared by 7b; not a separate required launch |
| — | `streamlit_research_app.py` | *(local UI)* | `RESEARCH_RUNTIME_ARN` |

Pattern for every **Runtime** demo:

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

agentcore configure -e <file>.py -n <agent_name> -r us-east-1
agentcore launch -a <agent_name> \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env AWS_REGION=us-east-1 \
  # …plus demo-specific --env flags…

agentcore invoke -a <agent_name> \
  '{"prompt":"...","actor_id":"demo","thread_id":"t1"}'
```

---

## 6) Demo 1 — Runtime only

FAQ keyword search. No Memory / Gateway.

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

agentcore configure -e langraph_agent.py -n langraph_agent -r us-east-1
agentcore launch -a langraph_agent \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env AWS_REGION=us-east-1

agentcore invoke -a langraph_agent \
  '{"prompt":"What plans do Lauki Phones offer?"}'
```

---

## 7) Demo 2 — Runtime + Memory

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

agentcore configure -e langraph_agent_memory.py -n langraph_agent_memory -r us-east-1
agentcore launch -a langraph_agent_memory \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1

# Turn 1 — store a fact
agentcore invoke -a langraph_agent_memory \
  '{"prompt":"My name is Mohamed","actor_id":"mohamed","thread_id":"demo-1"}'

# Turn 2 — recall (same actor_id + thread_id)
agentcore invoke -a langraph_agent_memory \
  '{"prompt":"What is my name?","actor_id":"mohamed","thread_id":"demo-1"}'
```

---

## 8) Demo 3 — Runtime + Memory + Gateway (MCP) + Cognito

### 8.1 What Cognito is doing

`scripts/create_mcp_gateway.py`:

1. Creates a Cognito User Pool + domain + confidential M2M app client (`client_credentials`)
2. Creates scope like `lauki-demo-gateway/invoke`
3. Creates the AgentCore Gateway with Cognito JWT authorizer
4. Optionally attaches a Lambda target with `get_weather` + `get_time`
5. Writes **`gateway-credentials.json`** (gitignored) with `client_secret`, `gatewayUrl`, etc.

Without that file you cannot mint Gateway tokens.

### 8.2 Create Gateway (region **us-west-2**)

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-west-2

.venv/bin/python scripts/create_mcp_gateway.py \
  --name lauki-demo-gateway \
  --region us-west-2 \
  --with-lambda-target
```

Re-run with a **new `--name`** if you need a fresh Gateway. Do not commit `gateway-credentials.json`.

### 8.3 Mint a Gateway bearer token

```bash
# From project root (reads gateway-credentials.json)
.venv/bin/python scripts/get_gateway_token.py

export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python -c 'import json;print(json.load(open("gateway-credentials.json"))["gateway"]["gatewayUrl"])')"
echo "$GATEWAY_URL"
```

Token lifetime is typically ~1 hour. Refresh before launch / when invokes return HTTP 401 from Gateway.

### 8.4 Optional MCP smoke test

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

Expect tool names containing `get_weather` and `get_time`.

### 8.5 Launch gateway agent (Runtime still **us-east-1**)

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
export GATEWAY_URL="$(.venv/bin/python -c 'import json;print(json.load(open("gateway-credentials.json"))["gateway"]["gatewayUrl"])')"

agentcore configure -e langraph_agent_gateway.py -n langraph_agent_gateway -r us-east-1
agentcore launch -a langraph_agent_gateway \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env GATEWAY_TOKEN="$GATEWAY_TOKEN"

agentcore invoke -a langraph_agent_gateway \
  '{"prompt":"What is the weather in Chennai?","actor_id":"demo","thread_id":"gw-1"}'
```

Expected: mock Lambda weather (e.g. `72°F / Sunny`), not live meteorology.

---

## 9) Demo 4 — Runtime + Memory + Gateway + Identity

Same Gateway tools, but the Runtime obtains the JWT via **AgentCore Identity**
(`@requires_access_token`) instead of baking `GATEWAY_TOKEN` into launch env.

### 9.1 Create / verify OAuth2 credential provider

Console (region **`us-east-1`** for Runtime Identity lookups used by east-1 agents):

1. **Bedrock → AgentCore → Identity → OAuth2 credential providers**
2. Create a **Custom OAuth2** provider that can perform client-credentials against your
   Cognito token endpoint from `gateway-credentials.json`
3. Name it exactly what you will pass as `IDENTITY_PROVIDER_NAME`
   (lab name: **`gateway-cognito-m2m`**)
4. Scopes must include your Gateway scope (lab: `lauki-demo-gateway/invoke`)

Identity needs a **Workload Access Token (WAT)** at invoke time. When calling
`InvokeAgentRuntime` yourself, pass **`runtimeUserId`** (Streamlit already does).
`agentcore invoke` from recent toolkits also supplies session identity; if Identity
fails, the code falls back to `GATEWAY_TOKEN` when that env var is set.

### 9.2 Launch

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

export GATEWAY_URL="$(.venv/bin/python -c 'import json;print(json.load(open("gateway-credentials.json"))["gateway"]["gatewayUrl"])')"
# Optional fallback while debugging Identity:
# export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"

agentcore configure -e langraph_agent_identity.py -n langraph_agent_identity -r us-east-1
agentcore launch -a langraph_agent_identity \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke
  # optional: --env GATEWAY_TOKEN="$GATEWAY_TOKEN"

agentcore invoke -a langraph_agent_identity \
  '{"prompt":"What is the weather in Chennai?","actor_id":"demo","thread_id":"id-1"}'
```

> Note: `langraph_agent_identity.py` defaults `IDENTITY_PROVIDER_NAME` to
> `gateway-oauth-provider` if unset. **Always pass** `gateway-cognito-m2m` (or your name)
> explicitly at launch.

---

## 10) Demo 5 — Harness-style tools on Runtime (your code)

Code Interpreter + Browser sandboxes, orchestrated by **your** LangGraph agent
(`langraph_agent_harness_tools.py`). This is **not** the managed Harness product.

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

agentcore configure -e langraph_agent_harness_tools.py -n langraph_agent_harness_tools -r us-east-1
agentcore launch -a langraph_agent_harness_tools \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1
```

### Required IAM

Default Runtime roles lack Code Interpreter / Browser. Grant them
(**`Resource: "*"`** — narrow ARNs have 403’d in practice):

```bash
# Discover the role name from config (do not guess):
.venv/bin/python - <<'PY'
from pathlib import Path
from bedrock_agentcore_starter_toolkit.utils.runtime.config import load_config
a = load_config(Path(".bedrock_agentcore.yaml")).agents["langraph_agent_harness_tools"]
print(a.aws.execution_role.split("/")[-1])
PY

.venv/bin/python scripts/grant_harness_tool_permissions.py \
  --role-name <role-name-from-above> \
  --region us-east-1
```

Lab example role name (only if your yaml matches):  
`AmazonBedrockAgentCoreSDKRuntime-us-east-1-79b0307c3f`

IAM applies immediately. **Code changes** need a new `agentcore launch`.

```bash
agentcore invoke -a langraph_agent_harness_tools \
  '{"prompt":"Run python: print(sum(range(10)))","actor_id":"demo","thread_id":"h1"}'
```

Expected: tool `run_python_code` → stdout **`45`**.

> `execute_code()` returns a boto3 dict with a non-JSON-serializable `stream`.
> The agent parses EventStream `structuredContent.stdout`. Do not `json.dumps(result)`.

---

## 11) Demo 6 — True Harness (managed loop, **no** agent Python)

| | Demo 5 | Demo 6 |
|---|---|---|
| Who runs the loop? | Your LangGraph on Runtime | AWS-managed Harness |
| Deploy `langraph_*.py`? | Yes | **No** |
| Invoke API | `InvokeAgentRuntime` / `agentcore invoke` | **`InvokeHarness`** via `invoke_harness_client.py` |
| ARN | `…:runtime/…` | **`…:harness/…` only** |

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

# Creates managed Harness + OpenAI API-key credential provider (needs OPENAI_API_KEY)
.venv/bin/python scripts/create_harness.py

# Print / export the Harness ARN from the script output, then:
export HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:harness/<harness-id>"
.venv/bin/python invoke_harness_client.py "What is 2+2? Use code interpreter."
```

You can also set `HARNESS_ID=<id>` instead of the full ARN (client builds the ARN).

**Do not** use:

- `HARNESS_RUNTIME_ARN` / any `…:runtime/…` with this client
- placeholders like `PASTE_HERE`

There is **no** `agentcore configure -e …` for Demo 6.

---

## 12) Demo 7 — Research agent + Streamlit

### 12.1 Two research entrypoints

| File | Pattern | Notes |
|---|---|---|
| `langgraph_research_agentcore.py` | LangChain `create_agent` | Agent name `langgraph_research_agent` |
| `research_create_agent_agentcore.py` | Same `create_agent` tools/helpers | **Preserved copy**; imported by the StateGraph agent |
| `langgraph_research_graph_agentcore.py` | Explicit `StateGraph` (`START → agent ⇄ tools → END`) | Agent name `langgraph_research_graph`; includes **`browse_url`** |

```
create_agent path:   create_agent(...)           ← prebuilt ReAct loop
StateGraph path:     START → agent ⇄ tools → END ← you own nodes/edges
```

Shared capabilities (when launched with the env below):

| Capability | Mechanism |
|---|---|
| Memory | `MEMORY_ID` + `AWS_REGION=us-east-1` |
| Gateway MCP | `GATEWAY_URL` + Identity (and optional `GATEWAY_TOKEN` fallback) |
| Identity | `IDENTITY_PROVIDER_NAME=gateway-cognito-m2m`, `M2M`, scope `lauki-demo-gateway/invoke` |
| RAG | `search_docs` over `rag_data/agentcore_knowledge.md` + `lauki_qna.csv` |
| Local tools | `web_search`, `calculator`, `get_current_datetime`, `search_docs` |
| Browser | **`browse_url`** on the StateGraph path (`research_create_agent_agentcore.py` tools). Grant Browser IAM on that Runtime role before first browse. |

> **Packaging note:** `.dockerignore` excludes `docs/` and most `*.md` but **keeps**
> `rag_data/**`. FAQ rows come from `lauki_qna.csv` (must stay at project root).
> If `search_docs` returns empty in the cloud, confirm those paths are in the
> CodeBuild source zip / image.

### 12.2 Launch StateGraph research agent (recommended)

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
set -a && source .env && set +a

# §13 — ensure root Dockerfile CMD targets the graph module before CodeBuild
# CMD ["opentelemetry-instrument", "python", "-m", "langgraph_research_graph_agentcore"]

export GATEWAY_URL="$(.venv/bin/python -c 'import json;print(json.load(open("gateway-credentials.json"))["gateway"]["gatewayUrl"])')"
# Optional Identity fallback:
# export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"

agentcore configure -e langgraph_research_graph_agentcore.py -n langgraph_research_graph -r us-east-1

agentcore launch -a langgraph_research_graph \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke

# Grant Code Interpreter + Browser on THIS agent’s execution role
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

### 12.3 Launch create_agent research agent (alternate)

Same env vars; entrypoint / name differ. **Confirm Dockerfile CMD** points at
`langgraph_research_agentcore` before launch (§13).

```bash
agentcore configure -e langgraph_research_agentcore.py -n langgraph_research_agent -r us-east-1
agentcore launch -a langgraph_research_agent \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke

agentcore invoke -a langgraph_research_agent \
  '{"prompt":"What is the weather in Chennai, and what is 15*8+3?","actor_id":"demo","thread_id":"r1"}'
```

### 12.4 Streamlit UI

After launch, copy the Runtime ARN from the launch output (or from
`.bedrock_agentcore.yaml` → `bedrock_agentcore.agent_arn`).

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
export RESEARCH_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/<agent-id>"

.venv/bin/streamlit run streamlit_research_app.py --server.port 8502 --server.address 0.0.0.0
```

Open **http://127.0.0.1:8502**.

> `streamlit_research_app.py` ships with a **lab-account default ARN** for the
> StateGraph Runtime. On your own account, **always** set `RESEARCH_RUNTIME_ARN`
> to the ARN printed by your `agentcore launch` (or from `.bedrock_agentcore.yaml`).
> Using another account’s ARN will fail authorization.

UI behavior that matters for demos:

- Streams SSE: `progress` → `step` → `token` → `final`
- Reuses one AgentCore **`runtimeSessionId` per chat** (sticky). **New session**
  button rotates it. A new session ID every message forces cold microVMs (~10–17s).
- Passes **`runtimeUserId`** so Identity can mint a WAT
- Shows capability graph, session latency/token chart, tool timeline

### 12.5 Browser tool (`browse_url`)

Available on the **StateGraph** research path. Flow:

1. `BrowserClient.start` (cloud Chromium)
2. Playwright `connect_over_cdp` via `generate_ws_headers`
3. Navigate → return title + visible text + `live_view_url`

Dependency: `playwright` (already in `pyproject.toml` / `uv sync`). No local Chromium
install is required for CDP-over-cloud.

Try: *“Browse https://example.com and tell me the page title.”*

---

## 13) Dockerfile CMD warning

CodeBuild for this project builds from the **project root `Dockerfile`**.
The final `CMD` must match the agent you are launching:

| Launching | Required `CMD` module |
|---|---|
| `langgraph_research_graph` | `langgraph_research_graph_agentcore` |
| `langgraph_research_agent` | `langgraph_research_agentcore` |
| Other demos | Their own module name (`langraph_agent`, …) — regenerate/fix Dockerfile before launch |

If `CMD` points at the wrong module, the Runtime starts the wrong agent even though
`agentcore launch -a <name>` succeeded. After changing `CMD`, run a fresh
`agentcore launch` so CodeBuild rebuilds the image.

If `agentcore launch` fails with **“image identifier does not exist”**, CodeBuild’s
image tag and `UpdateAgentRuntime` got out of sync. Fix by ensuring the root
`Dockerfile` CMD is correct, then re-launch; if it persists, update the CodeBuild
project buildspec image tag and `UpdateAgentRuntime` to the tag that was actually
pushed to ECR (see troubleshooting).

---

## 14) Destroy / cleanup

```bash
agentcore destroy -a <agent_name> --dry-run
agentcore destroy -a <agent_name> --force
# optional: --delete-ecr-repo
```

Gateway / Cognito / Lambda / Identity providers / Memory / Harness are **separate**.
Delete in Console or with AWS CLI when the lab is finished. Rotate Cognito secrets
if `gateway-credentials.json` was shared.

Managed Harness:

```bash
aws bedrock-agentcore-control delete-harness \
  --harness-id <harness-id> \
  --region us-east-1
```

---

## 15) Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'bedrock_agentcore…'` | Use `.venv/bin/python` / `uv sync` |
| `agentcore … --profile` | Unsupported — `export AWS_PROFILE=…` |
| Memory errors / empty MEMORY | Memory is **us-east-1**. Pass `--env AWS_REGION=us-east-1` on launch |
| Gateway `401` | Refresh token: `scripts/get_gateway_token.py`, relaunch with new `GATEWAY_TOKEN` |
| Weather “unable to retrieve” | Confirm Gateway tools via smoke test; refresh token; relaunch |
| Demo 5 `AccessDenied` on Code Interpreter / Browser | Run `scripts/grant_harness_tool_permissions.py` on **that** agent’s execution role |
| Demo 5 model invents `45` without stdout | Relaunch after EventStream stdout parser; check CloudWatch |
| Demo 6 rejects Runtime ARN | Use `HARNESS_ARN` (`…:harness/…`) + `invoke_harness_client.py` |
| Demo 6 `GetResourceApiKey` AccessDenied | Harness execution role needs API-key provider access (`scripts/create_harness.py`) |
| Identity never engages | Provider name mismatch; missing WAT / `runtimeUserId`; set fallback `GATEWAY_TOKEN` |
| Wrong agent behavior after launch | Root `Dockerfile` `CMD` points at another module — fix + relaunch (§13) |
| Launch: image tag does not exist | CodeBuild tag drift — rebuild/push tag that UpdateAgentRuntime expects |
| Streamlit “connection refused” | Start from project venv on port 8502; keep the process in a real terminal |
| First chat turn ~10–17s | Cold `runtimeSessionId` / cold microVM — reuse session (UI already does) |
| Bedrock model quota / access denied | Use `OPENAI_API_KEY` (all Runtime demos + Demo 6) |

Runtime logs:

```bash
# agent_id looks like: langgraph_research_graph-ZsDIkv2WYd
aws logs tail /aws/bedrock-agentcore/runtimes/<agent_id>-DEFAULT \
  --log-stream-name-prefix "$(date -u +%Y/%m/%d)/[runtime-logs]" \
  --since 1h --region us-east-1
```

---

## 16) File reference

```
01.langraph-agentcore-bedrock/
├── README.md
├── .env.example                       ← copy to .env (gitignored)
├── pyproject.toml                     ← includes playwright for browse_url
├── Dockerfile                         ← CMD must match the agent you launch
├── .streamlit/config.toml
├── gateway-credentials.json           ← gitignored (generated)
├── lauki_qna.csv                      ← FAQ corpus
├── rag_data/agentcore_knowledge.md    ← RAG corpus (packaged in Runtime zip)
├── docs/agentcore_knowledge.md        ← same text for local reading (often zip-excluded)
├── _shared.py                         ← FAQ tools, Memory, MCP→LangChain loader
├── langraph_agent.py                  ← Demo 1
├── langraph_agent_memory.py           ← Demo 2
├── langraph_agent_gateway.py          ← Demo 3
├── langraph_agent_identity.py         ← Demo 4
├── langraph_agent_harness_tools.py    ← Demo 5 (CI + Browser tools)
├── langgraph_research_agentcore.py    ← Demo 7a create_agent
├── research_create_agent_agentcore.py ← preserved create_agent + browse_url tools
├── langgraph_research_graph_agentcore.py ← Demo 7b StateGraph
├── streamlit_research_app.py          ← local SSE chat UI
├── invoke_harness_client.py           ← Demo 6 client
└── scripts/
    ├── create_mcp_gateway.py
    ├── create_lambda_gateway_target.py
    ├── get_gateway_token.py
    ├── grant_harness_tool_permissions.py
    ├── create_harness.py
    └── preflight_class.py             ← trainer: green-light before class
```

| Script | Purpose |
|---|---|
| `scripts/create_mcp_gateway.py` | Cognito M2M + Gateway (+ optional Lambda); writes `gateway-credentials.json` |
| `scripts/get_gateway_token.py` | Cognito client_credentials → prints JWT |
| `scripts/create_lambda_gateway_target.py` | Attach demo Lambda tools to an existing Gateway |
| `scripts/grant_harness_tool_permissions.py` | Code Interpreter + Browser (+ Memory) IAM on a Runtime role |
| `scripts/create_harness.py` | Managed Harness + OpenAI API-key provider |
| `scripts/preflight_class.py` | Trainer: verify Memory/Gateway/Runtimes/Harness before class |

---

## 17) Cold-start checklist

```bash
cd 01.langraph-agentcore-bedrock
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
uv sync
cp -n .env.example .env   # then edit secrets
set -a && source .env && set +a
aws sts get-caller-identity

# Memory: create in us-east-1, set MEMORY_ID in .env

# Gateway (west-2) — once
AWS_REGION=us-west-2 .venv/bin/python scripts/create_mcp_gateway.py \
  --name lauki-demo-gateway --region us-west-2 --with-lambda-target

# Identity provider gateway-cognito-m2m in Console (east-1) — once for Demos 4/7

# Demo 2 smoke
.venv/bin/agentcore configure -e langraph_agent_memory.py -n langraph_agent_memory -r us-east-1
.venv/bin/agentcore launch -a langraph_agent_memory \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1

# Demo 7b + UI
export GATEWAY_URL="$(.venv/bin/python -c 'import json;print(json.load(open("gateway-credentials.json"))["gateway"]["gatewayUrl"])')"
# Fix Dockerfile CMD → langgraph_research_graph_agentcore (§13)
.venv/bin/agentcore configure -e langgraph_research_graph_agentcore.py -n langgraph_research_graph -r us-east-1
.venv/bin/agentcore launch -a langgraph_research_graph \
  --env OPENAI_API_KEY="$OPENAI_API_KEY" \
  --env MEMORY_ID="$MEMORY_ID" \
  --env AWS_REGION=us-east-1 \
  --env GATEWAY_URL="$GATEWAY_URL" \
  --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
  --env IDENTITY_AUTH_FLOW=M2M \
  --env IDENTITY_SCOPES=lauki-demo-gateway/invoke

export RESEARCH_RUNTIME_ARN="$(.venv/bin/python - <<'PY'
from pathlib import Path
from bedrock_agentcore_starter_toolkit.utils.runtime.config import load_config
print(load_config(Path('.bedrock_agentcore.yaml')).agents['langgraph_research_graph'].bedrock_agentcore.agent_arn)
PY
)"
.venv/bin/streamlit run streamlit_research_app.py --server.port 8502 --server.address 0.0.0.0
```

### Trainer pre-flight (shared lab account)

```bash
.venv/bin/python scripts/preflight_class.py
```

(Trainers: keep your local class runbook untracked — see `.gitignore`.)

---

## 18) What can still fail (AWS reality)

These are **platform / ops** issues, not missing README steps. Plan for them:

| Risk | Likelihood in a live class | Mitigation |
|---|---|---|
| Cold `runtimeSessionId` / new microVM (~10–17s) | High on first call | Pre-warm; Streamlit sticky session; tell students once |
| Cognito `GATEWAY_TOKEN` expiry (~1h) | Medium | Re-mint + **relaunch** agents that baked the token |
| Identity WAT / provider misconfig | Medium for DIY accounts | Pass `GATEWAY_TOKEN` fallback; Streamlit sends `runtimeUserId` |
| Browser / Code Interpreter IAM forgotten | Medium on new roles | `scripts/grant_harness_tool_permissions.py` on **that** role |
| Dockerfile `CMD` wrong module | High if switching 7a↔7b | README §13; verify before launch |
| CodeBuild image-tag drift on update | Occasional | Rebuild; align ECR tag with `UpdateAgentRuntime` |
| Bedrock model quotas | High if using Bedrock LLMs | Keep `OPENAI_API_KEY` on Runtime env |
| AWS regional / service incidents | Low but real | Teach from CLI + cached UI; don’t create infra live |

Verified on the trainer account during doc QA (Memory, Gateway MCP `tools/list`,
all listed Runtimes `READY`, Harness `2+2→4`, graph warm `"hi"` ~1–3s). That does
**not** eliminate the table above for tomorrow — it means the **documented path works
when AWS and env are healthy**.

---

### Lab-account reference (optional)

If you are on the shared trainer account (`899736802567`) these IDs already exist.
**Students on their own accounts must create their own** — do not copy ARNs blindly.

| Resource | Reference value |
|---|---|
| Memory (us-east-1) | `memorybot-w6GzC7D97L` |
| Gateway URL (us-west-2) | see your `gateway-credentials.json` |
| Identity provider | `gateway-cognito-m2m` |
| Harness | `arn:aws:bedrock-agentcore:us-east-1:899736802567:harness/lauki_harness_demo-rk1Voq8Z3T` |
| Research StateGraph Runtime | `…/runtime/langgraph_research_graph-ZsDIkv2WYd` |
| Research create_agent Runtime | `…/runtime/langgraph_research_agent-oii60EHhFt` |
