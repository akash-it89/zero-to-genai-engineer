"""Rigorous standalone tests of every MCP tool function, called directly (no
agent, no MCP protocol involved) — proves the server's actual logic is correct
before any LangChain/agent wiring gets blamed for a bug that's really in here.

Run: python test_tools_standalone.py
Rebuilds helpdesk.db fresh first so results are deterministic and repeatable.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

# Fresh DB every run — these tests both read AND write, so a stale DB from a
# previous run would make failures ambiguous.
subprocess.run([sys.executable, str(HERE / "seed_data.py")], check=True, cwd=HERE)

import mcp_server as s  # noqa: E402  (must import after fresh DB is built)

passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


print("=== CUSTOMER TOOLS ===")
new_cust = s.create_customer("Test Customer", "test.customer@example.com", "pro")
check("create_customer returns id", "id" in new_cust and new_cust["id"] > 0, new_cust)
check("create_customer stores correct plan_tier", new_cust["plan_tier"] == "pro", new_cust)

bad_plan = s.create_customer("Bad Plan", "bad.plan@example.com", "gold")
check("create_customer rejects invalid plan_tier", "error" in bad_plan, bad_plan)

fetched = s.get_customer(new_cust["id"])
check("get_customer round-trips the same email", fetched["email"] == "test.customer@example.com", fetched)

missing = s.get_customer(999999)
check("get_customer reports missing id as error", "error" in missing, missing)

updated = s.update_customer(new_cust["id"], plan_tier="enterprise")
check("update_customer changes plan_tier", updated["plan_tier"] == "enterprise", updated)
check("update_customer leaves name unchanged when omitted", updated["name"] == "Test Customer", updated)

jane_matches = s.search_customers("Jane")
check("search_customers finds Jane Doe", any(c["name"] == "Jane Doe" for c in jane_matches), jane_matches)


print("\n=== AGENT TOOLS ===")
agents = s.list_agents()
check("list_agents returns 6 agents", len(agents) == 6, agents)
teams = {a["team"] for a in agents}
check("list_agents covers all 3 teams", teams == {"Billing", "Technical", "Onboarding"}, teams)


print("\n=== TICKET CRUD ===")
new_ticket = s.create_ticket(new_cust["id"], "Test subject", "Test description", priority="high")
check("create_ticket returns id", new_ticket.get("id", 0) > 0, new_ticket)
check("create_ticket starts status=open", new_ticket["status"] == "open", new_ticket)
check("create_ticket has no agent yet", new_ticket["agent_id"] is None, new_ticket)
tid = new_ticket["id"]

bad_ticket = s.create_ticket(999999, "x", "y")
check("create_ticket rejects unknown customer_id", "error" in bad_ticket, bad_ticket)

fetched_ticket = s.get_ticket(tid)
check("get_ticket joins customer_name", fetched_ticket.get("customer_name") == "Test Customer", fetched_ticket)

status_updated = s.update_ticket_status(tid, "in_progress")
check("update_ticket_status changes status", status_updated["status"] == "in_progress", status_updated)

bad_status = s.update_ticket_status(tid, "not_a_status")
check("update_ticket_status rejects invalid status", "error" in bad_status, bad_status)

priority_updated = s.update_ticket_priority(tid, "low")
check("update_ticket_priority changes priority", priority_updated["priority"] == "low", priority_updated)

assigned = s.assign_ticket(tid, agents[0]["id"])
check("assign_ticket sets agent_id", assigned["agent_id"] == agents[0]["id"], assigned)

bad_assign = s.assign_ticket(tid, 999999)
check("assign_ticket rejects unknown agent_id", "error" in bad_assign, bad_assign)

by_customer = s.list_tickets_by_customer(new_cust["id"])
check("list_tickets_by_customer finds the new ticket", any(t["id"] == tid for t in by_customer), by_customer)

by_agent = s.list_tickets_by_agent(agents[0]["id"])
check("list_tickets_by_agent finds the assigned ticket", any(t["id"] == tid for t in by_agent), by_agent)


print("\n=== NOTES ===")
note = s.add_ticket_note(tid, "Test Agent", "Investigating the issue.")
check("add_ticket_note returns id", note.get("id", 0) > 0, note)
notes = s.get_ticket_notes(tid)
check("get_ticket_notes returns the note just added", any(n["note_text"] == "Investigating the issue." for n in notes), notes)

bad_note = s.add_ticket_note(999999, "x", "y")
check("add_ticket_note rejects unknown ticket_id", "error" in bad_note, bad_note)


print("\n=== CLOSE / DELETE (destructive) ===")
closed = s.close_ticket(tid, "Fixed by restarting the integration.")
check("close_ticket sets status=closed", closed["status"] == "closed", closed)
notes_after_close = s.get_ticket_notes(tid)
check("close_ticket appended a resolution note", any("Fixed by restarting" in n["note_text"] for n in notes_after_close), notes_after_close)

del_result = s.delete_ticket(tid)
check("delete_ticket confirms the id", del_result.get("deleted_ticket_id") == tid, del_result)
gone = s.get_ticket(tid)
check("deleted ticket is really gone", "error" in gone, gone)
orphan_notes = s.get_ticket_notes(tid)
check("delete_ticket cascades to notes", orphan_notes == [], orphan_notes)


print("\n=== JOIN-POWERED INSIGHT TOOLS (the whole point of this schema) ===")
jane = s.search_customers("Jane Doe")[0]
history = s.get_customer_support_history(jane["id"])
check("get_customer_support_history returns Jane's profile", history["customer"]["name"] == "Jane Doe", history["customer"])
check("get_customer_support_history finds 4 tickets", history["total_tickets"] == 4, history["total_tickets"])
check("get_customer_support_history counts open tickets correctly",
      history["open_tickets"] == sum(1 for t in history["tickets"] if t["status"] != "closed"),
      history["open_tickets"])
check("get_customer_support_history includes agent names on assigned tickets",
      any(t["agent_name"] for t in history["tickets"]), history["tickets"])

workload = s.get_agent_workload()
check("get_agent_workload returns all 6 agents", len(workload) == 6, workload)
check("get_agent_workload is sorted busiest-first",
      all(workload[i]["active_tickets"] >= workload[i + 1]["active_tickets"] for i in range(len(workload) - 1)),
      workload)
aisha = next(a for a in workload if a["name"] == "Aisha Rahman")
check("get_agent_workload shows Aisha Rahman as busiest (seeded that way)",
      aisha["active_tickets"] == max(w["active_tickets"] for w in workload), workload)


print("\n=== KNOWLEDGE BASE / RAG TOOL ===")
rag_result = s.search_knowledge_base("How long is my password reset link valid for?")
check("search_knowledge_base mentions 30 minutes", "30" in rag_result["answer"], rag_result["answer"])
check("search_knowledge_base returns at least one source", len(rag_result["sources"]) > 0, rag_result["sources"])

rag_result2 = s.search_knowledge_base("What is the API rate limit on the Pro tier?")
check("search_knowledge_base mentions 1,000 or 1000 for Pro tier",
      "1,000" in rag_result2["answer"] or "1000" in rag_result2["answer"], rag_result2["answer"])

rag_result3 = s.search_knowledge_base("How many backup codes do I get for two-factor authentication?")
check("search_knowledge_base mentions 10 backup codes", "10" in rag_result3["answer"], rag_result3["answer"])

new_article = s.create_kb_article(
    "How to Rotate an Expired API Key",
    "If your API key expired after 90 days of inactivity, generate a new one from "
    "Settings > API Keys > Rotate Key. The old key remains valid for 24 hours to allow "
    "a graceful cutover.",
    "Technical",
)
check("create_kb_article returns an id", new_article.get("id", 0) > 0, new_article)

rag_result4 = s.search_knowledge_base("How long does the old API key stay valid after I rotate it?")
check("search_knowledge_base finds the newly published article (24 hours)",
      "24" in rag_result4["answer"], rag_result4["answer"])


print(f"\n{'=' * 60}\n{passed} passed, {failed} failed\n{'=' * 60}")
if failed:
    sys.exit(1)
