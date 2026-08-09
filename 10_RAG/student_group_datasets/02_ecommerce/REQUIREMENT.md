# Requirement — Amazon Marketplace Seller Support Assistant

## 1. Business context
A third-party seller on Amazon has to navigate a dense web of policy documents to understand fees, conduct rules, and what can get their account suspended. Amazon Seller Central's real support system fields huge volumes of these questions. A RAG assistant lets a seller self-serve accurate, cited answers instead of guessing or opening a support ticket.

## 2. Objective
Build a RAG chatbot that answers a **third-party Amazon seller's** questions about fees, account rules, and code of conduct — not a buyer-facing customer service bot.

## 3. Data provided
| File | Format | Pages | Content |
|---|---|---|---|
| `Amazon_Business_Solutions_Agreement.pdf` | PDF | 45 | Core legal contract: fees, IP rights, termination |
| `Amazon_Seller_Code_of_Conduct.pdf` | PDF | 8 | Reviews, feedback, customer messaging rules |
| `Amazon_Selling_Policies_and_Code_of_Conduct.pdf` | PDF | 3 | Fee schedule and policy summary |
| `Amazon_Financial_Data_XBRL.xml` + `_Labels_XBRL.xml` | XML | — | Real SEC financial facts (optional side-question source) |

## 4. Functional requirements
1. Chunk and index all 3 PDFs.
2. Retrieve relevant chunks per query.
3. Answer strictly from retrieved content, with source citation.
4. Correctly distinguish seller-facing questions (in scope) from buyer-facing ones (out of scope — this bot is not for retail customers asking "where's my package").

## 5. Guardrails
- Never invent a fee percentage or policy rule not in the documents.
- If asked a buyer/retail-customer question ("where's my order"), explain this assistant is for sellers only.
- If asked about a different platform (eBay, Etsy), decline — out of scope.

## 6. Acceptance test questions
| # | Question | Expected behavior |
|---|---|---|
| 1 | "Under what conditions can Amazon suspend my seller account?" | Answer from BSA, cited |
| 2 | "Can I ask a customer to remove a negative review?" | Answer from Code of Conduct, cited |
| 3 | "What's the referral fee structure?" | Answer from Selling Policies doc |
| 4 | "Where is my order? It hasn't arrived." | Bot declines — this is a seller assistant, not buyer support |
| 5 | "What are eBay's seller fees?" | Bot declines — out of scope |

## 7. Evaluation-Driven Design Justification (Mandatory)
Every pipeline decision below must be proven with metrics, not assumed. Follow the full methodology in [`../EVALUATION_METHODOLOGY.md`](../EVALUATION_METHODOLOGY.md) — parsing, chunking, embedding, vector DB, dense/sparse/hybrid retrieval, hybrid merge weighting, reranking, and LLM choice all require ablation tables with R@1/R@3/MRR@10/NDCG@3.

**Seed evaluation questions** (expand to 20+ per the methodology):
| Question | Ground-truth source |
|---|---|
| "What fees does Amazon charge for using Fulfillment by Amazon?" | `Amazon_Business_Solutions_Agreement.pdf` |
| "Under what conditions can my seller account be suspended?" | `Amazon_Business_Solutions_Agreement.pdf` |
| "Can I offer customers money for a positive review?" | `Amazon_Seller_Code_of_Conduct.pdf` |
| "What happens if I repeatedly violate the code of conduct?" | `Amazon_Seller_Code_of_Conduct.pdf` |
| "What's the referral fee mentioned in the selling policy summary?" | `Amazon_Selling_Policies_and_Code_of_Conduct.pdf` |
| "What's Amazon's total net sales in their latest 10-K?" | `Amazon_Financial_Data_XBRL.xml` |

## 8. Deliverables
- Working chatbot
- **Evaluation report** with all 8 ablation tables from the shared methodology, filled with real measured numbers
- Acceptance test results
- End-to-end RAGAS + DeepEval scores on your final chosen pipeline

## 9. Evaluation criteria (grading weights — see methodology Part E)
| Component | Weight |
|---|---|
| Evaluation rigor: ablation tables complete, real numbers, winner justified per stage | 40% |
| Correctness + seller-vs-buyer scope boundary on the 5 acceptance tests | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |
