# Journey Into AI-GM

*A technical history of six weeks of grim-fantasy software-making, April 9 – May 19, 2026. Compiled from 475 commits and 714 user prompts; honest about what shipped and what only seemed to.*

---

## 1. Project Genesis — April 9, 2026

The repository opens at `34712f4` with a single innocuous line: **"Initial project scaffold."** Two minutes later, `1704cf4` adds a repository setup note. Then, at 17:42 the same evening, the founding commit lands — `4817b3e`:

> 🎮 Complete working AI RPG Game Master
> - Ollama + GPU passthrough (gemma3:1b)
> - FastAPI backend (/gm/dice, /gm/chat)
> - Nginx proxy (localhost:3000 → backend:8000)
> - Frontend chat + dice + Enter-to-send
> - Warhammer/Cyberpunk/Neuroshima prompts
> - Fixed: Docker networking, nginx proxy_pass, CORS, paths
>
> Full stack: browser → nginx → FastAPI → Ollama GPU

The scope is already locked: a Polish-language AI Game Master fronting a dice-rolling, Warhammer-flavored RPG, running on a self-hosted Ollama instance behind Nginx. By April 10 (`4b417a4`) the unified `/api/campaigns/{id}/turns` endpoint and an `OllamaService` with Polish system prompts for "Warhammer/Cyberpunk/Neuroshima/Fantasy" was working end-to-end. Within 72 hours of the first commit, turn 62 of a real campaign confirmed `gemma3:4b` could generate Polish RPG prose (`0bfc8a1`).

The choice of stack — FastAPI + SQLite + vanilla JS + Nginx — never wavered. No frameworks beyond what was necessary. The dark-fantasy aesthetic and Polish narration are not a coat of paint applied later; they are present from the founding commit.

---

## 2. Architectural Evolution — V1 → V2

Six weeks compresses an unusual amount of architectural motion. Reading the git log, three eras are visible.

**Era 1: The "phase" era (April 9 – May 4).**
Work was organized as *Phase 6, Phase 7, Phase 8A/8B/8C/8D/8E/8F/8G/8H, Phase 9A, Phase 9B*. Each phase was a feature batch: Phase 6 added the character sheet; Phase 7 fixed the dice flow (`dfd0002` — "Phase 7 complete - dice roll full fix"); Phase 8 was an avalanche — combat, inventory, locations, voice, admin commands. Phase 9B alone landed 22+ tasks T01–T26 in ten days (`d1bc50c` through `3a320d0`). Polish commit messages started creeping in around `9f108cf` (April 25), reflecting the shift to Cursor as the primary co-author.

**Era 2: V2 architecture rebuild (May 11 – May 13).**
On May 12, the user delivered the pivotal prompt #357:

> *"so we are standing at a point where we need to decide if we are going to use LLM with some featuer of strict mechanics (prone to LLM halucinations) or if we rebuild whole project to be strict mechanics based, with LLM as a narrator promed by mechanics... change the LLM's job description from 'GM who runs the world' to 'interpreter + narrator who describes a world the system controls'."*

The next 36 hours generated `c55ab7d` ("docs: complete V2 architecture planning — 60 files, all decisions resolved") and a torrent of foundational task work: TASK_01 (DB schema, 12 new tables), TASK_02 (Intent Parser), TASK_03 (World State Machine), TASK_04 (Context Injector). The new paradigm: *the LLM no longer decides what is real.* It receives a `WYNIK MECHANICZNY` block from a Python-resolved `MechanicResolver` and narrates it. Phase 05 (combat), Phase 06 (economy), Phase 07 (narrator) followed in rapid sequence — six combat tasks (`b22299d`), seven economy tasks (`5fb1b9a`), four narrator tasks (`259c1d0`) all landed within one day.

**Era 3: The Hero-First Pivot (May 14–15).**
The original model tied each character to a campaign at creation. The user's prompt #509 changed that:

> *"jako ze jestesmy na etapie dungeonow a nie tylko ampanii, to jest chyba moment w ktorym powinnismy odwrocic flow. Teraz jest campania -> bochater a powinno byc tak ze tworzymy bohatera -> kampania lub dungeon, inne w przyslzosci."*

Task 42 was the architectural answer: heroes became first-class citizens (`1107780`), `characters.campaign_id` was made nullable, `characters.status` (`idle` | `in_campaign` | `in_dungeon`) was introduced. The "Hero-First Model" CLAUDE.md section is direct: *Heroes are independent entities. Deleting a campaign sets `characters.campaign_id = NULL, status = 'idle'` — hero is freed, NOT deleted.*

In parallel, the world map went from Cytoscape.js node-graph (`46dfe41`, Task 40 v1) to a Honeycomb.js + SVG hex grid (`ada6f4d`, `cf43a00`). One hex = one in-game hour. Dungeons (Task 41) shipped beside it — `dd62b85`, `3a1150b` — with seed dungeons `goblin_warren`, `crypt_of_bones`, `rat_tunnels`. Combat zones (T34) followed on May 18 (`b8bbf11`): every combatant now has `zone: 'engaged' | 'ranged'`, melee attacks are gated by zone, and enemies must spend a turn charging if mis-positioned.

---

## 3. Key Breakthroughs

A handful of commits stand out as the moments where a hard problem yielded.

**The F5 roll-bubble rehydration (issue #15, commit `85223f5`, May 18).**
Combat roll cards and skill-test result lines were vanishing on refresh — only GM narration survived. The user's prompt #662 spelled it out: *"all displayed in chat roll shoudl be visible and persist after f5."* Two root causes were diagnosed: `/combat/turns` returned only the *active* combat snapshot, so historical combats were unreachable; and skill tests persisted only `[Rzut: skill — d20]`, losing modifier, total, and outcome. The fix was structural: a new `list_all_combat_turns_for_campaign()` scanning every `combat_turns` row, a new `GET /api/campaigns/{id}/combat/turns/history` endpoint, and a richer persistence format `[Rzut: {label} — {d20} ±{mod} = {total} — {Outcome}]`. The frontend now fetches turns and combat history in parallel, interleaving them by `created_at` with combat events first on timestamp ties.

**The phantom-skill-test bug chain (issues #20 and downstream, commits `57d3c00` → `1725685` → `dbe9e39`).**
This is the canonical AI-GM saga: a small fix that wasn't small enough. The original symptom was "player types `atakuje goblina`, GM hallucinates a combat that was never started." The first fix (`57d3c00`) excluded `skill key='attack'` from the pre-LLM keyword scan. Done. Closed.

Then Geralt regressed. A warrior with `key='two_handed'` started a phantom skill test instead of fighting. The user did not say "great job"; they said *"is the test working?"* and pasted a debug log. The second fix (`1725685`) introduced `_COMBAT_CLASS_SKILLS` — a sentinel set that excludes all combat-class skills from skill-test creation at three sites (pre-LLM scan, post-cue scan, narrator tag handler). The third fix (`dbe9e39`) was an audit pass: the developer manually walked every row in `game_config_skills.trigger_keywords` looking for the same risk. Two more were found — `initiative` (keywords `inicjatywa szybko pierwszy refleks` matched generic narration) and `kowalstwo` (keywords included weapon nouns, so `wyciągam miecz z pochwy` triggered a blacksmith roll). Both got RAW_MIGRATIONS to trim their keyword lists.

The lesson sits in the commit message of `dbe9e39`: *"Audited all skill trigger_keywords for the same risk pattern; two more were obviously over-broad."* Single-symptom fixes are not architectural fixes.

**The Combat Sandbox isolation fix (`fab8b29`, May 18).**
The Combat Sandbox shipped as the user's explicit priority — prompt #678: *"i want you to create a solution for me - some sandbox where i could test combat mechanism without playing real game -> this is priority (new task)."* The first version was a "minimum viable" admin harness reusing the production combat engine. The second iteration added auto-enemy-turns. The third added a character-sheet card.

Then the user noticed: *"sandbox taking and use real data from database not temp copy. When hero die in sandbox it die in campaign, etc."* The fix (`fab8b29`) was elegant: every `/setup` call now `_clone_hero_for_sandbox()`s — a fresh row in `characters` with name `[SBX] <orig>` and `sheet_json.__sandbox_clone__=true`, with `character_inventory` and `character_spells` rows copied. `_purge_prior_sandbox_clones()` hard-deletes any prior clones, FK CASCADE handles their dependencies. Eldric (original id 1120) HP stayed at 5 across five sandbox enemy turns. The combat sandbox UX work continued for hours afterward — `5689f07` fixed action buttons being clickable before combat (a CSS `display:flex` overriding `[hidden]`), `c89b58f` fixed the busy-state race ("buttons stay disabled after enemy auto-turn"), `f568d7c4` added the advance-turn endpoint when it turned out that `resolve_attack(player)` didn't advance the turn server-side because the narration pipeline normally does that and the sandbox skips narration entirely.

**The T34 Combat UI completion (`6d9ba8a` + `b8bbf11` + `d57953f` + `74c350a`, May 18).**
Initiative panel + zone display + crit flash, all in one day. The crit-flash commit (`74c350a`) is worth quoting:

> CRIT (Nat 20): Inverse vignette: dark center, gold halo radiating INWARD from each viewport edge (four directional beams). "CIOS KRYTYCZNY" in Cinzel uppercase 700... Subtitle "Naturalny 20 — podwójne obrażenia" in italic IM Fell English.
>
> FUMBLE (Nat 1): Blood-red vignette closing IN from edges (opposite of crit). "FATALNE PUDŁO" in red with cracked text-shadow... 180ms 5-keyframe viewport shake.

This is the dark-fantasy aesthetic discipline in code. Total flash 700ms. Peak veil opacity 0.55. Shake 3px / 4 keyframes / 180ms. Respects `prefers-reduced-motion`. The numbers are documented as starting values per the game-design framework.

---

## 4. Work Patterns

The rhythm has texture. Some days are bug-fix days. Some days are feature-sprint days. Some days are documentation days.

**April 14** is a streaming-bubble bug-fix day: 13 commits between 12:42 and 21:55, almost all titled "fix: streaming bubble..." The decisive one is `7be7cce` ("fix: streaming SSE split + bubble resize jitter + thinking dots"), where the root cause is found in the commit body:

> Fix critical bug: buffer.split('\\n') was splitting on literal \\ + n (two chars) not real newlines — tokens never parsed during stream, everything dumped at end. Changed to split on real \n.

That is six hours of debugging compressed into one diff.

**April 30** is a voice-service day: 16 commits between 12:40 and 22:09, all `8G STT`. The user is testing on mobile and hears nothing; the fixes spiral through auto-stop logic, silence thresholds, RMS detection, hard timeouts, fallback paths. By 14:38 the dev has wired up a live mic-level debug overlay (`ee2d9ac`).

**May 13** is a feature-sprint day: 22 commits between 11:08 and 22:31, almost all V2 task work — Tasks 01 through 33SA shipped in approximately twelve hours of wall-clock time. The V2 rebuild was already planned, so this was execution, not exploration.

**May 14** is a smithing-skill day. The user asks for a Kowalstwo (smithing) skill test (#480) and expects to add it via the admin panel without code changes. The system returns Investigation instead. Then Athletics. Then *still* Athletics. Eight commits (`adb30f3` → `0baca82` → `cb9ccb7` → `71e1004`) walk through the layers: descriptions in the prompt, custom-skill override logic, `trigger_keywords` as DB column, Polish character normalization, and finally `71e1004` — the punchline:

> fix: game_config_skills has no is_active column — broke trigger_keywords silently
>
> All queries on game_config_skills used WHERE is_active = 1 but the table has no such column (it uses locked_at instead). This caused sqlite3 OperationalError which was swallowed by except Exception: pass, leaving the canonical skill as "athletics" despite the trigger_keywords matching.

A swallowed exception. Of course.

**May 18** is The Audit Day (its own section below).

---

## 5. Technical Debt — Shortcuts Taken and Paid Back

Two scaffolds in this project read as "we'll wire the frontend later" — and the audit caught both.

**Wound labels.** The backend function `economy_service.get_wound_label()` was written in `5fb1b9a` (May 13) as part of TASK_24. It mapped HP percentages to Polish labels: *Ranny* / *Ciężko Ranny* / *Poważnie Ranny* / *Na Skraju Śmierci*. It was correct and complete. It was *never called from any API response.* For five days the frontend rendered HP bars without wound labels. The audit caught it on May 18 (`9f357b1` — "T24 Wound Labels: ✅ → ⚠ (backend yes, frontend wound-label text no)"). The actual frontend implementation landed the same evening in `66d40e0` — and the developer deliberately replicated the threshold logic client-side rather than wiring the backend through, with a clean rationale: *"HP is already in every response, no extra HTTP bytes, no race conditions, labels are stable Polish strings."*

**XP grants.** `grant_character_xp` and the seed for `game_config_xp_awards` shipped with 22 sources — `combat.kill_minor`, `combat.kill_major`, `campaign.act_complete`, `exploration.new_location`, `skills.dc_hard_success`, and so on. The only one wired to a real game event was `combat.kill_*`. The other 21 sat in the DB as dead seeds. The May 18 audit (`9f357b1`) caught this too: *"22 sources seeded in `game_config_xp_awards`... but only 1/22 actually wired into code."* `d0c9b7d` documents the consequence — Stage 2 of the new execution queue is the XP loop, redesigned into four sub-stages (2A clock, 2B safe places, 2D 22-source wiring, 2C spending UI) with 32 sub-items, because *"bez 2A+2B+2D pętla jest pusta — gracz nie ma jak odpocząć, gdzie odpocząć, ani po co (poza zabijaniem potworów)."* (*Without 2A+2B+2D the loop is empty — the player has no way to rest, no place to rest, and no reason to rest besides killing monsters.*)

**The condition naming mess.** `combat_v2_service` used keys `fear_shaken` / `fear_frightened` / `terror`. The registry table `game_config_conditions` used `frightened` / `panicked` / `break`. The audit caught the mismatch on May 18; `97fcba3` was the migration + code rename. The commit message admits the underlying problem: a code path was writing rows whose `condition_type` did not exist as a row in the registry. The Stage 1 close-out W4 fixed it idempotently with a RAW migration.

These aren't bad-engineering moments. They are speed-versus-correctness tradeoffs that the audit re-corrected.

---

## 6. Challenges and Debugging Sagas

Two threads deserve closer reading.

### The Combat Sandbox UX cascade (May 18, ~10:00 – 13:30)

The Sandbox shipped at 09:52 (`6fa73bf`). Within 90 minutes, six follow-up fixes had landed:

| Commit | Time | Bug |
|---|---|---|
| `178d611` | 10:09 | "nothing happened" — current_turn != player but no enemy auto-turn |
| `5689f07` | 10:39 | Action buttons clickable before combat (CSS `display:flex` overriding `[hidden]`) |
| `c89b58f` | 10:43 | Buttons stuck disabled after enemy auto-turn (render fired with `busy=true`) |
| `3d67c24` | 11:02 | Log was opaque — added rich events feed mirroring player UI roll cards |
| `7bd5e8f` | 11:08 | HP bar missing on combatant rows |
| `d71e7c6` | 11:19 | Combat events from prior fights leaking into new fights |
| `c135238` | 11:49 | Player attack didn't advance turn server-side (sandbox skips narration) |
| `fab8b29` | 12:57 | Hero clone isolation (critical — see §3) |
| `6810961` | 13:01 | Shields routing to main_hand instead of off_hand |
| `f91e45f` | 13:05 | FK error after clone purge (active_combat referenced prior clone) |

This is what "iteration over a working prototype" looks like in commits. The user's prompts during this window are terse and diagnostic: log paste, log paste, screenshot, *"why there is so much space betewen HP barss and Wydarzenia WAlki?"* (#688), *"sandbox taking and use real data from database not temp copy."* (#689).

### The phantom-skill-test family

Three commits, each fixing what looked like the same bug at a deeper layer of generality:

1. **`57d3c00` — exclude key `attack`.** Single fix. Player types "atakuje" → hits `attack` skill keyword → phantom test. Excluded one key.
2. **`1725685` — exclude all combat-class skills.** Geralt's `two_handed` regression. The dev now realizes `attack`, `ranged_attack`, `two_handed`, `melee_attack`, `spell_attack` are weapon-stat modifiers used during real combat resolution and were never meant to fire as standalone skill checks. Introduces `_COMBAT_CLASS_SKILLS`.
3. **`dbe9e39` — audit all keywords.** The dev manually inspects every `game_config_skills.trigger_keywords` row. Catches `initiative` and `kowalstwo` (the smithing skill had been seeded with weapon-noun triggers like `metal ostrze zbroja miecz jakość`, so `wyciągam miecz z pochwy` was triggering a smithing roll).

Each commit broadens the fix until the bug class is closed, not just an instance. This pattern recurs in the codebase: see `4000761` ("Grant Item instructions" strengthened after debug log showed two items being silently dropped) and `1559d50` (T33 "Hybrid Input UI" — buttons now bypass the Intent Parser LLM call entirely so they cannot be misclassified).

---

## 7. The Audit Day (May 18, 2026)

This day is the inflection point.

By mid-May, the V2 rebuild was nominally complete. Phase 01–08 tasks were marked ✅. The roadmap claimed 67% completion. The user's prompt #698 punctured the optimism:

> *"i think we still didnt touch the hand / offhand difrentiation. SEcoundary we dont have address topic TASK_35_CHARACTER_SHEET_UI.md - almost all is not touched. We dont have xp earning and spending. Please read and check TASK_35_CHARACTER_SHEET_UI.md"*

The response was `69d3099` — "T35 status corrected ✅ → ⚠ — spec re-read reveals significant gaps." The commit body is candid: spec calls for location badge, wound label, XP progress bar, level-up banner, skill rank dots, stat tooltips, mobile bottom tab bar, real-time animations. Done in code: name+archetype+level header, HP/mana bars, gold, stat grid, skills list, 3-slot equipment, inventory, conditions, identity tab. About half of TASK_35.

Then the user delivered prompt #699 — the audit mandate:

> *"before we go, i want you do do an audit that will do file by file in /docs/V2_ARCHITECTURE and subfolders, and extend the roadmap with evry taks and subtask and mark them if its not done, done, or in progress. I dont want you to suggest by what its now in Roadmap file, but what relay is existing in code and whats in spec. No work before we establish all."*

What followed was `440f240` ("docs: spec-vs-code audit — 5-agent pass + spot-check corrections") and `9f357b1` ("docs: 2026-05-18 audit pass — corrected roadmap + decisions doc + spec amendments"). Five parallel Explore agents read every `TASK_XX` spec in `docs/V2_ARCHITECTURE` and verified each against actual backend/frontend code. Spot-checks caught several agent misreads (T34 crit flash, T43 World Map — both agents incorrectly marked ❌). Seven task statuses were re-corrected:

| Task | Roadmap before | Reality |
|---|---|---|
| T42 Persistent Hero | ✅ | ⚠ (schema done, endpoints + UI missing) |
| T20 Inventory | ✅ | ⚠ (3-slot shipped; 8-slot anatomical agreed) |
| T24 Wound Labels | ✅ | ⚠ (backend yes, frontend no) |
| T25V2 XP | ✅ | ⚠ (earning works, spending UI missing) |
| T35 Character Sheet | ✅ | ⚠ (~9 spec items missing) |
| T44 Debug System | ❌ | ⚠ (admin backend exists, player UI missing) |
| T36/T37/T38/T39 | ❌ | ⚠ (all have partial backend or basic UI) |

The honest accounting moved progress from 67% to 63% — *no regression, just partial completions now scoring 0.5 instead of 1.0.*

Two new canonical documents landed:
- `docs/V2_ARCHITECTURE/AUDIT_2026_05_18.md` — full spec-vs-code matrix
- `docs/V2_ARCHITECTURE/DECISIONS_2026_05_18.md` — 16 numbered decisions D1–D16

Then `b57b178` rewrote the roadmap. *"i want to go and mark out task, one by one in corect order"* (user prompt #702) became the **EXECUTION QUEUE** — 14 stages, ~75 numbered sub-items with short ID codes (W1–W5, X1–X10, Z1–Z6, S1–S12, E1–E7, H1–H5...). The phase-grouped view was kept below for context but is no longer the working surface. The day closed with Stage 1 complete: W1+W2+W3 (wound labels) in `66d40e0`, W4 (condition rename) in `97fcba3`, W5 (deceased NPC relationship) in `10072e8`. Three commits, three checkboxes. Then `6cf0468` re-designed Stage 2 (XP loop) into four sub-stages with 32 sub-items because the audit had revealed that the original 10-item Stage 2 was naïve — the clock didn't tick, safe-rest locations weren't editable, only 1/22 XP sources fired.

The audit's larger lesson is documented in `d0c9b7d`: the decisions D7+D12–D16 are now pinned in seven different spec files (TASK_25, TASK_26, TASK_23, 12_TRAVEL_SYSTEM, 01_IMPLEMENTATION_PLAN, TASK_08, TASK_13) so that *"przy kolejnym audycie tego samego dnia nie trzeba było ich odtwarzać"* — *so that at the next audit on the same day we don't have to reconstruct them.*

---

## 8. Tooling and Workflow Evolution

The workflow tightened in three observable ways.

**Implementation-record issues on GitHub became mandatory.** `e4595b2` (May 18) codifies the rule: *"Every new feature/task must be filed as a GitHub issue documenting what was implemented, with the structure established in issue #18 (task header, what was implemented, files changed, backend note, Numbers Policy, acceptance checklist, out-of-scope). Labels: enhancement + needs-testing — keep open until verified on DEV."* The rule didn't exist before mid-May; #18 was the template. By May 18, the CLAUDE.md `Implementation record issues (mandatory)` section was its own subsection.

**The execution queue replaced phase-grouping for daily work.** Phases were good for designing the system, bad for sequencing the day. `b57b178` flipped this: the queue is the working surface ("How to use this queue: pick topmost unchecked item, ship + mark + file needs-testing issue, don't skip silently"), the phase view kept for cross-reference.

**The Sandbox harness for combat testing.** This is the most consequential tooling decision in the log. Before the Sandbox, combat regressions could only be caught by playing through narrative — which meant either a full campaign session or scripted Playwright runs (the `ai_test_agent`, deferred to Phase 12). The Sandbox (`6fa73bf`, May 18) reuses the production combat engine end-to-end on an isolated hero clone, with a 📋 Kopiuj raport button that bundles hero + inventory + spells + combat state + events into clipboard markdown for bug reports. *"All existing combat behaviors (zone gating, AI charging, miscast, etc.) work in the sandbox without modification — same code path as the player UI."*

---

## 9. User-Claude Dynamic

The prompts file is the user's voice — Polish mixed freely with English, terse, screenshot-driven, occasionally Lord-of-the-Rings inspired, often catching Claude's optimism with a single sentence.

Three representative prompts:

**Prompt #357 (May 12, the V2 pivot):**
> *"so we are standing at a point where we need to decide if we are going to use LLM with some featuer of strict mechanics (prone to LLM halucinations) or if we rebuild whole project to be strict mechanics based, with LLM as a narrator promed by mechanics. you suggestion make sense and i like it. So nwo if we take approche: change the LLM's job description from 'GM who runs the world' to 'interpreter + narrator who describes a world the system controls.' - i need you to rebuild whole implementattion secenario to create a plan to rebuild."*

**Prompt #698 (May 18, the audit trigger):**
> *"i think we still didnt touch the hand / offhand difrentiation. SEcoundary we dont have address topic TASK_35_CHARACTER_SHEET_UI.md - almost all is not touched."*

**Prompt #699 (May 18, the audit mandate):**
> *"i want you do do an audit that will do file by file in /docs/V2_ARCHITECTURE and subfolders... I dont want you to suggest by what its now in Roadmap file, but what relay is existing in code and whats in spec. No work before we establish all."*

The pattern recurs across the timeline. Claude marks a task done; the user replies *"this isn't done"* (or one of its many phrasings — *"still no fight start"*, *"still rolling atletyka"*, *"nothing changed"*, *"i refreshed page bnut no implentation"*) and Claude course-corrects. The audit didn't invent this dynamic; it formalized it.

The user also pushes for visual design discipline — frequent invocations of `/frontend-design:frontend-design` (#477, #478, #648, #696, etc.), with prompts like #478:

> *"its to big, text over looks bad, math equasion on botmom looks bad. combine it all. i dona need super animation. It should be not to big but it should be compact. I could how in stage, first how dice with infor Roll, then roll, then nicle displayd result."*

This is what produced the staged Roll Popup (`6dd9bde` — "compact, staged, self-contained card"). The user wants compact. The user wants Polish labels. The user wants visual options and simple explanations.

---

## 10. Lessons and Meta-Observations

A new developer reading this history would learn the following.

**Spec drift is the dominant failure mode.** Not bugs in shipped code. Not bad architecture. The thing that bites repeatedly is: a spec is written, code is half-implemented to it, status is marked ✅, and three weeks later an audit reveals half the spec items are missing or named differently. The countermeasure that worked is `9f357b1`'s pinning of decisions back into the spec files they affect — D7 lives in TASK_25, TASK_26, TASK_23, 12_TRAVEL_SYSTEM, *and* 01_IMPLEMENTATION_PLAN, so when any of those is touched in future, the context is one click away.

**The dark-fantasy aesthetic is enforced in code, not just docs.** Crit flash overlay specifies viewport shake in pixels and milliseconds. The Roll Popup ("The Black Grimoire") uses clip-path polygons and Cinzel uppercase. Wound labels use IM Fell English italic with ❦ ornaments. Loading messages: *"GM konsultuje starsze, mroczniejsze księgi..."* Polish-language game labels are non-negotiable.

**The user prefers visual options + simple explanations + Polish UI.** The Smart Entry v3 form-first redesign (`755b214`) came directly from the user's frustration with the Q&A chat flow (#456: *"Lets get rid of Kreator, and Promote Warszaty - rename it to 'Bank pomysłów'"*). The button labels in the chat (`3903527`) come from #647: *"when button is used it send [EXAMINE:crack] - instead it shoudl show polish text from button so its cocherent."* The `prefers-reduced-motion` honoring on the crit flash is the user-empathy default.

**Trust the audit. Distrust optimism.** Claude's checkmarks bled into ✅ before the spec items were really shipped. The audit caught seven of those. The execution queue is now structured to make it harder to lie to oneself.

**SQLite is sufficient.** Through six weeks, 475 commits, 60+ database migrations, two architectural eras, and the introduction of zones / dungeons / hexes / spells / conditions / loot tables / NPCs / world-review queues / narrative items / Scholar mana / character clones — the database is still SQLite. The dev path runs `data/ai_gm.db` on host bind-mounted to `/data/ai_gm.db` in the backend container. The PROD path is the same. The bottleneck has never been the database.

---

## 11. Final Snapshot — May 19, 2026

The current branch is `main`. The working tree is clean. The most recent commits, in order:

| Hash | Subject |
|---|---|
| `d0c9b7d` | docs: pin Stage 2 XP loop decisions in 7 relevant spec files |
| `6cf0468` | docs: Stage 2 XP loop przeprojektowany — 4 podetapy + 22 źródła XP + zegar gry |
| `a920510` | docs(roadmap): W5 done — Stage 1 complete (commit 10072e8) |
| `10072e8` | fix(W5 / T28): deceased NPC relationship field |
| `b0a858f` | docs(roadmap): W4 done (commit 97fcba3) |
| `97fcba3` | fix(W4 / T16 / [D2]): condition rename — fear_shaken/terror → frightened/panicked |
| `cfa6526` | docs(roadmap): W1+W2+W3 done (commit 66d40e0) |
| `66d40e0` | feat(T24/W1+W2+W3): wound label rendered under player HP bars |

**What just shipped:** Stage 1 (audit close-outs W1–W5) is complete. T34 Combat UI is complete (initiative panel + zone display + crit flash + zone-change action). T46 Narrative Items is complete (lore items appear in inventory; narrative weapons flow into a pending-review queue admins can approve global or keep campaign-scoped). The Combat Sandbox (#21) is complete with hero clone isolation, auto enemy turns, character-sheet card, rich event feed, and Kopiuj raport for bug reports.

**Active priority:** Stage 2 — the XP loop — redesigned into four sub-stages (`6cf0468`):

- **2A — Game clock.** `advance_clock()` + travel/rest hookups + UI clock in header. *Currently the `ingame_hours` field exists in the DB and the narrator reads it, but nothing increments it.*
- **2B — Safe places.** LLM tag `[SET_SAFE_FOR_REST]` + safe_for_rest inheritance to hexes + admin UI + "Rozbij obóz" action with encounter risk.
- **2D — Wire 22 XP sources.** Hook the 22 seeded `game_config_xp_awards` rows to actual game events (campaign tags, exploration triggers, skill DC bonuses, narrative XP_GRANT, session).
- **2C — XP spending UI.** XP progress bar + "Awansuj" panel + `/rest` endpoints. Per D12, levels are display-only — no automatic bonuses, no level-up banner. XP is spent during long rest.

**Next unblocked task:** Stage 2A, T1 — implement `advance_clock()` and wire it to travel and rest. Without 2A, none of 2B/2C/2D works as a system; the loop is empty.

**The longer arc:** Phase 09 Frontend, Phase 10 Polish, Phase 11 Observability, Phase 12 AI Test Agent remain. The 8-slot anatomical equipment migration (D1, per prompt #700: *"head, torso, l arm, r arm, l leg, r leg"*) is queued at Stage 5. Auth refactor (D6, multi-user-ready) at Stage 10. The Hero Journal (T45) at Stage 11.

The repo today is a working dark-fantasy AI-GM RPG. It compiles, it runs, it has been played. It still has spec drift. The audit has at least one update left in it.

---

## Appendix — Cast of Recurring Issues

Implementation-record GitHub issues are how this project tracks what shipped. The recurring cast:

| # | Subject | Status & resolution |
|---|---|---|
| **#9** | Dungeon HUD overlapping character sheet | Fixed in `87f57cb` — `visibility:hidden` toggle so HUD stays in layout but doesn't block sheet clicks. |
| **#10** | Scholar balance — no offensive sustain | Fixed in `45f5011` (free cantrip d4+INT, mana regen `max(1, INT_mod*2)` post-combat) + `17bab4b` (Scholar starting spells granted in the standalone hero flow that was missing the call). |
| **#11** | Narrative items silently dropped | Fixed in `232722f` — `_grant_narrative_item_to_inventory` violated `inv_xor` CHECK by inserting NULL for all three key columns; now uses sentinel `__narrative__`. Real root cause in `d24d70b` — `extract_grant_cues()` was receiving plain text, not the full JSON; `_parsed_json.grant_item` was silently discarded. |
| **#12** | Lockpicking roll demanded even with matching key | Fixed via system-prompt change in `c0988a8` — AKCJA ZWYKŁA now explicitly lists "using a matching key to open a lock" as always no-roll. |
| **#13** | Pending review queue missing CREATE tags | Fixed in `d24d70b` — `process_create_tags()` was only called in the streaming SSE path, never in the main narrative turn handler. |
| **#14** | Azure OpenAI provider support | Fixed in `32b208c` — `AzureDriver` added to `llm_service.py`, uses `api-key` header (not Bearer), URL format `{base_url}/openai/deployments/{model}/chat/completions?api-version=2024-02-01`. |
| **#15** | F5 rehydration of roll bubbles | Fixed in `85223f5` — see §3. New endpoint `GET /api/campaigns/{id}/combat/turns/history`, richer skill-test persistence format. |
| **#16** | Loot table sidebar — heights and search | Fixed in `243e7c5` (`flex-shrink:0` so buttons don't compress) + `bb59ebe` (client-side search filter on the loot-table list). |
| **#17** | T34 Initiative panel | Filed and shipped in `6d9ba8a` — horizontal initiative track with active/acted/downed states, new-round gold sweep. |
| **#18** | Implementation-record issue template | The template issue itself. CLAUDE.md now requires every implementation be filed as an issue matching this structure. |
| **#19** | T34 Zone system | Backend `b8bbf11` + frontend `d57953f`. Combatants get `zone: 'engaged' | 'ranged'`, melee gating, AI charging, `POST /api/campaigns/{id}/combat/zone-change`. |
| **#20** | Phantom skill tests on combat verbs | Three-commit chain — `57d3c00` (exclude `attack`), `1725685` (exclude all combat-class skills `_COMBAT_CLASS_SKILLS`), `dbe9e39` (audit pass — trimmed `kowalstwo` weapon-noun keywords, cleared `initiative` keywords). See §3, §6. |
| **#21** | Combat Sandbox | Shipped `6fa73bf` plus ten follow-ups. Hero clone isolation `fab8b29`. See §3, §6. |
| **#22** | Sandbox Playwright autotest integration | Companion follow-up to #21. Not yet started. |
| **#23** | T34 Crit Flash | Shipped `74c350a`. CIOS KRYTYCZNY / FATALNE PUDŁO overlay. 700ms total, peak veil 0.55, 3px/180ms shake, respects `prefers-reduced-motion`. |
| **#24** | T35 Character Sheet UI audit | Filed when user noticed almost half the spec wasn't touched. Triggered the May 18 audit chain. Status moved ✅ → ⚠. |
| **#25** | (referenced; details outside the log window) | — |
| **#26** | (referenced; details outside the log window) | — |

---

*Compiled May 19, 2026. The story is not finished. The clock has not yet started ticking.*
