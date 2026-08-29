<div align="center">

# Session 00 — How Search Engines Work

**M00 · Foundations · no API key**

*Build a TF-IDF search engine from scratch — the idea under every RAG system you will write later.*

</div>

> **The big question:** How does Google decide which result is most relevant to your query?

This session introduces the core idea behind every search system — TF-IDF — and shows you how to build one from scratch in Python. No machine learning needed. Just math and logic.

By the end of this session, you will understand the engine that sat beneath Google before deep learning changed everything. That foundation makes everything in GenAI — embeddings, RAG, retrieval — click into place.

## Start here

Open [`notebooks/01_search_engine.ipynb`](notebooks/01_search_engine.ipynb) (Colab badge below, or local Jupyter). Then notebook 02.

**Browser lab:** [How Search Engines Work](https://nursnaaz.github.io/tutorial/how-search-engines-work) (~45 min). Do this before or with notebook 01.

```text
00_How_Search_Engine_Works/
├── README.md          ← you are here
├── notebooks/         ← 01 search engine · 02 TF-IDF math
└── slides/            ← PDFs for class
```

---

## What's MISSING after this session?

TF-IDF is fast and interpretable — but it breaks when you use different words to mean the same thing.

Search `"automobile accident"` and TF-IDF misses every document that says `"car crash"`.

That gap — **semantic mismatch** — is exactly what word embeddings and neural search solve. We build toward that in M00 onwards.

---

## Notebooks

Run these in order in **Google Colab** or locally with Jupyter.

| # | Notebook | What You Build | Time |
|---|---|---|---|
| 01 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/nursnaaz/zero-to-genai-engineer/blob/main/00_How_Search_Engine_Works/notebooks/01_search_engine.ipynb) [search_engine.ipynb](notebooks/01_search_engine.ipynb) | A working keyword search engine with tokenisation, stop word removal, stemming, inverted index, and TF-IDF ranking | 30 min |
| 02 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/nursnaaz/zero-to-genai-engineer/blob/main/00_How_Search_Engine_Works/notebooks/02_tfidf_explained.ipynb) [tfidf_explained.ipynb](notebooks/02_tfidf_explained.ipynb) | Step-by-step breakdown of TF-IDF math — why naive counting fails, how TF and IDF combine, full scoring from scratch | 45 min |

**No API key needed.** Everything runs on pure Python (`collections`, `math`).

---

## Slides

Class slides (hosted):

| Presentation | Topic |
|---|---|
| [GenAI intro](https://nursnaaz.github.io/zero-to-genai-engineer/00_How_Search_Engine_Works/slides/00_genai_intro.pdf) | What is GenAI |
| [How search engines work](https://nursnaaz.github.io/zero-to-genai-engineer/00_How_Search_Engine_Works/slides/00_how_search_engine_works.pdf) | From crawling to TF-IDF ranking |
| [Claude Code leak](https://nursnaaz.github.io/zero-to-genai-engineer/00_How_Search_Engine_Works/slides/00_claude_code_leak_summary.pdf) | The Claude Code system prompt leak |

---

## Setup

No installation required beyond a standard Python environment.

```bash
# If running locally
pip install notebook
jupyter notebook notebooks/01_search_engine.ipynb
```

For Colab: open the notebook link and click **"Open in Colab"**.

---

**Course nav:** [Pre-work](../prereq/) · [All sessions](../README.md) · [S01 Text to Numbers →](../01_Text_to_Numbers/)
