# Group 1 — Wells Fargo Customer Support Assistant

## Requirement
Build a RAG chatbot that answers a **Wells Fargo customer's** questions about their deposit account terms, fees, and credit card agreement — the way Wells Fargo's own support desk would.

**Why this makes sense:** every document in this folder comes from the same real bank. A real Wells Fargo customer's questions genuinely span all three documents (their checking account terms, what fees apply, and their credit card's APR/rules) — this is what one bank's actual support knowledge base looks like, not a mashup of competitors.

## Data sources (all real Wells Fargo documents)
| File | Pages | Covers |
|---|---|---|
| `WellsFargo_Deposit_Account_Agreement.pdf` | 44 | Full checking/savings account terms and conditions |
| `WellsFargo_Consumer_Account_Fees_Info.pdf` | 12 | Fee schedule (overdraft, monthly service fee, ATM) |
| `WellsFargo_Credit_Card_Agreement.pdf` | 4 | APR, interest charges, credit card terms |
| `WellsFargo_Financial_Data_XBRL.xml` | — | Real SEC-filed XBRL financial facts (2025 10-K) — structured, machine-readable data |
| `WellsFargo_Financial_Labels_XBRL.xml` | — | Human-readable labels for the financial data above |

**60 real PDF pages + 2 real XML files (structured financial data), one bank, four real document types.**

## Sample questions to validate retrieval
- "What's the monthly service fee on my checking account and how do I avoid it?" (fee schedule)
- "What's the APR on my Wells Fargo credit card?" (card agreement)
- "Can Wells Fargo close my account without notice — what does the agreement say?" (deposit agreement)

## Note
Earlier drafts mixed in Chase, Bank of America, and HDFC documents — those were real but made no sense together (no single support desk serves 4 competing banks). They've been moved to `../_excluded_out_of_scope/01_banking/` in case you want a *separate* "bank comparison" project later, but they are out of scope for this group's requirement.
