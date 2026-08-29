<div align="center">

# Hierarchical Helpdesk Orchestrator

### Session 11 · Day 3 · required app

*A supervisor routes work to a knowledge desk (RAG + web) and an ops desk (SQL + ticket writes that pause for a human).*

</div>

Built in [`../notebooks/03_multi_agent_orchestrator.ipynb`](../notebooks/03_multi_agent_orchestrator.ipynb). Does **not** rebuild retrieval — it starts the Session 10 MCP server and splits its tools across specialists.

<p align="center">
  <img src="docs/screenshots/app.png" alt="Helpdesk orchestrator — Streamlit chat with thread_id, answer style, and LangSmith tracing" width="920">
</p>
<p align="center"><em>Pick a <code>thread_id</code>, ask the helpdesk, and watch writes pause for a yes/no. LangSmith traces the supervisors and tools.</em></p>

```text
top_supervisor
  ├── knowledge_team  → rag_agent (search_knowledge_base) + search_agent (web)
  └── ops_team        → sql_agent (reads) + ticket_agent (writes → interrupt())
```

## Run

```bash
cd 11_LangGraph/multi_agent_orchestrator
pip install -r requirements.txt
python3 -m streamlit run app.py
```

Use `python3 -m streamlit` (not a pipx-isolated `streamlit`) so the interpreter that has LangGraph is the one serving the app.

**Keys:** `OPENAI_API_KEY` in `11_LangGraph/.env`, `10_RAG/.env`, or the repo root. Optional `TAVILY_API_KEY` (else DuckDuckGo). See [`../.env.example`](../.env.example).

## LangGraph Studio

```bash
cd 11_LangGraph/multi_agent_orchestrator
langgraph dev
```

Opens [LangGraph Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024) against `studio.py:graph`. HITL pauses show up as interrupts.

## What to try

| Ask | What should happen |
|---|---|
| “What is our refund / cancellation policy?” | Knowledge desk → RAG |
| “How many tickets has Jane Doe opened?” | Ops desk → SQL read |
| “Add a note that we offered a refund” | **Pauses** — type yes or no |
| New `thread_id`, then “what was just offered?” | Should **not** know |

Optional LangSmith: `LANGSMITH_TRACING=true` + API key + `LANGSMITH_PROJECT=helpdesk-orchestrator`.

← [Session 11](../README.md)
