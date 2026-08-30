<div align="center">

# Session 13 — Dining Bot (capstone)

### One restaurant manager assistant. RAG + SQL + HITL + Weather/Chart + Deep Agents planning.

</div>

---

**MISSING from S12:** Deep Agents gave you files, `AGENT.md`, and `SKILL.md`. Dining Bot is the product: one chat that answers from **documents** (RAG) or **tables** (read-only SQL), draws a chart, checks the weather, **adds a menu item only after a human says yes**, and for **multi-step “plan the week…”** work hands off to **`create_deep_agent()`**.

| File | What it is |
|---|---|
| [`dining_bot.py`](./dining_bot.py) | **Teach this one file** top → bottom (SECTION 0→8) |
| [`AGENT.md`](./AGENT.md) | Standing rules for the PLANNING harness |
| [`skills/weekly-ops-plan/SKILL.md`](./skills/weekly-ops-plan/SKILL.md) | On-demand skill for weekly ops plans |
| [`sample_docs/`](./sample_docs/) | **Real files:** `docx/`, `xlsx/`, `pptx/`, `pdf/` — parsed by `build_db.py` (M11-style) |
| [`generate_sample_docs.py`](./generate_sample_docs.py) | Regenerates the multi-format corpus |
| [`Dining_Bot_Requirement_v1.1.docx`](./Dining_Bot_Requirement_v1.1.docx) | The full spec |
| [`build_db.py`](./build_db.py) | Rebuilds `dining_bot.db` (`random.seed(42)`) |
| [`requirements.txt`](./requirements.txt) | Pins (needs **Python ≥3.11**) |

## Run (classroom)

```bash
cd 13_Project_Implementation
python3.11 -m venv .venv          # deepagents needs 3.11+
source .venv/bin/activate
pip install -r requirements.txt
python generate_sample_docs.py    # docx/xlsx/pptx/pdf (build_db auto-runs if missing)
python build_db.py
# OPENAI_API_KEY in ../10_RAG/.env (or a local .env)
streamlit run dining_bot.py
```

Optional MCP children (same file):

```bash
python dining_bot.py --mcp weather
python dining_bot.py --mcp chart
```

## Teaching map (`dining_bot.py`)

| SECTION | Story |
|---|---|
| 0 | Trusted restaurant context (never from the LLM) |
| 1 | Read-only vs write SQLite doors |
| 2 | sqlglot SELECT-only guard |
| 3 | In-process RAG + code-built citations |
| 4 | Weather + Chart as `--mcp` servers |
| 5 | ADD_MENU_ITEM + HITL `interrupt` |
| 6 | **Deep Agents** PLANNING (`AGENT.md` + skills + tools) |
| 7 | LangGraph router → FR intents **or** PLANNING |
| 8 | Streamlit + golden demos |

**Two rules (do not break them):**

1. SQL facts stay in SQL. Policies stay in documents. The router must not mix those.
2. The LLM never writes mutating SQL. The only DB write is **add menu item**, after HITL. Deep Agents may write **markdown plans** under `plans/` — not the database.

← [Course README](../README.md) · [S12 Deep Agents](../12_deepagents/)
