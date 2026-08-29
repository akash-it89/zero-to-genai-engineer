<div align="center">

# Session 12 — Why Deep Agents

### You have LangChain and LangGraph. This is what they cannot do without you building it by hand.

</div>

---

Official: [overview](https://docs.langchain.com/oss/python/deepagents/overview) · [memory](https://docs.langchain.com/oss/python/deepagents/memory) · [skills](https://docs.langchain.com/oss/python/deepagents/skills) · [subagents](https://docs.langchain.com/oss/python/deepagents/subagents) · [the three layers](https://www.langchain.com/blog/deep-agents-vs-langchain-vs-langgraph)

**Proof:** LangChain answers in chat (no file). LangGraph needs a new Python step for every “also add eggs.” `create_deep_agent()` is still a LangGraph graph, with file tools, `AGENT.md`, `SKILL.md`, your tools, and helpers already attached.

Notebook: five examples on a fake shop (Gulf Mart).

| # | Feature | What to see |
|---|---|---|
| 1 | `write_file` / `edit_file` | `shopping.md` then eggs appear **without** `add_node` |
| 2 | `/AGENT.md` (memory) | “Gulf Mart” appears though the user never said it. `memory=["/AGENT.md"]` + seed in `files=`. `MemorySaver` needs `thread_id`. |
| 3 | `SKILL.md` | `INV-001` appears from the how-to file, not from Python |
| 4 | Your `tools=` + file tools | `get_store_hours` lands in `hours.md` |
| 5 | Subagent | Helper lists prices in its own empty chat |

```bash
cp 12_deepagents/.env.example 12_deepagents/.env
cd 12_deepagents/notebooks
pip install -r requirements.txt
```

**Classroom slides:** [`notebooks/teaching_decks/teach_01_why_deep_agents.html`](notebooks/teaching_decks/teach_01_why_deep_agents.html) — food delivery: LLM vs agent vs harness, then `AGENTS.md` / `SKILL.md`. [GitHub Pages](https://nursnaaz.github.io/zero-to-genai-engineer/12_deepagents/notebooks/teaching_decks/teach_01_why_deep_agents.html)

Open [`notebooks/01_langchain_langgraph_deepagents.ipynb`](notebooks/01_langchain_langgraph_deepagents.ipynb). Kernel → Restart after first `%pip install`.

← [Course README](../README.md)
