-- Dining Bot sample database schema (SQLite) — v1.1
-- Generated for the Zero to GenAI Engineer capstone

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

CREATE TABLE ingredients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL DEFAULT 1,
    name          TEXT    NOT NULL,
    unit          TEXT    NOT NULL,          -- kg, g, l, ml, pcs
    stock         REAL    NOT NULL DEFAULT 0,
    reorder_level REAL    NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL
);

CREATE TABLE menu_item_ingredients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item_id  INTEGER NOT NULL REFERENCES menu_items(id),
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    qty           REAL    NOT NULL,          -- amount used per one serving, in ingredient.unit
    UNIQUE(menu_item_id, ingredient_id)
);

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

CREATE TABLE order_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id  INTEGER NOT NULL REFERENCES menu_items(id),
    qty           INTEGER NOT NULL CHECK (qty > 0),
    unit_price    REAL    NOT NULL,          -- price captured at time of order
    line_total    REAL    NOT NULL
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

CREATE TABLE payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id),
    method        TEXT    NOT NULL,          -- card, cash, upi, wallet
    amount        REAL    NOT NULL,
    status        TEXT    NOT NULL,          -- paid, refunded, failed
    paid_at       TEXT
);

CREATE TABLE sqlite_sequence(name,seq);

CREATE INDEX idx_oi_item         ON order_items(menu_item_id);

CREATE INDEX idx_oi_order        ON order_items(order_id);

CREATE INDEX idx_orders_created  ON orders(created_at);

CREATE INDEX idx_orders_status   ON orders(status);

CREATE INDEX idx_pay_order       ON payments(order_id);

