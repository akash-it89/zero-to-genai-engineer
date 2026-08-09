# Requirement — IRS Taxpayer Assistance Chatbot

## 1. Business context
The IRS's real "Interactive Tax Assistant" exists because most taxpayer questions are routine and answerable from published guidance — "do I need to file," "how much will be withheld," "can I claim my kid as a dependent." A RAG assistant modeled on this reduces reliance on paid tax preparers for basic questions and reduces IRS call-center load.

## 2. Objective
Build a RAG chatbot that answers a taxpayer's questions about **filing requirements, withholding, and dependents**, and can also do structured bracket lookups.

## 3. Data provided
| File | Format | Pages/size | Content |
|---|---|---|---|
| `IRS_Publication17.pdf` | PDF | 142 | General filing rules |
| `IRS_Publication15T.pdf` | PDF | 71 | Withholding methods |
| `IRS_Publication501.pdf` | PDF | 31 | Dependents, standard deduction, filing status |
| `tax_brackets_2026.csv` | CSV | — | 2026 federal tax bracket data |
| `IRS_SOI_Historical_Individual_Income_Tax_Table.xls` | XLS | — | Real historical IRS statistics, 1990–2023 |

## 4. Functional requirements
1. Chunk and index all 3 PDFs (page-aware).
2. Load the CSV and XLS as structured, queryable data — not just chunked prose.
3. **Routing requirement:** implement logic so a bracket/number question ("what's my tax bracket at $85K") queries the CSV directly rather than searching PDF text, while a rules question ("am I required to file") retrieves from the PDFs.
4. Every answer must cite its source (publication name + page, or "2026 tax bracket table").

## 5. Guardrails
- Never invent a bracket threshold, deduction amount, or filing rule not in the provided data.
- This bot gives general information, not personalized tax advice — include a disclaimer recommending a licensed tax professional or IRS.gov for complex situations.

## 6. Acceptance test questions
| # | Question | Expected behavior |
|---|---|---|
| 1 | "Am I required to file a tax return this year?" | Answer from Pub 501 |
| 2 | "How much will be withheld from my paycheck?" | Answer from Pub 15-T |
| 3 | "What's my tax bracket if I make $85,000 filing single?" | Answer from CSV, not PDF text — tests structured routing |
| 4 | "How has the top individual tax rate changed since 1990?" | Uses the historical XLS data |
| 5 | "Exactly how much do I owe this year?" | Bot declines precise calculation, recommends a tax professional/IRS tools |

## 7. Evaluation-Driven Design Justification (Mandatory)
Every pipeline decision below must be proven with metrics, not assumed. Follow the full methodology in [`../EVALUATION_METHODOLOGY.md`](../EVALUATION_METHODOLOGY.md). This group's Stage 5 (dense/sparse/hybrid) ablation should include a query-type breakdown that specifically separates "structured lookup" queries (should route to CSV/XLS) from "narrative rule" queries (should route to PDF text) — this breakdown is your proof for the routing logic required below.

**Seed evaluation questions** (expand to 20+ per the methodology):
| Question | Ground-truth source |
|---|---|
| "Do I need to file taxes if I only made $5,000 this year?" | `IRS_Publication501.pdf` |
| "How is federal withholding calculated for a biweekly paycheck?" | `IRS_Publication15T.pdf` |
| "What's the standard deduction for a single filer?" | `IRS_Publication17.pdf` |
| "What's my tax bracket if I make $85,000 filing single?" | `tax_brackets_2026.csv` |
| "What was the top marginal tax rate in 1990 vs. recent years?" | `IRS_SOI_Historical_Individual_Income_Tax_Table.xls` |

## 8. Deliverables
- Working chatbot with visible routing logic (structured data vs. PDF retrieval)
- **Evaluation report** with all 8 ablation tables from the shared methodology, filled with real measured numbers
- Acceptance test results
- End-to-end RAGAS + DeepEval scores on your final chosen pipeline

## 9. Evaluation criteria (grading weights — see methodology Part E)
| Component | Weight |
|---|---|
| Evaluation rigor: ablation tables complete, real numbers, winner justified per stage | 40% |
| Correct structured-vs-narrative routing on the 5 acceptance tests | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |
