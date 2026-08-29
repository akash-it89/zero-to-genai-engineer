#!/usr/bin/env python3
"""Build 01_langchain_langgraph_deepagents.ipynb. Run from this folder."""

from __future__ import annotations

import json
from pathlib import Path

NB_PATH = Path(__file__).with_name("01_langchain_langgraph_deepagents.ipynb")


def md(text: str) -> dict:
    text = text.strip("\n") + "\n"
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text: str) -> dict:
    text = text.strip("\n") + "\n"
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": _lines(text),
    }


def _lines(text: str) -> list[str]:
    parts = text.split("\n")
    out = []
    for i, line in enumerate(parts):
        if i < len(parts) - 1:
            out.append(line + "\n")
        elif line:
            out.append(line)
    return out


CELLS = []

CELLS.append(
    md(
        """[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/nursnaaz/zero-to-genai-engineer/blob/main/12_deepagents/notebooks/01_langchain_langgraph_deepagents.ipynb)"""
    )
)

CELLS.append(
    md(
        """# Why Deep Agents — if I already have LangChain and LangGraph?

**Session 12.** Official docs used while writing this:

- [Overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [Memory (`AGENTS.md` / `AGENT.md`)](https://docs.langchain.com/oss/python/deepagents/memory)
- [Skills (`SKILL.md`)](https://docs.langchain.com/oss/python/deepagents/skills)
- [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [LangChain vs LangGraph vs Deep Agents](https://www.langchain.com/blog/deep-agents-vs-langchain-vs-langgraph)

---

## The proof (say this to the class)

You already have two things:

| You already have | What it does | What it does **not** do |
|---|---|---|
| **LangChain** | Call a model. Optionally call **your** tools. Put the answer in **chat**. | Save a document. Remember a rule file. Open a how-to only when needed. |
| **LangGraph** | **You** write step 1, step 2, step 3 in Python. Those steps always run. | Survive “also do one more thing” unless **you add a new step in Python**. |

**Deep Agents** is not a third model. It is `create_deep_agent()`.

That function still returns a LangGraph graph (`CompiledStateGraph`).
LangChain’s own words: *Deep Agents is the LangChain agent plus extra middleware.*

The extras (this is what you are paying for):

| Piece | File / tool | Loaded when | Point |
|---|---|---|---|
| **File tools** | `write_file`, `read_file`, `edit_file` | When the model calls them | Work is a **document**, not a chat bubble |
| **Memory** | `AGENT.md` (docs also say `AGENTS.md`) | **Every** run | Standing rules. You do not paste them into every prompt |
| **Skill** | `skills/<name>/SKILL.md` | **Only if** the task matches the skill description | A how-to. Not stuffed into every prompt |
| **Your tools** | functions you pass in `tools=` | When the model calls them | Same as LangChain — **plus** the file tools above |
| **Helper** | `subagents=[{name, description, system_prompt}]` | When the model calls `task` | A second agent with an **empty** chat |

If LangChain is “talk,” and LangGraph is “I already wrote the steps,”
Deep Agents is “talk, and also keep files, rules, how-tos, and helpers.”

You need it when the user will say **“also change the document”** and you
refuse to add a new LangGraph node for every sentence.

This notebook proves each row with code. Five examples. Same shop: **Gulf Mart**.
"""
    )
)

CELLS.append(
    md(
        """---
# Setup (once)

After a fresh install: **Kernel → Restart Kernel**, then run from here.
"""
    )
)

CELLS.append(
    code(
        """%pip install -q "langgraph>=0.6" "langchain>=1.0" langchain-openai langchain-core python-dotenv "deepagents>=0.2"

import importlib.metadata, warnings, os
warnings.filterwarnings("ignore")
from pathlib import Path
from dotenv import load_dotenv

def _ver(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"

print("langgraph  :", _ver("langgraph"))
print("langchain  :", _ver("langchain"))
print("deepagents :", _ver("deepagents"))"""
    )
)

CELLS.append(
    code(
        """here = Path.cwd().resolve()
seen = []
for folder in [here, *here.parents]:
    for candidate in (
        folder / ".env",
        folder / "12_deepagents" / ".env",
        folder / "11_LangGraph" / ".env",
        folder / "10_RAG" / ".env",
    ):
        if candidate.is_file() and candidate not in seen:
            seen.append(candidate)
            load_dotenv(candidate, override=False)

if not os.getenv("OPENAI_API_KEY"):
    try:
        from google.colab import userdata  # type: ignore
        os.environ["OPENAI_API_KEY"] = userdata.get("OPENAI_API_KEY")
    except Exception:
        pass

HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))
print("OPENAI_API_KEY:", "set" if HAS_KEY else "MISSING")"""
    )
)

CELLS.append(
    code(
        """def skip_if_no_key(label: str) -> bool:
    if HAS_KEY:
        return False
    print("Skip", label, "— no OPENAI_API_KEY")
    return True


def show_files(state, n: int = 900):
    files = state.get("files") or {}
    print(len(files), "file(s) saved by the agent:")
    if not files:
        print("  none")
        return
    for path in sorted(files):
        blob = files[path]
        if isinstance(blob, dict):
            text = blob.get("content") or blob.get("data") or str(blob)
        else:
            text = getattr(blob, "content", None) or str(blob)
        print("\\n-----", path, "-----")
        print(str(text)[:n])


DEMO = Path.cwd().resolve() / "_deepagents_demo"
(DEMO / "skills" / "invoice").mkdir(parents=True, exist_ok=True)
print("demo folder:", DEMO)"""
    )
)

CELLS.append(
    md(
        """---
# What you already have (no Deep Agents yet)

## LangChain — answer in chat. No file.
"""
    )
)

CELLS.append(
    code(
        """from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

if skip_if_no_key("LangChain"):
    pass
else:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    msg = llm.invoke(
        [HumanMessage(content="Make a shopping list: milk, bread.")]
    )
    print(msg.content)
    print()
    print("PROOF: this object has no 'files'. The list exists only as chat.")
    print("keys on the response:", type(msg).__name__)"""
    )
)

CELLS.append(
    md(
        """## LangGraph — you listed the steps. “Add eggs” is not a step.
"""
    )
)

CELLS.append(
    code(
        """from typing import TypedDict
from langgraph.graph import END, START, StateGraph


class S(TypedDict):
    text: str


def write_list(state: S) -> dict:
    return {"text": "milk\\nbread"}


b = StateGraph(S)
b.add_node("write_list", write_list)
b.add_edge(START, "write_list")
b.add_edge("write_list", END)
g = b.compile()
print("type =", type(g).__name__)
print("graph steps:", list(g.get_graph().nodes))
print("result =", g.invoke({"text": ""}))
print()
print("PROOF: user now says 'add eggs'.")
print("There is no node named add_eggs. You must edit this Python and add one.")"""
    )
)

CELLS.append(
    md(
        """Those two cells are the gap.

- LangChain: no document.
- LangGraph: every new user request = new Python.

Deep Agents fills the gap. Five proofs below. Each one is one feature.
"""
    )
)

CELLS.append(
    md(
        """---
# Example 1 — File tools (`write_file` / `edit_file`)

**What it is:** Deep Agents always gives the model file tools.
([overview](https://docs.langchain.com/oss/python/deepagents/overview):
*offload large results to files*)

**Why it is essential:** LangChain’s shopping list died in chat. Here the
list is a real file named `shopping.md`. Then we say “add eggs” **without**
adding a LangGraph node.

**Look for:** `show_files` prints `shopping.md`. After the second call,
the word `eggs` is in that file.
"""
    )
)

CELLS.append(
    code(
        """from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langgraph.checkpoint.memory import MemorySaver
import inspect


def make_agent(**kwargs):
    # Same model every time. If a checkpointer is attached, run() MUST pass thread_id.
    kw = dict(model="openai:gpt-4o-mini", **kwargs)
    if "checkpointer" in inspect.signature(create_deep_agent).parameters:
        kw.setdefault("checkpointer", MemorySaver())
    return create_deep_agent(**kw)


def run(agent, user: str, *, files=None, thread: str):
    payload = {"messages": [{"role": "user", "content": user}]}
    if files:
        payload["files"] = files
    return agent.invoke(
        payload,
        config={"configurable": {"thread_id": thread}},
    )


file_agent = None
if skip_if_no_key("example 1"):
    pass
else:
    file_agent = make_agent(
        system_prompt="Save shopping lists with write_file. Edit with edit_file. Short files only.",
    )
    print("type =", type(file_agent).__name__, "(this is still LangGraph)")"""
    )
)

CELLS.append(
    code(
        """if file_agent is None:
    print("Skip")
    r1 = None
else:
    r1 = run(
        file_agent,
        "Create shopping.md with two lines: milk, bread.",
        thread="ex1-files",
    )
    print(r1["messages"][-1].content[:400])
    print()
    show_files(r1)"""
    )
)

CELLS.append(
    code(
        """if file_agent is None or r1 is None:
    print("Skip")
else:
    r2 = run(
        file_agent,
        "Add eggs to shopping.md. Keep milk and bread.",
        files=r1.get("files"),
        thread="ex1-files",
    )
    print(r2["messages"][-1].content[:400])
    print()
    show_files(r2)
    print()
    print("PROOF vs LangGraph: we did not add_node('add_eggs').")
    print("PROOF vs LangChain: shopping.md exists in state['files'].")"""
    )
)

CELLS.append(
    md(
        """---
# Example 2 — Memory (`AGENT.md`)

**What it is:** A markdown file of rules that load **every** run.
Docs: [Memory](https://docs.langchain.com/oss/python/deepagents/memory)
(they name it `AGENTS.md`; we use `/AGENT.md` — same idea).

**How to pass it (this is what crashed before):**

1. `memory=["/AGENT.md"]` — a **virtual** path. It starts with `/`.
   It is **not** a Mac folder like `/Users/.../AGENT.md`.
2. Put the file text in `files=` on `invoke`. Default storage is
   `StateBackend` (agent state), not your laptop disk.
3. If you attach `MemorySaver`, you **must** pass `thread_id`
   (`run()` already does this).

**Why it is essential:** In LangChain you paste “always say Gulf Mart” into
every prompt. Forget once, the rule is gone. Memory is one file. Change
the file, not the Python.

**Look for:** The user message does **not** contain “Gulf Mart”.
`shopping.md` still starts with `Store: Gulf Mart` because `/AGENT.md` said so.
"""
    )
)

CELLS.append(
    code(
        """AGENT_MD = (
    "Standing rules:\\n"
    "- Every shopping list file must start with the line: Store: Gulf Mart\\n"
    "- Never invent items the user did not name.\\n"
)
(DEMO / "AGENT.md").write_text(AGENT_MD)
print(AGENT_MD)

mem_agent = None
if skip_if_no_key("example 2"):
    pass
else:
    mem_agent = make_agent(
        memory=["/AGENT.md"],
        system_prompt="Write shopping.md. Follow /AGENT.md. Use write_file.",
    )
    out = run(
        mem_agent,
        "Create shopping.md. Items: rice, oil.",
        files={"/AGENT.md": create_file_data(AGENT_MD)},
        thread="ex2-memory",
    )
    print(out["messages"][-1].content[:300])
    print()
    show_files(out)
    print()
    print("PROOF: 'Gulf Mart' was not in the user message. It came from /AGENT.md.")"""
    )
)

CELLS.append(
    md(
        """---
# Example 3 — Skill (`SKILL.md`)

**What it is:** A how-to page. At start the agent only sees the **name**
and **description**. It reads the full file **only when the task matches**.
Docs: [Skills](https://docs.langchain.com/oss/python/deepagents/skills)
(Agent Skills spec, `name` + `description` in YAML).

**Memory vs skill (do not mix these up):**

| | Memory `AGENT.md` | Skill `SKILL.md` |
|---|---|---|
| When loaded | Always | Only if the job matches |
| Use for | Who we are / never-do rules | How to do **one** kind of job |

**Why it is essential:** A 200-line invoice how-to in the system prompt
is waste on “hello.” A skill stays on disk until someone asks for an invoice.

**How to pass it:** `skills=["/skills/"]` plus the skill file in `files=`
as `/skills/invoice/SKILL.md`. Same virtual-path rule as memory.

**Look for:** User did not say `INV-001`. The skill did. `invoice.md` has it.
"""
    )
)

CELLS.append(
    code(
        """SKILL_MD = '''---
name: invoice
description: Write a store invoice. Use when the user asks for an invoice or invoice.md.
---
# Invoice how-to
1. Line 1 must be: Invoice #: INV-001
2. Line 2 must be: Store: Gulf Mart
3. Then one line per item.
4. Save as invoice.md using write_file.
'''
(DEMO / "skills" / "invoice" / "SKILL.md").write_text(SKILL_MD)
print(SKILL_MD)

skill_agent = None
if skip_if_no_key("example 3"):
    pass
else:
    skill_agent = make_agent(
        skills=["/skills/"],
        system_prompt="If this is an invoice, read the invoice skill first. Use write_file.",
    )
    out = run(
        skill_agent,
        "Write invoice.md for 2 laptops.",
        files={"/skills/invoice/SKILL.md": create_file_data(SKILL_MD)},
        thread="ex3-skill",
    )
    print(out["messages"][-1].content[:300])
    print()
    show_files(out)
    print()
    print("PROOF: INV-001 was not in the user message. It came from SKILL.md.")
    print("You did not put the invoice format in Python. You put it in a file.")"""
    )
)

CELLS.append(
    md(
        """---
# Example 4 — Your tools + Deep Agents file tools

**What it is:** `tools=` is the same idea as LangChain: functions the model
can call. Deep Agents **keeps those** and **adds** `write_file` / `read_file`.

**Why it is essential:** LangChain `create_agent(tools=[get_hours])` can
call `get_hours` and tell you in chat. It still has no `hours.md` unless
**you** write a save-file tool. Deep Agents already has save-file.

**Look for:** `get_store_hours` returns `9am-9pm`. That string appears
inside `hours.md`, not only in chat.
"""
    )
)

CELLS.append(
    code(
        """from langchain.tools import tool


@tool
def get_store_hours() -> str:
    \"\"\"Return Gulf Mart opening hours. Call this before writing hours.md.\"\"\"
    return "9am-9pm daily"


tool_agent = None
if skip_if_no_key("example 4"):
    pass
else:
    tool_agent = make_agent(
        tools=[get_store_hours],
        system_prompt=(
            "Call get_store_hours, then write the result into hours.md "
            "using write_file. Do not invent hours."
        ),
    )
    out = run(
        tool_agent,
        "Save Gulf Mart hours into hours.md.",
        thread="ex4-tools",
    )
    print(out["messages"][-1].content[:400])
    print()
    show_files(out)
    print()
    print("PROOF vs LangChain: the tool result was saved to a file.")
    print("You did not implement write_file. Deep Agents shipped it.")"""
    )
)

CELLS.append(
    md(
        """---
# Example 5 — Helper (subagent) with an empty chat

**What it is:** A second agent. It gets **only** the job you send.
It does not see the whole main conversation.
Docs: [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)

**Why it is essential:** If one chat does “read 10 pages, then write a
summary,” the 10 pages sit in the prompt forever. A helper reads the 10
pages in its own chat and returns 5 bullets. The main agent stays small.

**Look for:** `price-lister` returns only prices. Main agent writes
`deal.md`. The messy chat is not copied into `deal.md` as a dump.
"""
    )
)

CELLS.append(
    code(
        """MESSY = '''
Sara: rice is 12 dirhams
Ali: oil is 18
Sara: ignore the old 9-dirham rice price from last month
Ali: bread is 3
'''

help_agent = None
if skip_if_no_key("example 5"):
    pass
else:
    help_agent = make_agent(
        system_prompt=(
            "Write deal.md. For prices, call the task tool and use "
            "price-lister. Do not copy the raw chat into deal.md."
        ),
        subagents=[
            {
                "name": "price-lister",
                "description": "Extract item + price bullets from chat. Nothing else.",
                "system_prompt": "Bullets only: item, price. Ignore old/strikethrough prices.",
            }
        ],
    )
    out = run(
        help_agent,
        "Make deal.md. Use price-lister.\\n\\n" + MESSY,
        thread="ex5-helper",
    )
    print(out["messages"][-1].content[:400])
    print()
    show_files(out)
    print()
    print("PROOF: the helper had its own chat. The main agent only needed bullets.")
    print("In LangGraph you would have drawn a 'prices' node and wired it yourself.")"""
    )
)

CELLS.append(
    md(
        """---
# One page you can screenshot for the class

| Question | LangChain | LangGraph | Deep Agents |
|---|---|---|---|
| Where does the work live? | Chat | State keys **you** named | Files the model writes |
| “Also add eggs” | Another chat | New `add_node` in Python | `edit_file` (Example 1) |
| Standing rule “always Gulf Mart” | Paste into every prompt | Paste into every node | `AGENT.md` (Example 2) |
| How-to for invoices | Giant system prompt | A node with that prompt | `SKILL.md` read on demand (Example 3) |
| Call my `get_store_hours` | Yes (`tools=`) | Yes (a node) | Yes, **and** it can save `hours.md` (Example 4) |
| Don’t flood the main chat | You hope | You split nodes | Helper with empty chat (Example 5) |

`create_deep_agent()` still returns `CompiledStateGraph`.
You did not replace LangGraph. You stopped writing a new node for every
“also …”.

**Still use LangGraph** when the step **must** happen (human must click
yes before send). That is Session 11. Deep Agents does not remove that.
You can put a Deep Agent **inside** a LangGraph node if you need both.

Docs: [overview](https://docs.langchain.com/oss/python/deepagents/overview) ·
[comparison](https://www.langchain.com/blog/deep-agents-vs-langchain-vs-langgraph)
"""
    )
)


def main() -> None:
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "cells": CELLS,
    }
    NB_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print("wrote", NB_PATH, "cells", len(CELLS))


if __name__ == "__main__":
    main()
