#!/usr/bin/env python3
"""
Generate accurate architecture PNGs for notebook 04.

Priority:
  1. Official LangGraph tutorial images (when downloadable)
  2. Mermaid diagrams rendered via mermaid.ink (paper-accurate flow)
  3. LangGraph compiled-graph PNGs (actual node names from our implementations)

Run from notebooks/assets/:
    python generate_diagrams.py
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "patterns"
OUT.mkdir(parents=True, exist_ok=True)

# ── Official LangGraph / tutorial images (verified paths) ──────────────────
OFFICIAL_URLS: dict[str, list[str]] = {
    "reflection": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/reflection/img/reflection.png",
    ],
    "reflexion": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/reflexion/img/reflexion.png",
    ],
    "rewoo": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/rewoo/img/rewoo.png",
    ],
    "rewoo_paper": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/rewoo/img/rewoo-paper-workflow.png",
    ],
    "tot": [
        "https://raw.githubusercontent.com/langchain-ai/langgraph/f239b39060096ab2c8bff0d6303781efee174a5c/docs/docs/tutorials/tot/img/tot.png",
    ],
    "plan_execute": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/plan-and-execute/img/plan-and-execute.png",
    ],
    "lats": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/lats/img/lats.png",
    ],
    "self_discover": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/self-discover/img/self-discover.png",
    ],
    "llm_compiler": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/llm-compiler/img/llm-compiler.png",
    ],
    "sql_agent": [
        "https://raw.githubusercontent.com/langchain-ai/langgraphjs/main/examples/sql/img/sql-agent.png",
    ],
}

# ── Paper-accurate Mermaid (used when no official PNG or as primary) ─────
MERMAID: dict[str, str] = {
    "cot": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8','secondaryColor':'#0f172a','tertiaryColor':'#334155'}}}%%
flowchart LR
    Q["Question"] --> S1["CoT Step 1<br/>(intermediate reasoning)"]
    S1 --> S2["CoT Step 2"]
    S2 --> S3["..."]
    S3 --> A["Final Answer"]
""",
    "react": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    START([User task]) --> T["Thought<br/>reason about state"]
    T --> A["Action<br/>select tool + args"]
    A --> O["Observation<br/>tool / env result"]
    O --> T
    O -->|task complete| ANS["Final Answer"]
    style T fill:#1e293b,stroke:#38bdf8
    style A fill:#1e293b,stroke:#38bdf8
    style O fill:#1e293b,stroke:#38bdf8
""",
    "reflection": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    G["Generate<br/>initial draft"] --> R["Reflect<br/>LLM critique"]
    R -->|score < threshold| V["Revise<br/>apply feedback"]
    V --> R
    R -->|approved| OUT["Final output"]
""",
    "reflexion": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    D["Actor<br/>draft attempt"] --> E["Environment<br/>tool / test feedback"]
    E --> SR["Self-Reflect<br/>verbal critique"]
    SR --> M[("Episodic<br/>memory")]
    M --> D
    SR -->|max trials| OUT["Final answer"]
""",
    "critic": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    G["Generate<br/>initial answer"] --> V["Tool Verify<br/>calculator / search / code"]
    V --> C["Critique<br/>compare to ground truth"]
    C --> F["Correct<br/>fix answer"]
    F --> V
    C -->|verified| OUT["Verified output"]
""",
    "rewoo": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart LR
    Q["Question"] --> P["Planner LLM<br/>Plan + #E1 #E2 ..."]
    P --> W["Workers<br/>execute tools (no LLM)"]
    W --> S["Solver LLM<br/>one final call"]
    S --> A["Answer"]
""",
    "plan_execute": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    Q["Task"] --> PL["Planner<br/>multi-step plan"]
    PL --> EX["Executor<br/>run step with tools"]
    EX --> RP{"Replanner"}
    RP -->|next step| EX
    RP -->|world changed| PL
    RP -->|done| OUT["Response"]
""",
    "tot": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    P["Problem"] --> EXP["Expand<br/>generate N thought candidates"]
    EXP --> SC["Score<br/>LLM judge each"]
    SC --> PR["Prune<br/>keep top-K"]
    PR -->|not solved| EXP
    PR -->|solved| OUT["Best solution"]
""",
    "self_discover": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart LR
    Q["Task"] --> SEL["SELECT<br/>pick reasoning modules"]
    SEL --> AD["ADAPT<br/>task-specific modules"]
    AD --> ST["STRUCTURE<br/>JSON plan"]
    ST --> RE["REASON<br/>execute plan"]
    RE --> OUT["Answer"]
""",
    "self_rag": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    Q["Query"] --> R["Retrieve<br/>fetch documents"]
    R --> G["Generate<br/>draft answer"]
    G --> RF{"Reflection tokens<br/>IsRel · IsSup · IsUse"}
    RF -->|not grounded| R
    RF -->|useful| OUT["Output + citations"]
""",
    "lats": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    SEL["Select node<br/>(MCTS)"] --> EXP["Expand<br/>parallel actions"]
    EXP --> REF["Reflect<br/>score state"]
    REF --> BP["Backpropagate<br/>update rewards"]
    BP --> SEL
    REF -->|terminal| OUT["Best trajectory"]
""",
    "llm_compiler": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    Q["Query"] --> PL["Planner<br/>tool-call DAG"]
    PL --> TF["Task Fetching Unit<br/>schedule ready nodes"]
    TF --> T1["Tool A"]
    TF --> T2["Tool B"]
    TF --> T3["Tool C"]
    T1 --> JOIN["Join / merge"]
    T2 --> JOIN
    T3 --> JOIN
    JOIN --> TF
    TF -->|all done| OUT["Final answer"]
""",
    "got": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    Q["Problem"] --> A["Thought A"]
    Q --> B["Thought B"]
    Q --> C["Thought C"]
    A --> M["Merge / aggregate<br/>(DAG, not tree)"]
    B --> M
    C --> M
    M --> OUT["Combined answer"]
""",
    "sql_agent": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    U["User question"] --> LT["list_tables"]
    LT --> GS["get_schema"]
    GS --> GQ["generate_query"]
    GQ -->|tool call| CQ["check_query"]
    CQ --> RQ["run_query"]
    RQ --> GQ
    GQ -->|no tool call| A["Natural language answer"]
""",
}

# Notebook overview diagrams (Section 1 maps, Chinook ER) — rendered as standalone PNGs
# because Jupyter/Colab do not render ```mermaid``` markdown blocks.
NOTEBOOK_DIAGRAMS: dict[str, str] = {
    "patterns_family_map": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TB
    subgraph single["Single-path reasoning"]
        COT[Chain-of-Thought]
        SD[Self-Discover]
    end
    subgraph loop["Loop agents"]
        REACT[ReAct]
        REFL[Reflection]
        REFX[Reflexion / CRITIC]
        PAE[Plan-and-Execute]
    end
    subgraph batch["Batch / search"]
        REWOO[REWOO]
        TOT[Tree of Thoughts]
        GOT[Graph of Thoughts]
        LATS[LATS]
    end
    Q[User task] --> single
    Q --> loop
    Q --> batch
    single --> OUT[Answer]
    loop --> OUT
    batch --> OUT
""",
    "patterns_decision_tree": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
flowchart TD
    START([New agent task]) --> T1{Need tools / external data?}
    T1 -->|No| T2{Quality of first draft OK?}
    T1 -->|Yes| T3{How many tool steps?}

    T2 -->|No, polish only| REFL[Reflection]
    T2 -->|Hard reasoning| SD[Self-Discover]
    T2 -->|Many solutions to explore| TOT[ToT / LATS]

    T3 -->|1-3 reactive steps| REACT[ReAct]
    T3 -->|Need retry after failure| REFX[Reflexion / CRITIC]
    T3 -->|5+ known steps upfront| REWOO[REWOO]
    T3 -->|Long workflow, may replan| PAE[Plan-and-Execute]
    T3 -->|Parallel independent tools| LLC[LLM Compiler]
""",
    "chinook_er": """%%{init: {'theme':'dark','themeVariables':{'primaryColor':'#1e293b','primaryTextColor':'#e2e8f0','primaryBorderColor':'#38bdf8','lineColor':'#94a3b8'}}}%%
erDiagram
    Customer ||--o{ Invoice : places
    Invoice ||--|{ InvoiceLine : contains
    InvoiceLine }o--|| Track : references
    Track }o--|| Album : on
    Album }o--|| Artist : by
    Track }o--|| Genre : categorized
    Employee ||--o{ Customer : supports
""",
}


def download_png(url: str, dest: Path, timeout: int = 45) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 500 or data[:4] != b"\x89PNG":
            return False
        dest.write_bytes(data)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def mermaid_ink_png(mermaid_src: str, dest: Path, timeout: int = 60) -> bool:
    """Render via mermaid.ink (no local deps)."""
    encoded = base64.urlsafe_b64encode(mermaid_src.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=0f172a"
    return download_png(url, dest, timeout=timeout)


def mermaid_cli_png(mermaid_src: str, dest: Path) -> bool:
    """Render via @mermaid-js/mermaid-cli if npx available."""
    mmd = dest.with_suffix(".mmd")
    mmd.write_text(mermaid_src, encoding="utf-8")
    try:
        subprocess.run(
            ["npx", "-y", "@mermaid-js/mermaid-cli", "-i", str(mmd), "-o", str(dest),
             "-b", "#0f172a", "-w", "1400", "-H", "900"],
            check=True, capture_output=True, timeout=120,
        )
        mmd.unlink(missing_ok=True)
        return dest.exists() and dest.stat().st_size > 500
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        mmd.unlink(missing_ok=True)
        return False


def render_mermaid(mermaid_src: str, dest: Path) -> str:
    if mermaid_cli_png(mermaid_src, dest):
        return "mermaid-cli"
    if mermaid_ink_png(mermaid_src, dest):
        return "mermaid.ink"
    return "failed"


def try_official(slug: str, dest: Path) -> str | None:
    for url in OFFICIAL_URLS.get(slug, []):
        if download_png(url, dest):
            return url
    return None


def generate_langgraph_pngs() -> dict[str, str]:
    """Compile minimal LangGraph graphs matching notebook node names → PNG."""
    results: dict[str, str] = {}
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        return results

    def save(slug: str, builder: StateGraph) -> None:
        try:
            png = builder.compile().get_graph().draw_mermaid_png()
            p = OUT / f"{slug}_langgraph.png"
            p.write_bytes(png)
            results[slug] = str(p)
        except Exception:
            pass

    def noop(_: dict) -> dict:
        return {}

    # ReAct: agent ↔ tools loop
    b = StateGraph(dict)
    b.add_node("agent", noop)
    b.add_node("tools", noop)
    b.add_edge(START, "agent")
    b.add_conditional_edges("agent", lambda s: "tools", ["tools", END])
    b.add_edge("tools", "agent")
    save("react", b)

    # Reflection
    b = StateGraph(dict)
    b.add_node("generate", noop)
    b.add_node("reflect", noop)
    b.add_edge(START, "generate")
    b.add_edge("generate", "reflect")
    b.add_conditional_edges("reflect", lambda s: "generate", ["generate", END])
    save("reflection", b)

    # Reflexion (LangGraph tutorial node names)
    b = StateGraph(dict)
    for n in ("draft", "execute_tools", "revise"):
        b.add_node(n, noop)
    b.add_edge(START, "draft")
    b.add_edge("draft", "execute_tools")
    b.add_edge("execute_tools", "revise")
    b.add_conditional_edges("revise", lambda s: "execute_tools", ["execute_tools", END])
    save("reflexion", b)

    # CRITIC (notebook names)
    b = StateGraph(dict)
    for n in ("answer", "verify", "correct"):
        b.add_node(n, noop)
    b.add_edge(START, "answer")
    b.add_edge("answer", "verify")
    b.add_edge("verify", "correct")
    b.add_edge("correct", END)
    save("critic", b)

    # REWOO
    b = StateGraph(dict)
    for n in ("plan", "worker", "solve"):
        b.add_node(n, noop)
    b.add_edge(START, "plan")
    b.add_edge("plan", "worker")
    b.add_edge("worker", "solve")
    b.add_edge("solve", END)
    save("rewoo", b)

    # Plan-and-Execute (notebook: planner → executor loop → summarize)
    b = StateGraph(dict)
    for n in ("planner", "executor", "summarize"):
        b.add_node(n, noop)
    b.add_edge(START, "planner")
    b.add_edge("planner", "executor")
    b.add_edge("executor", "summarize")
    b.add_edge("summarize", END)
    save("plan_execute", b)

    # ToT
    b = StateGraph(dict)
    for n in ("expand", "score", "pick"):
        b.add_node(n, noop)
    b.add_edge(START, "expand")
    b.add_edge("expand", "score")
    b.add_edge("score", "pick")
    b.add_edge("pick", END)
    save("tot", b)

    # Self-Discover
    b = StateGraph(dict)
    for n in ("select", "adapt", "structure", "reason"):
        b.add_node(n, noop)
    b.add_edge(START, "select")
    b.add_edge("select", "adapt")
    b.add_edge("adapt", "structure")
    b.add_edge("structure", "reason")
    b.add_edge("reason", END)
    save("self_discover", b)

    # SQL agent (LangGraph tutorial node names)
    b = StateGraph(dict)
    for n in ("list_tables", "call_get_schema", "get_schema", "generate_query", "check_query", "run_query"):
        b.add_node(n, noop)
    b.add_edge(START, "list_tables")
    b.add_edge("list_tables", "call_get_schema")
    b.add_edge("call_get_schema", "get_schema")
    b.add_edge("get_schema", "generate_query")
    b.add_conditional_edges("generate_query", lambda s: "check_query", ["check_query", END])
    b.add_edge("check_query", "run_query")
    b.add_edge("run_query", "generate_query")
    save("sql_agent", b)

    return results


def main() -> None:
    manifest: dict[str, dict] = {}
    slugs = list(MERMAID.keys())

    print("=== Step 1: Official LangGraph tutorial images ===")
    for slug in slugs:
        dest = OUT / f"{slug}_architecture.png"
        src = try_official(slug, dest)
        if src:
            print(f"  official  {slug:18} ← {src.split('/')[-3:]}/{src.split('/')[-1]}")
            manifest[slug] = {"source": "official", "url": src, "file": dest.name}
        else:
            print(f"  skip      {slug:18} (no official PNG)")

    print("\n=== Step 2: Mermaid-rendered paper-accurate diagrams ===")
    for slug, mmd in MERMAID.items():
        dest = OUT / f"{slug}_architecture.png"
        if slug in manifest:
            # Keep official; also save mermaid as backup
            backup = OUT / f"{slug}_mermaid.png"
            method = render_mermaid(mmd, backup)
            if method != "failed":
                manifest[slug]["mermaid_backup"] = backup.name
            continue
        method = render_mermaid(mmd, dest)
        if method != "failed":
            print(f"  {method:12} {slug:18} → {dest.name}")
            manifest[slug] = {"source": method, "file": dest.name}
        else:
            print(f"  FAILED      {slug:18}")

    print("\n=== Step 3: LangGraph compiled graph PNGs (node-accurate) ===")
    try:
        lg = generate_langgraph_pngs()
        for slug, path in lg.items():
            print(f"  langgraph   {slug:18} → {Path(path).name}")
            manifest.setdefault(slug, {})["langgraph_file"] = Path(path).name
    except Exception as exc:
        print(f"  WARN langgraph PNG step skipped: {exc}")

    # REWOO paper workflow as extra asset
    extra = OUT / "rewoo_paper_workflow.png"
    url = try_official("rewoo_paper", extra)
    if url:
        print(f"  official  rewoo_paper_workflow ← downloaded")

    print("\n=== Step 4: Notebook overview diagrams (family map, decision tree, ER) ===")
    for name, mmd in NOTEBOOK_DIAGRAMS.items():
        dest = OUT / f"{name}.png"
        method = render_mermaid(mmd, dest)
        if method != "failed":
            print(f"  {method:12} {name:24} → {dest.name}")
            manifest[name] = {"source": method, "file": dest.name}
        else:
            print(f"  FAILED      {name:24}")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    n_arch = len(list(OUT.glob("*_architecture.png")))
    print(f"\nDone: {n_arch} architecture PNGs + manifest.json in {OUT}")


if __name__ == "__main__":
    main()
