<div align="center">

# Session 13 — Dining Bot (capstone)

### One restaurant manager assistant. RAG + SQL + HITL + two MCP servers. You already built every piece.

</div>

---

**MISSING from S12:** Deep Agents gives you files, `AGENT.md`, and `SKILL.md`. Dining Bot is the product: one chat that answers from **documents** (RAG) or **tables** (read-only SQL), draws a chart, checks the weather, and **adds a menu item only after a human says yes**.

This folder is the **requirement + sample database**. You implement the app (LangGraph from S11; Deep Agents from S12 is optional, not required).

| File | What it is |
|---|---|
| [`Dining_Bot_Requirement_v1.1.docx`](./Dining_Bot_Requirement_v1.1.docx) | The spec. Read this first. |
| [`README_DATABASE.md`](./README_DATABASE.md) | How the SQLite sample DB is shaped |
| [`schema.sql`](./schema.sql) | Tables / indexes |
| [`build_db.py`](./build_db.py) | Rebuilds `dining_bot.db` (deterministic, `random.seed(42)`) |
| [`QUERIES.sql`](./QUERIES.sql) | 15 analytics SELECTs the SQL path should be able to produce |
| [`files.zip`](./files.zip) | Same sources **plus** a pre-built `dining_bot.db` (Git ignores `*.db`, so unzip this if you do not want to run the generator) |

```bash
cd 13_Project_Implementation
python3 build_db.py          # writes dining_bot.db next to this README
# or: unzip files.zip
```

**Two rules from the spec (do not break them):**

1. Facts that live in SQL stay in SQL. Policies / SOPs live in `documents` (RAG). The router must not mix those.
2. The LLM never writes SQL that changes data. The only write is **add menu item**, as a structured action, after HITL.

← [Course README](../README.md) · [S12 Deep Agents](../12_deepagents/)
