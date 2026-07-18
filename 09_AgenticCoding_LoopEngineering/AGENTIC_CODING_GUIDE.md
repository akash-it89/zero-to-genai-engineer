# Agentic Coding Guide
## How to Build Production Systems with AI Agents — Kiro IDE & Claude Code

> This guide accompanies **Session 09 (M05)** of Zero to GenAI Engineer.
> In class, we built a real production stock analysis system using these exact workflows.
> Follow this guide to replicate the process on your own projects.

---

## 🏗️ The Project We Built in Class

### [Bullish Stock Scanner V3](https://github.com/nursnaaz/TechnicalStockPrediction/tree/feature/v3-high-precision)

A precision-first stock analysis system built **entirely through agentic coding** — no line was written without an AI agent involved.

**What it does:**
- Fetches real market data and applies Minervini-style technical filters
- Scores every stock 0–100 using a gradient engine (Trend, Momentum, RSI, Relative Strength)
- Runs a market-regime gate: bearish market → zero signals (waits for the right conditions)
- Backtests predictions with a confusion matrix (precision/recall/F1, no look-ahead bias)
- Serves everything through a FastAPI backend + React/Cloudscape frontend

**Why this project demonstrates agentic coding:**
- Complex enough that no one person wrote it all — the agent handled the boilerplate, tests, and structure
- 308-test suite (unit + property + integration + Playwright E2E) — all agent-generated
- Spec was written first, code came second — the agent followed the spec, not intuition
- Built using **Kiro IDE** for spec design and **Claude Code** for loop engineering

**Stack:** Python 3.10 · FastAPI · React · AWS Cloudscape · SQLite · Polygon.io API

---

## 🤖 Two Tools, One Philosophy

Both Kiro IDE and Claude Code follow the same underlying idea:

> **You define the goal. The agent figures out the steps. You verify the output.**

The difference is *where* you do this:

| | Kiro IDE | Claude Code |
|---|---|---|
| **Best for** | Spec-first design, multi-file systems | Terminal-native loop engineering |
| **Project memory** | Steering files (`.kiro/steering/`) | `CLAUDE.md` |
| **Automation** | Hooks (trigger on file events) | Hooks (trigger on tool events) |
| **Planning** | `requirements.md` → `design.md` → `task.md` | `/plan` mode → `CLAUDE.md` |
| **Skill library** | `skill.md` | Slash commands (`/review`, `/init`) |
| **Autonomous loop** | Agent mode | `/goal` · `/loop` |
| **Stop condition** | Task checklist completion | Deterministic shell command |

---

## Part 1 — Kiro IDE: Spec-Driven Development

### What "Spec-Driven" Means

Instead of opening a blank file and asking an AI to "write me a stock scanner", you:

1. Write a requirements document (what to build)
2. Write a design document (how to build it)
3. Break it into tasks (the checklist)
4. Let the agent execute each task — one at a time, with your approval

This is how senior engineers work. The spec comes before the code.

---

### The Kiro Project Structure

When you open a project in Kiro IDE, it creates a `.kiro/` directory:

```
your-project/
├── .kiro/
│   ├── steering/           ← Persistent instructions (always in agent context)
│   │   ├── product.md      ← What the product is and who it's for
│   │   ├── tech-stack.md   ← Tech decisions (never change these mid-project)
│   │   └── structure.md    ← Folder layout and naming conventions
│   ├── specs/
│   │   └── feature-name/
│   │       ├── requirements.md   ← What to build
│   │       ├── design.md         ← How to build it
│   │       └── tasks.md          ← Execution checklist
│   └── hooks/              ← Automated triggers
│       ├── on-save.md
│       └── on-task-complete.md
├── skill.md                ← Agent skill definitions
└── ... your code
```

---

### Steering Files — The Agent's Permanent Memory

**Location:** `.kiro/steering/`

Steering files are injected into every agent prompt automatically. Think of them as the `CLAUDE.md` equivalent — but Kiro splits them into focused files instead of one big document.

**`product.md` — What you're building**
```markdown
# Product

This is a stock scanner for halal-screened US equities.
Target user: retail investor who follows Minervini trend-following methodology.
Core value: fewer, higher-conviction signals — never buy in a bearish market.

Non-goals:
- No options, no crypto, no leverage
- No real-time streaming (point-in-time scans only)
- No trade execution
```

**`tech-stack.md` — Locked decisions**
```markdown
# Tech Stack (DO NOT CHANGE)

Backend:  Python 3.10, FastAPI, SQLite, httpx
Frontend: React 18, AWS Cloudscape Design System, TypeScript
Data:     Polygon.io REST API (≥252 trading bars per ticker)
Testing:  pytest, Hypothesis, Playwright
Deploy:   Docker, single-host
```

**`structure.md` — Folder and naming conventions**
```markdown
# Project Structure

backend/
  core/       - business logic (ScanOrchestrator, ScoringEngine, etc.)
  backtest/   - BacktestEngine and metrics
  api/        - FastAPI routes
frontend/src/
  components/ - Cloudscape UI components
  hooks/      - React custom hooks
  types/      - TypeScript interfaces

Naming: snake_case for Python, PascalCase for React components.
Every module in backend/core/ must have a matching test in tests/unit/.
```

**Why steering files matter:**
When you open a new chat in Kiro and ask "add a new filter", the agent already knows your stack, your structure, your naming conventions, and your non-goals. You don't explain the project every time. The steering files do that for you.

---

### skill.md — What the Agent Can Do

**Location:** `skill.md` (project root)

A skill file tells Kiro which tools and behaviours are available to the agent. You can define custom skills for your domain.

```markdown
# Agent Skills

## scan-stock
Run a full scan against the live API.
Command: python -m backend.cli scan --universe sp500
Output: JSON list of candidates with score ≥ threshold

## run-backtest  
Run the backtesting engine over historical dates.
Command: python -m backend.cli backtest --start 2024-01-01 --end 2024-12-31
Output: confusion matrix + portfolio simulation to stdout

## run-tests
Run the full test suite.
Command: pytest tests/ -v --tb=short
Success: exit code 0, "X passed, 0 failed"

## lint
Check code style.
Command: ruff check . && mypy backend/
Success: no output (silent pass)
```

When you tell the agent "run the tests and fix failures", it knows exactly which command to run and what success looks like — because you defined it in `skill.md`.

---

### Hooks — Automated Triggers

**Location:** `.kiro/hooks/`

Hooks are shell commands that run automatically when specific events happen. They close the feedback loop without you having to manually check.

**`.kiro/hooks/on-save.md`**
```markdown
# On Save Hook

Trigger: any Python file in backend/ is saved
Action: run ruff check {file} and show output inline
Purpose: catch style errors immediately, not at commit time
```

**`.kiro/hooks/on-task-complete.md`**
```markdown
# On Task Complete Hook

Trigger: agent marks a task in tasks.md as [x] complete
Action: run pytest tests/ -v -k {task_name}
Purpose: verify each task passes its tests before moving to the next
```

**`.kiro/hooks/on-spec-approved.md`**
```markdown
# On Spec Approved Hook

Trigger: user approves requirements.md
Action: auto-generate design.md skeleton from requirements
Purpose: saves 20 minutes of boilerplate design writing
```

---

### The Spec Workflow: requirements.md → design.md → tasks.md

This is the core of Kiro's spec-driven development. Three documents. Three phases. In order.

#### Phase 1 — requirements.md (What to Build)

Write this yourself, or ask the agent to draft it from a one-paragraph description.

```markdown
# Requirements: Stock Scoring Engine

## User Story
As a retail investor, I want to score every stock in my universe 0–100
so I can rank candidates by conviction without manually reading charts.

## Functional Requirements
- FR1: Score must incorporate Trend (SMA alignment), Momentum (price vs highs),
       Strength (RSI + cross-universe RS percentile), Confirmation (volume)
- FR2: Score must apply penalty for overextension (price > 110% of SMA50)
- FR3: Score must apply penalty for exhaustion signals (gap-up > 5% on weak volume)
- FR4: Score range: 0 to 100 (float, 2 decimal places)
- FR5: Input: a dict of {indicator_name: value}. Output: ScoringResult(score, breakdown)

## Acceptance Criteria
- AC1: A stock with all Minervini hard filters passing scores ≥ 40
- AC2: A stock with overextension penalty applied scores ≤ 80 even with perfect indicators
- AC3: pytest tests/unit/test_scoring_engine.py exits with 0 failed
```

**How to use it in Kiro:**
- Open requirements.md in the spec panel
- Ask the agent: "Review these requirements. Are there any gaps or contradictions?"
- The agent flags issues before you write a line of code

#### Phase 2 — design.md (How to Build It)

After requirements are approved, write (or generate) the design.

```markdown
# Design: Stock Scoring Engine

## Class: ScoringEngine

Location: backend/core/scoring_engine.py

### Interface
```python
@dataclass
class ScoringResult:
    score: float           # 0.0 to 100.0
    breakdown: dict        # component scores for transparency
    penalties: list[str]   # human-readable list of applied penalties

class ScoringEngine:
    def calculate_enhanced_score(
        self,
        indicators: dict[str, float],
        rs_percentile: float   # 0-100, cross-universe rank
    ) -> ScoringResult:
        ...
```

### Scoring Formula
```
base_score = (
    trend_score     * 0.30 +  # SMA alignment
    momentum_score  * 0.25 +  # price vs 52-week high
    strength_score  * 0.25 +  # RSI + RS percentile
    confirmation    * 0.20    # volume confirmation
)
final_score = base_score - extension_penalty - exhaustion_penalty + stage2_bonus
final_score = clamp(final_score, 0, 100)
```

### Tests Required
- tests/unit/test_scoring_engine.py
- Use Hypothesis for property-based testing (score always in [0, 100])
```

**How to use it in Kiro:**
- Show the agent your requirements.md and ask: "Generate a design.md for the ScoringEngine"
- Review the proposed interface, adjust, approve
- The agent will not write implementation code until design.md is approved

#### Phase 3 — tasks.md (The Execution Checklist)

The agent generates this from the approved design. Each task is one atomic unit of work.

```markdown
# Tasks: Stock Scoring Engine

- [ ] 1. Create ScoringResult dataclass in backend/core/scoring_engine.py
- [ ] 2. Implement trend_score() — SMA 50/150/200 alignment check
- [ ] 3. Implement momentum_score() — price vs 52-week high calculation
- [ ] 4. Implement strength_score() — RSI component + RS percentile weighting
- [ ] 5. Implement confirmation_score() — volume ratio vs 50-day average
- [ ] 6. Implement extension_penalty() — overextension above SMA50 check
- [ ] 7. Implement exhaustion_penalty() — gap-up on weak volume detection
- [ ] 8. Implement calculate_enhanced_score() — combine all components
- [ ] 9. Write unit tests in tests/unit/test_scoring_engine.py
- [ ] 10. Write Hypothesis property test: score always in [0.0, 100.0]
- [ ] 11. Run pytest — fix any failures
- [ ] 12. Run mypy on scoring_engine.py — fix any type errors
```

**How to use it in Kiro:**
- Ask the agent: "Execute task 1"
- Review the code, approve, ask: "Execute task 2"
- The `on-task-complete` hook runs tests automatically after each approval
- If tests fail, the agent fixes them before you move to task 3

**The critical rule:** Never skip phases. Requirements → Design → Tasks. In order. Every time.

---

### How to Start a New Project in Kiro (Step by Step)

```
1. Open your project folder in Kiro IDE
2. Ask: "Initialize this as a Kiro project — create .kiro/ structure"
3. Fill in .kiro/steering/product.md  (5 sentences about what you're building)
4. Fill in .kiro/steering/tech-stack.md (your locked decisions)
5. Create .kiro/specs/feature-name/requirements.md (user story + acceptance criteria)
6. Ask: "Review my requirements and draft a design.md"
7. Review and approve design.md
8. Ask: "Generate tasks.md from this design"
9. Execute tasks one by one: "Execute task 1", review, "Execute task 2", ...
10. The hooks handle test-running automatically after each task
```

---

## Part 2 — Claude Code: Spec-Driven Loop Engineering

Claude Code is a terminal-native agent. You run it from the command line inside your project directory. The workflow is different from Kiro — less visual, more script-like — but the underlying idea is the same: define what done looks like, let the agent work.

---

### CLAUDE.md — The Project's Permanent Memory

**Location:** project root

`CLAUDE.md` is read at the start of every Claude Code session. It's the equivalent of Kiro's steering files — but in one document.

Create it with `/init`, then customise it:

```markdown
# CLAUDE.md — Stock Scanner

## What This Project Is
A precision stock scanner. FastAPI backend, React frontend, SQLite storage.
Polygon.io for market data. Halal-screened US equities only.

## Tech Stack (Do Not Change)
- Python 3.10, FastAPI, pytest, Hypothesis, mypy, ruff
- React 18, AWS Cloudscape, TypeScript
- SQLite (no Postgres, no Redis)

## File Layout
backend/core/     → business logic
backend/api/      → FastAPI routes  
tests/unit/       → one file per core module
frontend/src/     → React components

## Quality Gates (Must Pass Before Commit)
pytest tests/ -v       → 0 failed
mypy backend/          → Success: no issues found
ruff check .           → no output (clean)

## Never
- No hardcoded API keys
- No look-ahead in backtesting (only data available on as_of_date)
- No changing the scoring formula without updating tests/unit/test_scoring_engine.py
```

---

### /init — Bootstrap Your CLAUDE.md

Run this once when you start a new project:

```bash
# Inside your project directory
claude
> /init
```

Claude reads all your existing files and generates a `CLAUDE.md` draft. Review it, add your tech-stack decisions and "Never" rules, save it.

---

### /plan — Think Before You Code

Before asking Claude to build something complex, enter plan mode:

```bash
> /plan build the ScoringEngine class with the formula from design.md
```

Claude will output a step-by-step plan — which files to create, which functions to write, in what order — **without writing any code**. You read the plan, adjust it ("skip step 3, we already have that"), then confirm.

Only after confirmation does Claude start writing code.

**Why this matters:** Without `/plan`, Claude may start coding immediately in the wrong direction. With `/plan`, you catch wrong assumptions before they cost you 10 minutes of reverting.

---

### Model Settings — Choosing the Right Model

```bash
# Use Opus for complex design and architecture work
claude --model claude-opus-4-8

# Use Sonnet (default) for day-to-day coding
claude

# Check which model is active
> /model
```

**Rule of thumb:**
- Writing new modules from a design doc → Opus (higher reasoning)
- Adding a function to an existing module → Sonnet (faster, cheaper)
- Loop engineering (`/goal`) → Sonnet (speed matters in loops)

---

### Slash Commands — Your Skill Library

These are built-in Claude Code skills, equivalent to Kiro's `skill.md`:

| Command | What It Does |
|---|---|
| `/init` | Reads your codebase, generates `CLAUDE.md` |
| `/plan <task>` | Plans the implementation without writing code |
| `/review` | Reviews the current diff for bugs and improvements |
| `/model` | Shows or changes the active model |
| `/goal <condition>` | Runs autonomously until condition is met, then stops |
| `/loop <task>` | Repeats a task indefinitely (background watcher) |

You can also create your own slash commands in `~/.claude/commands/`:

```markdown
# ~/.claude/commands/scan.md
Run the full stock scanner and show results.
Command: python -m backend.cli scan --universe sp500
Show the top 10 candidates sorted by score.
```

Then use it as `/scan` from any Claude Code session.

---

### Hooks — Automated Triggers in Claude Code

Claude Code hooks run shell commands automatically on events — the same concept as Kiro hooks, but configured in `~/.claude/settings.json`.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "ruff check ${file} 2>&1 | head -20"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "pytest tests/ -q 2>&1 | tail -5"
          }
        ]
      }
    ]
  }
}
```

**What these hooks do:**
- `PostToolUse Write` → runs `ruff check` on every file Claude writes (catches style errors immediately)
- `Stop` → runs `pytest` when Claude finishes a task (verifies it before you move on)

This closes the loop automatically. You don't have to remember to run tests.

---

### /goal — The Spec-Driven Loop

`/goal` is the Claude Code equivalent of Kiro's task execution — but fully autonomous. You define the finish line; Claude works until it gets there.

**The formula:**
```
/goal <what to build>
      — stop only when <exact shell command> <exact expected output>
      — max <N> turns
```

**Example — build and test the ScoringEngine:**
```
/goal implement ScoringEngine in backend/core/scoring_engine.py
following the interface in docs/design.md.
Stop only when:
  pytest tests/unit/test_scoring_engine.py -v exits with code 0
  AND mypy backend/core/scoring_engine.py prints "Success: no issues found"
Max 12 turns.
```

**What Claude does:**
1. Reads `design.md` for the interface
2. Writes `scoring_engine.py`
3. Writes `tests/unit/test_scoring_engine.py`
4. Runs pytest → 2 failures → reads failures → fixes the implementation
5. Runs mypy → 1 type error → adds type hints
6. All checks pass → stops

You come back to a working, tested, type-checked module.

**The stop condition must be deterministic** — a shell command with an exact, verifiable output. "The code looks good" is not a stop condition. "pytest exits with code 0 and prints '12 passed, 0 failed'" is.

---

### /loop — The Background Watcher

`/loop` runs forever. Use it for tasks that have no natural finish line.

```
/loop every 5 minutes: run python -m backend.cli scan --universe watchlist.txt
and if any stock scores above 85, append it to signals_today.txt with a timestamp
```

**Use `/loop` for:**
- Monitoring a scan output and alerting on new signals
- Watching a test suite and auto-fixing failures as they appear
- Keeping a changelog or PR description up to date as files change

**Use `/goal` for:**
- Building a new feature until tests pass
- Refactoring a module until mypy is clean
- Writing a spec until all acceptance criteria are met

---

### The Claude Code Spec Workflow (Step by Step)

```
1. Initialize the project
   > /init
   → Review and customize CLAUDE.md

2. Plan before coding
   > /plan implement the ScoringEngine from docs/design.md
   → Read the plan, correct any wrong assumptions, confirm

3. Execute with a goal
   > /goal implement ScoringEngine
         stop only when pytest tests/unit/test_scoring_engine.py -v exits 0
         max 10 turns
   → Walk away. Come back to a working module.

4. Review what was built
   > /review
   → Claude reviews its own output for bugs and improvements

5. Move to next component
   > /plan implement MarketRegimeAnalyzer from docs/design.md
   → Repeat from step 2
```

---

## Side-by-Side: Kiro vs Claude Code

| Workflow Step | Kiro IDE | Claude Code |
|---|---|---|
| **Project setup** | Create `.kiro/steering/` files | `/init` → customize `CLAUDE.md` |
| **Define what to build** | `requirements.md` (user stories, AC) | `/plan <task>` in the terminal |
| **Define how to build it** | `design.md` (interface, data models) | Add design decisions to `CLAUDE.md` |
| **Break into tasks** | `tasks.md` (checkbox list) | `/goal` with a stop condition |
| **Execute one task** | "Execute task 3" in the agent panel | `/goal <task> — stop when <test passes>` |
| **Auto-verify on save** | `.kiro/hooks/on-save.md` | `PostToolUse Write` hook in settings.json |
| **Auto-test on complete** | `.kiro/hooks/on-task-complete.md` | `Stop` hook → runs pytest |
| **Skill library** | `skill.md` | `~/.claude/commands/*.md` |
| **Background monitor** | Agent mode (continuous) | `/loop <task>` |
| **Choose model** | Kiro model selector | `--model claude-opus-4-8` flag |

Both tools work. Many engineers use both — Kiro for the initial spec and architecture, Claude Code for implementation loops and verification.

---

## The Mental Model: Agentic Coding in 3 Rules

**Rule 1 — Spec before code**
Never ask an agent to "build X" without first writing what X is (requirements) and how X works (design). The spec is your contract with the agent. Without it, the agent guesses.

**Rule 2 — Verifiable stop conditions**
Every task must have a machine-checkable finish line. Not "looks good" — a shell command with an exact expected output. This is what separates loop engineering from vibe coding.

**Rule 3 — Review before the next task**
Agents move fast. The only way to catch drift is to review each output before approving the next step. In Kiro this is the approval step. In Claude Code this is `/review`. Skip this step and errors compound.

---

## What to Build Next (Your Practice Project)

Try building a simpler version of what we built in class:

```
/goal build a Python stock screener that:
- fetches the last 30 days of daily OHLCV for AAPL, MSFT, GOOGL using yfinance
- calculates: 20-day SMA, 50-day SMA, RSI(14), and volume vs 20-day average
- prints a summary table: ticker | price | above_sma50 | rsi | volume_signal

Stop only when:
  python screener.py exits with code 0
  AND the output contains a table with all 3 tickers
  AND mypy screener.py prints "Success: no issues found"
Max 8 turns.
```

Then add a stop condition: only show stocks where RSI < 60 (not overbought) and price is above the 50-day SMA. That's a Minervini-style filter in 15 lines — built by an agent in under 8 turns.

---

*Session 09 · Module M05 · Zero to GenAI Engineer*
*Built with Kiro IDE + Claude Code — the same tools Mohamed used to build TechnicalStockPrediction V3*
