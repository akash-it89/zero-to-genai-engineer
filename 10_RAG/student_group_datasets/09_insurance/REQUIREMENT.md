# Requirement — State Farm Customer Support Assistant

## 1. Business context
State Farm is a multi-line insurer — a real policyholder frequently holds auto, home, and renters coverage simultaneously (a classic real-life "multi-policy discount" customer). Support has to answer questions across all lines, often comparing coverage across states. A RAG assistant unifies this.

## 2. Objective
Build a RAG chatbot that answers a State Farm policyholder's questions across their **auto, homeowners, and renters policies**, correctly handling state-specific differences (Florida vs. Texas auto; Maine vs. Oklahoma home).

## 3. Data provided
| File | Format | Pages | Content |
|---|---|---|---|
| `StateFarm_Homeowners_Policy_Maine.pdf` | PDF | 166 | Full homeowners policy (Maine) |
| `StateFarm_Auto_Policy_Booklet_FL.pdf` | PDF | 60 | Full auto policy (Florida) |
| `StateFarm_Auto_Policy_Booklet_TX.pdf` | PDF | 43 | Full auto policy (Texas) |
| `StateFarm_Homeowners_Policy_Oklahoma.pdf` | PDF | 40 | Full homeowners policy (Oklahoma) |
| `StateFarm_Renters_Policy_Oklahoma.pdf` | PDF | 34 | Full renters policy (Oklahoma) |
| `California_DOI_Rate_Filings_2026.xlsx` | XLSX | — | Real CA DOI rate-filing register (confirmed 14 real State Farm rows) |

## 4. Functional requirements
1. Chunk and index all 5 PDFs, tagged by **product line** (auto/home/renters) and **state**.
2. Retrieve and answer strictly from retrieved content, with citation (policy + state).
3. **Routing requirement:** when a user doesn't specify a state, ask which state their policy is in before answering a state-specific question, rather than guessing.
4. Support cross-state comparison questions using the XLSX rate data where relevant.

## 5. Guardrails
- Never invent a coverage limit, exclusion, or premium not present in the documents.
- Never answer as if State Farm's Florida auto terms apply to a Texas customer, or vice versa — state mismatches are a hard failure.
- This bot explains policy language, it does not approve/deny actual claims — always recommend contacting a real State Farm agent for an actual claim decision.

## 6. Acceptance test questions
| # | Question | Expected behavior |
|---|---|---|
| 1 | "Does my State Farm homeowners policy cover water damage from a burst pipe?" | Answer cites the correct state's homeowners policy (ask which state if unspecified) |
| 2 | "What's my liability limit under my Texas auto policy?" | Answer from Auto TX booklet specifically, not Florida |
| 3 | "Am I covered for theft under my renters policy?" | Answer from Renters policy |
| 4 | Compare Maine vs. Oklahoma homeowners coverage for the same peril | Correctly distinguishes the two state-specific documents |
| 5 | "Is my water damage claim approved?" | Bot declines to approve/deny, recommends contacting a State Farm agent |

## 7. Evaluation-Driven Design Justification (Mandatory)
Every pipeline decision below must be proven with metrics, not assumed. Follow the full methodology in [`../EVALUATION_METHODOLOGY.md`](../EVALUATION_METHODOLOGY.md). With the largest document set of all 9 groups (343 pages), this group should show particular rigor on Stage 2 (chunking) and Stage 7 (reranking) — long, repetitive policy-form language across similar-but-different state versions is exactly where naive top-k dense retrieval confuses Maine's and Oklahoma's homeowners forms, and reranking is likely to show a measurable R@3 gain here. Prove it with the table, don't assume it.

**Seed evaluation questions** (expand to 20+ per the methodology):
| Question | Ground-truth source |
|---|---|
| "Does my Oklahoma homeowners policy cover mold damage?" | `StateFarm_Homeowners_Policy_Oklahoma.pdf` |
| "What's the liability coverage limit in the Florida auto policy?" | `StateFarm_Auto_Policy_Booklet_FL.pdf` |
| "Is my bicycle covered under my renters policy if stolen?" | `StateFarm_Renters_Policy_Oklahoma.pdf` |
| "How does the Maine homeowners policy handle water damage compared to Oklahoma's?" | `StateFarm_Homeowners_Policy_Maine.pdf` + `StateFarm_Homeowners_Policy_Oklahoma.pdf` (cross-document) |
| "How many State Farm auto rate filings were approved in California recently?" | `California_DOI_Rate_Filings_2026.xlsx` |

## 8. Deliverables
- Working chatbot with visible state/product-line routing
- **Evaluation report** with all 8 ablation tables from the shared methodology, filled with real measured numbers
- Acceptance test results
- End-to-end RAGAS + DeepEval scores on your final chosen pipeline

## 9. Evaluation criteria (grading weights — see methodology Part E)
| Component | Weight |
|---|---|
| Evaluation rigor: ablation tables complete, real numbers, winner justified per stage | 40% |
| Correct state-specific routing on the 5 acceptance tests — mixing up FL/TX or Maine/Oklahoma is a hard failure | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |
