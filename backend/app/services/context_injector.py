"""
Context Injector — V2 Phase 01 Task 04

Assembles the complete narrator prompt from DB facts + mechanic results.
This is the primary anti-hallucination layer: the narrator only sees what
the injector explicitly provides.

The injector runs after the WSM + resolvers. It does NOT call the LLM.
It returns a single prompt string passed to llm_service.generate_chat().
"""

from __future__ import annotations

import json
import re
import sqlite3
import structlog
from dataclasses import dataclass

logger = structlog.get_logger()

# ── Default values ─────────────────────────────────────────────────────────

DEFAULT_TONE = (
    "Mroczne fantasy. Świat jest surowy i niesprawiedliwy. "
    "Bohater nie jest wybrańcem — przeżywa dzięki sprytowi i szczęściu. "
    "Nie ma miejsca na epicki optymizm. Konsekwencje są realne."
)

NARRATOR_CONSTRAINTS = """\
=== INSTRUKCJE DLA NARRATORA ===
Jesteś narratorem. Twoja rola:
1. Opisz wynik mechaniczny podany w bloku WYNIK MECHANICZNY. Nie zmieniaj go.
2. Opisy lokacji i postaci bazuj wyłącznie na danych z bloków ŚWIAT i POSTACIE NA SCENIE.
3. Nie wymyślaj nazw własnych, postaci, przedmiotów ani miejsc niewymienionych w kontekście.
4. Opisz stan zdrowia i emocje postaci zgodnie z blokiem STAN POSTACI.
5. Utrzymaj ton kampanii z bloku TON KAMPANII.
6. Pisz po polsku. Użyj 2-4 zdań. Nie zadawaj pytań graczowi.
7. Nie decyduj o kolejnych akcjach gracza."""

# Wound labels by HP percentage
_WOUND_LABELS = [
    (100, "Zdrowy/a"),
    (75,  "Lekko zadrapany/a"),
    (50,  "Ranny/a"),
    (25,  "Poważnie ranny/a"),
    (10,  "Ciężko ranny/a — każdy ruch boli"),
    (1,   "Na skraju śmierci — ledwo oddycha"),
    (0,   "Nieprzytomny/a — rzuty na śmierć"),
]

# Fear condition → label. Three stages per spec T16 (post 2026-05-18 W4 merge):
# frightened (failed Fear save) → panicked (failed Terror save) → break (Nat 1
# on Terror save, forced auto-flee).
_FEAR_LABELS = {
    "frightened": "Przerażony/a — trudno skupić myśli",
    "panicked":   "Ogarnięty/a paniką — ciało nie słucha",
    "break":      "Złamany/a — musi uciekać",
}

# Polish honorifics / common titles — NOT treated as invented proper nouns
_POLISH_WHITELIST = {
    "pan", "pani", "mistrz", "kapitan", "szef", "głowa", "lord", "lady",
    "rycerz", "strażnik", "strażniczka", "kupiec", "karczmarz", "karczma",
    "lekarz", "czarownik", "czarownica", "mag", "wiedźma", "wiedźmin",
    "goblin", "ork", "troll", "szkielet", "wampir", "wilk", "bandyta",
}

MAX_PERSONALITY_PROMPT_LEN = 200
MAX_PROMPT_TOKENS_APPROX = 3000   # rough char-based heuristic (1 token ≈ 4 chars)
MAX_PROMPT_CHARS = MAX_PROMPT_TOKENS_APPROX * 4


# ── Return type for post-processing ───────────────────────────────────────

@dataclass
class PostProcessResult:
    text: str
    retry_needed: bool
    substitutions_made: int = 0


def build_plan_enemy_keys_block(conn: sqlite3.Connection, campaign_id: int) -> str:
    """#1284/#1296 — surface a campaign's plan-specific enemy keys to the narrator.

    The static system_prompt only lists ~10 generic keys and forbids inventing new
    ones. Named plan bosses (materialized into game_config_enemies) would otherwise
    be unreachable — the LLM would map them onto a generic key. Listing the real,
    playable keys here lets the narrator emit [COMBAT_START:<key>] for the actual
    boss so _fetch_enemy_row resolves the full stat block + loot instead of a
    12HP/11AC stand-in.

    Only keys that actually exist and are active in game_config_enemies are listed,
    so we never point the narrator at a non-playable key. Standalone (not a method)
    so both the solo ContextInjector and the multiplayer narrator (#1296) reuse it.
    """
    try:
        row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not row or not row[0]:
            return ""
        plan = json.loads(row[0])
        plan_enemies = plan.get("key_enemies") or []
        if not plan_enemies:
            return ""
        keys = [str(e.get("key") or "").strip() for e in plan_enemies if isinstance(e, dict)]
        keys = [k for k in keys if k]
        if not keys:
            return ""
        placeholders = ",".join("?" for _ in keys)
        live = {
            r["key"]: dict(r)
            for r in conn.execute(
                f"""SELECT key, label, tier FROM game_config_enemies
                    WHERE key IN ({placeholders}) AND COALESCE(is_active, 1) = 1""",
                keys,
            ).fetchall()
        }
        if not live:
            return ""
    except Exception:
        return ""

    lines = [
        "=== WROGOWIE TEJ KAMPANII (dodatkowe DOZWOLONE klucze [COMBAT_START]) ===",
        "Oprócz standardowych kluczy z kontraktu, w TEJ kampanii możesz też użyć "
        "poniższych — to konkretni, nazwani przeciwnicy z planu. Gdy walka dotyczy "
        "którejś z tych postaci, użyj DOKŁADNIE jej klucza (nie mapuj na generyczny "
        "typ, nie wymyślaj wariantu):",
    ]
    for e in plan_enemies:
        if not isinstance(e, dict):
            continue
        k = str(e.get("key") or "").strip()
        meta = live.get(k)
        if not meta:
            continue
        name = meta.get("label") or e.get("name") or k
        tier = meta.get("tier") or e.get("tier") or "standard"
        lines.append(f"- {k} — {name} ({tier})")
    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


# ── Main class ─────────────────────────────────────────────────────────────

class ContextInjector:
    """
    Assembles the narrator prompt for every turn.

    Usage:
        injector = ContextInjector(conn)
        prompt = injector.build(
            session_flags=flags,
            mechanic_result=result,
            action_type="ATTACK",
            character_id=15,
            campaign_id=42,
        )
        raw_response = llm_service.generate_chat([{"role":"user","content":prompt}])
        final, retry = injector.post_process(raw_response, session_flags, mechanic_result).text, ...
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        # PT-F7 #1141: key of the current location, derived from current_location_id
        # during build() and reused by post_process/whitelist (which lack campaign_id).
        self._cached_loc_key: str = ""

    def _current_location_key(self, campaign_id: int | None, session_flags: dict | None = None) -> str:
        """PT-F7 #1141: current location key from current_location_id (single source).

        Production always passes campaign_id → DB derive (and caches for the sub-blocks
        that lack campaign_id, like the whitelist). The session_flags fallback exists
        only for legacy/unit callers that invoke a sub-block directly without a
        campaign_id — production flags never carry the key anymore."""
        if campaign_id is not None:
            from app.services.location_state_service import get_current_location_key
            key = get_current_location_key(self.conn, campaign_id) or ""
            self._cached_loc_key = key
            return key
        if self._cached_loc_key:
            return self._cached_loc_key
        if session_flags:
            return session_flags.get("current_location_key", "") or ""
        return ""

    def build(
        self,
        session_flags: dict,
        mechanic_result: dict,
        action_type: str,
        character_id: int,
        campaign_id: int,
        player_message: str = "",
    ) -> str:
        """
        Build the complete narrator prompt string.

        Args:
            session_flags: Current session state (includes location_key, combat_roster, etc.)
            mechanic_result: Resolved mechanical outcome from resolver
            action_type: The action that was resolved (e.g. "ATTACK", "DIALOGUE")
            character_id: Active character
            campaign_id: Active campaign
            player_message: Raw player input (used by U29 for candidate search in ŚWIAT block)

        Returns:
            Complete prompt string to pass to LLM narrator.
        """
        location_key = self._current_location_key(campaign_id)

        # Load required data
        location = self._get_location(location_key)
        character = self._get_character(character_id)
        npcs = self._get_npcs_in_location(location_key)
        combat_roster = session_flags.get("combat_roster", [])
        active_conditions = self._get_active_conditions(character_id)
        ingame_hours = session_flags.get("ingame_hours", 9)
        tone = self._get_campaign_tone(campaign_id)

        # Stage 9 P2 — Continuity injection: if there's been a ≥30 min gap since
        # the last narrative turn AND we haven't already injected for this gap,
        # prepend the latest player_summary as a "previously, on…" prefix.
        continuity_block = self._build_continuity_block(campaign_id, session_flags)

        # L13c (#689): when an active tile dungeon run is in progress, the player is
        # INSIDE the dungeon — suppress all overworld context (world/ŚWIAT, location,
        # overworld NPCs, stale, narrative-state, content-index). Otherwise those
        # blocks dominate the [LOCH] block and the narrator invents overworld scenes
        # (e.g. a forest) and offers travel hooks. Keep only the dungeon tile,
        # combat mechanic, character state and tone.
        _drun = (session_flags or {}).get("dungeon_run") or {}
        _in_dungeon = (
            _drun.get("system") == "tiles_v2"
            and not _drun.get("completed")
            and not _drun.get("failed")
        )

        hero_chronicle_block = self._build_hero_chronicle_block(character_id, campaign_id)

        if _in_dungeon:
            blocks = [
                continuity_block,
                self._build_length_directive_block(session_flags, action_type, mechanic_result, player_message),
                self._build_loch_block(session_flags),
                self._build_entities_block([], combat_roster),  # enemies only, no overworld NPCs
                self._build_mechanic_block(action_type, mechanic_result),
                self._build_character_state_block(character, active_conditions),
                self._build_tone_block(tone),
                NARRATOR_CONSTRAINTS,
            ]
        else:
            # Build blocks
            blocks = [
                continuity_block,
                hero_chronicle_block,
                self._build_reputation_block(character_id, campaign_id),
                self._build_length_directive_block(session_flags, action_type, mechanic_result, player_message),
                self._build_narrative_state_block(session_flags),
                self._build_world_block(session_flags, ingame_hours, player_message, campaign_id),
                self._build_stale_block(session_flags),
                self._build_entities_block(npcs, combat_roster),
                self._build_plan_enemy_keys_block(campaign_id),
                self._build_mechanic_block(action_type, mechanic_result),
                self._build_character_state_block(character, active_conditions),
                self._build_tone_block(tone),
                self._build_content_index_block(mechanic_result),
                self._build_loch_block(session_flags),
                NARRATOR_CONSTRAINTS,
            ]

        prompt = "\n\n".join(b for b in blocks if b)

        # Token budget guard
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = self._trim_prompt(blocks, npcs, combat_roster, tone)
            logger.warning("context_injector_trimmed", char_len=len(prompt))

        return prompt

    def post_process(
        self,
        narrator_response: str,
        session_flags: dict,
        mechanic_result: dict,
        must_reveal_infos: list[str] | None = None,
    ) -> PostProcessResult:
        """
        Post-process narrator response:
        1. Check must_reveal_info presence (fuzzy match)
        2. Detect and substitute invented proper nouns

        Returns PostProcessResult with final text and retry_needed flag.
        """
        must_reveal_infos = must_reveal_infos or []

        # 1. must_reveal_info check
        for info in must_reveal_infos:
            if not self._fuzzy_check_info(narrator_response, info):
                logger.info("context_injector_must_reveal_missing", info=info[:50])
                return PostProcessResult(text=narrator_response, retry_needed=True)

        # 2. Invented noun detection (light heuristic)
        location_key = self._current_location_key(None, session_flags)
        whitelist = self._build_whitelist(session_flags)
        processed, subs = self._strip_invented_nouns(narrator_response, whitelist)

        # 3. Language check — if response looks non-Polish, flag retry
        if self._is_non_polish(processed):
            logger.warning("context_injector_language_drift", response_start=processed[:50])
            return PostProcessResult(text=processed, retry_needed=True)

        return PostProcessResult(text=processed, retry_needed=False, substitutions_made=subs)

    def build_retry_prompt(
        self,
        original_prompt: str,
        reason: str,
        must_reveal_info: str | None = None,
    ) -> str:
        """Build a retry prompt when must_reveal_info was missing or language drifted."""
        if must_reveal_info:
            prefix = (
                f"WAŻNE: Twoja poprzednia odpowiedź nie zawierała wymaganej informacji.\n"
                f'NPC KONIECZNIE musi wspomnieć: "{must_reveal_info}"\n'
                f"Przepisz odpowiedź uwzględniając tę informację.\n\n"
            )
        elif reason == "language":
            prefix = "WAŻNE: Odpowiedz WYŁĄCZNIE po polsku.\n\n"
        else:
            prefix = "WAŻNE: Poprzednia odpowiedź była nieprawidłowa. Spróbuj ponownie.\n\n"
        return prefix + original_prompt

    # ── Block builders ─────────────────────────────────────────────────────

    # Stage 9 P2 — Continuity injection.
    # Gap threshold: 30 min (matches XS15 session.start_bonus, SESSION_GAP_MINUTES).
    # Idempotency: session_flags["continuity_injected_at_turn"] tracks the last
    # turn_number we injected for, so we don't re-inject within the same session window.
    _CONTINUITY_GAP_MINUTES = 30

    def _build_continuity_block(self, campaign_id: int, session_flags: dict) -> str:
        try:
            from datetime import datetime, timezone
            # Find the timestamp of the most recent narrative turn.
            row = self.conn.execute(
                """
                SELECT id, turn_number, created_at FROM campaign_turns
                WHERE campaign_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()
            if not row:
                return ""  # no prior turns to bridge from
            last_turn_number = int(row["turn_number"] or 0)
            try:
                last_ts = datetime.fromisoformat(str(row["created_at"]).replace(" ", "T"))
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                gap_min = (datetime.now(timezone.utc) - last_ts).total_seconds() / 60
            except Exception:
                return ""
            if gap_min < self._CONTINUITY_GAP_MINUTES:
                return ""
            # One-shot per gap: don't re-inject within the same session window.
            last_injected = int(session_flags.get("continuity_injected_at_turn") or 0)
            if last_injected == last_turn_number:
                return ""

            # Fetch the player_summary (never gm_summary — gracz nie widzi GM notes).
            from app.services.history_summary_service import (
                SUMMARY_AUDIENCE_PLAYER,
                fetch_latest_saved_summary,
            )
            row_s = fetch_latest_saved_summary(
                self.conn, campaign_id, audience=SUMMARY_AUDIENCE_PLAYER
            )
            text = ((row_s or {}).get("summary_text") or "").strip()
            if not text:
                return ""  # silent skip if no summary exists yet

            # Mark as injected so the next turn in this session doesn't re-prepend.
            try:
                flags = dict(session_flags)
                flags["continuity_injected_at_turn"] = last_turn_number
                import json
                self.conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                    (json.dumps(flags, ensure_ascii=False), str(campaign_id)),
                )
                self.conn.commit()
            except Exception as e:
                logger.warning("continuity_flag_write_failed", error=str(e))

            return (
                f"=== TWOJA PRZYGODA DOTYCHCZAS ===\n"
                f"(Po {int(gap_min)} min przerwy — wznowienie sesji. "
                f"Wpleć krótko poniższe wydarzenia w narrację pierwszego akapitu, "
                f"nie cytuj dosłownie.)\n"
                f"{text}"
            )
        except Exception as e:
            logger.warning("continuity_block_failed", error=str(e))
            return ""

    def _build_narrative_state_block(self, session_flags: dict) -> str:
        """D6 (#381) — inject compressed Narrative State (key events + active seeds)
        so the LLM keeps story continuity across many turns."""
        try:
            from app.services.narrative_state_service import format_narrative_state_block
            return format_narrative_state_block(session_flags.get("narrative_state"))
        except Exception as e:
            logger.warning("narrative_state_block_failed", error=str(e))
            return ""

    def _build_hero_chronicle_block(self, character_id: int, campaign_id: int | None = None) -> str:
        """#1096 — inject hero's cross-campaign chronicle so the narrator can reference
        the character's past. Silently returns empty string when no history exists.

        #1100 — when the current region is known, also inject the relevant subset of
        STRUCTURED key decisions (cheaper + precise NPC/region callbacks)."""
        try:
            from app.services.chapter_summary_service import get_hero_chronicle
            region = None
            if campaign_id is not None:
                try:
                    from app.services import reputation_service as rep
                    region = rep.resolve_region(self.conn, campaign_id)
                except Exception:
                    region = None
            return get_hero_chronicle(
                self.conn, character_id, limit=3, relevant_region=region,
            )
        except Exception as e:
            logger.warning("hero_chronicle_block_failed", error=str(e))
            return ""

    def _build_reputation_block(self, character_id: int, campaign_id: int) -> str:
        """#1099/#1103 — inject region + faction reputation standings for narrator.

        Region block always checked. Faction blocks added for any non-neutral
        faction standings the character has accumulated. Empty when all neutral.
        """
        try:
            from app.services import reputation_service as rep
            region = rep.resolve_region(self.conn, campaign_id)
            region_value = rep.get_reputation(self.conn, character_id, region)
            parts = [rep.reputation_context_line(region_value, region)]

            # #1103: inject faction standings (non-neutral only)
            try:
                faction_rows = self.conn.execute(
                    """
                    SELECT cr.scope_key, cr.value, f.name
                    FROM character_reputation cr
                    JOIN game_config_factions f ON f.key = cr.scope_key
                    WHERE cr.character_id = ? AND cr.scope_type = 'faction'
                      AND ABS(cr.value) >= 20
                    ORDER BY ABS(cr.value) DESC
                    LIMIT 3
                    """,
                    (int(character_id),),
                ).fetchall()
                for row in faction_rows:
                    line = rep.faction_context_line(row["value"], row["name"])
                    if line:
                        parts.append(line)
            except Exception:
                pass

            return "\n".join(p for p in parts if p)
        except Exception as e:
            logger.warning("reputation_block_failed", error=str(e))
            return ""

    def _build_world_block(
        self,
        session_flags: dict,
        ingame_hours: int,
        player_message: str = "",
        campaign_id: int | None = None,
    ) -> str:
        """U29 — build rich ŚWIAT block from hex data + DB candidates.

        Falls back to simple location-only block when no hex in session_flags.
        """
        try:
            from app.services.location_context_injector import build_swiat_block
            # #1209 — the narrator must know the player is INSIDE the anchored
            # location; without this the block narrated raw hex terrain.
            _cur_loc_key = self._current_location_key(campaign_id, session_flags) or None
            swiat = build_swiat_block(
                self.conn, session_flags, player_message,
                current_location_key=_cur_loc_key,
            )
            if swiat:
                swiat += f"\nCzas: {_clock_display(ingame_hours)}"
                weather = self._build_weather_line(session_flags, ingame_hours, campaign_id)
                if weather:
                    swiat += f"\n{weather}"
                return swiat
        except Exception as e:
            logger.warning("build_swiat_block_failed", error=str(e))

        # Fallback: simple format when no hex context (pre-U29 behavior)
        session_flags = session_flags or {}
        location_key = self._current_location_key(campaign_id, session_flags)
        location = self._get_location(location_key)
        lines = ["=== ŚWIAT ==="]
        if location:
            lines.append(f"Lokacja: {location.get('label', '?')}")
            loc_type = location.get("location_type") or location.get("type") or ""
            if loc_type:
                lines.append(f"Typ: {loc_type}")
            desc = (location.get("description") or "").strip()
            if desc:
                lines.append(f"Opis: {desc}")
            else:
                logger.debug("context_injector_no_description", location=location.get("key"))
            rules = {}
            try:
                rules = json.loads(location.get("rules") or "{}")
            except (json.JSONDecodeError, TypeError):
                pass
            atmosphere = rules.get("atmosphere", "")
            if atmosphere:
                lines.append(f"Atmosfera: {atmosphere}")
        else:
            lines.append("Lokacja: nieznana")
        lines.append(f"Czas: {_clock_display(ingame_hours)}")
        weather = self._build_weather_line(session_flags, ingame_hours, campaign_id)
        if weather:
            lines.append(weather)
        return "\n".join(lines)

    def _build_weather_line(
        self,
        session_flags: dict,
        ingame_hours: int,
        campaign_id: int | None,
    ) -> str:
        """PT-D3 (#1126) — linia POGODA (pora roku + pogoda opisowa). '' gdy off/brak."""
        if campaign_id is None:
            return ""
        try:
            from app.services import weather_service
            hex_type = None
            cur = (session_flags or {}).get("current_hex") or {}
            q, r = cur.get("q"), cur.get("r")
            if q is not None and r is not None:
                row = self.conn.execute(
                    "SELECT hex_type FROM world_hexes WHERE q=? AND r=? LIMIT 1",
                    (int(q), int(r)),
                ).fetchone()
                if row:
                    hex_type = row["hex_type"] if isinstance(row, sqlite3.Row) else row[0]
            return weather_service.build_weather_line(
                int(campaign_id), int(ingame_hours), hex_type=hex_type, conn=self.conn
            )
        except Exception as e:
            logger.warning("build_weather_line_failed", error=str(e))
            return ""

    _STORY_STALE_THRESHOLD = 12  # #1026: raised from 5 — was triggering too early

    # ── #1038 — Adaptacyjna długość narracji ────────────────────────────────
    # Resolver łączy stan-lokacji (B: turns_at_location) + intencję gracza
    # (C: action_type / słowa-klucze) → jeden poziom → wstrzykuje [DŁUGOŚĆ: ...].
    # Słownik poziomów (A) jest konfigurowalny (strojenie — Numbers Policy #1038).
    _NARRATION_LEVELS = {
        "WALKA":       "2-3 krótkie, dynamiczne zdania akcji (patrz ACTIVE COMBAT)",
        "PEŁNY":       "4-6+ zdań — pełny opis sensoryczny miejsca (widzisz/słyszysz/czujesz)",
        "ŚREDNI":      "3-4 zdania — opisz to, co gracz bada; bez re-opisu całej lokacji",
        "ZWIĘZŁY":     "1-3 zdania — odpowiedz na akcję, NIE opisuj ponownie znanego miejsca",
        "MECHANICZNY": "1-2 zdania — zwięzła reakcja na prostą akcję",
    }
    # Próg "nowa lokacja" (turns_at_location <= próg → PEŁNY). Startowy = 0.
    _NEW_LOCATION_TURNS = 0
    # Akcje czysto mechaniczne → MECHANICZNY.
    _MECHANICAL_ACTIONS = frozenset({"ITEM_PICKUP", "ITEM_USE", "DEATH_SAVE", "FEAR_TEST"})
    # Akcje walki → WALKA (poza sygnałem combat_roster).
    _COMBAT_ACTIONS = frozenset({"ATTACK", "FLEE"})
    # Akcje examine → ŚREDNI.
    _EXAMINE_ACTIONS = frozenset({"EXAMINE", "SEARCH"})
    # Słowa-klucze intencji "rozejrzyj się / zbadaj" (C) — fallback gdy action_type ogólny.
    _EXAMINE_KEYWORDS = (
        "rozejrz", "rozglą", "zbadaj", "badam", "przyjrz", "obejrz", "oglądam",
        "szukam", "przeszuk", "lustruj", "patrzę", "obserwuj",
    )

    def _resolve_narration_length(
        self, session_flags: dict, action_type: str, mechanic_result: dict, player_message: str
    ) -> tuple[str, str]:
        """Resolver długości narracji (#1038). Zwraca (poziom, opis).

        Pierwszeństwo wg macierzy: walka > nowa lokacja > examine > mechaniczne > akcja.
        B = turns_at_location (stan lokacji), C = action_type / słowa-klucze (intencja).
        """
        action = (action_type or "").upper()
        combat_active = bool(session_flags.get("combat_roster")) or action in self._COMBAT_ACTIONS
        if combat_active:
            return "WALKA", self._NARRATION_LEVELS["WALKA"]

        turns = int(session_flags.get("turns_at_location", 0) or 0)
        # B: nowa lokacja / zmiana sceny → PEŁNY (nadpisuje intencję, poza walką).
        if turns <= self._NEW_LOCATION_TURNS or action == "MOVEMENT":
            return "PEŁNY", self._NARRATION_LEVELS["PEŁNY"]

        # Ta sama lokacja — C koryguje bazę.
        msg = (player_message or "").lower()
        examine = action in self._EXAMINE_ACTIONS or any(k in msg for k in self._EXAMINE_KEYWORDS)
        if examine:
            return "ŚREDNI", self._NARRATION_LEVELS["ŚREDNI"]
        if action in self._MECHANICAL_ACTIONS:
            return "MECHANICZNY", self._NARRATION_LEVELS["MECHANICZNY"]
        return "ZWIĘZŁY", self._NARRATION_LEVELS["ZWIĘZŁY"]

    def _build_length_directive_block(
        self, session_flags: dict, action_type: str, mechanic_result: dict, player_message: str
    ) -> str:
        """Wstrzykuje deterministyczną dyrektywę długości do kontekstu narratora (#1038)."""
        level, desc = self._resolve_narration_length(
            session_flags, action_type, mechanic_result, player_message
        )
        return f"[DŁUGOŚĆ: {level} — {desc}]"

    def _build_stale_block(self, session_flags: dict) -> str:
        turns = session_flags.get("turns_at_location", 0)
        if turns < self._STORY_STALE_THRESHOLD:
            return ""
        return f"[STORY_STALE: {turns} tur bez ruchu — zasugeruj bohaterowi opuszczenie lokacji]"

    def _build_entities_block(self, npcs: list[dict], combat_roster: list[dict]) -> str:
        lines = ["=== POSTACIE NA SCENIE ==="]
        has_content = False

        for npc in npcs:
            name = npc.get("label") or npc.get("name") or npc.get("key", "?")
            attitude = npc.get("attitude") or npc.get("npc_type") or "neutralny"
            lines.append(f"NPC: {name} [{attitude}]")
            personality = (npc.get("personality_prompt") or "").strip()
            if personality:
                truncated = personality[:MAX_PERSONALITY_PROMPT_LEN]
                lines.append(f"Osobowość: {truncated}")
            has_content = True

        if combat_roster:
            lines.append("WROGOWIE W WALCE:")
            for enemy in combat_roster:
                hp = enemy.get("hp", "?")
                hp_max = enemy.get("hp_max", "?")
                name = enemy.get("name") or enemy.get("key", "?")
                tier = enemy.get("tier", "")
                status = "żywy" if (isinstance(hp, (int, float)) and hp > 0) else "martwy"
                tier_str = f"Tier: {tier}, " if tier else ""
                lines.append(f"- {name} ({tier_str}HP: {hp}/{hp_max}) [{status}]")
            has_content = True

        if not has_content:
            lines.append("Brak postaci w tej lokacji.")

        return "\n".join(lines)

    def _build_plan_enemy_keys_block(self, campaign_id: int) -> str:
        """#1284 — surface this campaign's plan-specific enemy keys to the narrator.

        Thin wrapper over the standalone `build_plan_enemy_keys_block` so the same
        block can be reused by the multiplayer narrator (#1296), which does not go
        through this injector.
        """
        return build_plan_enemy_keys_block(self.conn, campaign_id)

    def _build_content_index_block(self, mechanic_result: dict) -> str:
        """Stage 2B-Schema S14: surface AVAILABLE CONTENT + nearby places to the narrator."""
        return (mechanic_result.get("available_content_index") or "").strip()

    def _build_mechanic_block(self, action_type: str, result: dict) -> str:
        builders = {
            "ATTACK":         self._mechanic_attack,
            "FLEE":           self._mechanic_flee,
            "DIALOGUE":       self._mechanic_dialogue,
            "MOVEMENT":       self._mechanic_movement,
            "SEARCH":         self._mechanic_search,
            "REST":           self._mechanic_rest,
            "EXAMINE":        self._mechanic_examine,
            "SKILL_ATTEMPT":  self._mechanic_skill,
            "STEALTH_ATTEMPT":self._mechanic_stealth,
            "ITEM_USE":       self._mechanic_item_use,
            "ITEM_PICKUP":    self._mechanic_item_pickup,
            "FEAR_TEST":      self._mechanic_fear_test,
            "DEATH_SAVE":     self._mechanic_death_save,
        }
        builder = builders.get(action_type, self._mechanic_generic)
        return builder(result)

    def _mechanic_attack(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: ATAK"]
        lines.append(f"Cel: {r.get('target_name', r.get('target', '?'))}")
        roll, mod, total, dc = r.get("roll","?"), r.get("modifier","?"), r.get("total","?"), r.get("dc","?")
        lines.append(f"Rzut: {roll} + {mod} = {total} vs DC {dc}")
        outcome = "TRAFIENIE KRYTYCZNE" if r.get("crit") else ("TRAFIENIE" if r.get("hit") else "PUDŁO")
        lines.append(f"Wynik: {outcome}")
        if r.get("hit"):
            dmg = r.get("damage", "?")
            hp_b, hp_a = r.get("target_hp_before","?"), r.get("target_hp_after","?")
            tname = r.get("target_name", r.get("target","cel"))
            lines.append(f"Obrażenia: {dmg} → {tname} HP: {hp_b} → {hp_a}")
            if r.get("target_dead") or (isinstance(hp_a, (int,float)) and hp_a <= 0):
                lines.append(f"{tname} GINIE.")
        if r.get("crit"):
            loc = r.get("hit_location", "")
            lines.append(f"KRYTYK: podwójne obrażenia." + (f" Trafiony w: {loc}." if loc else ""))
        return "\n".join(lines)

    def _mechanic_flee(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: UCIECZKA"]
        roll, mod, total = r.get("roll","?"), r.get("modifier","?"), r.get("total","?")
        enemy_total = r.get("enemy_total", "?")
        lines.append(f"Rzut DEX: {roll} + {mod} = {total} vs {enemy_total}")
        success = r.get("success", r.get("fled", False))
        lines.append(f"Wynik: {'UCIECZKA UDANA' if success else 'UCIECZKA NIEUDANA'}")
        if not success:
            opp = r.get("opportunity_damage")
            if opp:
                lines.append(f"Atak okazji: {r.get('enemy_name','wróg')} zadaje {opp} obrażeń.")
        if success:
            new_loc = r.get("new_location_name")
            if new_loc:
                lines.append(f"Nowa lokacja: {new_loc}")
        return "\n".join(lines)

    def _mechanic_dialogue(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: ROZMOWA"]
        lines.append(f"NPC: {r.get('npc_name', r.get('npc_key','?'))}")
        topic = r.get("topic") or "powitanie"
        lines.append(f"Temat: {topic}")
        must_reveal = r.get("must_reveal_info")
        if must_reveal:
            lines.append(f'NPC MUSI POWIEDZIEĆ (naturalnie, w kontekście): "{must_reveal}"')
        if r.get("secret_roll"):
            roll, mod, total, dc = r.get("roll","?"), r.get("modifier","?"), r.get("total","?"), r.get("dc","?")
            lines.append(f"Rzut Perswazji: {roll} + {mod} = {total} vs DC {dc}")
            success = r.get("success", False)
            lines.append(f"Wynik: {'SUKCES' if success else 'PORAŻKA'}")
            if not success:
                lines.append("Sekret NIE zostaje ujawniony. NPC zmienia temat.")
        return "\n".join(lines)

    def _mechanic_movement(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: RUCH"]
        lines.append(f"Z: {r.get('from_location_name', r.get('from','?'))}")
        lines.append(f"Do: {r.get('to_location_name', r.get('to','?'))}")
        encounter = r.get("encounter_triggered")
        if encounter:
            lines.append("SPOTKANIE NA DRODZE: wrogowie pojawiają się na ścieżce.")
        return "\n".join(lines)

    def _mechanic_search(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ==="]
        focus = r.get("focus") or "ogólne"
        lines.append(f"Akcja: PRZESZUKIWANIE (fokus: {focus})")
        roll, mod, total, dc = r.get("roll","?"), r.get("modifier","?"), r.get("total","?"), r.get("dc","?")
        lines.append(f"Rzut: {roll} + {mod} = {total} vs DC {dc}")
        success = r.get("success", False)
        lines.append(f"Wynik: {'SUKCES' if success else 'PORAŻKA'}")
        if success:
            found = r.get("found", [])
            lines.append(f"Znalezione: {', '.join(found) if found else 'nic wyjątkowego'}")
        else:
            lines.append("Nic szczególnego nie znaleziono.")
        return "\n".join(lines)

    def _mechanic_rest(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ==="]
        rest_type = r.get("rest_type", "krótki")
        lines.append(f"Akcja: ODPOCZYNEK ({rest_type})")
        status = r.get("status", "W TRAKCIE").upper()
        lines.append(f"Status: {status}")
        if status == "ZAKOŃCZONY":
            hp_b, hp_a = r.get("hp_before","?"), r.get("hp_after","?")
            lines.append(f"HP przywrócone: {hp_b} → {hp_a}")
            cleared = r.get("cleared_conditions") or []
            lines.append(f"Usunięte stany: {', '.join(cleared) if cleared else 'brak'}")
        elif status == "PRZERWANY":
            lines.append("Odpoczynek przerwany! Wrogowie atakują.")
        return "\n".join(lines)

    def _mechanic_examine(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: ZBADANIE"]
        target = r.get("target_name") or r.get("target", "?")
        lines.append(f"Cel: {target}")
        db_data = r.get("target_description") or r.get("db_description") or "brak danych w bazie"
        lines.append(f"Dane z bazy: {db_data}")
        return "\n".join(lines)

    def _mechanic_skill(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ==="]
        skill = r.get("skill_name") or r.get("skill_key", "?")
        lines.append(f"Akcja: TEST UMIEJĘTNOŚCI ({skill})")
        roll, mod, total, dc = r.get("roll","?"), r.get("modifier","?"), r.get("total","?"), r.get("dc","?")
        lines.append(f"Rzut: {roll} + {mod} = {total} vs DC {dc}")
        success = r.get("success", False)
        lines.append(f"Wynik: {'SUKCES' if success else 'PORAŻKA'}")
        consequence = r.get("consequence") or r.get("consequence_text", "")
        if consequence:
            lines.append(f"Konsekwencja: {consequence}")
        return "\n".join(lines)

    def _mechanic_stealth(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: SKRADANIE"]
        roll, mod, total, dc = r.get("roll","?"), r.get("modifier","?"), r.get("total","?"), r.get("dc","?")
        lines.append(f"Rzut Skradania: {roll} + {mod} = {total} vs DC {dc}")
        success = r.get("success", False)
        lines.append(f"Wynik: {'UKRYTY/A — nie wykryty/a' if success else 'WYKRYTY/A'}")
        return "\n".join(lines)

    def _mechanic_item_use(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: UŻYCIE PRZEDMIOTU"]
        lines.append(f"Przedmiot: {r.get('item_name', r.get('item_key','?'))}")
        effect = r.get("effect_description", "")
        if effect:
            lines.append(f"Efekt: {effect}")
        hp_change = r.get("hp_change")
        if hp_change:
            lines.append(f"HP: {r.get('hp_before','?')} → {r.get('hp_after','?')}")
        return "\n".join(lines)

    def _mechanic_item_pickup(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: PODNIESIENIE PRZEDMIOTU"]
        lines.append(f"Przedmiot: {r.get('item_name', r.get('item_key','?'))}")
        lines.append("Przedmiot dodany do ekwipunku.")
        return "\n".join(lines)

    def _mechanic_fear_test(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: TEST STRACHU"]
        source = r.get("source", "nieznane źródło")
        lines.append(f"Źródło: {source}")
        roll, mod, total, dc = r.get("roll","?"), r.get("modifier","?"), r.get("total","?"), r.get("dc","?")
        lines.append(f"Rzut WIS: {roll} + {mod} = {total} vs DC {dc}")
        success = r.get("success", False)
        lines.append(f"Wynik: {'SUKCES — opanowany/a' if success else 'PORAŻKA'}")
        if not success:
            cond = r.get("condition_applied", "")
            if cond:
                label = _FEAR_LABELS.get(cond, cond)
                lines.append(f"Zastosowany stan: {label}")
        return "\n".join(lines)

    def _mechanic_death_save(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ===", "Akcja: RZUT NA ŚMIERĆ"]
        roll, dc = r.get("roll","?"), r.get("dc","?")
        lines.append(f"Rzut: {roll} vs DC {dc}")
        success = r.get("success", False)
        nat20, nat1 = r.get("nat_20", False), r.get("nat_1", False)
        if nat20:
            lines.append("Wynik: NAT 20 — PRZEŻYŁ/A CUDEM (1 HP)")
        elif success:
            lines.append("Wynik: SUKCES — trzyma się życia")
        elif nat1:
            lines.append("Wynik: NAT 1 — 2 PORAŻKI (krytyczna klęska)")
        else:
            lines.append("Wynik: PORAŻKA")
        successes, failures = r.get("successes", "?"), r.get("failures", "?")
        lines.append(f"Postęp: {successes} sukcesu / {failures} porażki")
        return "\n".join(lines)

    def _mechanic_generic(self, r: dict) -> str:
        lines = ["=== WYNIK MECHANICZNY ==="]
        action = r.get("action_type", "AKCJA")
        lines.append(f"Akcja: {action}")
        outcome = r.get("outcome") or r.get("result", "")
        if outcome:
            lines.append(f"Wynik: {outcome}")
        return "\n".join(lines)

    def _build_character_state_block(self, character: dict | None, conditions: list[dict]) -> str:
        lines = ["=== STAN POSTACI ==="]
        if character:
            sheet = {}
            try:
                sheet = json.loads(character.get("sheet_json") or "{}")
            except (json.JSONDecodeError, TypeError):
                pass
            name = character.get("name") or character.get("imie", "Bohater")
            lines.append(f"Postać: {name}")
            hp = sheet.get("current_hp", character.get("current_hp", 0))
            max_hp = sheet.get("max_hp", character.get("max_hp", 1))
            wound = _wound_label(hp, max_hp)
            lines.append(f"Stan zdrowia: {wound}")
        else:
            lines.append("Postać: nieznana")
            lines.append("Stan zdrowia: nieznany")

        # Separate fear from other conditions
        fear_label = None
        other_conditions = []
        for cond in conditions:
            ctype = cond.get("condition_type", "")
            if ctype in _FEAR_LABELS:
                fear_label = _FEAR_LABELS[ctype]
            else:
                # S8 (#603): preferuj label+opis z katalogu; fallback do surowego klucza.
                label = cond.get("catalog_label") or ctype
                desc = cond.get("catalog_description")
                other_conditions.append(f"{label} — {desc}" if desc else label)

        lines.append(f"Aktywne stany: {', '.join(other_conditions) if other_conditions else 'brak'}")
        if fear_label:
            lines.append(f"Strach: {fear_label}")

        # PT-D1 (#1124): zmęczenie z podróży (sheet.conditions). Przy 3 stackach narrator
        # dostaje jawny fakt o skrajnym wyczerpaniu (chip pokazuje się osobno na karcie).
        try:
            from app.services.fatigue_service import read_fatigue_level
            fatigue = read_fatigue_level(sheet.get("conditions") or []) if character else 0
            if fatigue >= 3:
                lines.append("Zmęczenie: SKRAJNE WYCZERPANIE — postać ledwo trzyma się na nogach; "
                             "opisz ociężałość, drżące ręce i tępy umysł (nie wymyślaj skutków mechanicznych).")
            elif fatigue == 2:
                lines.append("Zmęczenie: mocno zmęczona — ruchy wolniejsze, uwaga rozproszona.")
            elif fatigue == 1:
                lines.append("Zmęczenie: lekko zmęczona po długim marszu.")
        except Exception:
            pass

        return "\n".join(lines)

    def _build_loch_block(self, session_flags: dict) -> str:
        """L3 (Decision 3) — inject dungeon tile context for the LLM narrator.

        When the active dungeon_run is v2 (tile graph), provide the current tile's
        room_description and door_hints. LLM must colorize 1–2 sentences only — no
        inventing new facts.
        """
        run = (session_flags or {}).get("dungeon_run") or {}
        if run.get("system") != "tiles_v2":
            return ""

        graph = run.get("graph") or {}
        nodes = graph.get("nodes") or {}
        positions = run.get("positions") or {}

        # Find the current node for the first character position
        current_node_id = next(iter(positions.values()), None) or graph.get("entry_node")
        if not current_node_id:
            return ""

        node = nodes.get(current_node_id) or {}
        content = node.get("content") or {}
        room_description = content.get("room_description") or ""
        if not room_description:
            return ""

        door_hints = node.get("door_hints") or {}
        open_doors = node.get("doors_open") or {}
        hints_parts = [
            f"{d}: {door_hints[d]}"
            for d in ("N", "S", "E", "W")
            if open_doors.get(d) and door_hints.get(d)
        ]
        hints_str = ", ".join(hints_parts) if hints_parts else "brak otwartych drzwi"

        return (
            "[LOCH]\n"
            f"Opis pomieszczenia: {room_description}\n"
            f"Drzwi: {hints_str}\n"
            "Instrukcja: Koloryzuj opis 1–2 zdaniami klimatycznie. "
            "Nie wymyślaj nowych faktów. Nie zmieniaj opisu pomieszczenia.\n"
            "[/LOCH]"
        )

    def _build_tone_block(self, tone: str) -> str:
        return f"=== TON KAMPANII ===\n{tone}"

    # ── DB helpers ─────────────────────────────────────────────────────────

    def _get_location(self, key: str) -> dict | None:
        if not key:
            return None
        row = self.conn.execute(
            "SELECT key, label, description, location_type, rules, safe_for_rest FROM game_locations WHERE key = ?",
            (key,)
        ).fetchone()
        return dict(row) if row else None

    def _get_npcs_in_location(self, location_key: str) -> list[dict]:
        if not location_key:
            return []
        # V2 join table
        rows = self.conn.execute(
            """SELECT n.key, n.label, n.npc_type, n.personality_prompt
               FROM location_npc_assignments lna
               JOIN npcs n ON n.key = lna.npc_key
               WHERE lna.location_key = ? AND lna.is_active = 1 AND n.is_active = 1""",
            (location_key,)
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]
        # Fallback: old npc_keys JSON on game_locations
        loc_row = self.conn.execute(
            "SELECT npc_keys FROM game_locations WHERE key = ?", (location_key,)
        ).fetchone()
        if not loc_row or not loc_row[0]:
            return []
        try:
            keys = json.loads(loc_row[0])
        except (json.JSONDecodeError, TypeError):
            return []
        result = []
        for npc_key in keys:
            row = self.conn.execute(
                "SELECT key, label, npc_type, personality_prompt FROM npcs WHERE key = ? AND is_active = 1",
                (npc_key,)
            ).fetchone()
            if row:
                result.append(dict(row))
        return result

    def _get_character(self, character_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, name, sheet_json FROM characters WHERE id = ?",
            (character_id,)
        ).fetchone()
        return dict(row) if row else None

    def _get_active_conditions(self, character_id: int) -> list[dict]:
        try:
            rows = self.conn.execute(
                """SELECT condition_type, severity, expires_at
                   FROM character_conditions
                   WHERE character_id = ?
                   AND (expires_at IS NULL OR CAST(expires_at AS INTEGER) > 0)""",
                (character_id,)
            ).fetchall()
        except Exception:
            return []
        conds = [dict(r) for r in rows]
        # S8 (#603): wzbogać o label+description z katalogu game_config_conditions
        # (narrator dostaje opis stanu z bazy, nie hard-coded jak _FEAR_LABELS).
        try:
            catalog = {
                str(r["key"]): (r["label"], r["description"])
                for r in self.conn.execute(
                    "SELECT key, label, description FROM game_config_conditions WHERE is_active = 1"
                ).fetchall()
            }
        except Exception:
            catalog = {}
        for c in conds:
            meta = catalog.get(str(c.get("condition_type") or ""))
            if meta:
                c["catalog_label"] = meta[0]
                c["catalog_description"] = meta[1]
        return conds

    def _get_campaign_tone(self, campaign_id: int) -> str:
        row = self.conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,)
        ).fetchone()
        if row and row[0]:
            try:
                plan = json.loads(row[0])
                tone = plan.get("tone_descriptor") or plan.get("campaign_tone", "")
                if tone:
                    return tone
            except (json.JSONDecodeError, TypeError):
                pass
        return DEFAULT_TONE

    # ── Post-processing helpers ────────────────────────────────────────────

    @staticmethod
    def _fuzzy_check_info(response: str, must_reveal: str) -> bool:
        """Check if key words from must_reveal appear in the narrator response."""
        response_lower = response.lower()
        # Extract words longer than 3 chars as key terms
        words = [w.lower() for w in re.findall(r'\b\w{4,}\b', must_reveal)]
        if not words:
            return True
        # Require at least 2 key words (or all if fewer than 2)
        required = max(1, min(2, len(words)))
        found = sum(1 for w in words if w in response_lower)
        return found >= required

    def _build_whitelist(self, session_flags: dict) -> set[str]:
        """Build a set of known proper nouns that the narrator is allowed to use."""
        whitelist = set(_POLISH_WHITELIST)
        # Add NPC names from entities block
        location_key = self._current_location_key(None, session_flags)
        for npc in self._get_npcs_in_location(location_key):
            name = npc.get("label") or npc.get("name") or ""
            for word in name.split():
                whitelist.add(word.lower())
        # Add enemy names from combat roster
        for enemy in session_flags.get("combat_roster", []):
            name = enemy.get("name") or ""
            for word in name.split():
                whitelist.add(word.lower())
        return whitelist

    @staticmethod
    def _strip_invented_nouns(text: str, whitelist: set[str]) -> tuple[str, int]:
        """
        Light heuristic: replace mid-sentence capitalized words not in whitelist.
        Returns (processed_text, substitution_count).
        """
        # Find capitalized words that are NOT at sentence start
        # Pattern: a lowercase word or punctuation, then a space, then Capitalized word
        pattern = re.compile(r'(?<=[a-ząćęłńóśźż,;]\s)([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,})')
        substitutions = 0

        def maybe_replace(m):
            nonlocal substitutions
            word = m.group(1)
            if word.lower() not in whitelist:
                substitutions += 1
                logger.debug("context_injector_noun_substituted", original=word)
                return "tajemnicza postać"
            return word

        processed = pattern.sub(maybe_replace, text)
        return processed, substitutions

    @staticmethod
    def _is_non_polish(text: str) -> bool:
        """
        Detect if response appears entirely non-Polish.
        Only flags when there are ZERO Polish diacritics in a response of 5+ words.
        This avoids false positives — many valid Polish words have no diacritics.
        """
        words = re.findall(r'\b[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+\b', text)
        if len(words) < 5:
            return False
        # If any Polish special character exists, assume Polish
        return not bool(re.search(r'[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', text))

    def _trim_prompt(self, blocks: list[str], npcs: list[dict],
                     roster: list[dict], tone: str) -> str:
        """Trim prompt if over token budget. Never trim mechanic block or constraints."""
        # blocks = [world, entities, mechanic, char_state, tone, constraints]
        # Trim strategy: reduce entities to only alive combatants, keep NPCs minimal
        if len(roster) > 1:
            alive = [e for e in roster if e.get("hp", 1) > 0]
            blocks[1] = self._build_entities_block(npcs[:1], alive)
        if len(blocks) >= 1 and len(blocks[0]) > 300:
            # Truncate world description
            lines = blocks[0].split("\n")
            blocks[0] = "\n".join(lines[:5])
        prompt = "\n\n".join(b for b in blocks if b)
        return prompt


# ── Module-level convenience function ──────────────────────────────────────

def build_narrator_prompt(
    conn: sqlite3.Connection,
    session_flags: dict,
    mechanic_result: dict,
    action_type: str,
    character_id: int,
    campaign_id: int,
) -> str:
    """Convenience wrapper for use in game_engine.py."""
    return ContextInjector(conn).build(
        session_flags=session_flags,
        mechanic_result=mechanic_result,
        action_type=action_type,
        character_id=character_id,
        campaign_id=campaign_id,
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _wound_label(hp: int | float, max_hp: int | float) -> str:
    if max_hp <= 0:
        return "Stan zdrowia nieznany"
    pct = (hp / max_hp) * 100
    for threshold, label in _WOUND_LABELS:
        if pct >= threshold:
            return label
    return "Na skraju śmierci — ledwo oddycha"


def _time_of_day(ingame_hours: int) -> str:
    hour = ingame_hours % 24
    if 5 <= hour < 9:
        return "świt"
    if 9 <= hour < 13:
        return "rano"
    if 13 <= hour < 17:
        return "południe"
    if 17 <= hour < 20:
        return "popołudnie"
    if 20 <= hour < 23:
        return "zmierzch"
    return "noc"


def _clock_display(ingame_hours: int) -> str:
    """Full clock string injected into narrator context: 'Dzień 3, 09:00 (rano)'."""
    h = int(ingame_hours)
    day = (h // 24) + 1
    hour = h % 24
    return f"Dzień {day}, {hour:02d}:00 ({_time_of_day(h)})"
