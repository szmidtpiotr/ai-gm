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

# Fear condition → label
_FEAR_LABELS = {
    "fear_shaken":    "Zdenerwowany/a — lekki niepokój",
    "fear_frightened":"Przestraszony/a — trudno skupić myśli",
    "terror":         "Opanowany/a przez terror — ciało nie słucha",
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

    def build(
        self,
        session_flags: dict,
        mechanic_result: dict,
        action_type: str,
        character_id: int,
        campaign_id: int,
    ) -> str:
        """
        Build the complete narrator prompt string.

        Args:
            session_flags: Current session state (includes location_key, combat_roster, etc.)
            mechanic_result: Resolved mechanical outcome from resolver
            action_type: The action that was resolved (e.g. "ATTACK", "DIALOGUE")
            character_id: Active character
            campaign_id: Active campaign

        Returns:
            Complete prompt string to pass to LLM narrator.
        """
        location_key = session_flags.get("current_location_key") or ""

        # Load required data
        location = self._get_location(location_key)
        character = self._get_character(character_id)
        npcs = self._get_npcs_in_location(location_key)
        combat_roster = session_flags.get("combat_roster", [])
        active_conditions = self._get_active_conditions(character_id)
        ingame_hours = session_flags.get("ingame_hours", 9)
        tone = self._get_campaign_tone(campaign_id)

        # Build blocks
        blocks = [
            self._build_world_block(location, ingame_hours),
            self._build_entities_block(npcs, combat_roster),
            self._build_mechanic_block(action_type, mechanic_result),
            self._build_character_state_block(character, active_conditions),
            self._build_tone_block(tone),
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
        location_key = session_flags.get("current_location_key", "")
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

    def _build_world_block(self, location: dict | None, ingame_hours: int) -> str:
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
            # Atmosphere from rules JSON if present
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

        lines.append(f"Pora: {_time_of_day(ingame_hours)}")
        return "\n".join(lines)

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
                other_conditions.append(ctype)

        lines.append(f"Aktywne stany: {', '.join(other_conditions) if other_conditions else 'brak'}")
        if fear_label:
            lines.append(f"Strach: {fear_label}")

        return "\n".join(lines)

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
        return [dict(r) for r in rows]

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
        location_key = session_flags.get("current_location_key", "")
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
