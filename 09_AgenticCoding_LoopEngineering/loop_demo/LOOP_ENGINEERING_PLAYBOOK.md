# Loop Engineering Playbook
## Complete Reference for Mohamed's GenAI-2026 Students

> **One sentence definition:**  
> Instead of typing prompts into an AI, you design the *system* that prompts it, checks the result, and retries — automatically.

---

## How `/goal` and `/loop` Work

| Command | Behaviour | Use when |
|---|---|---|
| `/goal <condition>` | Claude works autonomously until the condition is TRUE, then stops | You have a clear finish line |
| `/loop <task>` | Claude repeats a task forever (or on a timer) until you stop it | You want a background watcher / daemon |

### The Formula for a Perfect `/goal`
```
/goal <what to build or fix>
      — stop only when <exact shell command> <exact expected output>
      — max <N> turns
```

**Why the stop condition matters:**  
A separate small model (Claude Haiku) reads the transcript after every turn and answers one question: *"Has the condition been met — yes or no?"*  
If yes → loop stops automatically.  
If no → Claude reads the failure, fixes it, tries again.

---

---

# SECTION A — Run Right Now
## (No external setup needed. Claude creates everything from scratch.)

---

### A-01 · Build a Streamlit App From Scratch

```
/goal build a Streamlit app in app.py with 3 tabs:
Tab 1 — a text input that counts words and characters live,
Tab 2 — a simple BMI calculator with height and weight sliders,
Tab 3 — a colour picker that shows the hex code of the chosen colour.
Stop only when python -c "import ast; ast.parse(open('app.py').read()); print('SYNTAX OK')" prints SYNTAX OK
AND grep -c "st.tabs\|st.tab" app.py returns a number greater than 0.
Max 8 turns.
```

**What the loop does:**  
Creates app.py → syntax check fails on a missing import → adds import → tabs structure wrong → fixes → all checks pass → stops.  
**Deliverable:** a working multi-tab Streamlit app you can launch with `streamlit run app.py`

---

### A-02 · Build a FastAPI Endpoint Until Tests Pass

```
/goal create a FastAPI app in api.py with these routes:
GET /health → {"status": "ok"},
POST /echo → returns the JSON body unchanged,
POST /reverse → returns {"result": <reversed string>} for {"text": "..."}
Write tests in test_api.py using httpx.AsyncClient.
Stop only when pytest test_api.py -v exits with code 0 and shows "3 passed".
Max 10 turns.
```

**What the loop does:**  
Writes api.py and test_api.py → test for /reverse fails (wrong key name) → fixes → test for /echo fails (content-type issue) → fixes → 3 passed → stops.  
**Deliverable:** a production-ready FastAPI app with a passing test suite.

---

### A-03 · Prompt Engineering Loop (the sentiment demo)

**Setup files (already created in this folder):**
- `prompt.txt` — starting system prompt
- `golden_dataset.json` — 10 labelled examples
- `score_prompt.py --demo` — verifier

```
/goal improve the system prompt in prompt.txt for a sentiment classifier
— test it against golden_dataset.json using: python score_prompt.py --demo
— keep refining the prompt
— stop only when the output contains "Accuracy: 9" or "Accuracy: 10"
— max 10 turns
```

**What the loop does:**  
Reads score → sees 7/10 → reads failure hints → adds sarcasm rule, neutral rule, understatement rule to prompt.txt → re-scores → 10/10 → stops.  
**Deliverable:** a production-quality few-shot sentiment prompt, auto-engineered.

---

### A-04 · Add Type Hints Until mypy Passes

```
/goal create a file utils.py with 5 utility functions (string cleaning,
list deduplication, date formatter, safe divide, email validator),
then add full type hints to every function and parameter.
Stop only when mypy utils.py --strict exits with code 0 and prints "Success: no issues found".
Max 8 turns.
```

**What the loop does:**  
Writes utils.py → mypy finds missing return types → adds them → mypy finds `Any` in email validator → narrows the type → passes → stops.  
**Deliverable:** a fully typed utility module, zero mypy errors.

---

### A-05 · Write Tests Until Coverage Hits 80%

```
/goal create a file calculator.py with add, subtract, multiply, divide,
power, and modulo functions. Then write pytest tests in test_calculator.py
covering as many paths as possible.
Stop only when pytest --cov=calculator --cov-report=term test_calculator.py
shows "TOTAL" coverage of 80% or higher AND exits with code 0.
Max 10 turns.
```

**What the loop does:**  
Writes calculator.py + basic tests → coverage 45% → adds edge cases (divide by zero, negative numbers) → 68% → adds boundary tests → 83% → stops.  
**Deliverable:** a fully tested module with proven 80%+ coverage.

---

### A-06 · Security Audit + Auto-Fix

```
/goal create a Python script vulnerable.py that intentionally contains
these issues: a hardcoded API key, a bare except clause, and an f-string
used in a subprocess call. Then fix all of them.
Stop only when:
bandit -r vulnerable.py -ll shows "No issues identified"
AND grep "except:" vulnerable.py returns empty
AND grep "sk-\|api_key = \"" vulnerable.py returns empty.
Max 8 turns.
```

**What the loop does:**  
Creates the vulnerable file → bandit finds 3 HIGH issues → fixes hardcoded key with os.getenv → fixes bare except → fixes subprocess injection → bandit clean → stops.  
**Deliverable:** a before/after demonstration of automated security hardening.

---

### A-07 · Build a Number Guessing Game Until Automated Tests Pass

```
/goal build a number guessing game in game.py:
The game picks a random number 1–10, gives "too high" / "too low" hints,
accepts user input in a loop, and prints "Correct! You got it in N guesses."
when the number is found.
Write a test in test_game.py that patches random.randint to return 7,
feeds the inputs [3, 9, 7] via monkeypatch, and asserts the final output
contains "Correct" and "3 guesses".
Stop only when pytest test_game.py -v exits code 0 and shows "1 passed".
Max 8 turns.
```

**What the loop does:**  
Writes game.py → test fails because input() blocks in tests → refactors to accept input stream → "3 guesses" message format wrong → fixes → 1 passed → stops.

---

### A-08 · Build a RAG Pipeline Until Eval Score Passes

```
/goal build a complete RAG pipeline in rag.py:
1. Create a small in-memory knowledge base of 10 facts about Python
2. Embed them with sentence-transformers (all-MiniLM-L6-v2)
3. Store in a simple numpy cosine similarity index
4. Answer queries by retrieving top-2 facts and returning them
Write an evaluator in eval_rag.py that asks 5 test questions and checks
that the retrieved context contains the correct answer keyword for each.
Stop only when python eval_rag.py exits 0 and prints "Score: 5/5".
Max 10 turns.
```

**What the loop does:**  
Writes rag.py → retrieval returns wrong facts for 2 queries → adjusts chunk strategy → score 3/5 → improves embedding call → 5/5 → stops.  
**Deliverable:** a working mini-RAG system with a passing eval suite — directly demonstrates M05 concepts.

---

### A-09 · Refactor a Messy Script Into a Clean Package

```
/goal create a messy script called messy.py with: no docstrings,
mixed snake_case and camelCase names, magic numbers, and no error handling.
Then refactor it into a proper module called clean.py following PEP-8:
add docstrings to every function, consistent naming, named constants, and
try/except blocks at every external call.
Stop only when:
pylint clean.py --fail-under=8 exits with code 0
AND python -m pydoc clean shows "FUNCTIONS" in the output.
Max 10 turns.
```

**What the loop does:**  
Writes messy.py → refactors to clean.py → pylint 6.2 (too many warnings) → fixes naming → 7.8 → adds missing docstrings → 8.4 → stops.

---

### A-10 · Build a Complete CLI Tool

```
/goal build a command-line tool in cli.py using argparse with 3 subcommands:
"count" (counts words/lines in a file),
"reverse" (reverses lines in a file),
"stats" (shows file size, line count, word count, unique word count).
Write tests in test_cli.py that create temp files and test each subcommand.
Stop only when pytest test_cli.py -v exits 0 and shows "3 passed"
AND python cli.py --help does not raise any error.
Max 8 turns.
```

---

### A-11 · Self-Healing Data Pipeline

```
/goal build an ETL pipeline in etl.py that reads data.csv,
drops rows where "age" is null or negative,
converts "date" column to datetime,
computes "revenue_per_user" = revenue / users (handle division by zero),
and writes the cleaned data to output.csv.
First create a sample data.csv with 20 rows including some bad data.
Stop only when python -c "
import pandas as pd
df = pd.read_csv('output.csv')
assert len(df) > 0, 'output is empty'
assert 'revenue_per_user' in df.columns, 'missing column'
assert df['age'].min() > 0, 'negative age found'
assert df['revenue_per_user'].isna().sum() == 0, 'null values found'
print('PIPELINE OK')
" prints PIPELINE OK.
Max 8 turns.
```

---

### A-12 · Build + Document a Python Library

```
/goal build a small Python library called texttools/ with an __init__.py
that exports 4 functions: word_count, sentence_tokenize, remove_stopwords,
and keyword_extract. Add Google-style docstrings to every function.
Stop only when:
python -m pytest tests/test_texttools.py exits 0
AND python -c "import texttools; help(texttools)" shows all 4 function names.
Max 10 turns.
```

---

### A-13 · `/loop` — Live Test Watcher (runs forever)

```
/loop watch this project for changes — every 2 minutes run pytest,
if any test fails read the traceback, find the source file, fix the bug,
and re-run until green. Print a one-line summary after each check.
```

**This one never stops on its own** — it's a background CI guardian.  
Stop it manually with `Ctrl+C` or close the Claude Code session.

---

### A-14 · `/loop` — Continuous Code Quality Monitor

```
/loop every 5 minutes run pylint src/ --fail-under=7 — if the score drops
below 7, identify the lowest-scoring file, fix the top 3 issues in it,
and re-run. Log each check with a timestamp to quality.log.
```

---

---

# SECTION B — Ideas
## (Great for inspiration. Need external dependencies before you can run them.)

---

### B-01 · Babysit GitHub Pull Requests

```
/loop babysit all my open PRs — check for failing CI checks every 10 minutes,
read the error log, fix the code, push the fix. When reviewer comments appear,
open a worktree, address each comment, and push the update.
```

**Needs:** GitHub access (MCP or gh CLI), a real repo with open PRs, CI configured.  
**Why it's powerful:** This is the Boris Cherny canonical example — the one that started the loop engineering movement.

---

### B-02 · Production Log Monitor + Auto-Fix

```
/loop watch /var/log/app/error.log every 5 minutes —
for each new ERROR line: classify it as known/unknown,
for unknown errors create a minimal reproduction script,
fix the source file, add a regression test, and open a GitHub PR.
```

**Needs:** Access to a running server's log file, GitHub repo, deployment pipeline.  
**Why it's powerful:** This is what on-call engineers do at 3am. The loop does it instead.

---

### B-03 · Auto-Label + Triage GitHub Issues

```
/loop check for new GitHub issues every 15 minutes —
read each unlabelled issue, classify it as bug/feature/question/duplicate,
apply the correct label, add a templated response, and if it's a duplicate
find the original issue and link it.
```

**Needs:** GitHub MCP or GitHub CLI with write access to the repo.

---

### B-04 · Dependency Vulnerability Scanner + Updater

```
/goal run pip-audit on this project — for every HIGH or CRITICAL vulnerability
found, identify the affected package, check if a patched version exists,
update requirements.txt to the safe version, run the test suite to confirm
nothing breaks, and open a PR for each fix.
Stop only when pip-audit shows 0 HIGH or CRITICAL vulnerabilities
AND pytest exits 0.
```

**Needs:** A real Python project with pinned dependencies and a test suite.

---

### B-05 · Slack + GitHub Issue Sync

```
/loop every 30 minutes read the #bugs Slack channel for new messages —
for each message that describes a bug and hasn't been triaged yet:
create a GitHub issue with a structured template (title, steps to reproduce,
expected vs actual behaviour), reply in Slack with the issue link.
```

**Needs:** Slack MCP, GitHub MCP, appropriate permissions.

---

### B-06 · Database Anomaly Watcher

```
/loop every hour query the analytics database for these signals:
revenue drop > 20% vs same hour yesterday,
error rate spike > 5x baseline,
new users < 10% of daily average.
If any alert fires, generate a plain-English incident summary,
post it to the #alerts Slack channel, and draft a SQL query
that digs one level deeper into the anomaly.
```

**Needs:** Database MCP (Postgres/BigQuery), Slack MCP.

---

### B-07 · Auto-Generate Changelogs From Git Commits

```
/goal read all git commits since the last release tag,
group them into Features / Bug Fixes / Breaking Changes / Chores,
write CHANGELOG.md in Keep a Changelog format,
and bump the version in pyproject.toml according to semantic versioning rules.
Stop only when CHANGELOG.md exists AND python -c "
import tomllib, re
v = tomllib.load(open('pyproject.toml','rb'))['project']['version']
with open('CHANGELOG.md') as f: content = f.read()
assert v in content, 'version not in changelog'
print('CHANGELOG OK')
" prints CHANGELOG OK.
```

**Needs:** A git repo with conventional commit history and a pyproject.toml.

---

### B-08 · Multi-Repo Dependency Migration

```
/goal find every Python file across all repos in ~/projects/ that imports
from the old openai package using ChatCompletion.create() and migrate them
to the new openai.chat.completions.create() API.
Stop only when grep -r "ChatCompletion.create" ~/projects/ --include="*.py"
returns empty AND all test suites that existed before still pass.
```

**Needs:** Multiple local repos, test suites, time (potentially hours).

---

### B-09 · Automated A/B Prompt Tester

```
/goal run 3 rounds of A/B testing between prompt_a.txt and prompt_b.txt
against eval_dataset.json. Each round: test both prompts, record accuracy,
improve the losing prompt based on its failure cases, run again.
Stop only when one prompt reaches 95%+ accuracy
OR 3 rounds complete and the winner is declared in results.md.
```

**Needs:** A large eval dataset (50+ examples) and a paid API key (many calls).

---

### B-10 · CI Pipeline Auto-Repair

```
/loop watch GitHub Actions for this repo every 5 minutes —
when a workflow fails: download the full log, identify the failing step,
determine if it's a code issue or an infra issue, if code: fix and push,
if infra: open an issue with the exact error and suggested fix.
```

**Needs:** GitHub Actions configured, MCP or gh CLI.

---

### B-11 · LLMOps Evaluation Loop (Langfuse)

```
/loop every night at midnight:
pull the last 100 LLM traces from Langfuse,
compute average latency / cost / faithfulness score,
compare to last week's baseline,
if faithfulness drops below 0.75 open a GitHub issue with trace examples,
if cost per request increases > 30% draft a prompt compression strategy.
Save a weekly report to reports/YYYY-MM-DD.md.
```

**Needs:** Langfuse MCP, GitHub MCP, a running production app sending traces.

---

---

# Stop Condition Cheat Sheet

| Goal type | Stop condition pattern |
|---|---|
| Build until tests pass | `pytest tests/ exits 0 and shows "N passed"` |
| Build until coverage | `pytest --cov=src shows TOTAL >= 80%` |
| Fix until linter clean | `pylint src/ --fail-under=8 exits 0` |
| Fix until type-safe | `mypy src/ --strict shows "Success: no issues"` |
| Fix until security clean | `bandit -r src/ -ll shows "No issues identified"` |
| Score/eval loop | `python score.py prints "Score: N/N"` |
| File-based check | `python -c "assert ...; print('OK')" prints OK` |
| Format check | `black --check src/ exits 0` |
| Build verification | `python -c "import myapp; print('IMPORT OK')" prints IMPORT OK` |

---

## The Three Rules of a Good Stop Condition

1. **Binary** — the condition is either met or not. No "looks good to me."  
2. **Observable** — a shell command produces output Claude can read.  
3. **Bounded** — always add `max N turns` to prevent infinite loops.

---

## Files in This Demo Folder

| File | Purpose |
|---|---|
| `prompt.txt` | Starting system prompt for the sentiment classifier |
| `golden_dataset.json` | 10 labelled sentiment examples (the eval set) |
| `score_prompt.py` | Verifier — run with `--demo` (no API) or without (Gemini) |
| `LOOP_ENGINEERING_PLAYBOOK.md` | This file |

**Quick start for the demo in class:**
```bash
cd /Users/mohamednoordeenalaudeen/Documents/GenAI-2026/loop_demo
cat prompt.txt                    # show the weak starting prompt
python score_prompt.py --demo     # show 7/10 baseline
# then fire /goal in Claude Code (see A-03 above)
```
