<div align="center">

# Session 11 — Notebooks

**S11a–e · run from this folder so relative paths stay valid**

</div>

```bash
cd 11_LangGraph/notebooks
pip install -r requirements.txt
# keys: 11_LangGraph/.env  or  10_RAG/.env
```

| # | Notebook | Day | Required | Slides |
|---|---|---|---|---|
| 01 | [Fundamentals & agents](01_langgraph_fundamentals_and_agents.ipynb) | S11a | **Yes** | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/11_LangGraph/notebooks/teaching_decks/teach_01_langgraph_fundamentals.html) |
| 02 | [Human-in-the-loop](02_human_in_the_loop.ipynb) | S11b | **Yes** | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/11_LangGraph/notebooks/teaching_decks/teach_02_human_in_the_loop.html) |
| 03 | [Multi-agent orchestrator](03_multi_agent_orchestrator.ipynb) | S11c | **Yes** — then [`../multi_agent_orchestrator/`](../multi_agent_orchestrator/) | taught from the notebook + app |
| 04 | [Reasoning patterns](04_agent_reasoning_patterns_masterclass.ipynb) | S11d | Bonus | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/11_LangGraph/notebooks/teaching_decks/teach_04_agent_reasoning_patterns.html) |
| 05 | [SQL agent](05_sql_agent_langgraph.ipynb) | S11e | Bonus | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/11_LangGraph/notebooks/teaching_decks/teach_05_sql_agent.html) |

**Notebook 03** starts the Session 10 MCP server at `../../10_RAG/notebooks/production_mcp_agents_rag_capstone/`. Install that `requirements.txt` if you skipped Notebook 16.

**Notebook 05** downloads `Chinook.db` on first run (gitignored).

- Slides: [`teaching_decks/`](teaching_decks/)
- Diagrams (04 / 05): [`assets/patterns/`](assets/patterns/) — regenerate with `python assets/generate_diagrams.py`
- Browser: [ReAct](https://nursnaaz.github.io/tutorial/one-tool-one-loop) · [HITL](https://nursnaaz.github.io/tutorial/human-in-the-loop) · [MCP](https://nursnaaz.github.io/tutorial/mcp-as-usb)

← [Session 11 README](../README.md)
