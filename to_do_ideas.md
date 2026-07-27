# Planned work / ideas backlog

## PM3 #1222 — LLM fallback for descriptive-travel target extraction

**TODO (no new LLM call yet):** the descriptive-travel resolver
(`resolve_player_text_to_known_hex`, `hex_travel_service.py`) currently extracts
the destination with regex + fuzzy-prefix matching against known/discovered
hexes. When a player phrases a destination the regex/fuzzy path can't catch
("chcę tam gdzie płynie ta rzeka co ją mijaliśmy"), there is no target
extraction.

`app/services/turn/turn_intent.py` has **no** destination-extraction classifier
today (only risky-intent + hex-enter trigger). When such a classifier is added
(or an existing LLM call is extended to also emit a `travel_target` field),
wire it in AFTER the regex/known-hex resolver and BEFORE the vague hint — reuse
its output through the same `execute_travel` path. **Do not add a dedicated
extra LLM round-trip just for this** (latency/cost); piggyback on the intent or
narrator call instead.

## WL-9 #1504 — wyspiarze as background NPCs in OTHER regions' narration

**TODO (not cheap → deferred):** lore §7 (`docs/world/regions/wybrzeze_lez.md`)
sets a connecting thread — wyspiarze are the *only* race present in EVERY region
(mercenaries, sailors, smugglers: port of Vilnograd, Obóz Gorączki on the
Pustkowia, etc.). WL-9 delivered this thread only where it was cheap: inside
`RACE_PLAN_HINT["wyspiarze"]` (reaches campaigns whose **hero** is a wyspiarz).

For a wyspiarz to appear as flavor in a **dwarf/elf/człowiek** campaign's
narration, the injection point would have to be keyed by campaign *region*, not
by hero race — the current `race_plan_hint()` is race-keyed. That needs either a
per-region narrator flavor field or a world-context injection independent of the
hero, which is a broader prompt change. Deferred until there is a region-level
narration hint to piggyback on (do **not** add a dedicated LLM call for it).
