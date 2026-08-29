<div align="center">

# Session 10 — Notebooks

**Run from this folder so `data/` and `production_*` paths work.**

</div>

```bash
cd 10_RAG/notebooks
pip install -r requirements.txt
cp ../.env.example ../.env    # if you have not already
```

Each notebook also has a `%pip install` cell for Colab / a fresh kernel.

| # | File | Required? | Builds on |
|---|---|---|---|
| 01 | [Why RAG](01_why_rag_the_case_for_retrieval.ipynb) | **Yes** | — |
| 02 | [Chunking — LangChain](02_ingestion_and_chunking_langchain.ipynb) | **Yes** | 01 |
| 03 | [Chunking — LlamaIndex](03_ingestion_and_chunking_llamaindex.ipynb) | **Yes** | 02 (same ideas) |
| 04 | [Embeddings](04_embeddings.ipynb) | **Yes** | 02 |
| 05 | [Vector databases](05_vector_databases.ipynb) | **Yes** | 04 |
| 06 | [Sparse retrieval](06_sparse_retrieval.ipynb) | **Yes** | 04 |
| 07 | [Hybrid search](07_hybrid_search.ipynb) | **Yes** | 05 + 06 |
| 08 | [Reranking](08_reranking.ipynb) | **Yes** | 07 |
| 09 | [RAGAS](09_ragas_evaluation.ipynb) | **Yes** | 08 |
| 10 | [DeepEval](10_deepeval_evaluation.ipynb) | **Yes** | 09 |
| 11 | [Production chatbots](11_production_ready_chatbots.ipynb) | **Yes — this is M06 (memory)** | 08–10 |
| 12 | [Pinecone showdown](12_retrieval_showdown_pinecone.ipynb) | **Yes** (`PINECONE_API_KEY`) | 06–08 |
| 13 | [Capstone chatbot](13_capstone_production_rag_chatbot.ipynb) | Capstone | 11 → [`production_rag_chatbot/`](production_rag_chatbot/) |
| 13s | [Student copy of 13](13_capstone_production_rag_chatbot_STUDENT.ipynb) | Practice | same |
| 14 | [Capstone + memory](14_capstone_production_rag_chatbot_memory.ipynb) | Capstone | 13 → [`production_rag_chatbot_memory/`](production_rag_chatbot_memory/) |
| 14s | [Student copy of 14](14_capstone_production_rag_chatbot_memory_STUDENT.ipynb) | Practice | same |
| 15 | [Multimodal RAG](15_multimodal_rag_images.ipynb) | Extra | 05 + vision |
| 16 | [MCP helpdesk](16_capstone_mcp_agents_rag.ipynb) | Extra · **needed for S11 Day 3** | 13 → [`production_mcp_agents_rag_capstone/`](production_mcp_agents_rag_capstone/) |

Class slides are on [GitHub Pages](https://nursnaaz.github.io/zero-to-genai-engineer/). Sample files: [`data/`](data/). `_extracted_images/` is created when you run notebook 15 (gitignored).

**Browser labs:** [Tiny RAG](https://nursnaaz.github.io/tutorial/tiny-rag) (with 01) · [Chunking](https://nursnaaz.github.io/tutorial/chunking-intuition) (with 02) · [Hybrid + RRF](https://nursnaaz.github.io/tutorial/hybrid-search-rrf) (with 07) · [Citations](https://nursnaaz.github.io/tutorial/citations-and-refusals) · [Injection](https://nursnaaz.github.io/tutorial/rag-injection-guardrails) · [Memory](https://nursnaaz.github.io/tutorial/chatbots-forget) (with 11) · [Production](https://nursnaaz.github.io/tutorial/production-challenges) (with 13) · [MCP](https://nursnaaz.github.io/tutorial/mcp-as-usb) (with 16)

← [Session 10](../README.md)
