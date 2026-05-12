# TASK 22 — Memory & History

**Status:** ❓ Needs Design
**Blocking:** Design discussion needed

---

## What Needs to Be Designed

1. **Purpose of /mem** — Recall past events ("what did the innkeeper say?"), search lore, or both? Does it search ALL turns or only key narrative turns?
2. **Memory scope** — Current implementation: semantic search over `campaign_turns`. Is this sufficient or do we need a curated "important events" log?
3. **Summary display** — "Historia" button exists in right panel but its placement and the summary UX need design. On-demand only or periodically surfaced?
4. **Dual-summary** — `POST /campaigns/{id}/dual-summary-preview` exists but is not integrated. What is it for? (Player-facing summary vs GM-facing summary?)
5. **GM continuity** — Should the GM automatically receive a condensed summary of past N turns at the start of each new session to maintain narrative continuity?
6. **Purpose of /helpme** — `POST /campaigns/{id}/helpme` exists but its player-facing purpose is unclear. Hint system? Rules reminder? In-world "ask a sage"?
7. **Memory as a game mechanic** — Should recalling memories have any narrative cost or be a free "rewind" ability?

## Current State

- `/mem <query>` → `POST /campaigns/{id}/memory/ask` → semantic search over `campaign_turns`
- `/helpme` → `POST /campaigns/{id}/helpme` — purpose unspecified
- AI summary: `POST /campaigns/{id}/history/summary` — generates + stores to `campaign_ai_summaries`
- `POST /campaigns/{id}/history/summary/ensure` — idempotent version
- "Historia" button in right panel → calls summary endpoint; cooldown per ~20 turns; owner can regenerate
- `POST /campaigns/{id}/dual-summary-preview` — exists, generates two summary versions, NOT integrated into player UI

---

*This file will be filled with full specification after the design discussion.*
