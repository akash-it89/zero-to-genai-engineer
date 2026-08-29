---
name: rca-pack
description: Turn an incident log into a timeline, RCA, and a draft customer note. Load when the user asks for RCA, incident write-up, or a customer comms draft.
---

# Incident RCA pack

1. Delegate the raw log to `timeline-writer`. Use its dated bullets. Do not paste the whole log into the main chat.
2. Write `timeline.md` from those bullets.
3. Write `rca.md` — what broke, owner, next fix. Facts only.
4. Write a *draft* `customer_note.md`. Do not send it. Never invent outage minutes.
5. Keep each file under 160 words.
