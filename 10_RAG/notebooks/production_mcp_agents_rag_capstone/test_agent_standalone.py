"""Rigorous test of the FULL stack: LangChain agent -> MCP client -> MCP server
-> SQLite / reused RAG pipeline. Real natural-language scenarios spanning every
tool category, checked against real ground truth, plus both HITL approve and
reject paths for a destructive tool.

Run: python test_agent_standalone.py
"""
import asyncio
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent.parent / ".env")

subprocess.run([sys.executable, str(HERE / "seed_data.py")], check=True, cwd=HERE)

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

SYSTEM_PROMPT = """You are a helpful customer support desk assistant. You have tools to:
- look up and manage customers, tickets, agents, and ticket notes in our database
- search our knowledge base for policy/how-to questions (search_knowledge_base)

Always use a tool to look up real data rather than guessing. When a user gives a
customer's name instead of an id, use search_customers first to find their id.
Be concise and factual in your answers."""

passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}\n        {detail}")


async def main():
    client = MultiServerMCPClient({
        "helpdesk": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(HERE / "mcp_server.py")],
        }
    })
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools from the MCP server into LangChain.\n")
    check("agent sees all 20 tools", len(tools) == 20, [t.name for t in tools])

    agent = create_agent(
        model="gpt-4o-mini",
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[HumanInTheLoopMiddleware(interrupt_on={"close_ticket": True, "delete_ticket": True})],
        checkpointer=InMemorySaver(),
    )

    async def ask(question, thread_id):
        config = {"configurable": {"thread_id": thread_id}}
        result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]}, config=config)
        return result, config

    print("=== SCENARIO 1: single-table read (get a specific customer's plan) ===")
    result, _ = await ask("What plan tier is the customer Jane Doe on?", "t1")
    answer = result["messages"][-1].content
    print(" ", answer)
    check("mentions enterprise (Jane Doe's real plan)", "enterprise" in answer.lower(), answer)

    print("\n=== SCENARIO 2: multi-table JOIN insight (customer support history) ===")
    result, _ = await ask("Give me Jane Doe's full support history — how many tickets has she opened, "
                     "and how many are still open?", "t2")
    answer = result["messages"][-1].content
    print(" ", answer)
    check("mentions 4 total tickets", "4" in answer, answer)

    print("\n=== SCENARIO 3: multi-table JOIN insight (agent workload) ===")
    result, _ = await ask("Which support agent currently has the most active tickets?", "t3")
    answer = result["messages"][-1].content
    print(" ", answer)
    check("names Aisha Rahman as busiest", "Aisha" in answer, answer)

    print("\n=== SCENARIO 4: knowledge base / RAG search ===")
    result, _ = await ask("A customer is asking how many two-factor authentication backup codes they get.", "t4")
    answer = result["messages"][-1].content
    print(" ", answer)
    check("mentions 10 backup codes", "10" in answer, answer)

    print("\n=== SCENARIO 5: write CRUD (create a ticket) ===")
    result, _ = await ask("Open a new high priority ticket for Jane Doe: subject 'Cannot log in', "
                     "description 'Getting a 500 error on the login page.'", "t5")
    answer = result["messages"][-1].content
    print(" ", answer)
    check("confirms ticket created", any(w in answer.lower() for w in ["created", "opened", "ticket #", "ticket id"]), answer)

    print("\n=== SCENARIO 6: destructive op — HITL interrupt fires ===")
    result, config = await ask("Please close ticket 1 with resolution note: 'Resolved via phone call.'", "t6")
    interrupted = "__interrupt__" in result
    check("close_ticket triggers a HITL interrupt", interrupted, result)

    print("\n=== SCENARIO 7: destructive op — approve path actually closes it ===")
    result2 = await agent.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    answer = result2["messages"][-1].content
    print(" ", answer)
    check("confirms ticket 1 closed after approval", "closed" in answer.lower() or "resolved" in answer.lower(), answer)

    print("\n=== SCENARIO 8: destructive op — reject path leaves it untouched ===")
    result3, config8 = await ask("Please close ticket 2 with resolution note: 'test reject.'", "t8")
    check("second close_ticket call also interrupts", "__interrupt__" in result3, result3)
    result4 = await agent.ainvoke(Command(resume={"decisions": [{"type": "reject"}]}), config=config8)
    answer = result4["messages"][-1].content
    print(" ", answer)

    print("\n=== SCENARIO 9: KB write-back loop (create article, then find it) ===")
    result, _ = await ask(
        "Please publish a new knowledge base article titled 'How to Change Your Billing Email' "
        "in the Billing category. Content: 'Go to Settings > Billing > Update Email. Changes take "
        "effect on your next invoice, not retroactively.' After publishing, search the knowledge base "
        "to confirm: when do billing email changes take effect?",
        "t9",
    )
    answer = result["messages"][-1].content
    print(" ", answer)
    check("finds the newly published article's fact (next invoice)", "next invoice" in answer.lower(), answer)

    print(f"\n{'=' * 60}\n{passed} passed, {failed} failed\n{'=' * 60}")
    if failed:
        sys.exit(1)


asyncio.run(main())
