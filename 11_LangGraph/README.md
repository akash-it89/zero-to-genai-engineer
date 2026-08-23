# Session 11 — LangGraph (Stateful Agents)
### M10 — Complete

> **What was MISSING from S10:** Module 10 built a genuinely production-grade RAG pipeline —
> hybrid retrieval, reranking, a groundedness guardrail, conversational memory — but
> `ProductionRAGChatbot.chat()` is a **straight line**: retrieve → rerank → guardrail →
> generate, every time, no matter what. It can't retry a bad retrieval, can't rewrite a vague
> question, can't pause and ask a human when it's genuinely stuck, and its "memory" is a
> Python list living inside one process. LangGraph is the fix: it turns that straight line
> into a **graph with cycles, persistent state, and a pause button** — which is exactly what
> "agent" means once you stop hand-waving the word.

> **Where this sits relative to S10f:** Module 10's Notebook 11 already used `create_agent` +
> LangChain 1.0's `middleware=` system to add memory, `HumanInTheLoopMiddleware`,
> `ModelRetryMiddleware`/`ModelFallbackMiddleware`, `Store`-backed long-term memory, and
> `response_format=ProviderStrategy(schema=...)` structured output — all of that is real,
> already built, and this module doesn't re-teach it. What `create_agent` + middleware
> *doesn't* give you is custom, multi-step control flow specific to your own business logic —
> there's no `RetrievalGradingMiddleware` or `QueryRewriteMiddleware`, because "grade this
> retrieval, rewrite the query, try again, then escalate" isn't a generic concern any
> off-the-shelf middleware could anticipate. That's a `StateGraph` you build yourself. This
> module teaches the primitives (`interrupt()`, `Command`, `checkpointer`, `Store`) that both
> `create_agent`'s middleware *and* the capstone's bespoke retry loop are built from — so you
> can reach for a middleware when the concern is generic, and hand-build a graph when it isn't.

---

## What This Session Covers

| Day | Topic | Key Concepts |
|-----|-------|--------------|
| S11a | LangGraph Fundamentals & Agents | `StateGraph`, nodes, edges, conditional routing, `add_messages` reducer, tool-calling agents (`ToolNode`, `create_agent`), checkpointer memory, streaming |
| S11b | Human-in-the-Loop & Multi-Agent | `interrupt()` / `Command(resume=...)`, long-term memory (`Store`), supervisor pattern with `Command(goto=...)` handoffs |
| S11c | Capstone — Agentic RAG | Every Module 10 building block (hybrid search, rerank, groundedness) reused inside a self-correcting LangGraph agent: query rewriting, retrieval grading, hallucination checks, human escalation |

---

## Contents

| File | Description |
|------|--------------|
| `notebooks/01_langgraph_fundamentals_and_agents.ipynb` | Graphs, state, conditional edges, tool-calling agents, memory, streaming |
| `notebooks/02_human_in_the_loop_and_multi_agent.ipynb` | `interrupt()`-based approval flows, long-term memory, supervisor multi-agent pattern |
| `notebooks/03_agentic_rag_capstone.ipynb` | **Flagship project** — Self-Correcting Agentic RAG, built on top of the Module 10 pipeline, then hardened with the rest of the Module 10 toolkit |
| `capstone_agentic_rag/` | The production graph (`graph.py`), a Streamlit app (`app.py`), and a no-API-key pytest suite (`tests/test_graph.py`) |

---

## Why LangGraph (not just LangChain / LCEL)

An LCEL chain (`prompt \| llm \| parser`) is a **DAG that runs once, forward, and stops.**
That's fine for "retrieve then answer." It falls apart the moment the task needs any of:

- **Loops** — "try again with a better query" (LCEL has no way back to an earlier step)
- **Branching on model output** — "if the answer isn't grounded, regenerate; if it's still
  bad, ask a human" (conditional logic belongs in code, not a pipe chain)
- **Durable, resumable state** — pause mid-task (approval, rate limit, crash) and resume
  *exactly where it left off*, not from the top
- **Multiple cooperating agents** — a supervisor that hands work to specialists and gets
  control back

LangGraph models the whole thing as a **graph**: `State` (a typed, shared scratchpad) flows
through `Nodes` (plain Python functions) connected by `Edges` (including conditional ones
that branch on the current state). A `Checkpointer` snapshots that state after every node,
which is what makes memory, crash-recovery, and human-in-the-loop all the same mechanism
instead of three separate features.

---

## Key Concepts & Latest API (verified against LangChain/LangGraph docs, Aug 2026)

LangChain and LangGraph both shipped **v1.0** in 2026. The headline change: `create_agent`
(in the `langchain` package) is now the recommended way to build a tool-calling agent —
built *on top of* the LangGraph runtime, with a middleware system for customizing the loop.
`create_react_agent` (in `langgraph.prebuilt`) still works but is the legacy prebuilt; we
teach the underlying `StateGraph` mechanics first so students understand what either
high-level API is doing for them, not just how to call it.

| Concept | Import | What it does |
|---|---|---|
| `StateGraph` | `langgraph.graph` | Declares the state schema, then `add_node` / `add_edge` / `add_conditional_edges` / `compile()` |
| `START`, `END` | `langgraph.graph` | Sentinel nodes marking graph entry/exit |
| `MessagesState`, `add_messages` | `langgraph.graph` | Prebuilt chat-history state + reducer that appends instead of overwriting |
| `create_agent` | `langchain.agents` | LangChain 1.0's high-level agent builder — model + tools + middleware, built on `StateGraph` |
| `create_react_agent` | `langgraph.prebuilt` | Legacy prebuilt ReAct agent (still supported; `create_agent` is now recommended for new code) |
| `ToolNode`, `tools_condition` | `langgraph.prebuilt` | Executes tool calls the model requested; routes back to the model or to `END` |
| `Command` | `langgraph.types` | A node's return value that both updates state **and** picks the next node (`goto=`) — this is how multi-agent handoffs work |
| `Send` | `langgraph.types` | Fans one node out into N parallel node executions (map-reduce over a list) |
| `interrupt()` | `langgraph.types` | Pauses the graph mid-node, surfaces a payload to the caller, and waits — the primitive behind every human-in-the-loop pattern |
| `Command(resume=...)` | `langgraph.types` | Resumes a graph paused by `interrupt()`, feeding the human's response back into the exact node that asked |
| `MemorySaver` / `InMemorySaver` | `langgraph.checkpoint.memory` | In-process checkpointer — short-term memory keyed by `thread_id` |
| `Store` (`InMemoryStore`) | `langgraph.store.memory` | Cross-thread, long-term memory (user facts that outlive a single conversation) |
| `graph.stream(..., stream_mode=...)` | — | `"values"` (full state each step), `"updates"` (diff per node), `"messages"` (LLM tokens) |
| `create_supervisor` | `langgraph_supervisor` (companion package) | One-line supervisor multi-agent setup on top of the same `Command(goto=...)` handoff mechanism |

**Sources consulted:**
- [LangChain & LangGraph Reach v1.0](https://www.langchain.com/blog/langchain-langgraph-1dot0)
- [Interrupts — Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Making it easier to build human-in-the-loop agents with interrupt](https://www.langchain.com/blog/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt)
- [create_react_agent reference](https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent)
- [Self-Reflective RAG with LangGraph](https://www.langchain.com/blog/agentic-rag-with-langgraph)
- [Human-in-the-loop — Docs by LangChain](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

Because framework APIs move fast, every notebook's install cell pins nothing tighter than
`langgraph>=0.6` / `langchain>=1.0` and prints the installed version on import — if an
import in these notebooks breaks against a newer release, that printed version number is
the first thing to check.

---

## How to Teach This Effectively — the Plan

**1. Never open with the framework. Open with the pain.**
Re-run `ProductionRAGChatbot.chat()` from Module 10 live, on a question deliberately chosen
to need a second retrieval attempt (too vague the first time). Watch it confidently return
a weak, unguarded answer because it has no way to say "let me try that search again." *That
gap* is the entire motivation for S11 — don't state it, show it.

**2. Build the mental model before the API.**
Draw the graph on a whiteboard/slide before writing code: boxes (nodes) and arrows (edges),
one arrow forking into two with a diamond (conditional edge), one arrow pointing backward
(the loop LCEL couldn't do). Only once students can draw an agent's control flow by hand
should the `StateGraph` API show up — it's then just syntax for a picture they already
understand.

**3. Teach the primitive under every "magic" helper.**
`create_agent` and `create_react_agent` both hide a `StateGraph` with a model node, a tools
node, and a conditional edge between them. Build that graph by hand first (S11a Section 3)
so the prebuilt helpers read as "the same four lines, packaged" instead of a black box.

**4. Make state visible, always.**
After every graph run, print the full state dict and — separately — call
`graph.get_graph().draw_mermaid()` to render the actual graph. Students should never have to
imagine what the graph looks like or what's in state; both are one line of code away, every
single time.

**5. HITL and memory are the payoff, not a bonus topic — and be precise about what's genuinely new.**
Don't teach `interrupt()` as if S10 never touched it — Notebook 11 (S10f) already built a
full working `interrupt()` + `Command(resume=...)` approval flow via
`HumanInTheLoopMiddleware`, and used `checkpointer=`/`Store` for memory on `create_agent`.
Overclaiming novelty here is a fast way to lose credibility with students who just did that
notebook. The honest framing: S10f showed the *packaged* version for a generic concern
(approve-this-one-tool-call); S11 shows the *primitive* it's built from, applied to a
decision no generic middleware could package — "we retried retrieval and generation and are
still not confident, escalate to a human." Same precision for memory: `ProductionRAGChatbot`
(Notebook 13 specifically, not all of S10) stored history in a plain `self.history` list that
dies when the process exits — *that* comparison is fair game; S10f's own `checkpointer=`
usage is not something to reinvent, only to point back to.

**6. The capstone must extend prior work, not restart from a tutorial.**
The flagship project (`03_agentic_rag_capstone.ipynb`) literally imports
`HybridIndex`, `Reranker`, and the exact prompts from
`10_RAG/notebooks/production_rag_chatbot/rag_pipeline.py`. Nothing about retrieval, fusion,
or reranking is retaught — LangGraph's job is to add what a straight Python chain
structurally cannot (retry loops, self-grading, a human escape hatch), and to give the rest
of Module 10's production concerns (RAGAS scoring, resilience, token budget, long-term
memory, structured output) a place to live as real graph nodes instead of scattered
standalone demos. Students should leave seeing LangGraph as "the orchestration layer on top
of what I already built," not a separate, disconnected framework.

**7. Assess with a trace, not just a final answer.**
Because state and node transitions are fully inspectable, grade the *path* the agent took —
did it correctly grade a weak retrieval as insufficient? did it rewrite the query sensibly?
did it escalate instead of confidently hallucinating? — not only whether the final answer
looks right. A correct answer reached by skipping the grading step is a bug, not a pass.

---

## Real-World Use Cases for LangGraph (beyond this capstone)

| Use case | Why a graph, not a chain |
|---|---|
| **Customer support triage** | Router node classifies the ticket; billing/technical/refund specialist subgraphs handle it; a supervisor collects and merges results |
| **Code review agent** | Loop: run linter/tests → if failing, ask the model to fix → re-run → stop only when green (the exact "5-step loop pattern" from S09, now as a graph) |
| **Approval-gated automation** (send email, execute a trade, delete a record) | `interrupt()` before the risky tool call; a human approves, edits, or rejects before the graph resumes |
| **Deep research agent** | `Send` fans a topic out into parallel sub-searches; results are reduced back into one report node |
| **Long-running personal assistant** | `Store`-backed long-term memory recalls user preferences across sessions that started days apart |

---

## Capstone — Self-Correcting Agentic RAG

**The pitch:** the full Module 10 toolkit — hybrid retrieval, RRF fusion, cross-encoder
reranking, the `min_rerank_score` guardrail, condense-question memory, RAGAS faithfulness
scoring, token-budget trimming, long-term `Store` memory, resilient LLM calls, and structured
output — reused, not re-taught (see the coverage map below for exactly where each one lives),
wrapped in a LangGraph agent that can now do what a straight pipeline never could:

```
        ┌────────────┐
        │  condense  │  (memory-aware question rewrite)
        └─────┬──────┘
              ▼
        ┌────────────┐
   ┌───▶│  retrieve  │  (Module 10's HybridIndex + Reranker, verbatim)
   │    └─────┬──────┘
   │          ▼
   │   ┌───────────────┐   insufficient, retries left
   │   │grade_documents│───────────────────┐
   │   └─────┬─────────┘                   ▼
   │      sufficient              ┌────────────────┐
   │          ▼                   │  rewrite_query │
   │    ┌────────────┐            └───────┬────────┘
   │    │  generate  │◀───────────────────┘
   │    └─────┬──────┘
   │          ▼
   │  ┌───────────────────┐  not grounded, retries left
   │  │ check_groundedness│──────────────────┐
   │  └─────┬─────────────┘                  │
   │     grounded                            ▼
   │        │                    retries exhausted (either check)
   │        ▼                                ▼
   │      END                     ┌────────────────────┐
   └───────────────────────────── │  human_escalation   │
                                   │     interrupt()      │
                                   └──────────┬───────────┘
                                              ▼
                                             END
```

The diagram above is the **core teaching graph**, built inline in the notebook so the
self-correction mechanism is easy to follow line by line. `capstone_agentic_rag/graph.py`
ships the **production version**: two more nodes up front (`trim_history`,
`recall_preferences`) and several nodes hardened with the rest of what Module 10 taught — see
the coverage map below for exactly what and where.

Run it end to end in `notebooks/03_agentic_rag_capstone.ipynb`, then ship it as a chat app
from `capstone_agentic_rag/` (`streamlit run app.py`) — including a live trace panel showing
which nodes fired, how many retries happened, and why (if it happened) the agent handed off
to a human instead of guessing.

---

## Coverage Map — Every Module 10 Tool, and Where It Lives Here

An honest accounting, not a marketing claim: what's genuinely wired into the capstone, and
what's a deliberate extension point rather than a re-implementation.

| Module 10 tool / technique | Notebook it was taught in | Used in M11 how |
|---|---|---|
| Recursive chunking | S10b (Notebook 02) | Reused via `chunk_documents()`, imported unmodified |
| Dense embeddings (bge-small) + Chroma | S10c (Notebooks 04/05) | Reused via `HybridIndex`, imported unmodified |
| BM25 sparse retrieval | S10d (Notebook 06) | Reused via `HybridIndex`, imported unmodified |
| RRF hybrid fusion | S10d (Notebook 07) | Reused via `HybridIndex.search()`, imported unmodified |
| Cross-encoder reranking | S10d (Notebook 08) | Reused via `Reranker`, imported unmodified |
| `min_rerank_score` guardrail | Notebook 13 (`ProductionRAGChatbot`) | `grade_documents()` — fast heuristic pre-filter before the LLM judge |
| **RAGAS Faithfulness** | S10e (Notebook 09) | `check_groundedness()` — the actual metric, scored live per turn, not just offline (falls back to an LLM-judge prompt if `ragas` isn't installed) |
| Condense-question memory | Notebook 13 (`ProductionRAGChatbot`) | `condense()` — same prompt, reading graph state instead of a `self.history` list |
| Short-term memory (checkpointer) | S10f (Notebook 11, §3–4) | `builder.compile(checkpointer=...)` — the same primitive `create_agent(checkpointer=...)` uses |
| Token-budget trimming | S10f (Notebook 11, §5b) | `trim_history()` — same `RemoveMessage(id=REMOVE_ALL_MESSAGES)` pattern, applied by hand |
| Long-term memory (`Store`) | S10f (Notebook 11, §6) | `recall_preferences()` + `remember_answer_style()` — same `Store`, a plain key instead of semantic search |
| Resilience (retry/fallback) | S10f (Notebook 11, §10) | `resilient_invoke()` — the same idea as `ModelRetryMiddleware`, applied manually since these are bare `StateGraph` nodes |
| Structured output | S10f (Notebook 11, §11) | `extract_structured_citations()` — `llm.with_structured_output()`, the same idea as `response_format=ProviderStrategy(schema=...)` |
| Human-in-the-loop | S10f (Notebook 11, §9) | `human_escalation()` — the same `interrupt()`/`Command(resume=...)` primitive, applied to a decision no prebuilt middleware covers |
| Observability | S10f (Notebook 11, §12) | Same pattern documented (3 `LANGSMITH_*` env vars, zero code change) — works identically for a `StateGraph`, not just `create_agent`; the Streamlit trace panel is this module's practical stand-in when LangSmith isn't configured |
| Testing | S10f (Notebook 11, §13) | `capstone_agentic_rag/tests/test_graph.py` — the same trajectory-assertion philosophy, extended to test retry counts and routing decisions directly |
| DeepEval | S10e (Notebook 10) | **Extension point, not implemented.** RAGAS alone covers the same "automated grounding check" teaching point; adding both would duplicate, not add, coverage |
| FAISS · Pinecone | S10c (Notebook 05) | **Extension point.** `HybridIndex` uses Chroma; swapping the vector store is a `rag_pipeline.py` change, not an M11 one |
| SPLADE | S10d (Notebook 06) | **Extension point.** BM25 is the sparse half of `HybridIndex`; SPLADE is a documented alternative, not additive here |
| FlashRank / Cohere rerank | S10d (Notebook 08) | **Extension point.** The cross-encoder reranker is what `ProductionRAGChatbot` ships with; swapping rerankers doesn't change anything about the *graph* |
| Multimodal RAG (images) | Notebook 15 | **Out of scope.** A text-document capstone; multimodal retrieval is its own project |
| MCP agents | Notebook 16 | **Out of scope.** That notebook is already its own capstone in `10_RAG/`; duplicating it here would be redundant, not additive |
