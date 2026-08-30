# Sample docs — multi-format RAG corpus

Real policy files in **four formats** (not markdown). `build_db.py` parses them into the SQLite `documents` table — same idea as M11 Document Intelligence.

## Layout

```
sample_docs/
  docx/   Word policies & handbooks
  xlsx/   Spreadsheets (promo calendar, inventory, loyalty, pricing)
  pptx/   Training decks (ops, patio, marketing)
  pdf/    Manuals & inspection reports
```

## Generate / refresh files

```bash
pip install python-docx openpyxl python-pptx fpdf2 pypdf
python generate_sample_docs.py    # writes docx/xlsx/pptx/pdf
python build_db.py                # ingests → dining_bot.db
```

`build_db.py` auto-runs the generator on first clone if folders are empty.

## Files included

| Format | Files |
|---|---|
| **docx** | Discount Policy, Refund Policy, Employee Handbook, Opening Hours, Menu Guide, Payment Policy |
| **xlsx** | Promo Calendar, Inventory Master, Loyalty Rules, Supplier Prices, Delivery Zones |
| **pptx** | Manager Ops Training, Seating & Patio Ops, Marketing All-Hands |
| **pdf** | Food Safety SOP, Delivery Manual, Health Inspection Report |

## Citations in Dining Bot

Provenance is real: `Discount Policy · Manager limits · v1.2 · docx:Discount_Policy_v1.3.docx`

Edit content in `generate_sample_docs.py`, regenerate, then `python build_db.py`.
