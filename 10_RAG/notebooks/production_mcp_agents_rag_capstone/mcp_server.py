"""Helpdesk MCP server — structured DB tools and a RAG search tool, side by side.

Every tool below is reachable the exact same way over the MCP protocol: a plain
Python function, a docstring the calling LLM reads to decide when to use it, and
type-hinted arguments FastMCP turns into a JSON schema automatically. Nothing
about the *protocol* changes between a tool that runs `SELECT` and a tool that
runs a full hybrid-search + rerank RAG pipeline — that's the point of this file.

Run directly for local testing (stdio transport):
    python mcp_server.py
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).parent
DB_PATH = HERE / "helpdesk.db"
KB_DIR = HERE / "kb_articles"

# This server is spawned as its own subprocess (stdio transport) — it doesn't
# automatically inherit whatever .env-loading the parent notebook already did,
# so it loads its own copy of the same .env explicitly.
load_dotenv(HERE.parent.parent / ".env")

# The reused production RAG pipeline lives one directory over, in its own module —
# imported, not reimplemented. See seed_data.export_kb_to_files() for how the
# kb_articles table becomes the .txt files this pipeline ingests.
sys.path.insert(0, str(HERE.parent / "production_rag_chatbot"))
from rag_pipeline import ProductionRAGChatbot  # noqa: E402

sys.path.insert(0, str(HERE))
from seed_data import export_kb_to_files  # noqa: E402

mcp = FastMCP("helpdesk")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOMER TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_customer(name: str, email: str, plan_tier: str) -> dict:
    """Create a new customer record. plan_tier must be one of: free, pro, enterprise.
    Returns the newly created customer including its id."""
    if plan_tier not in ("free", "pro", "enterprise"):
        return {"error": f"Invalid plan_tier {plan_tier!r} — must be free, pro, or enterprise."}
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO customers (name, email, plan_tier, signup_date) VALUES (?, ?, ?, ?)",
            (name, email, plan_tier, _now()[:10]),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    except sqlite3.IntegrityError as e:
        return {"error": f"Could not create customer: {e}"}
    finally:
        conn.close()


@mcp.tool()
def get_customer(customer_id: int) -> dict:
    """Fetch a single customer by id, including their name, email, and plan tier."""
    conn = _connect()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else {"error": f"No customer with id {customer_id}."}


@mcp.tool()
def update_customer(customer_id: int, name: str | None = None, email: str | None = None,
                     plan_tier: str | None = None) -> dict:
    """Update one or more fields on an existing customer. Only pass the fields you
    want to change — omitted fields are left unchanged. Returns the updated customer."""
    conn = _connect()
    existing = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not existing:
        conn.close()
        return {"error": f"No customer with id {customer_id}."}
    new_name = name if name is not None else existing["name"]
    new_email = email if email is not None else existing["email"]
    new_plan = plan_tier if plan_tier is not None else existing["plan_tier"]
    if new_plan not in ("free", "pro", "enterprise"):
        conn.close()
        return {"error": f"Invalid plan_tier {new_plan!r} — must be free, pro, or enterprise."}
    conn.execute(
        "UPDATE customers SET name = ?, email = ?, plan_tier = ? WHERE id = ?",
        (new_name, new_email, new_plan, customer_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def search_customers(name_contains: str) -> list[dict]:
    """Search for customers whose name contains the given text (case-insensitive).
    Use this when the user gives a customer's name but not their exact id."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM customers WHERE name LIKE ? ORDER BY name", (f"%{name_contains}%",)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# AGENT TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_agents() -> list[dict]:
    """List every support agent and which team they're on (Billing, Technical, or Onboarding)."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM agents ORDER BY team, name").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# TICKET TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_ticket(customer_id: int, subject: str, description: str,
                   priority: str = "medium") -> dict:
    """Open a new support ticket for a customer. priority must be one of: low, medium, high.
    The ticket starts unassigned (no agent) and with status 'open'. Returns the new ticket."""
    if priority not in ("low", "medium", "high"):
        return {"error": f"Invalid priority {priority!r} — must be low, medium, or high."}
    conn = _connect()
    customer = conn.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not customer:
        conn.close()
        return {"error": f"No customer with id {customer_id}."}
    now = _now()
    cur = conn.execute(
        """INSERT INTO tickets (customer_id, agent_id, subject, description, status,
           priority, screenshot_path, created_at, updated_at)
           VALUES (?, NULL, ?, ?, 'open', ?, NULL, ?, ?)""",
        (customer_id, subject, description, priority, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def get_ticket(ticket_id: int) -> dict:
    """Fetch full details of a single ticket by id, including its current status,
    priority, and which customer/agent (if any) it belongs to."""
    conn = _connect()
    row = conn.execute(
        """SELECT t.*, c.name AS customer_name, a.name AS agent_name
           FROM tickets t
           JOIN customers c ON t.customer_id = c.id
           LEFT JOIN agents a ON t.agent_id = a.id
           WHERE t.id = ?""",
        (ticket_id,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else {"error": f"No ticket with id {ticket_id}."}


@mcp.tool()
def update_ticket_status(ticket_id: int, status: str) -> dict:
    """Change a ticket's status. status must be one of: open, in_progress, closed.
    For closing a ticket, prefer the close_ticket tool instead, which also records a
    resolution note."""
    if status not in ("open", "in_progress", "closed"):
        return {"error": f"Invalid status {status!r} — must be open, in_progress, or closed."}
    conn = _connect()
    existing = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existing:
        conn.close()
        return {"error": f"No ticket with id {ticket_id}."}
    conn.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?", (status, _now(), ticket_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def update_ticket_priority(ticket_id: int, priority: str) -> dict:
    """Change a ticket's priority. priority must be one of: low, medium, high."""
    if priority not in ("low", "medium", "high"):
        return {"error": f"Invalid priority {priority!r} — must be low, medium, or high."}
    conn = _connect()
    existing = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existing:
        conn.close()
        return {"error": f"No ticket with id {ticket_id}."}
    conn.execute(
        "UPDATE tickets SET priority = ?, updated_at = ? WHERE id = ?", (priority, _now(), ticket_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def assign_ticket(ticket_id: int, agent_id: int) -> dict:
    """Assign a ticket to a specific support agent by agent id. Use list_agents first
    if you only know the agent's name."""
    conn = _connect()
    ticket = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    agent = conn.execute("SELECT id, name FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not ticket:
        conn.close()
        return {"error": f"No ticket with id {ticket_id}."}
    if not agent:
        conn.close()
        return {"error": f"No agent with id {agent_id}."}
    conn.execute(
        "UPDATE tickets SET agent_id = ?, updated_at = ? WHERE id = ?", (agent_id, _now(), ticket_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def close_ticket(ticket_id: int, resolution_note: str) -> dict:
    """Close a ticket AND record how it was resolved, in one step. This is a
    DESTRUCTIVE, hard-to-reverse action — always confirm with the user what the
    resolution was before calling this."""
    conn = _connect()
    existing = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existing:
        conn.close()
        return {"error": f"No ticket with id {ticket_id}."}
    now = _now()
    conn.execute("UPDATE tickets SET status = 'closed', updated_at = ? WHERE id = ?", (now, ticket_id))
    conn.execute(
        "INSERT INTO ticket_notes (ticket_id, author, note_text, created_at) VALUES (?, ?, ?, ?)",
        (ticket_id, "AI Support Agent", resolution_note, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def delete_ticket(ticket_id: int) -> dict:
    """Permanently delete a ticket and all of its notes. This is DESTRUCTIVE and
    IRREVERSIBLE — prefer close_ticket in almost every case. Only use this for
    genuine duplicates or test data."""
    conn = _connect()
    existing = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existing:
        conn.close()
        return {"error": f"No ticket with id {ticket_id}."}
    conn.execute("DELETE FROM ticket_notes WHERE ticket_id = ?", (ticket_id,))
    conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return {"deleted_ticket_id": ticket_id}


@mcp.tool()
def list_tickets_by_customer(customer_id: int, status: str | None = None) -> list[dict]:
    """List every ticket belonging to one customer, optionally filtered by status
    (open, in_progress, closed)."""
    conn = _connect()
    if status:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE customer_id = ? AND status = ? ORDER BY created_at DESC",
            (customer_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


@mcp.tool()
def list_tickets_by_agent(agent_id: int, status: str | None = None) -> list[dict]:
    """List every ticket assigned to one agent, optionally filtered by status."""
    conn = _connect()
    if status:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE agent_id = ? AND status = ? ORDER BY created_at DESC",
            (agent_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# TICKET NOTES TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def add_ticket_note(ticket_id: int, author: str, note_text: str) -> dict:
    """Append a note to a ticket's history without changing its status. Use this
    to log progress on an open or in_progress ticket."""
    conn = _connect()
    existing = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existing:
        conn.close()
        return {"error": f"No ticket with id {ticket_id}."}
    now = _now()
    cur = conn.execute(
        "INSERT INTO ticket_notes (ticket_id, author, note_text, created_at) VALUES (?, ?, ?, ?)",
        (ticket_id, author, note_text, now),
    )
    conn.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
    conn.commit()
    row = conn.execute("SELECT * FROM ticket_notes WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return _row_to_dict(row)


@mcp.tool()
def get_ticket_notes(ticket_id: int) -> list[dict]:
    """Get the full note history/timeline for one ticket, oldest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM ticket_notes WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-TABLE INSIGHT TOOLS — these are the ones that actually require a JOIN
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_customer_support_history(customer_id: int) -> dict:
    """Get a single combined view of everything about one customer's support
    history: their profile, every ticket they've ever opened, which agent handled
    each one, and the most recent note on each ticket. This joins customers,
    tickets, agents, and ticket_notes in one call instead of four separate lookups."""
    conn = _connect()
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not customer:
        conn.close()
        return {"error": f"No customer with id {customer_id}."}
    tickets = conn.execute(
        """SELECT t.id, t.subject, t.status, t.priority, t.created_at,
                  a.name AS agent_name, a.team AS agent_team
           FROM tickets t
           LEFT JOIN agents a ON t.agent_id = a.id
           WHERE t.customer_id = ?
           ORDER BY t.created_at DESC""",
        (customer_id,),
    ).fetchall()
    result_tickets = []
    for t in tickets:
        latest_note = conn.execute(
            "SELECT note_text, created_at FROM ticket_notes WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
            (t["id"],),
        ).fetchone()
        d = _row_to_dict(t)
        d["latest_note"] = _row_to_dict(latest_note) if latest_note else None
        result_tickets.append(d)
    conn.close()
    return {
        "customer": _row_to_dict(customer),
        "total_tickets": len(result_tickets),
        "open_tickets": sum(1 for t in result_tickets if t["status"] != "closed"),
        "tickets": result_tickets,
    }


@mcp.tool()
def get_agent_workload() -> list[dict]:
    """Get every agent's current workload: how many open + in_progress tickets
    each one is carrying right now, sorted busiest first. Joins agents and tickets
    with a GROUP BY — use this to answer 'who is overloaded' or 'who should this
    new ticket go to' style questions."""
    conn = _connect()
    rows = conn.execute(
        """SELECT a.id, a.name, a.team,
                  SUM(CASE WHEN t.status != 'closed' THEN 1 ELSE 0 END) AS active_tickets,
                  SUM(CASE WHEN t.status = 'closed' THEN 1 ELSE 0 END) AS closed_tickets
           FROM agents a
           LEFT JOIN tickets t ON t.agent_id = a.id
           GROUP BY a.id
           ORDER BY active_tickets DESC"""
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE TOOLS — RAG, wrapped as MCP tools exactly like the SQL ones
# ═══════════════════════════════════════════════════════════════════════════

_rag_bot: ProductionRAGChatbot | None = None


def _get_rag_bot() -> ProductionRAGChatbot:
    """Lazily build the hybrid-search + rerank RAG index once per server process,
    over whatever .txt files are currently exported from kb_articles. Reused on
    every search_knowledge_base call instead of rebuilding per call."""
    global _rag_bot
    if _rag_bot is None:
        _rag_bot = ProductionRAGChatbot(top_k=8, top_n=4, model="gpt-4o-mini")
        paths = sorted(str(p) for p in KB_DIR.glob("*.txt"))
        _rag_bot.ingest(paths)
    return _rag_bot


@mcp.tool()
def search_knowledge_base(question: str) -> dict:
    """Answer a question from the support knowledge base (password resets, billing
    policy, API rate limits, data export, 2FA, integrations, cancellation policy,
    etc.) using hybrid retrieval + reranking, grounded with citations. Use this for
    'how do I...' / 'what is your policy on...' style questions — NOT for looking up
    a specific customer's ticket, which lives in the database instead."""
    bot = _get_rag_bot()
    bot.history = []  # each tool call is independent — no cross-call memory bleed
    result = bot.chat(question)
    return {
        "answer": result["answer"],
        "sources": [{"title": s["source"], "score": s["score"]} for s in result["sources"]],
    }


@mcp.tool()
def create_kb_article(title: str, content: str, category: str) -> dict:
    """Publish a new knowledge base article — for example, turning a resolved
    ticket's solution into a reusable article. The article becomes searchable via
    search_knowledge_base immediately (the index is rebuilt after every new
    article)."""
    global _rag_bot
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO kb_articles (title, content, category, created_at) VALUES (?, ?, ?, ?)",
        (title, content, category, _now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM kb_articles WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()

    export_kb_to_files()
    _rag_bot = None  # force a rebuild on the next search_knowledge_base call

    return _row_to_dict(row)


if __name__ == "__main__":
    mcp.run()
