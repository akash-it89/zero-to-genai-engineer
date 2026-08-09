# Capstone RAG Chatbot — 9 Group Requirements Overview

Each group builds a RAG-powered support chatbot for a **real single company or agency**, grounded only in the real documents provided in its folder. Full requirement brief is in each group's `REQUIREMENT.md`.

| # | Group folder | Persona / who this bot serves | Core skill being tested | Data |
|---|---|---|---|---|
| 1 | `01_banking` | Wells Fargo customer support | Grounded fee/policy Q&A, no hallucinated numbers | 3 PDF (60pg) + 2 XML |
| 2 | `02_ecommerce` | Amazon marketplace seller support | Seller-vs-buyer scope boundary | 3 PDF (56pg) + 2 XML |
| 3 | `03_telecom` | Verizon customer support | Routing across product lines (wireless/Fios/international) | 3 PDF (40pg) + 2 XML |
| 4 | `04_legal` | Law firm paralegal contract search | Cross-document retrieval + correct client attribution | 5 HTML contracts (~105K words) + 2 XML |
| 5 | `05_healthcare` | NIH/MedlinePlus-style consumer health info | **Hard refusal on diagnostic questions** (safety-critical) | 11,274 XML + PDF + TSV |
| 6 | `06_finance_complaints` | Consumer credit-rights helpline | Correct law-to-scenario routing (ECOA vs. Fair Housing Act) | 4 PDF (18pg) + CSV |
| 7 | `07_airline_travel` | Delta customer support | Passenger-vs-cargo document routing | 2 PDF (45pg) + 2 XML |
| 8 | `08_tax_government` | IRS taxpayer assistance | Structured (CSV/XLS) vs. narrative (PDF) retrieval routing | 3 PDF (244pg) + CSV + XLS |
| 9 | `09_insurance` | State Farm customer support | State-specific + product-line routing (hard fail if mixed) | 5 PDF (343pg) + XLSX |

## What's common to every group's requirement
- Every answer must **cite its source document** — no answer without a traceable source.
- Every bot must **explicitly refuse** rather than guess when the answer isn't in the provided documents.
- Every group has a defined **out-of-scope test** (a competitor, a different persona, or a request needing live account access) that the bot must correctly decline.
- **Every design decision must be proven with metrics — not assumed.** See [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md) for the full, mandatory methodology shared across all 9 groups.

## Evaluation-driven pipeline requirement (mandatory, all 9 groups)
This capstone is graded primarily on **evidence**, not on "does the chatbot work." Every group must run ablation experiments — comparing at least 2 real alternatives, measured on their own 20+ question evaluation set — for every stage of the pipeline, and pick each winner by citing the numbers:

| Stage | What's compared | Metrics required |
|---|---|---|
| Parsing | pypdf vs. pdfplumber vs. PyMuPDF (or HTML-strip method for the legal group) | Clean-text %, downstream R@3 |
| Chunking | fixed-size vs. recursive/sentence-aware vs. semantic, at 2+ sizes/overlaps | R@1, R@3, MRR@10, NDCG@3 |
| Embedding model | 2+ real models (e.g. MiniLM, bge-small, text-embedding-3-small) | R@1, R@3, MRR@10, NDCG@3, latency |
| Vector DB | ChromaDB vs. FAISS (or others) | R@3 parity + speed/filtering/persistence |
| Retrieval mode | dense vs. sparse (BM25) vs. hybrid, broken out by query type | R@1, R@3, MRR@10, NDCG@3 |
| Hybrid merge | RRF vs. weighted-α, with α swept | R@3, MRR@10, NDCG@3 — must state the winning % weight |
| Reranking | none vs. cross-encoder | R@3, NDCG@3, added latency |
| LLM (generation) | 2+ real LLMs, retrieval held fixed | RAGAS (faithfulness, answer relevancy, context precision/recall) + DeepEval (hallucination, G-Eval) |

Full metric definitions, table formats, and a worked example synthesis paragraph are in [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md).

## Deliverable format (same for all 9 groups)
1. Working chatbot (Streamlit or FastAPI+Streamlit, per the course's UI progression rule)
2. **Evaluation report** with all 8 ablation tables above, filled with real measured numbers, and a synthesis paragraph justifying the final chosen configuration
3. Acceptance test results for the 5 questions listed in that group's `REQUIREMENT.md`
4. End-to-end RAGAS + DeepEval scores on the final pipeline

## Grading weights (all 9 groups)
| Component | Weight |
|---|---|
| Evaluation rigor (ablation tables, real numbers, justified winners) | 40% |
| Correctness on the group's specific acceptance tests | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |

*(Healthcare group only: diagnostic-refusal correctness is a hard gate worth 25%, rebalancing the other weights — see `05_healthcare/REQUIREMENT.md`.)*
