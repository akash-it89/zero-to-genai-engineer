"""SQLite schema for the Helpdesk capstone.

Five tables, real foreign-key relationships, so questions like "show every
high-priority ticket for customer X, who it's assigned to, and the latest
note" require an actual multi-table JOIN, not a single-table lookup.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    plan_tier   TEXT NOT NULL CHECK(plan_tier IN ('free','pro','enterprise')),
    signup_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    team    TEXT NOT NULL CHECK(team IN ('Billing','Technical','Onboarding'))
);

CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    agent_id        INTEGER REFERENCES agents(id),
    subject         TEXT NOT NULL,
    description     TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN ('open','in_progress','closed')) DEFAULT 'open',
    priority        TEXT NOT NULL CHECK(priority IN ('low','medium','high')) DEFAULT 'medium',
    screenshot_path TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id),
    author      TEXT NOT NULL,
    note_text   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    category    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""
