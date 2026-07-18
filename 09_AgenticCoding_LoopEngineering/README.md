# Session 09 — Agentic Coding & Loop Engineering
### M05 — Complete

> **What was MISSING from S07:** We could call LLMs, chain them, optimise prompts — but we were still writing all the code ourselves. This session teaches how to make the AI write the code FOR you, reliably, through spec-driven workflows and loop engineering.

---

## What This Session Covers

| Day | Topic | Key Concepts |
|-----|-------|--------------|
| S09a | Agentic Coding | History of agentic AI (Prompt Engineering → ReAct → AutoGPT → RALPH → Loop), what makes a good `/goal`, Kiro IDE spec-driven workflow |
| S09b | Loop Engineering | `/goal` vs `/loop`, the 5-step loop pattern (Trigger → Action → Verify → Decide → Stop), Claude Code spec-driven workflow, hooks, stop conditions |

---

## Contents

| File | Description |
|------|-------------|
| `AGENTIC_CODING_GUIDE.md` | Full guide to agentic coding — history, patterns, tooling |
| `loop_demo/LoopEngineering.md` | Loop engineering concepts and theory |
| `loop_demo/LOOP_ENGINEERING_PLAYBOOK.md` | Hands-on playbook with 20+ exercises |

---

## Key Concepts

### The 5-Step Loop Pattern
```
Trigger → Action → Verify → Decide → Stop
```

1. **Trigger** — What kicks off the loop (a `/goal` command, a failing test)
2. **Action** — The AI writes/modifies code
3. **Verify** — A deterministic check (test suite, linter, type checker)
4. **Decide** — Pass → stop, Fail → loop back to Action
5. **Stop** — Only when the verifier passes with exact expected output

### Stop Conditions Must Be Deterministic

A good stop condition is a shell command with an exact expected output:
```
pytest tests/ --tb=short    # expected: "all passed"
npm run lint                # expected: "0 errors"
```

"Looks good" or "seems done" are NOT valid stop conditions.

### Kiro vs Claude Code Workflows

| Tool | Workflow |
|------|----------|
| **Kiro IDE** | Steering files → `requirements.md` → `design.md` → `tasks.md` → hooks |
| **Claude Code** | `/init` → `/plan` → `/goal` with stop condition → `/review` → repeat |

---

## Demo Project

The [Bullish Stock Scanner V3](https://github.com/nursnaaz/TechnicalStockPrediction/tree/feature/v3-high-precision) was built entirely through agentic coding — FastAPI + React + 308 tests, produced through spec-driven loops.

---

## Prerequisites

- All prior sessions (S00–S07) for context
- Familiarity with CLI tools (terminal, git)
- Kiro IDE or Claude Code installed

---

*Part of the GenAI-2026 curriculum — zero-to-genai-engineer track*
