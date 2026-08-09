# Group 3 — Verizon Customer Support Assistant

## Requirement
Build a RAG chatbot that answers a **Verizon customer's** questions across their wireless plan, home internet (Fios), and international travel service — the way Verizon's own support desk handles a customer with multiple Verizon services.

**Why this makes sense:** all three documents are real Verizon documents covering different real product lines a single Verizon customer plausibly uses at once (phone + home internet + travel). One company, multiple real product lines — not a mashup of AT&T/T-Mobile/Verizon.

## Data sources (all real Verizon documents)
| File | Pages | Covers |
|---|---|---|
| `Verizon_Fios_Internet_Terms_of_Service.pdf` | 27 | Home internet service agreement |
| `Verizon_Global_Services_International_Rates.pdf` | 7 | International travel voice/data/text rates by country |
| `Verizon_Customer_Agreement.pdf` | 6 | Core wireless customer agreement |
| `Verizon_Financial_Data_XBRL.xml` | — | Real SEC-filed XBRL financial facts (2025 10-K) |
| `Verizon_Financial_Labels_XBRL.xml` | — | Human-readable labels for the financial data above |

**40 real PDF pages + 2 real XML files, one carrier, three real product lines.**

## Sample questions to validate retrieval
- "What does my Fios agreement say about service outages?" (Fios ToS)
- "How much does data cost if I travel to Mexico?" (Global Services rates)
- "What's Verizon's dispute resolution process for my wireless account?" (Customer Agreement)

## Note
Earlier drafts included AT&T's terms and a GSMA *engineering* specification — the AT&T doc was a competitor mismatch, and GSMA is an industry standards body (not a consumer carrier) writing for network engineers, not customers. Both moved to `../_excluded_out_of_scope/03_telecom/`. If you want a stretch/challenge variant later — "a technical assistant for a network engineer" — GSMA's 219-page cloud infrastructure spec is excellent for that, but it's a different persona and shouldn't share a knowledge base with a consumer support bot.
