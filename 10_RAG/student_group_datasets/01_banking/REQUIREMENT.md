# Requirement — Wells Fargo Customer Support Assistant

## 1. Business context (why this bot needs to exist)
Wells Fargo's phone/chat support fields enormous volumes of repetitive questions: "what's my overdraft fee," "what's the APR on my card," "can the bank close my account." Every one of these has a factual, documented answer sitting in a policy PDF that most customers never read. A RAG assistant answers instantly, cites the exact clause, and frees human agents for cases that actually need judgment.

## 2. Objective
Build a RAG chatbot that answers a Wells Fargo customer's questions about their **deposit account terms, applicable fees, and credit card agreement**, using only the documents provided, and always cites which document/page the answer came from.

## 3. Data provided
| File | Format | Pages | Content |
|---|---|---|---|
| `WellsFargo_Deposit_Account_Agreement.pdf` | PDF | 44 | Full checking/savings account terms |
| `WellsFargo_Consumer_Account_Fees_Info.pdf` | PDF | 12 | Fee schedule |
| `WellsFargo_Credit_Card_Agreement.pdf` | PDF | 4 | Card APR, interest, terms |
| `WellsFargo_Financial_Data_XBRL.xml` + `_Labels_XBRL.xml` | XML | — | Real SEC financial facts (optional: use for an "is this bank financially stable" side-question) |

## 4. Functional requirements
1. Chunk and index all 3 PDFs (page-aware chunking — retain page number as metadata).
2. Retrieve relevant chunks for a user query (hybrid search recommended: BM25 + embeddings).
3. Generate an answer **grounded only in retrieved chunks** — no outside knowledge.
4. Every answer must cite the source document name (and ideally page number).
5. If the answer isn't in the provided documents, the bot must say so — not guess.

## 5. Guardrails (non-negotiable)
- Never invent a fee amount, APR, or rule not present in the documents.
- If asked about a different bank (Chase, HDFC, etc.), respond that it's out of scope for this assistant.
- If asked something requiring personal account access ("what's my balance"), explain that the bot only answers general policy questions, not account-specific lookups.

## 6. Acceptance test questions
| # | Question | Expected behavior |
|---|---|---|
| 1 | "What's the monthly service fee on my checking account and how do I avoid it?" | Answer from Fees PDF, cited |
| 2 | "What's the APR on my Wells Fargo credit card?" | Answer from Card Agreement, cited |
| 3 | "Can Wells Fargo close my account without notice?" | Answer from Deposit Agreement, cited |
| 4 | "What's Chase's overdraft fee?" | Bot declines — out of scope |
| 5 | "What's my current account balance?" | Bot explains it can't access personal account data |

## 7. Evaluation-Driven Design Justification (Mandatory)
Every pipeline decision below must be proven with metrics, not assumed. Follow the full methodology in [`../EVALUATION_METHODOLOGY.md`](../EVALUATION_METHODOLOGY.md) — metric definitions, ablation table formats, and required experiments for: parsing strategy, chunking strategy, embedding model, vector DB, dense vs. sparse vs. hybrid retrieval, hybrid merge weighting, reranking, and LLM choice.

**Seed evaluation questions** (expand to 20+ per the methodology; each needs a ground-truth source):
| Question | Ground-truth source |
|---|---|
| "What's the monthly service fee on my checking account?" | `WellsFargo_Consumer_Account_Fees_Info.pdf` |
| "What happens if I overdraw my account?" | `WellsFargo_Consumer_Account_Fees_Info.pdf` |
| "Can Wells Fargo close my account without notice?" | `WellsFargo_Deposit_Account_Agreement.pdf` |
| "How do I dispute a transaction on my checking account?" | `WellsFargo_Deposit_Account_Agreement.pdf` |
| "What's the APR on my Wells Fargo credit card?" | `WellsFargo_Credit_Card_Agreement.pdf` |
| "What fees apply to wire transfers?" | `WellsFargo_Consumer_Account_Fees_Info.pdf` |
| "What's Wells Fargo's reported revenue in their latest 10-K?" | `WellsFargo_Financial_Data_XBRL.xml` |

## 8. Deliverables
- Working chatbot (Streamlit or FastAPI+Streamlit)
- **Evaluation report** with all 8 ablation tables from the shared methodology, filled with real measured numbers
- Results of the 5 acceptance tests above, with screenshots or logged transcripts
- End-to-end RAGAS + DeepEval scores on your final chosen pipeline

## 9. Evaluation criteria (grading weights — see methodology Part E for full detail)
| Component | Weight |
|---|---|
| Evaluation rigor: ablation tables complete, real numbers, winner justified per stage | 40% |
| Correctness + citation accuracy on the 5 acceptance tests | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |
