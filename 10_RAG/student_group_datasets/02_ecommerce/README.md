# Group 2 — Amazon Marketplace Seller Support Assistant

## Requirement
Build a RAG chatbot that answers a **third-party Amazon seller's** questions about fees, account rules, and conduct policy — the kind of assistant Amazon's own Seller Central help desk would provide.

**Why this makes sense:** all three documents are real, current Amazon documents governing the exact same relationship (Amazon ↔ its marketplace sellers). A real seller's questions genuinely span all three.

## Data sources (all real Amazon documents, from Amazon's own CDN)
| File | Pages | Covers |
|---|---|---|
| `Amazon_Business_Solutions_Agreement.pdf` | 45 | The core legal contract: fees, IP rights, account termination |
| `Amazon_Seller_Code_of_Conduct.pdf` | 8 | Rules on reviews, feedback, customer messaging |
| `Amazon_Selling_Policies_and_Code_of_Conduct.pdf` | 3 | Selling-on-Amazon fee schedule and policy summary |
| `Amazon_Financial_Data_XBRL.xml` | — | Real SEC-filed XBRL financial facts (2025 10-K) |
| `Amazon_Financial_Labels_XBRL.xml` | — | Human-readable labels for the financial data above |

**56 real PDF pages + 2 real XML files, one company, one persona (the seller), five real documents.**

## Sample questions to validate retrieval
- "Under what conditions can Amazon suspend my seller account?" (BSA)
- "Am I allowed to ask customers to remove a negative review?" (Code of Conduct)
- "What's the referral fee structure mentioned in the selling policies doc?" (Selling Policies)

## Note
Earlier drafts paired the Amazon seller contract with a *fictional* company's ("BrownBox") customer-facing support conversations — that mismatch (different company, different audience: seller vs. buyer) has been removed. The BrownBox parquet file is in `../_excluded_out_of_scope/02_ecommerce/` if you want to build a **separate** buyer-facing e-commerce support project instead — just don't merge the two.
