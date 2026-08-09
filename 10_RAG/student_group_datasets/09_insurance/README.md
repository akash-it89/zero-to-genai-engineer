# Group 9 — State Farm Customer Support Assistant

## Requirement
Build a RAG chatbot that answers a **State Farm policyholder's** questions across their auto, home, and renters policies — the way State Farm's own support desk handles a customer who holds multiple State Farm policies (very common in real life — State Farm is a multi-line insurer by design).

**Why this is coherent:** every document is a real, State-Farm-branded policy form, filed with real state insurance departments. One insurer, multiple real product lines — not a mashup of unrelated carriers or unrelated insurance types.

## Data sources (all real, State Farm-branded policy filings)
| File | Pages | Covers |
|---|---|---|
| `StateFarm_Homeowners_Policy_Maine.pdf` | **166** | Full State Farm Homeowners Policy (Maine filing, form HW-2119) |
| `StateFarm_Auto_Policy_Booklet_FL.pdf` | 60 | Full State Farm Personal Car Policy (Florida, form 9810C) |
| `StateFarm_Auto_Policy_Booklet_TX.pdf` | 43 | Full State Farm Personal Car Policy (Texas, form 9843C) |
| `StateFarm_Homeowners_Policy_Oklahoma.pdf` | 40 | Full State Farm Homeowners Policy (Oklahoma, form HW-2136) |
| `StateFarm_Renters_Policy_Oklahoma.pdf` | 34 | Full State Farm Renters Policy (Oklahoma, form H4-2136) |

**343 real pages, one insurer, three real product lines (auto/home/renters), verified via state insurance department filings.**

## Bonus: real structured data
| File | What it is |
|---|---|
| `California_DOI_Rate_Filings_2026.xlsx` | Real California Dept. of Insurance rate-filing register — confirmed to contain 14 real State Farm rows (auto and homeowners rate changes, % requested/approved, filing dates) among ~5,300 total filings |

## Sample questions to validate retrieval
- "Does my State Farm homeowners policy cover water damage from a burst pipe?" (Homeowners)
- "What's my liability limit under my Texas auto policy?" (Auto TX)
- "Am I covered for theft under my renters policy?" (Renters)
- Good cross-state test: compare the Maine vs. Oklahoma homeowners forms for the same coverage question — tests whether retrieval correctly separates state-specific policy language.

## Note
Earlier drafts included the federal Medicare handbook, a Shelter Insurance homeowners form, and a generic (non-State-Farm) Maine ISO form — three unrelated organizations mixed with State Farm. Moved to `../_excluded_out_of_scope/09_insurance/`. If you want a **multi-carrier independent insurance agency** variant instead (a real, different business model — brokers do sell multiple carriers), those files can be reintroduced under that explicit reframing.
