"""Generates helpdesk.db (SQLite) with realistic, joinable seed data, and writes
the KB article bodies out as .txt files for the RAG pipeline to ingest.

Run directly to (re)build the database from scratch:
    python seed_data.py
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from schema import SCHEMA_SQL

HERE = Path(__file__).parent
DB_PATH = HERE / "helpdesk.db"
KB_DIR = HERE / "kb_articles"

random.seed(42)  # deterministic — same DB every time this is run, for reproducible teaching demos

# ── Agents: 6 agents, 3 teams, 2 each ───────────────────────────────────────
AGENTS = [
    ("Maria Chen", "Billing"),
    ("Tom Okafor", "Billing"),
    ("Aisha Rahman", "Technical"),
    ("Diego Fernandez", "Technical"),
    ("Liam O'Brien", "Onboarding"),
    ("Priya Nair", "Onboarding"),
]

# ── Customers: a handful of "notable" ones with deliberate ticket patterns,
# plus filler customers for realistic volume ────────────────────────────────
NOTABLE_CUSTOMERS = [
    # (name, email, plan_tier, signup_date)
    ("Jane Doe", "jane.doe@brightframe.io", "enterprise", "2024-01-15"),
    ("Marcus Webb", "marcus@webbstudio.com", "pro", "2024-03-02"),
    ("Sofia Martins", "sofia.martins@lumen.co", "enterprise", "2023-11-20"),
    ("Rahul Verma", "rahul.v@quickcart.in", "pro", "2024-05-10"),
    ("Elena Petrova", "elena@petrovadesign.com", "free", "2024-07-01"),
]
FILLER_FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Drew",
                "Nina", "Omar", "Grace", "Felix", "Hana", "Leo", "Zara", "Ivan", "Ruth", "Kai", "Amara", "Noah"]
FILLER_LAST = ["Kim", "Patel", "Nguyen", "Silva", "Novak", "Haddad", "Okoro", "Larsen",
               "Costa", "Iqbal", "Weiss", "Tanaka", "Osei", "Byrne", "Sato", "Duarte", "Berg", "Aziz", "Lund", "Reyes"]
PLAN_TIERS = ["free", "pro", "enterprise"]


def build_customers():
    customers = list(NOTABLE_CUSTOMERS)
    used_emails = {c[1] for c in customers}
    while len(customers) < 22:
        first, last = random.choice(FILLER_FIRST), random.choice(FILLER_LAST)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}@example.com"
        if email in used_emails:
            continue
        used_emails.add(email)
        plan = random.choices(PLAN_TIERS, weights=[0.45, 0.4, 0.15])[0]
        days_ago = random.randint(10, 500)
        signup = (datetime(2026, 1, 1) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        customers.append((name, email, plan, signup))
    return customers


# ── Tickets: deliberately give Jane Doe (enterprise) a rich multi-ticket
# history, and skew workload so agents are NOT evenly loaded — both matter
# for the JOIN-powered "insight" tools to have a real, non-trivial answer.
TICKET_TEMPLATES = [
    ("Can't reset my password", "I clicked the reset link but it says expired. Can you help?", "Technical"),
    ("Invoice amount looks wrong", "My invoice this month is higher than usual, can someone check?", "Billing"),
    ("API returning 429 errors", "We're getting rate limited constantly since yesterday.", "Technical"),
    ("How do I export all my data?", "Need a full CSV export of the last 6 months.", "Technical"),
    ("Want to upgrade to Enterprise", "We're growing fast and need the Enterprise plan features.", "Billing"),
    ("Integration with our CRM broke", "Webhook stopped firing two days ago, no errors logged on our side.", "Technical"),
    ("Requesting a refund", "We were charged after cancelling, please refund.", "Billing"),
    ("2FA backup codes not working", "None of my 10 backup codes are being accepted.", "Technical"),
    ("Downgrade timing question", "If I downgrade today, when does it actually take effect?", "Billing"),
    ("Onboarding call follow-up", "Can we schedule a follow-up to review our workspace setup?", "Onboarding"),
    ("New team member access", "Need to add 3 new teammates to our workspace.", "Onboarding"),
    ("Late payment fee dispute", "I paid on day 6, was that within the grace period?", "Billing"),
]

STATUS_WEIGHTS = {"open": 0.35, "in_progress": 0.25, "closed": 0.40}
PRIORITY_WEIGHTS = {"low": 0.3, "medium": 0.45, "high": 0.25}


def build_tickets(customer_ids: list[int], agent_ids: dict[str, list[int]]):
    """agent_ids: team name -> list of agent ids on that team."""
    tickets = []
    now = datetime(2026, 8, 1)

    # Jane Doe (customer_ids[0]) gets a deliberately rich history: 4 tickets,
    # mixed status/priority, so "customer support history" has real substance.
    jane_id = customer_ids[0]
    jane_tickets = [
        (jane_id, "Can't reset my password", "I clicked the reset link but it says expired.", "closed", "medium", 40),
        (jane_id, "API returning 429 errors", "We're getting rate limited constantly since yesterday.", "in_progress", "high", 5),
        (jane_id, "Want to upgrade to Enterprise", "Already Enterprise — question about a second workspace.", "closed", "low", 90),
        (jane_id, "Integration with our CRM broke", "Webhook stopped firing two days ago.", "open", "high", 1),
    ]
    for cid, subj, desc, status, pri, days_ago in jane_tickets:
        team = "Technical" if "API" in subj or "Integration" in subj or "reset" in subj else "Billing"
        agent = random.choice(agent_ids[team]) if status != "open" else (random.choice(agent_ids[team]) if random.random() > 0.3 else None)
        created = now - timedelta(days=days_ago)
        tickets.append((cid, agent, subj, desc, status, pri, None, created, created + timedelta(hours=random.randint(1, 48))))

    # Everyone else gets 0-3 tickets, randomly distributed but skewed so
    # Technical agents end up busier than Onboarding agents (real workload variance).
    for cid in customer_ids[1:]:
        n = random.choices([0, 1, 2, 3], weights=[0.25, 0.4, 0.25, 0.1])[0]
        for _ in range(n):
            subj, desc, team = random.choice(TICKET_TEMPLATES)
            status = random.choices(list(STATUS_WEIGHTS), weights=list(STATUS_WEIGHTS.values()))[0]
            priority = random.choices(list(PRIORITY_WEIGHTS), weights=list(PRIORITY_WEIGHTS.values()))[0]
            days_ago = random.randint(1, 180)
            created = now - timedelta(days=days_ago)
            # Technical team gets picked more often -> heavier workload, on purpose.
            weighted_team = random.choices([team, "Technical"], weights=[0.6, 0.4])[0]
            agent = random.choice(agent_ids[weighted_team]) if status != "open" or random.random() > 0.4 else None
            tickets.append((cid, agent, subj, desc, status, priority, None,
                             created, created + timedelta(hours=random.randint(1, 72))))

    return tickets


NOTE_SNIPPETS_EARLY = [
    "Confirmed the issue on our end, investigating root cause.",
    "Asked customer for more details, awaiting response.",
    "Escalated to engineering for further review.",
    "Reproduced the bug locally, filing internal ticket.",
]
NOTE_SNIPPETS_LATE = [
    "Applied the fix, monitoring for recurrence.",
    "Customer confirmed the issue is resolved.",
    "Followed up with billing team to verify charge.",
    "Provided step-by-step instructions via email.",
]


def build_notes(ticket_rows_with_ids):
    """ticket_rows_with_ids: list of (ticket_id, agent_name_or_None, status)"""
    notes = []
    for ticket_id, agent_name, status in ticket_rows_with_ids:
        if agent_name is None:
            continue
        n_notes = {"open": random.choice([0, 1]), "in_progress": random.choice([1, 2]),
                   "closed": random.choice([1, 2, 3])}[status]
        base_time = datetime(2026, 8, 1) - timedelta(days=random.randint(0, 30))
        # Sample without replacement so a single ticket never repeats the same note
        # text twice, and closed tickets end on a resolution-sounding note.
        if n_notes == 0:
            continue
        if status == "closed" and n_notes >= 2:
            chosen = random.sample(NOTE_SNIPPETS_EARLY, n_notes - 1) + [random.choice(NOTE_SNIPPETS_LATE)]
        else:
            pool = NOTE_SNIPPETS_EARLY + NOTE_SNIPPETS_LATE
            chosen = random.sample(pool, min(n_notes, len(pool)))
        for i, text in enumerate(chosen):
            notes.append((ticket_id, agent_name, text, base_time + timedelta(hours=i * 6)))
    return notes


# ── KB articles: real content with specific, verifiable facts ──────────────
KB_ARTICLES = [
    ("How to Reset Your Password", "Account", """\
To reset your password, go to the login page and click "Forgot Password." Enter the email
address associated with your account and check your inbox for a reset link. The reset link
is valid for 30 minutes — if it expires, simply request a new one from the same page. Once
you click the link, choose a new password that is at least 10 characters long and includes
at least one number. For security, you will be logged out of all other active sessions once
your password is changed."""),

    ("Billing FAQ: Understanding Your Invoice", "Billing", """\
Invoices are generated automatically on the 1st of every month and reflect usage from the
previous billing cycle. Payment is due within 14 days of the invoice date. If payment is not
received, a 5-day grace period applies before any penalty — after the grace period, a late
fee of 1.5% of the outstanding balance is added per month until the invoice is paid. We accept
credit card payments on all plans; ACH bank transfer is available only on the Enterprise plan."""),

    ("How to Export Your Data", "Data", """\
You can export your data at any time from Settings > Data > Export. Choose either CSV or JSON
format. Exports of up to 100,000 rows are generated instantly and available for download
immediately. Larger exports are processed in the background and emailed to you as a download
link within 24 hours. Free tier accounts are limited to 1 export per calendar month; Pro and
Enterprise accounts have unlimited exports."""),

    ("Upgrading or Downgrading Your Plan", "Billing", """\
Upgrading your plan takes effect immediately, and billing is prorated for the remainder of
the current cycle. Downgrading takes effect at the start of your next billing cycle — you
keep your current plan's features until then, so there is no service interruption.
Enterprise plans require contacting our sales team directly and carry a minimum 12-month
contract term; Enterprise accounts cannot be self-service downgraded from the dashboard."""),

    ("API Rate Limits Explained", "Technical", """\
API rate limits scale with your plan: Free tier allows 100 requests per minute, Pro tier
allows 1,000 requests per minute, and Enterprise allows 10,000 requests per minute (higher
limits are negotiable for Enterprise customers with sustained high-volume needs). Exceeding
your limit returns an HTTP 429 status code. When you receive a 429, your client should back
off and wait at least 60 seconds before retrying — repeated immediate retries can extend
your rate-limit window."""),

    ("Setting Up Two-Factor Authentication", "Account", """\
Enable two-factor authentication from Settings > Security > Enable 2FA. We support
authenticator apps using TOTP (Google Authenticator, Authy, etc.) as well as SMS-based codes.
When you enable 2FA, the system generates 10 single-use backup codes — store these somewhere
safe, since each code only works once and they are the only way back into your account if you
lose access to your authenticator device. Two-factor authentication is mandatory for all
Enterprise accounts and cannot be disabled by individual users on an Enterprise workspace."""),

    ("Troubleshooting Failed Integrations", "Technical", """\
If an integration or webhook stops working, check three things first: (1) API keys expire
automatically after 90 days of inactivity — regenerate the key if it's expired, (2) confirm
the webhook URL configured on your end is still correct and reachable, and (3) if you use an
IP allowlist, make sure our servers' IP range, 203.0.113.0/24, is allowed through your
firewall. You can review exactly what was sent and received under Settings > Integrations >
Logs — logs are retained for 30 days."""),

    ("Our Cancellation and Refund Policy", "Billing", """\
You can cancel your subscription at any time from Settings > Subscription > Cancel, and there
is no cancellation fee. Refunds are only available for charges made within the last 14 days —
if your most recent charge was within that window, you'll receive a prorated refund
automatically; charges older than 14 days are not eligible for a refund. After cancellation,
your account data is retained for 30 days in case you change your mind, and then it is
permanently deleted from our systems."""),
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    KB_DIR.mkdir(exist_ok=True)
    for f in KB_DIR.glob("*.txt"):
        f.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)

    # Agents
    agent_ids_by_team: dict[str, list[int]] = {"Billing": [], "Technical": [], "Onboarding": []}
    for name, team in AGENTS:
        cur = conn.execute("INSERT INTO agents (name, team) VALUES (?, ?)", (name, team))
        agent_ids_by_team[team].append(cur.lastrowid)
    agent_id_to_name = {}
    for row in conn.execute("SELECT id, name FROM agents"):
        agent_id_to_name[row[0]] = row[1]

    # Customers
    customers = build_customers()
    customer_ids = []
    for name, email, plan, signup in customers:
        cur = conn.execute(
            "INSERT INTO customers (name, email, plan_tier, signup_date) VALUES (?, ?, ?, ?)",
            (name, email, plan, signup),
        )
        customer_ids.append(cur.lastrowid)

    # Tickets
    tickets = build_tickets(customer_ids, agent_ids_by_team)
    ticket_ids_for_notes = []
    for cid, agent_id, subj, desc, status, pri, screenshot, created, updated in tickets:
        cur = conn.execute(
            """INSERT INTO tickets (customer_id, agent_id, subject, description, status,
               priority, screenshot_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, agent_id, subj, desc, status, pri, screenshot,
             created.strftime("%Y-%m-%d %H:%M:%S"), updated.strftime("%Y-%m-%d %H:%M:%S")),
        )
        agent_name = agent_id_to_name.get(agent_id) if agent_id else None
        ticket_ids_for_notes.append((cur.lastrowid, agent_name, status))

    # Notes
    notes = build_notes(ticket_ids_for_notes)
    for ticket_id, author, text, ts in notes:
        conn.execute(
            "INSERT INTO ticket_notes (ticket_id, author, note_text, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, author, text, ts.strftime("%Y-%m-%d %H:%M:%S")),
        )

    # KB articles: stored in DB (source of truth) AND materialized as .txt files
    # for the RAG pipeline's file-based ingest() — see export_kb_to_files().
    for title, category, content in KB_ARTICLES:
        conn.execute(
            "INSERT INTO kb_articles (title, content, category, created_at) VALUES (?, ?, ?, ?)",
            (title, content, category, "2026-01-01 00:00:00"),
        )

    conn.commit()

    n_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    n_agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    n_tickets = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    n_notes = conn.execute("SELECT COUNT(*) FROM ticket_notes").fetchone()[0]
    n_kb = conn.execute("SELECT COUNT(*) FROM kb_articles").fetchone()[0]
    conn.close()

    export_kb_to_files()

    print(f"Built {DB_PATH.name}: {n_customers} customers, {n_agents} agents, "
          f"{n_tickets} tickets, {n_notes} notes, {n_kb} KB articles.")


def export_kb_to_files():
    """Materialize every kb_articles DB row as a .txt file in KB_DIR, so the
    RAG pipeline (which ingests file paths) can index them. The DB row is the
    source of truth; these files are a regenerable export, not a second copy
    to maintain by hand."""
    KB_DIR.mkdir(exist_ok=True)
    for f in KB_DIR.glob("*.txt"):
        f.unlink()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, title, content FROM kb_articles").fetchall()
    conn.close()
    paths = []
    for article_id, title, content in rows:
        slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:40].strip("_")
        path = KB_DIR / f"{article_id:02d}_{slug}.txt"
        path.write_text(f"{title}\n\n{content}", encoding="utf-8")
        paths.append(path)
    return paths


if __name__ == "__main__":
    main()
