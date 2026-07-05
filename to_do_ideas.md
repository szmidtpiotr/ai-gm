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
