# Group 8 — IRS Taxpayer Assistance Chatbot

## Requirement
Build a RAG chatbot modeled on the **IRS's own real "Interactive Tax Assistant"** that answers a taxpayer's questions about filing status, withholding, and dependents.

**Why this is coherent:** all 3 publications are from the same agency (IRS), covering complementary real-world taxpayer questions — this mirrors an actual IRS product, not a hypothetical.

## Data sources (all real official IRS publications)
| File | Pages | Covers |
|---|---|---|
| `IRS_Publication17.pdf` | 142 | "Your Federal Income Tax" — general filing rules |
| `IRS_Publication15T.pdf` | 71 | Federal income tax withholding methods |
| `IRS_Publication501.pdf` | 31 | Dependents, standard deduction, filing information |
| `tax_brackets_2026.csv` | — | 2026 federal tax bracket data (structured lookup) |
| `IRS_SOI_Historical_Individual_Income_Tax_Table.xls` | — | Real IRS Statistics of Income historical table, 1990–2023 (genuine Excel file, authored by IRS SOI staff) |

**244 real pages + 1 CSV + 1 real Excel file, one agency, four complementary data types.**

## Sample questions to validate retrieval
- "Am I required to file a tax return this year?" (Pub 501)
- "How much will be withheld from my paycheck?" (Pub 15-T)
- "What's my tax bracket if I make $85,000 filing single?" (CSV — tests structured lookup vs. narrative PDF retrieval)

## How to use for RAG
Good exercise in **routing**: some questions should hit the CSV (structured bracket lookup), others should hit the PDFs (narrative rules) — test whether your retrieval picks the right source type, not just the right document.
