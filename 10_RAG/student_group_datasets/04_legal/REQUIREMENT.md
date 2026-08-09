# Requirement — Law Firm Contract Intelligence Assistant

## 1. Business context
A corporate law firm's paralegal team manages contracts for many unrelated clients at once, stored in a shared document management system. When a partner asks "which of our clients' contracts have an indemnification clause?" or "what's the termination notice period across our MSAs?", a paralegal today has to manually reread every contract. A RAG assistant makes this instant and reduces billable research hours.

**Note — this is NOT a single-company customer support bot.** The persona is the law firm itself, and a real firm's contract database legitimately holds many unrelated clients' agreements side by side. That's why 5 unrelated companies' contracts belong together here.

## 2. Objective
Build a RAG chatbot for a law firm's paralegal team that can search across multiple real client contracts and answer clause-specific, cross-contract questions, always identifying which client/contract the answer came from.

## 3. Data provided
| File | Format | Words | Client / contract type |
|---|---|---|---|
| `Amgen_Master_Services_Agreement.htm` | HTML | ~46,955 | Amgen — Master Services Agreement |
| `Fitness_Intl_Facility_License_Agreement.htm` | HTML | ~26,172 | Fitness International (LA Fitness) — facility license |
| `OncoSec_License_Agreement.htm` | HTML | ~21,207 | OncoSec Medical — license agreement |
| `Kubient_Master_Services_Agreement.htm` | HTML | ~6,751 | Kubient/Sphere Digital — master services agreement |
| `Groveware_Software_License_Agreement.htm` | HTML | ~4,244 | Groveware Technologies — software license |
| `Amgen_Financial_Data_XBRL.xml` + `_Labels_XBRL.xml` | XML | — | Amgen's real SEC financial data (bonus: pairs with Amgen's contract as a fuller "client file") |

## 4. Functional requirements
1. Strip HTML and chunk each contract, tagging every chunk with **client name + contract type** metadata.
2. Retrieve relevant chunks across ALL 5 contracts for a given query (cross-document retrieval, not just single-document).
3. Answer must identify which client/contract the clause came from.
4. Support comparison questions ("which of these have X clause") — this requires retrieving from multiple documents and synthesizing, not just the top-1 match.

## 5. Guardrails
- Never invent a clause or term not present in the actual contract text.
- If a clause genuinely doesn't exist in a contract, say so explicitly rather than guessing ("the Groveware agreement does not appear to contain an indemnification clause").
- Do not blend language from two different contracts into one answer without clearly attributing each part.

## 6. Acceptance test questions
| # | Question | Expected behavior |
|---|---|---|
| 1 | "What's the termination notice period in the Amgen MSA?" | Answer cites Amgen contract specifically |
| 2 | "Which of these contracts include an indemnification clause?" | Cross-document synthesis, correctly attributes each |
| 3 | "Does the Kubient agreement have an exclusivity provision?" | Correctly answers "no" if absent — tests negative retrieval |
| 4 | "What's Amgen's total revenue based on their financial filing?" | Uses the XBRL bonus data, cites it separately from the contract |
| 5 | "What does the Fitness International contract say about renewal terms?" | Answer cites Fitness Intl contract specifically |

## 7. Evaluation-Driven Design Justification (Mandatory)
Every pipeline decision below must be proven with metrics, not assumed. Follow the full methodology in [`../EVALUATION_METHODOLOGY.md`](../EVALUATION_METHODOLOGY.md). Because this group's documents are HTML (not PDF), your Stage 1 "parsing" ablation compares HTML-tag-stripping approaches (e.g., BeautifulSoup `get_text()` vs. `html2text` vs. regex strip) instead of PDF parsers — measure the same downstream R@3 impact.

**Seed evaluation questions** (expand to 20+ per the methodology):
| Question | Ground-truth source |
|---|---|
| "What's the termination notice period in the Amgen MSA?" | `Amgen_Master_Services_Agreement.htm` |
| "Does the Groveware license agreement include an exclusivity clause?" | `Groveware_Software_License_Agreement.htm` |
| "What are the payment terms in the Kubient agreement?" | `Kubient_Master_Services_Agreement.htm` |
| "What's the renewal term in the Fitness International facility license?" | `Fitness_Intl_Facility_License_Agreement.htm` |
| "What confidentiality obligations exist in the OncoSec license?" | `OncoSec_License_Agreement.htm` |
| "What's Amgen's R&D expense per their latest 10-K?" | `Amgen_Financial_Data_XBRL.xml` |

## 8. Deliverables
- Working chatbot with visible per-answer source attribution (client name)
- **Evaluation report** with all 8 ablation tables from the shared methodology, filled with real measured numbers
- Acceptance test results
- End-to-end RAGAS + DeepEval scores on your final chosen pipeline

## 9. Evaluation criteria (grading weights — see methodology Part E)
| Component | Weight |
|---|---|
| Evaluation rigor: ablation tables complete, real numbers, winner justified per stage | 40% |
| Correct client/contract attribution + negative-retrieval handling on the 5 acceptance tests | 30% |
| End-to-end RAGAS + DeepEval scores on final pipeline | 20% |
| Code quality / app usability | 10% |
