# Requirement — Verizon Customer Support Assistant

## 1. Business context
A Verizon customer often has more than one Verizon service at once — wireless phone plan, home internet (Fios), maybe international travel add-ons. Real Verizon support has to answer across all of these. A RAG assistant unifies these into one support experience instead of three separate help pages.

## 2. Objective
Build a RAG chatbot that answers a Verizon customer's questions across their **wireless plan, home internet (Fios), and international travel rates**.

## 3. Data provided
| File | Format | Pages | Content |
|---|---|---|---|
| `Verizon_Customer_Agreement.pdf` | PDF | 6 | Core wireless customer agreement |
| `Verizon_Fios_Internet_Terms_of_Service.pdf` | PDF | 27 | Home internet service agreement |
| `Verizon_Global_Services_International_Rates.pdf` | PDF | 7 | International voice/data/text rates by country |
| `Verizon_Financial_Data_XBRL.xml` + `_Labels_XBRL.xml` | XML | — | Real SEC financial facts (optional side-question source) |

## 4. Functional requirements
1. Chunk and index all 3 PDFs.
2. Retrieve and answer strictly from retrieved content, with citation.
3. Correctly route a question to the right product line (wireless vs. Fios vs. international) — don't answer a Fios outage question using the international rates document.

## 5. Guardrails
- Never invent a rate, fee, or term not present in the documents.
- If asked about AT&T or T-Mobile, decline — out of scope.
- If asked something needing live account access (e.g. "why is my bill higher this month"), explain the bot only answers general policy questions.

## 6. Acceptance test questions
| # | Question | Expected behavior |
|---|---|---|
| 1 | "What does my Fios agreement say about service outages?" | Answer from Fios ToS |
| 2 | "How much does data cost if I travel to Mexico?" | Answer from Global Services rates |
| 3 | "What's Verizon's dispute resolution process for my wireless account?" | Answer from Customer Agreement |
| 4 | "What's AT&T's international rate to Mexico?" | Bot declines — out of scope |
| 5 | "Why is my bill $20 higher this month?" | Bot explains it can't access account-specific billing |

## 7. Evaluation-Driven Design Justification (Mandatory)
Every pipeline decision below must be proven with metrics, not assumed. Follow the full methodology in [`../EVALUATION_METHODOLOGY.md`](../EVALUATION_METHODOLOGY.md). Since this group's core skill is cross-document routing, pay particular attention to Stage 5 (dense vs. sparse vs. hybrid) broken out by which of the 3 source documents each query should hit — this is your strongest evidence for whether your retrieval config actually routes correctly.

**Seed evaluation questions** (expand to 20+ per the methodology):
| Question | Ground-truth source |
|---|---|
| "What does my Fios agreement say about service credits for outages?" | `Verizon_Fios_Internet_Terms_of_Service.pdf` |
| "How much does a text message cost when traveling in the UK?" | `Verizon_Global_Services_International_Rates.pdf` |
| "Can Verizon change my wireless plan terms?" | `Verizon_Customer_Agreement.pdf` |
| "What's the early termination process for my wireless line?" | `Verizon_Customer_Agreement.pdf` |
| "What's Verizon's total wireless service revenue in their latest 10-K?" | `Verizon_Financial_Data_XBRL.xml` |

## 8. Deliverables
- Working chatbot
- **Evaluation report** with all 8 ablation tables from the shared methodology, filled with real measured numbers
- Acceptance test results
- End-to-end RAGAS + DeepEval scores on your final chosen pipeline

## 9. Evaluation criteria (grading weights — see methodology Part E)
| Component | Weight |
|---|---|
| Evaluation rigor: ablation tables complete, real numbers, winner justified per stage | 40% |
| Correctness + product-line routing accuracy on the 5 acceptance tests | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |
