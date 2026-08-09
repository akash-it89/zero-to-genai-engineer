"""Tests the MCP server over the REAL protocol (stdio subprocess), using the raw
mcp client SDK — no LangChain involved yet. Isolates "does MCP itself work"
from "does the LangChain adapter work", so a failure here can't be confused
with a LangChain-side bug.

Run: python test_mcp_protocol.py
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
SERVER_PATH = HERE / "mcp_server.py"

subprocess.run([sys.executable, str(HERE / "seed_data.py")], check=True, cwd=HERE)


def _payload(result):
    """FastMCP serializes a list-returning tool as one content block PER item
    (not one block holding a JSON array) — structuredContent is the reliable
    place to read the real return value back out, for both dicts and lists."""
    if result.structuredContent is not None:
        sc = result.structuredContent
        return sc["result"] if set(sc.keys()) == {"result"} else sc
    return json.loads(result.content[0].text)


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tool_names = sorted(t.name for t in tools_result.tools)
            print(f"Discovered {len(tool_names)} tools over real MCP protocol:")
            for name in tool_names:
                print(" -", name)
            expected = {
                "create_customer", "get_customer", "update_customer", "search_customers",
                "list_agents",
                "create_ticket", "get_ticket", "update_ticket_status", "update_ticket_priority",
                "assign_ticket", "close_ticket", "delete_ticket",
                "list_tickets_by_customer", "list_tickets_by_agent",
                "add_ticket_note", "get_ticket_notes",
                "get_customer_support_history", "get_agent_workload",
                "search_knowledge_base", "create_kb_article",
            }
            missing = expected - set(tool_names)
            extra = set(tool_names) - expected
            assert not missing, f"MISSING tools over protocol: {missing}"
            assert not extra, f"UNEXPECTED tools over protocol: {extra}"
            print(f"\nAll {len(expected)} expected tools present, none missing, none extra.")

            print("\n--- Calling get_agent_workload over the wire ---")
            result = await session.call_tool("get_agent_workload", {})
            payload = _payload(result)
            assert len(payload) == 6, f"expected 6 agents, got {len(payload)}"
            assert payload[0]["name"] == "Aisha Rahman", f"expected Aisha Rahman busiest, got {payload[0]}"
            print("OK — 6 agents returned, Aisha Rahman correctly busiest:", payload[0])

            print("\n--- Calling search_customers over the wire ---")
            result = await session.call_tool("search_customers", {"name_contains": "Jane"})
            payload = _payload(result)
            assert any(c["name"] == "Jane Doe" for c in payload), payload
            print("OK — found Jane Doe via real MCP tool call:", payload[0]["name"])

            print("\n--- Calling create_ticket + get_ticket round-trip over the wire ---")
            jane_id = payload[0]["id"]
            created = await session.call_tool(
                "create_ticket",
                {"customer_id": jane_id, "subject": "Protocol test", "description": "test", "priority": "low"},
            )
            created_payload = _payload(created)
            assert created_payload["status"] == "open", created_payload
            fetched = await session.call_tool("get_ticket", {"ticket_id": created_payload["id"]})
            fetched_payload = _payload(fetched)
            assert fetched_payload["subject"] == "Protocol test", fetched_payload
            print("OK — created + fetched ticket over real protocol:", fetched_payload["subject"])

            print("\n--- Calling an invalid tool args case (should return an error dict, not crash) ---")
            bad = await session.call_tool("create_customer", {"name": "X", "email": "x@x.com", "plan_tier": "platinum"})
            bad_payload = _payload(bad)
            assert "error" in bad_payload, bad_payload
            print("OK — invalid plan_tier correctly returned as error over the wire:", bad_payload)

    print("\n" + "=" * 60)
    print("ALL MCP PROTOCOL-LEVEL TESTS PASSED")
    print("=" * 60)


asyncio.run(main())
