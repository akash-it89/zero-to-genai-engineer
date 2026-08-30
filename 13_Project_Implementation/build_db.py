import sqlite3, os, random, datetime as dt, sys, subprocess
from pathlib import Path

# Write next to this script (not a machine-local absolute path).
DB = str(Path(__file__).resolve().parent / "dining_bot.db")
HERE = Path(__file__).resolve().parent
SAMPLE_DOCS = HERE / "sample_docs"


def ensure_sample_doc_files() -> None:
    """Generate docx/xlsx/pptx/pdf corpus if missing (first clone / fresh setup)."""
    has_any = any(
        list((SAMPLE_DOCS / sub).glob("*"))
        for sub in ("docx", "xlsx", "pptx", "pdf")
        if (SAMPLE_DOCS / sub).is_dir()
    )
    if not has_any:
        print("  sample_docs/ empty — running generate_sample_docs.py …")
        subprocess.run([sys.executable, str(HERE / "generate_sample_docs.py")], check=True)


def load_documents_from_sample_docs(sample_dir: Path):
    from sample_doc_loader import load_all_sample_docs

    return load_all_sample_docs(sample_dir)

if os.path.exists(DB):
    os.remove(DB)

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = ON;")
cur = con.cursor()

# ------------------------------------------------------------------
# SCHEMA  (matches Section 8 of the requirement)
# ------------------------------------------------------------------
cur.executescript("""
-- Single-restaurant assumption. restaurant_id kept on business tables so the
-- north-star multi-tenant path stays reachable, but always = 1 here.

CREATE TABLE menu_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL DEFAULT 1,
    name          TEXT    NOT NULL,
    description   TEXT,
    category      TEXT    NOT NULL,          -- Starters, Main Course, Breads, Rice, Desserts, Beverages
    price         REAL    NOT NULL CHECK (price >= 0),
    is_veg        INTEGER NOT NULL DEFAULT 1 CHECK (is_veg IN (0,1)),
    active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at    TEXT    NOT NULL
);

CREATE TABLE ingredients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL DEFAULT 1,
    name          TEXT    NOT NULL,
    unit          TEXT    NOT NULL,          -- kg, g, l, ml, pcs
    stock         REAL    NOT NULL DEFAULT 0,
    reorder_level REAL    NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL
);

-- links menu items to the ingredients they consume (for future planning work)
CREATE TABLE menu_item_ingredients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item_id  INTEGER NOT NULL REFERENCES menu_items(id),
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    qty           REAL    NOT NULL,          -- amount used per one serving, in ingredient.unit
    UNIQUE(menu_item_id, ingredient_id)
);

CREATE TABLE orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL DEFAULT 1,
    table_no      INTEGER,
    order_type    TEXT    NOT NULL DEFAULT 'dine_in',  -- dine_in, takeaway, delivery
    status        TEXT    NOT NULL,          -- paid, open, cancelled
    subtotal      REAL    NOT NULL DEFAULT 0,
    discount      REAL    NOT NULL DEFAULT 0,
    tax           REAL    NOT NULL DEFAULT 0,
    total         REAL    NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL
);

CREATE TABLE order_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id  INTEGER NOT NULL REFERENCES menu_items(id),
    qty           INTEGER NOT NULL CHECK (qty > 0),
    unit_price    REAL    NOT NULL,          -- price captured at time of order
    line_total    REAL    NOT NULL
);

CREATE TABLE payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id),
    method        TEXT    NOT NULL,          -- card, cash, upi, wallet
    amount        REAL    NOT NULL,
    status        TEXT    NOT NULL,          -- paid, refunded, failed
    paid_at       TEXT
);

-- RAG corpus. embedding stored as JSON text so the file stays pure-SQLite;
-- the team replaces this with a real vector store / pgvector later.
CREATE TABLE documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL DEFAULT 1,
    name          TEXT    NOT NULL,          -- e.g. "Discount Policy"
    section       TEXT,                      -- e.g. "Manager limits"
    version       TEXT    NOT NULL,          -- e.g. "v1.2"
    last_updated  TEXT    NOT NULL,
    chunk         TEXT    NOT NULL,          -- the retrievable text chunk
    source_type   TEXT    NOT NULL DEFAULT 'md',  -- docx, xlsx, pptx, pdf, csv, md, ...
    source_file   TEXT,                      -- original filename e.g. Promo_Calendar.xlsx
    embedding     TEXT                       -- JSON array placeholder, NULL until ingested
);

CREATE TABLE audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id   INTEGER NOT NULL DEFAULT 1,
    actor_id        TEXT    NOT NULL,        -- who proposed the action
    action          TEXT    NOT NULL,        -- e.g. ADD_MENU_ITEM
    payload         TEXT    NOT NULL,        -- JSON of the structured action
    approval_status TEXT    NOT NULL,        -- APPROVED, REJECTED
    approved_by     TEXT,                    -- who approved (HITL); NULL if rejected
    approved_at     TEXT,                    -- when approved; NULL if rejected
    executed_at     TEXT                     -- when the write committed; NULL if not executed
);

CREATE INDEX idx_orders_created  ON orders(created_at);
CREATE INDEX idx_orders_status   ON orders(status);
CREATE INDEX idx_oi_order        ON order_items(order_id);
CREATE INDEX idx_oi_item         ON order_items(menu_item_id);
CREATE INDEX idx_pay_order       ON payments(order_id);
""")

now = dt.datetime(2026, 8, 29, 9, 0, 0)
def iso(d): return d.strftime("%Y-%m-%d %H:%M:%S")

# ------------------------------------------------------------------
# MENU ITEMS  (a believable South-Indian + North-Indian menu)
# category, name, desc, price(AED), is_veg
# ------------------------------------------------------------------
menu = [
    ("Starters", "Veg Spring Rolls", "Crispy rolls stuffed with spiced vegetables", 18.0, 1, 1),
    ("Starters", "Chicken 65", "Spicy deep-fried chicken, curry-leaf tempered", 26.0, 0, 1),
    ("Starters", "Paneer Tikka", "Char-grilled cottage cheese in tandoori spices", 28.0, 1, 1),
    ("Starters", "Gobi Manchurian", "Cauliflower florets in tangy Indo-Chinese sauce", 22.0, 1, 1),
    ("Starters", "Prawn Koliwada", "Batter-fried prawns, Mumbai street style", 34.0, 0, 1),

    ("Main Course", "Butter Chicken", "Tandoori chicken in silky tomato-butter gravy", 42.0, 0, 1),
    ("Main Course", "Paneer Butter Masala", "Cottage cheese in rich makhani gravy", 36.0, 1, 1),
    ("Main Course", "Chicken Biryani", "Hyderabadi dum biryani with basmati rice", 38.0, 0, 1),
    ("Main Course", "Mutton Rogan Josh", "Kashmiri slow-cooked lamb curry", 52.0, 0, 1),
    ("Main Course", "Dal Makhani", "Black lentils simmered overnight with cream", 28.0, 1, 1),
    ("Main Course", "Fish Curry", "Coastal-style fish in coconut-tamarind gravy", 44.0, 0, 1),
    ("Main Course", "Veg Biryani", "Fragrant basmati with seasonal vegetables", 30.0, 1, 1),
    ("Main Course", "Chana Masala", "Chickpeas in onion-tomato masala", 24.0, 1, 1),

    ("Breads", "Butter Naan", "Leavened flatbread brushed with butter", 8.0, 1, 1),
    ("Breads", "Garlic Naan", "Naan topped with garlic and coriander", 10.0, 1, 1),
    ("Breads", "Tandoori Roti", "Whole-wheat flatbread from the tandoor", 6.0, 1, 1),
    ("Breads", "Laccha Paratha", "Flaky layered wheat paratha", 9.0, 1, 1),

    ("Rice", "Steamed Basmati Rice", "Plain long-grain basmati", 12.0, 1, 1),
    ("Rice", "Jeera Rice", "Basmati tempered with cumin", 16.0, 1, 1),

    ("Desserts", "Gulab Jamun", "Milk-solid dumplings in rose syrup (2 pcs)", 14.0, 1, 1),
    ("Desserts", "Gajar Ka Halwa", "Slow-cooked carrot pudding with nuts", 18.0, 1, 1),
    ("Desserts", "Rasmalai", "Cottage-cheese discs in saffron milk (2 pcs)", 16.0, 1, 1),

    ("Beverages", "Masala Chai", "Spiced Indian tea", 8.0, 1, 1),
    ("Beverages", "Sweet Lassi", "Chilled sweet yogurt drink", 12.0, 1, 1),
    ("Beverages", "Fresh Lime Soda", "Lime, soda, sweet or salted", 10.0, 1, 1),
    # two inactive items so the "active" flag is meaningful in the data
    ("Starters", "Mushroom Pepper Fry", "Discontinued seasonal special", 24.0, 1, 0),
    ("Desserts", "Kulfi Falooda", "Off menu - supplier discontinued", 20.0, 1, 0),
]
for i, (cat, name, desc, price, veg, active) in enumerate(menu):
    created = now - dt.timedelta(days=120 - i)  # staggered create dates
    cur.execute("""INSERT INTO menu_items
        (name, description, category, price, is_veg, active, created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (name, desc, cat, price, veg, active, iso(created)))

# map name -> id, and keep active menu ids with prices for order generation
cur.execute("SELECT id, name, price, active FROM menu_items")
rows = cur.fetchall()
name_to_id = {r[1]: r[0] for r in rows}
active_items = [(r[0], r[2]) for r in rows if r[3] == 1]  # (id, price)

# ------------------------------------------------------------------
# INGREDIENTS
# ------------------------------------------------------------------
ingredients = [
    ("Chicken", "kg", 24.0, 10.0),
    ("Mutton", "kg", 9.0, 8.0),          # below reorder -> good demo for "what's low"
    ("Basmati Rice", "kg", 60.0, 20.0),
    ("Paneer", "kg", 14.0, 6.0),
    ("Fish Fillet", "kg", 7.0, 8.0),      # below reorder
    ("Prawns", "kg", 5.0, 5.0),
    ("Onions", "kg", 45.0, 15.0),
    ("Tomatoes", "kg", 38.0, 15.0),
    ("Butter", "kg", 12.0, 5.0),
    ("Cream", "l", 9.0, 4.0),
    ("Wheat Flour", "kg", 50.0, 20.0),
    ("Cauliflower", "kg", 11.0, 6.0),
    ("Chickpeas", "kg", 18.0, 8.0),
    ("Black Lentils", "kg", 16.0, 8.0),
    ("Carrots", "kg", 10.0, 5.0),
    ("Milk", "l", 30.0, 12.0),
    ("Yogurt", "kg", 15.0, 6.0),
    ("Cooking Oil", "l", 40.0, 15.0),
    ("Garlic", "kg", 6.0, 3.0),
    ("Ginger", "kg", 5.0, 3.0),
]
for name, unit, stock, reorder in ingredients:
    cur.execute("""INSERT INTO ingredients (name, unit, stock, reorder_level, updated_at)
        VALUES (?,?,?,?,?)""", (name, unit, stock, reorder, iso(now - dt.timedelta(days=1))))

cur.execute("SELECT id, name FROM ingredients")
ing_id = {r[1]: r[0] for r in cur.fetchall()}

# ------------------------------------------------------------------
# RECIPE LINKS (a subset - enough to be useful, not exhaustive)
# ------------------------------------------------------------------
recipes = {
    "Butter Chicken":       [("Chicken", 0.25), ("Butter", 0.03), ("Tomatoes", 0.15), ("Cream", 0.05)],
    "Paneer Butter Masala": [("Paneer", 0.2), ("Butter", 0.03), ("Tomatoes", 0.15), ("Cream", 0.05)],
    "Chicken Biryani":      [("Chicken", 0.3), ("Basmati Rice", 0.2), ("Onions", 0.1), ("Yogurt", 0.05)],
    "Mutton Rogan Josh":    [("Mutton", 0.35), ("Onions", 0.1), ("Yogurt", 0.08)],
    "Dal Makhani":          [("Black Lentils", 0.15), ("Butter", 0.02), ("Cream", 0.04)],
    "Fish Curry":           [("Fish Fillet", 0.25), ("Tomatoes", 0.1), ("Onions", 0.08)],
    "Veg Biryani":          [("Basmati Rice", 0.2), ("Cauliflower", 0.08), ("Carrots", 0.06)],
    "Chana Masala":         [("Chickpeas", 0.15), ("Onions", 0.08), ("Tomatoes", 0.1)],
    "Gobi Manchurian":      [("Cauliflower", 0.2), ("Cooking Oil", 0.05)],
    "Butter Naan":          [("Wheat Flour", 0.12), ("Butter", 0.01)],
    "Gajar Ka Halwa":       [("Carrots", 0.2), ("Milk", 0.1), ("Cream", 0.03)],
    "Sweet Lassi":          [("Yogurt", 0.2), ("Milk", 0.05)],
}
for item, comps in recipes.items():
    mid = name_to_id[item]
    for ing_name, qty in comps:
        cur.execute("""INSERT INTO menu_item_ingredients (menu_item_id, ingredient_id, qty)
            VALUES (?,?,?)""", (mid, ing_id[ing_name], qty))

# ------------------------------------------------------------------
# ORDERS + ORDER ITEMS + PAYMENTS
# 60 days of history. Weekends busier. Most orders paid; a few open/cancelled.
# Popularity weights make some items clear best-sellers (good for analytics demos).
# ------------------------------------------------------------------
random.seed(42)
TAX_RATE = 0.05  # 5% VAT

# popularity weight per active item id
pop = {}
weights_by_name = {
    "Butter Chicken": 10, "Chicken Biryani": 12, "Garlic Naan": 14, "Butter Naan": 11,
    "Paneer Butter Masala": 8, "Dal Makhani": 7, "Masala Chai": 9, "Gulab Jamun": 6,
    "Veg Biryani": 6, "Sweet Lassi": 5, "Mutton Rogan Josh": 4, "Fish Curry": 4,
    "Jeera Rice": 5, "Steamed Basmati Rice": 5, "Chicken 65": 6, "Paneer Tikka": 5,
}
for iid, price in active_items:
    pass
cur.execute("SELECT id, name, price FROM menu_items WHERE active=1")
active_full = cur.fetchall()
weighted_pool = []
for iid, nm, price in active_full:
    w = weights_by_name.get(nm, 2)
    weighted_pool += [(iid, price)] * w

methods = ["card", "card", "card", "upi", "upi", "cash", "wallet"]

order_id = 0
start_day = now - dt.timedelta(days=60)
for d in range(61):
    day = start_day + dt.timedelta(days=d)
    is_weekend = day.weekday() >= 4  # Fri/Sat busier in UAE week
    base = random.randint(14, 22)
    n_orders = base + (10 if is_weekend else 0)
    for _ in range(n_orders):
        # random time during service hours 12:00-23:00
        hour = random.choices(range(12, 24), weights=[3,5,6,4,2,2,3,6,7,5,3,1])[0]
        minute = random.randint(0, 59)
        created = day.replace(hour=hour, minute=minute, second=random.randint(0,59))

        # order status distribution
        r = random.random()
        if r < 0.90:   status = "paid"
        elif r < 0.96: status = "open"
        else:          status = "cancelled"

        otype = random.choices(["dine_in","takeaway","delivery"], weights=[6,2,2])[0]
        table_no = random.randint(1, 20) if otype == "dine_in" else None

        n_lines = random.randint(1, 5)
        picked = {}
        for _ in range(n_lines):
            iid, price = random.choice(weighted_pool)
            picked[iid] = picked.get(iid, 0) + random.randint(1, 3)

        subtotal = 0.0
        line_rows = []
        for iid, qty in picked.items():
            price = next(p for (i,p) in [(a,c) for a,b,c in active_full] if i == iid)
            lt = round(price * qty, 2)
            subtotal += lt
            line_rows.append((iid, qty, price, lt))

        # occasional discount (manager promo)
        discount = 0.0
        if random.random() < 0.15:
            discount = round(subtotal * random.choice([0.05, 0.10, 0.15]), 2)

        taxable = subtotal - discount
        tax = round(taxable * TAX_RATE, 2)
        total = round(taxable + tax, 2)
        if status == "cancelled":
            total_final = total  # recorded but not paid
        else:
            total_final = total

        cur.execute("""INSERT INTO orders
            (table_no, order_type, status, subtotal, discount, tax, total, created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (table_no, otype, status, round(subtotal,2), discount, tax, total_final, iso(created)))
        order_id = cur.lastrowid

        for iid, qty, price, lt in line_rows:
            cur.execute("""INSERT INTO order_items
                (order_id, menu_item_id, qty, unit_price, line_total)
                VALUES (?,?,?,?,?)""", (order_id, iid, qty, price, lt))

        # payments only for paid orders (+ a couple of refunds)
        if status == "paid":
            pay_status = "paid"
            if random.random() < 0.02:
                pay_status = "refunded"
            paid_at = created + dt.timedelta(minutes=random.randint(20, 90))
            cur.execute("""INSERT INTO payments (order_id, method, amount, status, paid_at)
                VALUES (?,?,?,?,?)""",
                (order_id, random.choice(methods), total_final, pay_status, iso(paid_at)))
            # Keep revenue deterministic: a refunded payment means the order is no
            # longer paid revenue. Mark the order 'refunded' so SUM(orders.total WHERE
            # status='paid') and SUM(payments.amount WHERE status='paid') always agree.
            if pay_status == "refunded":
                cur.execute("UPDATE orders SET status='refunded' WHERE id=?", (order_id,))
        elif status == "open":
            pass  # no payment yet

con.commit()

# ------------------------------------------------------------------
# DOCUMENTS  (RAG corpus — docx / xlsx / pptx / pdf in sample_docs/)
# ------------------------------------------------------------------
ensure_sample_doc_files()
docs = load_documents_from_sample_docs(SAMPLE_DOCS)
for name, section, version, updated, chunk, source_type, source_file in docs:
    cur.execute(
        """INSERT INTO documents
        (name, section, version, last_updated, chunk, source_type, source_file, embedding)
        VALUES (?,?,?,?,?,?,?,NULL)""",
        (name, section, version, updated, chunk, source_type, source_file),
    )
print(f"  Loaded {len(docs)} document chunks from {SAMPLE_DOCS.name}/")

# ------------------------------------------------------------------
# AUDIT LOG  (a few sample rows so the shape is clear)
# ------------------------------------------------------------------
# actor_id, action, payload, approval_status, approved_by, approved_at, executed_at
mgr = "manager-001"
t1 = now - dt.timedelta(days=30, hours=2)
t2 = now - dt.timedelta(days=12, hours=5)
t3 = now - dt.timedelta(days=6, hours=1)
audit = [
    # approved + executed
    (mgr, "ADD_MENU_ITEM",
     '{"action":"ADD_MENU_ITEM","name":"Chicken Biryani","price":38.0,"category":"Main Course"}',
     "APPROVED", mgr, iso(t1), iso(t1 + dt.timedelta(seconds=4))),
    # rejected: no approver, no approved_at, no executed_at
    (mgr, "ADD_MENU_ITEM",
     '{"action":"ADD_MENU_ITEM","name":"Truffle Naan","price":45.0,"category":"Breads"}',
     "REJECTED", None, None, None),
    # approved + executed
    (mgr, "ADD_MENU_ITEM",
     '{"action":"ADD_MENU_ITEM","name":"Rasmalai","price":16.0,"category":"Desserts"}',
     "APPROVED", mgr, iso(t3), iso(t3 + dt.timedelta(seconds=3))),
]
for actor_id, action, payload, status, approver, appr_at, exec_at in audit:
    cur.execute("""INSERT INTO audit_log
        (actor_id, action, payload, approval_status, approved_by, approved_at, executed_at)
        VALUES (?,?,?,?,?,?,?)""",
        (actor_id, action, payload, status, approver, appr_at, exec_at))

con.commit()

# ------------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------------
def count(t):
    return cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

print("=== Dining Bot sample database built ===")
for t in ["menu_items","ingredients","menu_item_ingredients","orders","order_items",
          "payments","documents","audit_log"]:
    print(f"  {t:24s} {count(t):6d} rows")

rev = cur.execute("""SELECT ROUND(SUM(total),2) FROM orders WHERE status='paid'""").fetchone()[0]
rev_pay = cur.execute("""SELECT ROUND(SUM(amount),2) FROM payments WHERE status='paid'""").fetchone()[0]
print(f"\n  Total paid revenue (60d): AED {rev:,.2f}")
print(f"  Revenue via payments    : AED {rev_pay:,.2f}")
assert abs(rev - rev_pay) < 0.01, "REVENUE MISMATCH between orders and payments!"
print("  Revenue definition is consistent across both paths: OK")
top = cur.execute("""
    SELECT m.name, SUM(oi.qty) q
    FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id
    JOIN orders o ON o.id=oi.order_id AND o.status='paid'
    GROUP BY m.id ORDER BY q DESC LIMIT 5""").fetchall()
print("  Top 5 items by qty:")
for n,q in top:
    print(f"    {n:24s} {q}")

con.close()
print("\nWritten:", DB)
