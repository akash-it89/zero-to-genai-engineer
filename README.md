<div align="center">

# 🤖 Zero to GenAI Engineer

### From complete beginner → production AI engineer — one module at a time.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Mohamed_Noordeen-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/nursnaaz)
[![GitHub](https://img.shields.io/badge/GitHub-nursnaaz-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nursnaaz)
[![AWS](https://img.shields.io/badge/AWS-GenAI_Innovation_Center-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://linkedin.com/in/nursnaaz)

**Real code · Real projects · Built to get you hired**

</div>

---

## 👨‍🏫 Your Instructor

<img align="right" src="https://github.com/nursnaaz.png" width="120" style="border-radius:50%"/>

**Mohamed Noordeen Alaudeen**

Data Scientist at **AWS Generative AI Innovation Center** · Dubai, UAE

- 🏆 **Emerging Global Leader in GenAI** — Internet 2.0 Conference Award (2024)
- 👥 **29,000+ LinkedIn followers** · 1,000+ professionals mentored
- 📚 **Published Author** — Packt Publishing (*Data Science Interview Questions*)
- 🎓 **IIM Lucknow** · 10+ years in AI/ML
- 🌍 Speaker at global AI conferences

> *"I built this course because I wanted students to learn GenAI the way professionals actually use it — not just theory, but real systems that get you hired."*

---

## 🧭 How to Follow This Course

| If you are… | Do this |
|---|---|
| **New / beginner** | Complete [`prereq/`](./prereq/) (~3 hrs), then start at **[S00](./00_How_Search_Engine_Works/)** and go session-by-session |
| **Catching up** | Use the [session table](#-sessions-shipped-so-far) below — open each folder’s README, run notebooks in order. For **S10 (RAG)**, finish notebooks **01–11** before the optional extras |
| **Fully caught up (through S11)** | Ship / polish the **[Self-Correcting Agentic RAG](./11_LangGraph/capstone_agentic_rag/)** portfolio project. **Next cohort topic: Memory & Chatbots (M06)** |

> Every session answers one question: *"What was missing from the last one?"*  
> That MISSING chain is what makes this a complete system — not a collection of tutorials.

New sessions drop every **Saturday / Sunday**. Star the repo to get notified. Questions → **WhatsApp cohort group**.

---

## 🗺️ The Curriculum

> **Two tracks, one goal.**  
> The **public sessions** in this repo (S00 onwards) are a free, open foundation track — released every weekend. The **23-module program** below is the full curriculum this repo is building towards.

### Where we are right now

| Status | Modules |
|---|---|
| ✅ **Complete & in this repo** | **M00–M05 · M07 · M08 · M10** (sessions **S00–S11**) |
| ⏭ **Next to teach** | **M06 — Memory & Chatbots** (sliding window · summarisation · system prompts · domain chatbot) |
| ⏸ **Deferred** | **M09 — LangChain Agents** (ReAct tool-calling already covered in S11a via `ToolNode` / `create_agent`) |

**Tip for students:** Day to day, follow **session folders** (`10_RAG/`, `11_LangGraph/`). Curriculum codes (M07, M10, …) are the long-term syllabus map — folder number is not always the same as module number (e.g. `10_RAG/` = Session S10 = modules **M07 + M08**; `11_LangGraph/` = Session S11 = module **M10**).

<details>
<summary><strong>What each completed module covers</strong> (click to expand)</summary>

<br>

- **M00 — Foundation (S00–S03):** TF-IDF search → embeddings → Transformer → GPT evolution & alignment (RLHF → DPO)
- **M01 — Modern LLM Internals (S04):** BPE from scratch · tiktoken · Temperature · Top-K · Top-P
- **M02 — Local LLMs & API Providers (S05):** Ollama · LM Studio · OpenRouter · Databricks · Distill project
- **M03 — Prompt Engineering + LangChain (S06a/b + S07):** DSPy signatures · CoT · few-shot optimisers · unified chat interface · LCEL · streaming
- **M04 — Prompt Optimization (S06c/d):** MIPROv2 · GEPA · full optimisation ladder
- **M05 — Agentic Coding (S09):** `/goal` · `/loop` · Kiro · Claude Code · deterministic verifiers
- **M07 — RAG Basics (S10a–c):** why RAG · LangChain + LlamaIndex chunking · embeddings · FAISS → Chroma → Pinecone
- **M08 — Production RAG (S10d–g + extras):** BM25 · hybrid · reranking · RAGAS/DeepEval · production chatbots · Pinecone showdown · RAG Studio
- **M10 — LangGraph (S11a–d):** `StateGraph` · HITL · multi-agent · self-correcting Agentic RAG · RAG-as-tools

</details>

### Sessions shipped so far

| Session | Module | Topic | What You Build | Released |
|---|---|---|---|---|
| [S00](./00_How_Search_Engine_Works/) | M00 Part 1a | How Search Engines Work | TF-IDF search engine from scratch | 2026-04-06 |
| [S01](./01_Text_to_Numbers/) | M00 Part 1b | Text to Numbers | Movie recommender with 5 embedding methods | 2026-04-13 |
| [S02](./02_Transformer_Architecture/) | M00 Part 2 | Transformer Architecture | Encoder-Decoder Transformer — English → Italian | 2026-04-19 |
| [S03](./03_GPT_Evolution_and_Alignment/) | M00 Part 3 ✅ | GPT Evolution & Alignment | GPT from scratch · 11 paper summaries · [▶ Slides](https://nursnaaz.github.io/zero-to-genai-engineer/03_GPT_Evolution_and_Alignment/GPT_Papers_Presentation.html) | 2026-04-27 |
| [S04a](./04_BPE_Temperature_Top_K_Top_P/) | M01 Day 1 | BPE Tokenization | BPE algorithm from scratch · tiktoken · token cost analysis | 2026-05-02 |
| [S04b](./04_BPE_Temperature_Top_K_Top_P/) | M01 Day 2 ✅ | Sampling Parameters | Temperature · Top-K · Top-P · softmax math · visualisations | 2026-05-03 |
| [S05a](./05_Local_LLMs_and_API_Providers/) | M02 Day 1 | Local LLMs & API Providers | Ollama · LM Studio · OpenRouter · Databricks · map-reduce summarizer | 2026-05-09 |
| [S05b](./05_Local_LLMs_and_API_Providers/) | M02 Day 2 ✅ | Distill Project | AI classroom assessment tool: transcript → adaptive quiz + voice debrief | 2026-05-10 |
| [S06a](./06_Prompt_Engineering_DSPY_GEPA_COT/) | M03 Part 1 | Prompt Writing + CoT + DSPy Signatures | `dspy.Signature` · `ChainOfThought` predictor · zero-shot baseline · ATIS intent classification · save/load prompts as JSON | 2026-06-06 |
| [S06b](./06_Prompt_Engineering_DSPY_GEPA_COT/) | M03 Part 2 | Few-Shot Optimisation | `LabeledFewShot` · `BootstrapFewShot` · `BootstrapFewShotWithRandomSearch` · `answer_exact_match` evaluation · side-by-side comparison | 2026-06-06 |
| [S06c](./06_Prompt_Engineering_DSPY_GEPA_COT/) | M04 Part 1 | MIPROv2 — Instruction Optimisation | `MIPROv2` optimizer · instruction text search · `auto="light"` mode · optimised instruction saved to `MiproV2Prompt.json` | 2026-06-06 |
| [S06d](./06_Prompt_Engineering_DSPY_GEPA_COT/) | M04 Part 2 ✅ | GEPA — Guided Error-Based Prompt Adaptation | Reflection model (`gpt-5`) · error diagnosis loop · prompt rewrite cycle · save to `GEPAPrompt.json` · Ollama variant | 2026-06-06 |
| [S07](./07_LangChain_Notebooks/) | M03 Part 3 ✅ | LangChain Fundamentals | Unified interface · OpenAI · Claude · Gemini · Ollama · `ChatPromptTemplate` · `InMemoryChatMessageHistory` · streaming · LCEL chain | 2026-06-13 |
| [S08](./08_Recap/) | Recap | Full Course Recap (S00–S07) | Visual recap of all 8 sessions: TF-IDF → Word2Vec → Transformers → GPT → BPE → Local LLMs → DSPy → LangChain · [▶ Slides](https://nursnaaz.github.io/zero-to-genai-engineer/08_Recap/RECAP_PRESENTATION.html) | 2026-06-20 |
| [S09a](./09_AgenticCoding_LoopEngineering/) | M05 Day 1 | Agentic Coding | History of agentic AI: Prompt Engineering → ReAct → AutoGPT → RALPH → Loop · What makes a good `/goal` · stop conditions · deterministic verifiers · **Kiro IDE** spec-driven workflow · **[Demo: Bullish Stock Scanner V3](https://github.com/nursnaaz/TechnicalStockPrediction/tree/feature/v3-high-precision)** | 2026-06-27 |
| [S09b](./09_AgenticCoding_LoopEngineering/) | M05 Day 2 ✅ | Loop Engineering | `/goal` vs `/loop` · 5-step loop pattern (Trigger → Action → Verify → Decide → Stop) · **Claude Code** workflow · full loop engineering playbook · **[→ Full Guide](./09_AgenticCoding_LoopEngineering/AGENTIC_CODING_GUIDE.md)** | 2026-06-28 |
| [S10a](./10_RAG/) | M07 Day 1 | The Case for RAG | Why LLMs need retrieval · hallucination under knowledge gaps · groundedness + traceability · [▶ Slides](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_01_why_rag.html) | 2026-07-05 |
| [S10b](./10_RAG/notebooks/02_ingestion_and_chunking_langchain.ipynb) | M07 Day 2 | Ingestion & Chunking — LangChain + LlamaIndex | 6 chunking strategies · same pipeline in [LangChain](./10_RAG/notebooks/02_ingestion_and_chunking_langchain.ipynb) and [LlamaIndex](./10_RAG/notebooks/03_ingestion_and_chunking_llamaindex.ipynb) · Contextual Retrieval | 2026-07-11 |
| [S10c](./10_RAG/notebooks/04_embeddings.ipynb) | M07 Day 3 | Embeddings & Vector Databases | Embeddings as geometry of meaning · [FAISS → Chroma → Pinecone](./10_RAG/notebooks/05_vector_databases.ipynb) · [▶ Revision Deck](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/revision_notebooks_01_to_05.html) | 2026-07-12 |
| [S10d](./10_RAG/notebooks/06_sparse_retrieval.ipynb) | M08 Day 1 | Sparse Retrieval, Hybrid Search & Reranking | BM25 vs dense vs SPLADE · RRF / weighted fusion · cross-encoder / FlashRank / Cohere reranking · [▶ Why BM25](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_06_why_bm25.html) · [▶ Why Hybrid](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_07_why_hybrid.html) · [▶ Why Reranking](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_08_why_reranking.html) | 2026-07-18 |
| [S10e](./10_RAG/notebooks/09_ragas_evaluation.ipynb) | M08 Day 2 | Evaluating RAG — RAGAS & DeepEval | Faithfulness · answer relevancy · context precision/recall · [DeepEval](./10_RAG/notebooks/10_deepeval_evaluation.ipynb) as CI-native eval | 2026-07-18 |
| [S10f](./10_RAG/notebooks/11_production_ready_chatbots.ipynb) | M08 Day 3 | Production-Ready RAG Chatbots | Memory · streaming · guardrails · human-in-the-loop · resilience · structured output · observability · pre-deploy testing | 2026-07-19 |
| [S10g](./10_RAG/notebooks/12_retrieval_showdown_pinecone.ipynb) | M08 Capstone | Retrieval Showdown — Live on Pinecone | Dense + BM25 + hybrid on **one real Pinecone index** · 10 adversarial queries · 6 rerankers compared | 2026-07-19 |
| [S10 extras](./10_RAG/) | M08+ | Capstones & deepening | Notebooks **13–16** (production chatbot + memory · multimodal RAG · MCP agents) · **[RAG Studio](./10_RAG/capstone_rag_studio/)** (FastAPI + React strategy workbench) · [9 student group datasets](./10_RAG/student_group_datasets/) | Optional |
| [S11a](./11_LangGraph/notebooks/01_langgraph_fundamentals_and_agents.ipynb) | M10 Day 1 | LangGraph Fundamentals & Agents | `StateGraph` · conditional edges · hand-built ReAct with `ToolNode` · `create_agent` · checkpointer memory · streaming (`values`/`updates`/`messages`) | 2026-08-15 |
| [S11b](./11_LangGraph/notebooks/02_human_in_the_loop_and_multi_agent.ipynb) | M10 Day 2 | Human-in-the-Loop & Multi-Agent | `interrupt()` + `Command(resume=...)` · long-term `Store` memory · multi-agent supervisor with `Command(goto=...)` | 2026-08-15 |
| [S11c](./11_LangGraph/notebooks/03_agentic_rag_capstone.ipynb) | M10 Capstone | Self-Correcting Agentic RAG | S10 RAG pipeline (`HybridIndex`, `Reranker`, …) wrapped in a LangGraph agent: retrieval grading · query rewrite · RAGAS Faithfulness gate · human escalation · Streamlit app in [`capstone_agentic_rag/`](./11_LangGraph/capstone_agentic_rag/) | 2026-08-15 |
| [S11d](./11_LangGraph/notebooks/04_rag_as_tools_agentic_retrieval.ipynb) | M10 Day 4 ✅ | RAG as Tools | Same S10 retrieval exposed as `@tool`s — the model chooses whether / what / how often to retrieve; then tools-inside-a-graph with a verification node the model can’t skip | 2026-08-15 |

---

### Full Curriculum — 23 Modules

The complete zero-to-production GenAI engineer track.

| Module | Topic | Covered In | Status | What Was Taught |
|---|---|---|---|---|
| M00 | Foundations: Search → Text → Transformers → GPT Evolution | S00–S03 | ✅ Complete | TF-IDF · Word2Vec · Self-attention · Encoder-Decoder · GPT-1/2/3 · RLHF · Constitutional AI · DPO |
| M01 | Modern LLM Internals: Tokenization & Sampling | S04 | ✅ Complete | BPE algorithm from scratch · tiktoken · Temperature · Top-K · Top-P · sampling visualisations |
| M02 | Local LLMs & API Providers | S05 | ✅ Complete | Ollama (local, free) · LM Studio (GUI) · OpenRouter (100+ models, one key) · Databricks (enterprise) · map-reduce pattern · Distill project |
| M03 | Prompt Engineering Fundamentals + LangChain | S06a/S06b + S07 | ✅ Complete | `dspy.Signature` · `ChainOfThought` · Zero-shot → Few-shot → `LabeledFewShot` · `BootstrapFewShot` · `BootstrapFewShotWithRandomSearch` · LangChain unified interface · `ChatPromptTemplate` · streaming · LCEL |
| M04 | Prompt Optimization: MIPROv2 & GEPA *(ad-hoc deep dive)* | S06c/S06d | ✅ Complete | **MIPROv2** instruction search · **GEPA** reflection / rewrite loop · full optimisation ladder (Zero-shot → BootstrapFewShot → MIPROv2 → GEPA) |
| M05 | Agentic Coding & Loop Engineering | S09 | ✅ Complete | Prompt Engineering → ReAct → AutoGPT → RALPH → Loop · `/goal` vs `/loop` · 5-step loop · deterministic verifiers · Kiro + Claude Code |
| M06 | Memory & Chatbots | — | ⏭ **Next** | Sliding window · summarisation memory · system prompt design · domain chatbot *(pieces already appear inside S10f; M06 makes them a dedicated foundation)* |
| M07 | RAG Basics | S10a–S10c | ✅ Complete | Why RAG · LangChain **and** LlamaIndex chunking (6 strategies) · embeddings · FAISS → Chroma → Pinecone |
| M08 | Production RAG | S10d–S10g (+ NB13–16, RAG Studio) | ✅ Complete | BM25 vs dense vs SPLADE · hybrid (RRF) · reranking · RAGAS + DeepEval · production chatbots · Pinecone showdown · strategy studio |
| M09 | LangChain Agents | — | ⏸ Deferred | ReAct / tools covered in **S11a** (`create_agent` / `ToolNode`) — dedicated M09 session deferred |
| M10 | LangGraph (Stateful Agents) | S11a–S11d | ✅ Complete | `StateGraph` · conditional routing · tool-calling agents · checkpointer · `interrupt()` HITL · `Store` · multi-agent supervisor · agentic RAG · RAG-as-tools |
| M11 | CrewAI (Multi-Agent Teams) | — | 🔜 | Agents · tasks · crews · hierarchical process · planning |
| M12 | MCP (Model Context Protocol) | — | 🔜 | Tools · resources · prompts · FastMCP server · Claude Desktop |
| M13 | Document Intelligence | — | 🔜 | PDF/Word/Excel parsing · OCR · structured extraction · document Q&A |
| M14 | Code Intelligence | — | 🔜 | AST analysis · code review pipeline · security scanning · test generation |
| M15 | Multimodal AI | — | 🔜 | Vision API · CLIP embeddings · visual document parsing · multimodal RAG |
| M16 | AI Research Assistant | — | 🔜 | Multi-source synthesis · citation tracking · research agent |
| M17 | FastAPI + Docker Deployment | — | 🔜 | REST API · containerisation · Hugging Face Spaces / Railway deploy |
| M18 | LLMOps & Evaluation | — | 🔜 | Langfuse tracing · RAGAS · LLM-as-judge · CI/CD eval |
| M19 | Guardrails & AI Safety | — | 🔜 | Input/output validation · prompt injection defence · content moderation |
| M20 | Fine-Tuning with LoRA/QLoRA | — | 🔜 | Unsloth · Together AI · PEFT · preference data · DPO fine-tuning |
| M21 | LlamaIndex Knowledge System | — | 🔜 | Knowledge graphs · query engines · agents · enterprise RAG |
| M22 | Capstone: End-to-End Business AI | — | 🔜 | Full production system combining M01–M21 |

---

## 📅 Session Changelog

| Date | Session | What Shipped |
|---|---|---|
| 2026-08-15 | **S11a–d** | **LangGraph (M10)** — fundamentals + tool-calling agents; `interrupt()` human-in-the-loop + multi-agent supervisor; **Self-Correcting Agentic RAG** capstone reusing the S10 (`10_RAG`) `HybridIndex`/`Reranker` pipeline; **S11d RAG-as-tools**. **[→ Module](./11_LangGraph/)** · **[→ Capstone App](./11_LangGraph/capstone_agentic_rag/)** · **[→ NB01](./11_LangGraph/notebooks/01_langgraph_fundamentals_and_agents.ipynb)** · **[→ NB02](./11_LangGraph/notebooks/02_human_in_the_loop_and_multi_agent.ipynb)** · **[→ NB03](./11_LangGraph/notebooks/03_agentic_rag_capstone.ipynb)** · **[→ NB04](./11_LangGraph/notebooks/04_rag_as_tools_agentic_retrieval.ipynb)** |
| 2026-07-19 | S10g | **Retrieval Showdown — Live on Pinecone (M08 Capstone)** — dense + BM25 + hybrid on one real Pinecone index; dense fails an exact-code lookup, hybrid recovers it; 6 rerankers compared. **[→ Notebook 12](./10_RAG/notebooks/12_retrieval_showdown_pinecone.ipynb)** |
| 2026-07-19 | S10f | **Production-Ready RAG Chatbots (M08 Day 3)** — short-term → persistent → long-term memory · streaming · guardrails · HITL · resilience · structured output · observability · pytest before deploy. **[→ Notebook 11](./10_RAG/notebooks/11_production_ready_chatbots.ipynb)** |
| 2026-07-18 | S10e | **Evaluating RAG — RAGAS & DeepEval (M08 Day 2)** — four RAGAS metrics with planted defects; DeepEval as CI-native pytest evals. **[→ NB09](./10_RAG/notebooks/09_ragas_evaluation.ipynb)** · **[→ NB10](./10_RAG/notebooks/10_deepeval_evaluation.ipynb)** |
| 2026-07-18 | S10d | **Sparse Retrieval, Hybrid Search & Reranking (M08 Day 1)** — BM25 vs dense vs SPLADE · RRF · reranking. **[▶ Why BM25](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_06_why_bm25.html)** · **[▶ Why Hybrid](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_07_why_hybrid.html)** · **[▶ Why Reranking](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_08_why_reranking.html)** · **[→ NB06–08](./10_RAG/notebooks/)** |
| 2026-07-12 | S10c | **Embeddings & Vector Databases (M07 Day 3)** — FAISS → Chroma → Pinecone · [▶ Revision Deck](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/revision_notebooks_01_to_05.html). **[→ NB04](./10_RAG/notebooks/04_embeddings.ipynb)** · **[→ NB05](./10_RAG/notebooks/05_vector_databases.ipynb)** |
| 2026-07-11 | S10b | **Ingestion & Chunking (M07 Day 2)** — LangChain + LlamaIndex twins · 6 chunking strategies. **[→ NB02](./10_RAG/notebooks/02_ingestion_and_chunking_langchain.ipynb)** · **[→ NB03](./10_RAG/notebooks/03_ingestion_and_chunking_llamaindex.ipynb)** |
| 2026-07-05 | S10a | **The Case for RAG (M07 Day 1)** — why retrieval · grounded chain. **[▶ Slides](https://nursnaaz.github.io/zero-to-genai-engineer/10_RAG/notebooks/teaching_decks/teach_01_why_rag.html)** |
| 2026-06-28 | S09b | **Loop Engineering (M05 Day 2)** — `/goal` vs `/loop` · Claude Code workflow · playbook. **[→ Guide](./09_AgenticCoding_LoopEngineering/AGENTIC_CODING_GUIDE.md)** |
| 2026-06-27 | S09a | **Agentic Coding (M05 Day 1)** — Prompt→ReAct→AutoGPT→RALPH→Loop · Kiro specs · [Bullish Stock Scanner V3](https://github.com/nursnaaz/TechnicalStockPrediction/tree/feature/v3-high-precision) |
| 2026-06-20 | S08 | **Full Course Recap** — S00–S07. **[▶ Presentation](https://nursnaaz.github.io/zero-to-genai-engineer/08_Recap/RECAP_PRESENTATION.html)** · **[▶ Slides](https://nursnaaz.github.io/zero-to-genai-engineer/08_Recap/RECAP_SLIDES.html)** |
| 2026-06-13 | S07 | **LangChain Fundamentals (M03 Part 3)** — OpenAI · Claude · Gemini · Ollama · templates · history · streaming · LCEL |
| 2026-06-06 | S06a–d | **DSPy → MIPROv2 → GEPA (M03–M04)** — signatures · CoT · few-shot optimisers · instruction search · reflection rewrite · JSON prompt artifacts |
| 2026-05-09 → 10 | S05 | **Local LLMs & Distill (M02)** — 6 provider notebooks · Distill classroom assessment product |
| 2026-05-02 → 03 | S04 | **BPE & Sampling (M01)** — BPE from scratch · temperature / top-k / top-p · Excel workbooks |
| 2026-04-06 → 27 | S00–S03 | **Foundations (M00)** — TF-IDF · embeddings · Transformer · GPT & alignment papers |
| 2026-04-03 | Prereq | Python for GenAI · Math Intuition · Neural Networks + cheat sheet |

---

## 🏗️ Projects Built in This Course

Real applications built during the course — open source, forkable, contribution-ready.

| Project | Session | Description | Stack |
|---|---|---|---|
| **[Self-Correcting Agentic RAG](./11_LangGraph/capstone_agentic_rag/)** | S11c–d — M10 | Flagship portfolio project: S10 hybrid RAG reused unmodified, wrapped in a LangGraph agent that grades retrievals, rewrites weak queries, self-checks with RAGAS Faithfulness, escalates to a human via `interrupt()`, and can also run retrieval as tools. Streamlit app with live agent-trace panel + pytest suite. | LangGraph · LangChain · OpenAI · RAGAS · Streamlit · ChromaDB · `bm25s` |
| **[RAG Studio](./10_RAG/capstone_rag_studio/)** | S10 — M08 | Swap retrieval strategy variants side-by-side · Chat & Compare · RAGAS/DeepEval evaluation · governance | FastAPI · React · RAGAS · DeepEval |
| **[Retrieval Showdown — Live on Pinecone](./10_RAG/notebooks/12_retrieval_showdown_pinecone.ipynb)** | S10g — M08 | Dense vs BM25 vs hybrid on one real Pinecone index — including dense failing an exact-code lookup and hybrid recovering it | Pinecone · `bm25s` · SPLADE · Sentence-Transformers · Cohere · OpenAI |
| **[Distill](./05_Local_LLMs_and_API_Providers/distill/)** | S05 — M02 | AI classroom assessment: transcript → structured summary → adaptive MCQ + “Teach It Back” voice interview → personalised debrief | FastAPI · React · Ollama / LM Studio · OpenAI Whisper · Jinja2 |
| **[Bullish Stock Scanner V3](https://github.com/nursnaaz/TechnicalStockPrediction/tree/feature/v3-high-precision)** | S09 — M05 | Precision-first stock analysis built entirely through agentic coding (Kiro + Claude Code) · 308-test suite | FastAPI · React · AWS Cloudscape · SQLite · Polygon.io |
| **[CineMatch Movie Recommender](./01_Text_to_Numbers/movie_recommender/)** | S01 — M00 | Movie recommendations with 5 embedding methods + cosine similarity | FastAPI · React |
| **[Holmes GPT](./03_GPT_Evolution_and_Alignment/holmes_gpt_ui.py)** | S03 — M00 | GPT trained from scratch on the Sherlock Holmes corpus — interactive generation UI | PyTorch · Streamlit |
| **[Multi-Provider Race](./05_Local_LLMs_and_API_Providers/apps/multi_provider_race.py)** | S05 — M02 | Same prompt → multiple providers · compare speed + quality | Ollama · OpenRouter · Databricks |
| **[Map-Reduce Summarizer](./05_Local_LLMs_and_API_Providers/apps/map_reduce_demo.py)** | S05 — M02 | Summarize documents longer than the context window | OpenRouter · LangChain |

### ⭐ Contribute to Distill

Distill is a live open-source project built in this course. Contributing is part of the curriculum.

- **Study / run here:** [`05_Local_LLMs_and_API_Providers/distill/`](./05_Local_LLMs_and_API_Providers/distill/)
- **Open a PR on the live repo:** [Contribution Guide](https://github.com/nursnaaz/distill/blob/main/CONTRIBUTING.md)

The guide walks you through forking, branching, opening a PR, and responding to review — the exact workflow used at every AI company. Mohamed reviews every PR personally.

---

## 🎮 Interactive Tutorials

Hands-on tutorials you can run in your browser — no setup, no install. Best used with **S00–S02**.

| Tutorial | Session | Level | Time |
|---|---|---|---|
| [How Search Engines Work](https://nursnaaz.github.io/tutorial/how-search-engines-work) | S00 | Beginner | 45 min |
| [Cosine Similarity & Movie Recommender](https://nursnaaz.github.io/tutorial/cosine-similarity-movie-recommender) | S01 | Beginner | 45 min |
| [Self-Attention Mechanism](https://nursnaaz.github.io/tutorial/self-attention) | S02 | Beginner | 30 min |
| [Positional Encoding](https://nursnaaz.github.io/tutorial/positional-encoding) | S02 | Beginner | 35 min |
| [Multi-Head Attention](https://nursnaaz.github.io/tutorial/multi-head-attention) | S02 | Intermediate | 60 min |

👉 **Full tutorial library:** [nursnaaz.github.io](https://nursnaaz.github.io)

---

## 🚀 Start Here — Pre-work (Beginners)

**New to Python, ML, or AI?** Complete the pre-work first — takes ~3 hours.

📁 **[→ Go to Pre-work](./prereq/)**

| Notebook | What You Learn | Time |
|---|---|---|
| [01 — Python for GenAI](./prereq/notebooks/01_python_for_genai.ipynb) | Variables, loops, functions, dicts, f-strings | 60 min |
| [02 — Math Intuition](./prereq/notebooks/02_math_intuition.ipynb) | Vectors, dot product, softmax | 60 min |
| [03 — Neural Networks](./prereq/notebooks/03_neural_networks_intuition.ipynb) | How models learn — in plain English | 60 min |

After the notebooks, read the **[Cheat Sheet](./prereq/cheatsheet.md)** — keep it open during S00.

---

## 🛠️ Tech Stack

| Purpose | Tool | First Used |
|---|---|---|
| Cloud LLMs | OpenAI · Anthropic · Gemini | S04–S07 |
| Multi-model access | OpenRouter | S05 |
| Local LLMs | Ollama · LM Studio | S05 |
| Enterprise LLMs | Databricks | S05 |
| Tokenization | tiktoken | S04 |
| Prompt optimisation | DSPy (MIPROv2 · GEPA) | S06 |
| App framework | LangChain · LCEL | S07 |
| Agentic coding | Claude Code · Kiro | S09 |
| RAG ingestion | LangChain · LlamaIndex · pypdf · Unstructured · RapidOCR | S10 / M07 |
| RAG retrieval | FAISS · ChromaDB · Pinecone · Sentence Transformers · `bm25s` · SPLADE | S10 / M07–M08 |
| RAG fusion & reranking | RRF · Cross-Encoders · FlashRank · Cohere · Pinecone rerank | S10 / M08 |
| RAG evaluation | RAGAS · DeepEval | S10 / M08 |
| Stateful agents | LangGraph | S11 / M10 |
| UI / APIs | Streamlit · FastAPI · React *(selected projects)* | S01+ |

**Coming later:** CrewAI · MCP · Langfuse · Unsloth / Together AI · Docker deploy

---

<div align="center">

*Built with ❤️ by Mohamed Noordeen Alaudeen &nbsp;|&nbsp; AWS GenAI Innovation Center*

⭐ **Star this repo** if you find it useful — it helps others discover it.

Questions? Ask in the **WhatsApp cohort group**.

</div>
