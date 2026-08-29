# Dining Bot — Sample Database

A ready-to-run SQLite database for the Dining Bot capstone. No server, no setup —
one file your whole team can open, query, and commit.

## Files

| File | What it is |
|---|---|
| `dining_bot.db` | The SQLite database, fully seeded. This is the one you connect to. |
| `schema.sql` | The schema (CREATE TABLE / INDEX statements) for reference. |
| `build_db.py` | The generator. Re-run it to rebuild `dining_bot.db` from scratch. |
| `QUERIES.sql` | 15 tested analytics queries — the read-only SELECTs the Analytics subgraph produces. |
| `README_DATABASE.md` | This file. |

## Quick start

```python
import sqlite3
con = sqlite3.connect("dining_bot.db")
con.execute("PRAGMA foreign_keys = ON;")
cur = con.cursor()
cur.execute("SELECT ROUND(SUM(total),2) FROM orders WHERE status='paid';")
print(cur.fetchone())      # total paid revenue
con.close()
```

Rebuild any time (data is deterministic — `random.seed(42)`):

```bash
python3 build_db.py
```

## What's inside

Single restaurant ("restaurant_id = 1" everywhere). ~60 days of order history
ending 2026-08-29, with weekends busier, believable best-sellers, occasional
discounts and refunds, and a small set of inactive menu items so the `active`
flag actually means something.

| Table | Rows | Purpose in the build |
|---|---|---|
| `menu_items` | 27 | Menu — the read source and the one write target (add menu item). Includes 2 inactive rows. |
| `ingredients` | 20 | Stock levels with reorder thresholds. Read-only context. |
| `menu_item_ingredients` | 36 | Recipe links (item → ingredients). For later planning work. |
| `orders` | ~1,370 | Order headers. `status` is paid / open / cancelled. Drives revenue analytics. |
| `order_items` | ~3,900 | Line items. Drives top-item and category analytics. |
| `payments` | ~1,240 | One per paid order; a few refunds. Method = card / upi / cash / wallet. |
| `documents` | 10 | RAG corpus — real policy / SOP / menu chunks. `embedding` is NULL until you ingest. |
| `audit_log` | 3 | Sample rows showing the HITL write lifecycle: `actor_id, action, payload, approval_status, approved_by, approved_at, executed_at` (2 approved+executed, 1 rejected with NULL approver/exec). |

## The two design rules baked into the data

1. **Structured facts live in SQL; unstructured knowledge lives in `documents`.**
   "What was last week's revenue?" → `orders` (see QUERIES.sql).
   "What's our discount policy?" → `documents` (RAG). The router must never cross these.

2. **`documents.embedding` is deliberately empty.** The Knowledge subgraph fills it
   during ingestion. Storing embeddings as text/JSON keeps this a pure single-file
   SQLite database; swap in a real vector index when you outgrow it.

## Enforcing the read-only rule in SQLite

SQLite has no per-role GRANT like Postgres, so the Analytics subgraph enforces
read-only at the connection, not the database:

```python
# read-only connection for the analytics / RAG path
con = sqlite3.connect("file:dining_bot.db?mode=ro", uri=True)
```

Combined with the SQL validator (reject anything that isn't a single SELECT),
this is the two-guard defense from the requirement. The write path (add menu
item, after approval) uses a separate normal connection held only by trusted code.

## Notes for the team

- Money is in AED with a flat 5% VAT already computed into `orders.tax` / `total`.
- **Revenue is deterministic.** `orders.status` is one of paid / open / cancelled / refunded.
  A refunded order also has a refunded payment, so `SUM(orders.total) WHERE status='paid'`
  and `SUM(payments.amount) WHERE status='paid'` return the **same** number (AED 176,590.10).
  The requirement pins revenue to the `orders.total` form; both paths agree by design so a
  student who joins to payments won't get a different answer. The build script asserts this.
- Timestamps are `TEXT` in `YYYY-MM-DD HH:MM:SS` — use SQLite's `date()` / `strftime()`.
- `unit_price` on `order_items` is captured at order time, so changing a menu
  price later won't rewrite history (correct behaviour — don't "fix" it).
- Everything is deterministic. If two people rebuild, they get identical data.
