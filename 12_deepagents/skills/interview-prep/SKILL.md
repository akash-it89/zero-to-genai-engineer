---
name: interview-prep
description: Build an interview prep pack from a CV and a job description. Load this skill when the user asks to prep for an interview, write STAR stories, do a gap analysis, or build a battlecard.
---

# Interview prep pack

## Goal

Two short files a candidate can read the night before. Facts only. No cover letter.

## Steps

1. Call the `keyword-miner` subagent on the JD. Use its bullets. Do not re-extract in the main conversation.
2. Write `gap_analysis.md`:
   - 5 bullets of JD-must-have vs CV.
   - One bullet **must** say: the JD wants Arabic; the CV does not list it. Never claim she speaks it.
3. Write `star_stories.md`:
   - Exactly 2 STAR stories (Situation, Task, Action, Result).
   - Use only CV facts (RAG chatbot, RAGAS evaluation).
4. Keep each file under 180 words.

## Output

Write the files with the filesystem tools. Do not dump the full pack as a chat essay.
