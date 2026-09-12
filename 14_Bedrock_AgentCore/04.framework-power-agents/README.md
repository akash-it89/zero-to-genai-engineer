# Framework Power Agents — LangGraph vs Strands vs CrewAI

Parent index: [`../README.md`](../README.md).

**Goal:** One classroom demo notebook that builds a **powerful agent** three ways —
same capabilities, three frameworks — so students *see* the architectural difference.

| Framework | Shape | Best for demoing |
|---|---|---|
| **LangGraph** | Graph / `create_agent` ReAct loop | Explicit control flow, tool nodes, AgentCore research stack |
| **Strands** | Single `Agent` + tools | Fast Support Copilot style, clean tool list |
| **CrewAI** | Multi-agent crew (roles + tasks) | Researcher → Analyst → Writer briefs |

## Features covered in the notebook

| Feature | How it appears |
|---|---|
| Tools | FAQ search, calculator, datetime, web search |
| RAG | Keyword search over `data/lauki_qna.csv` + `data/agentcore_knowledge.md` |
| MCP / Gateway | Optional cell — load tools from AgentCore Gateway if `GATEWAY_*` set |
| Memory | Optional cell — AgentCore Memory patterns per framework |
| Browser / Harness | Explained + optional stubs (full Runtime demos stay in lab **01**) |

## Run (local)

```bash
cd 04.framework-power-agents
uv sync --python 3.11
cp .env.example .env   # set OPENAI_API_KEY
source .venv/bin/activate
set -a && source .env && set +a
jupyter notebook powerful_agents_comparison.ipynb
# or: jupyter lab powerful_agents_comparison.ipynb
```

Optional for AgentCore cells: `AWS_*`, `MEMORY_ID`, `GATEWAY_URL`, `GATEWAY_TOKEN`
(create those using lab **01** Steps 1–2, or any sibling lab’s bootstrap).

## Files

```
04.framework-power-agents/
├── README.md
├── .env.example
├── pyproject.toml
├── data/
│   ├── lauki_qna.csv
│   └── agentcore_knowledge.md
└── powerful_agents_comparison.ipynb
```
