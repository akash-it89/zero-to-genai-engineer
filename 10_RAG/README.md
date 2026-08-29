<div align="center">

# Session 10 — RAG + Memory & Chatbots

### M07 Basics + M08 Production + M06 Memory · Complete

*Ground the model in **your** documents — then remember the conversation, and measure whether it actually did.*

[![LangChain](https://img.shields.io/badge/LangChain-1.0-1C3C3C?style=for-the-badge)](https://python.langchain.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-chunking-FF3600?style=for-the-badge)](https://www.llamaindex.ai/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

[Start here](#-start-here) · [Path](#-learning-path) · [Slides](https://nursnaaz.github.io/zero-to-genai-engineer/) · [Apps](#-run-the-apps) · [What's next](#-whats-missing-after-this-session)

</div>

---

> **What was MISSING from S09:** agentic coding lets an LLM *write* software. It still only knows training data. Ask it about *your* PDFs, policies, or tickets and it will guess.
>
> RAG is the fix: **retrieve the right passages first, then generate an answer grounded in those passages.**

Work **top to bottom**. Do not jump to Streamlit until notebooks **01–11** make sense.

**Memory & Chatbots (M06) ships here.** Notebook **11** is short-term memory, summarisation, long-term `Store`, streaming, guardrails, and HITL. Notebooks **13–14** turn that into a production Streamlit bot. Session 11 reuses those primitives.

---

## 🚀 Start here

```bash
cp 10_RAG/.env.example 10_RAG/.env          # paste OPENAI_API_KEY
cd 10_RAG/notebooks
pip install -r requirements.txt
```

Then open [Notebook 01](notebooks/01_why_rag_the_case_for_retrieval.ipynb) or the [Why RAG slides](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_01_why_rag.html).

**Browser labs (no API key, do these next to the matching notebook):** [Tiny RAG](https://nursnaaz.github.io/tutorial/tiny-rag) · [Chunking](https://nursnaaz.github.io/tutorial/chunking-intuition) · [Hybrid + RRF](https://nursnaaz.github.io/tutorial/hybrid-search-rrf) · [Citations and refusals](https://nursnaaz.github.io/tutorial/citations-and-refusals) · [RAG injection](https://nursnaaz.github.io/tutorial/rag-injection-guardrails) · [Chatbots forget](https://nursnaaz.github.io/tutorial/chatbots-forget) · [Production challenges](https://nursnaaz.github.io/tutorial/production-challenges)

Every notebook: [`notebooks/README.md`](notebooks/README.md).

---

## 🗺️ Learning path

```text
S10a  Why RAG
S10b  Chunking (LangChain) + same ideas in LlamaIndex
S10c  Embeddings → FAISS / Chroma / Pinecone
S10d  BM25 → hybrid (RRF) → reranking
S10e  RAGAS + DeepEval
S10f  Production chatbots = Memory & Chatbots (M06)
S10g  Retrieval showdown on a real Pinecone index
        │
        ├── 13–14  Production chatbot (+ memory)     capstone
        ├── 15      Multimodal RAG                    extra
        ├── 16      MCP helpdesk                      extra · needed for S11 Day 3
        ├── RAG Studio                                portfolio (FastAPI + React)
        └── student_group_datasets/                   9 cohort briefs
```

### Core (required) — S10a → S10g

| Day | Notebook | Topic | Slides |
|---|---|---|---|
| **S10a** | [01 — Why RAG](notebooks/01_why_rag_the_case_for_retrieval.ipynb) | Hallucination vs grounded retrieval | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_01_why_rag.html) |
| **S10b** | [02 — Chunking (LangChain)](notebooks/02_ingestion_and_chunking_langchain.ipynb) | 6 chunking strategies | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_02_ingestion_chunking.html) |
| S10b | [03 — Chunking (LlamaIndex)](notebooks/03_ingestion_and_chunking_llamaindex.ipynb) | Same ideas, second framework | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_03_ingestion_chunking_llamaindex.html) |
| **S10c** | [04 — Embeddings](notebooks/04_embeddings.ipynb) | Geometry of meaning | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_04_embeddings.html) |
| S10c | [05 — Vector databases](notebooks/05_vector_databases.ipynb) | FAISS → Chroma → Pinecone | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_05_vector_databases.html) |
| | Recap of 01–05 | | [▶ Revision](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/revision_notebooks_01_to_05.html) |
| **S10d** | [06 — Sparse retrieval](notebooks/06_sparse_retrieval.ipynb) | BM25 vs dense vs SPLADE | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_06_why_bm25.html) |
| S10d | [07 — Hybrid search](notebooks/07_hybrid_search.ipynb) | RRF / weighted fusion | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_07_why_hybrid.html) |
| S10d | [08 — Reranking](notebooks/08_reranking.ipynb) | Cross-encoder / FlashRank / Cohere | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_08_why_reranking.html) |
| **S10e** | [09 — RAGAS](notebooks/09_ragas_evaluation.ipynb) | Faithfulness, relevancy, context metrics | |
| S10e | [10 — DeepEval](notebooks/10_deepeval_evaluation.ipynb) | CI-native evals | |
| **S10f** | [11 — Production chatbots](notebooks/11_production_ready_chatbots.ipynb) | **M06:** memory, summarisation, Store, streaming, guardrails, HITL | [▶](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_11_production_chatbots.html) |
| **S10g** | [12 — Retrieval showdown](notebooks/12_retrieval_showdown_pinecone.ipynb) | Dense vs BM25 vs hybrid on one Pinecone index | |

Pipeline recap: [▶ Full pipeline](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_09_full_pipeline_recap.html).

### Capstones (after 01–12)

| Item | What it is | When |
|---|---|---|
| [13 — Production chatbot](notebooks/13_capstone_production_rag_chatbot.ipynb) ([student copy](notebooks/13_capstone_production_rag_chatbot_STUDENT.ipynb)) | Build `ProductionRAGChatbot` → [`production_rag_chatbot/`](notebooks/production_rag_chatbot/) | After NB11 |
| [14 — + memory](notebooks/14_capstone_production_rag_chatbot_memory.ipynb) ([student copy](notebooks/14_capstone_production_rag_chatbot_memory_STUDENT.ipynb)) | Durable memory on the same pipeline | After NB13 |
| [15 — Multimodal](notebooks/15_multimodal_rag_images.ipynb) ([slides](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_15_multimodal_rag.html)) | Images + text in one index | Extra |
| [16 — MCP helpdesk](notebooks/16_capstone_mcp_agents_rag.ipynb) | RAG + SQL tools over MCP | Extra · **required before S11 Day 3** |
| **[RAG Studio](capstone_rag_studio/)** | Swap retrieval strategies side by side. [Eval slides](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/capstone_rag_studio/reports/rag_strategy_evaluation_presentation.html) | Portfolio |
| **[Group datasets](student_group_datasets/)** | 9 real-company briefs | Cohort project |

---

## 📂 Folder map

```text
10_RAG/
├── README.md                          ← you are here
├── .env.example
├── notebooks/                         ← 01 → 16
│   ├── data/                          ← sample PDFs / HTML / eval corpora
│   ├── teaching_decks/                ← classroom HTML slides
│   ├── production_rag_chatbot/        ← Streamlit (NB13)
│   ├── production_rag_chatbot_memory/ ← Streamlit (NB14)
│   └── production_mcp_agents_rag_capstone/  ← MCP server (NB16 → S11)
├── capstone_rag_studio/               ← FastAPI + React
├── student_group_datasets/            ← 9 group briefs
└── reference/                         ← optional extra reading
```

Do **not** move `notebooks/production_*` — Session 11 imports them by this path.

---

## 🖥️ Run the apps

<p align="center">
  <img src="notebooks/production_rag_chatbot/docs/screenshots/app.png" alt="Production RAG Chatbot" width="920">
</p>
<p align="center"><em>Notebook 13 — hybrid retrieval, rerank, cited answers.</em></p>

<p align="center">
  <img src="notebooks/production_rag_chatbot_memory/docs/screenshots/app.png" alt="Production RAG Chatbot + Memory" width="920">
</p>
<p align="center"><em>Notebook 14 — the same engine, plus durable short-term and long-term memory.</em></p>

<p align="center">
  <img src="capstone_rag_studio/docs/screenshots/app.png" alt="RAG Studio Ingest" width="920">
</p>
<p align="center"><em>RAG Studio — swap every RAG stage, then compare and evaluate. See the [project README](capstone_rag_studio/README.md) for Chat, Strategies, and Eval shots.</em></p>

```bash
# After notebook 13
cd 10_RAG/notebooks/production_rag_chatbot && streamlit run app.py

# After notebook 14
cd 10_RAG/notebooks/production_rag_chatbot_memory && streamlit run app.py

# After notebook 16 (S11 Day 3 starts this)
cd 10_RAG/notebooks/production_mcp_agents_rag_capstone
python seed_data.py && python mcp_server.py
```

RAG Studio: [`capstone_rag_studio/README.md`](capstone_rag_studio/README.md) (Python + Node 18+).

---

## ➡️ What's MISSING after this session?

`ProductionRAGChatbot.chat()` is a **straight line**: retrieve → rerank → guardrail → generate. It cannot retry, rewrite, or pause.

That control flow is Session 11 — **[LangGraph](../11_LangGraph/)**.

**Prerequisites:** S00–S09 (especially S07 LangChain and S00/S01 retrieval). `OPENAI_API_KEY` for most notebooks. Pinecone / Cohere / Tavily only when a notebook says so.

---

<div align="center">

**Course nav:** [← S09 Agentic Coding](../09_AgenticCoding_LoopEngineering/) · [All sessions](../README.md) · [S11 LangGraph →](../11_LangGraph/)

</div>
