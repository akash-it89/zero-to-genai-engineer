# Group 4 — Law Firm Contract Intelligence Assistant

## Requirement
Build a RAG chatbot for a **corporate law firm's paralegal team** that can search across many different clients' contracts to answer clause-specific questions — e.g. "which of our clients' contracts have an indemnification clause?"

**Why this is NOT a "grab-bag" despite being 5 unrelated companies:** unlike a customer-support bot (which must belong to one company), a **law firm's own contract database legitimately contains many unrelated clients' agreements side by side** — that's how real legal document management systems (iManage, NetDocuments) work. The persona here is the *law firm*, not any one of the 5 companies. This is a fundamentally different product from "customer support chatbot," and the multi-company diversity is a feature, not a flaw.

## Data sources (all real SEC EDGAR-filed material contracts)
| File | Words | Client / contract type |
|---|---|---|
| `Amgen_Master_Services_Agreement.htm` | ~46,955 | Amgen — Master Services Agreement |
| `Fitness_Intl_Facility_License_Agreement.htm` | ~26,172 | Fitness International (LA Fitness) — facility license |
| `OncoSec_License_Agreement.htm` | ~21,207 | OncoSec Medical — license agreement |
| `Kubient_Master_Services_Agreement.htm` | ~6,751 | Kubient/Sphere Digital — master services agreement |
| `Groveware_Software_License_Agreement.htm` | ~4,244 | Groveware Technologies — software license |

**~105,000 words, 5 real clients, 3 contract types.**

## Bonus: real financial data for one client (Amgen)
| File | What it is |
|---|---|
| `Amgen_Financial_Data_XBRL.xml` | Real SEC-filed XBRL financial facts from Amgen's 2025 10-K |
| `Amgen_Financial_Labels_XBRL.xml` | Human-readable labels for the data above |

A real law firm's "client file" for Amgen would plausibly include both the signed contract *and* that client's public financial filings — this pairing models that.

## Sample questions to validate retrieval
- "What's the termination notice period in the Amgen MSA?"
- "Which of these contracts include an indemnification clause?"
- "Does the Kubient agreement have an exclusivity provision?" (tests correct rejection/negative retrieval if it doesn't)

## Note
If your instructor wants a **single-company** legal variant instead (e.g. "in-house counsel assistant for one company"), that requires a different, harder-to-source dataset — real companies rarely have more than one or two material contracts publicly filed. CUAD (510 contracts, PDF+TXT+Excel) is still available as a manual download if you want to swap in a bigger single dataset: https://zenodo.org/records/4595826/files/CUAD_v1.zip
