---
name: meeting-pack
description: Turn a messy standup or meeting transcript into a short pack. Load this skill when the user asks to pack a meeting, extract actions, or write decisions.md / actions.md.
---

# Meeting pack

## Goal

Two files a manager can read in two minutes. Names only from the transcript.

## Steps

1. Delegate action extraction to the `action-miner` subagent (`task` tool). Use its bullets. Do not re-extract in the main conversation.
2. Write `decisions.md` — 4 bullets. Only people who were in the room.
3. Write `actions.md` — owner + task. **Never assign Arabic copy to Aisha.** Fatima owns Arabic retail copy.
4. Keep each file under 160 words. Do not invent attendees.

## Output

Write the files with the filesystem tools. Do not dump the pack as a chat essay.
