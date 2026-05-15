"""
World State Machine — V2 Phase 01 Task 03

Validates ACTION tags from the Intent Parser and routes them to the
correct resolver. Pure Python — no LLM calls. All blocked actions
return a Polish system message that is sent directly to the player
without narrator involvement.

Usage in game_engine.py:
    from app.services.world_state_machine import WorldStateMachine, WSMResult
    wsm = WorldStateMachine(conn)
    result = wsm.validate_and_route(session_flags, action_type, params,
                                     character_id, campaign_id)
"""

from __future__ import annotations

import json
import sqlite3
import structlog
from dataclasses import dataclass, field

logger = structlog.get_logger()

# ── Valid game states ──────────────────────────────────────────────────────

VALID_STATES = {
    "NARRATIVE",
    "COMBAT",
    "SKILL_TEST_PENDING",
    "DEATH_SAVE_PENDING",
    "FEAR_TEST_PENDING",
    "SHOPPING",
    "RESTING",
}

# ── Result types ───────────────────────────────────────────────────────────

@dataclass
class WSMResult:
    valid: bool
    blocked_message: str | None = None   # Polish system message if blocked
    resolver_key: str | None = None       # e.g. "combat_resolver"
    new_state: str | None = None          # state to transition to
    state_flags_update: dict = field(default_factory=dict)

    @classmethod
    def blocked(cls, message: str) -> "WSMResult":
        return cls(valid=False, blocked_message=message)

    @classmethod
    def routed(cls, resolver: str, new_state: str | None = None,
               flags: dict | None = None, flags_update: dict | None = None) -> "WSMResult":
        return cls(valid=True, resolver_key=resolver, new_state=new_state,
                   state_flags_update=flags or flags_update or {})


# ── State-level action permission table ───────────────────────────────────
# Maps (state, action_type) → blocking message or None (allowed)

_STATE_BLOCKS: dict[str, dict[str, str]] = {
    "COMBAT": {
        "DIALOGUE":    "Nie możesz rozmawiać podczas walki.",
        "MOVEMENT":    "Nie możesz się swobodnie poruszać podczas walki. Użyj Uciekaj.",
        "SEARCH":      "Nie czas na przeszukiwanie podczas walki.",
        "ITEM_PICKUP": "Nie możesz zbierać przedmiotów podczas walki.",
        "REST":        "Nie możesz odpoczywać podczas walki.",
        "EXAMINE":     "Nie czas na to podczas walki.",
        "SHOP":        "Nie możesz handlować podczas walki.",
    },
    "SHOPPING": {
        "ATTACK":          "Jesteś w trakcie handlu. Najpierw zakończ transakcję.",
        "FLEE":            "Jesteś w trakcie handlu. Najpierw zakończ transakcję.",
        "DIALOGUE":        "Jesteś w trakcie handlu. Zakończ lub kup/sprzedaj przedmiot.",
        "MOVEMENT":        "Jesteś w trakcie handlu. Najpierw zakończ transakcję.",
        "SEARCH":          "Jesteś w trakcie handlu.",
        "ITEM_PICKUP":     "Jesteś w trakcie handlu.",
        "REST":            "Jesteś w trakcie handlu. Najpierw zakończ transakcję.",
        "EXAMINE":         "Jesteś w trakcie handlu.",
        "SKILL_ATTEMPT":   "Jesteś w trakcie handlu.",
    },
    "RESTING": {
        "DIALOGUE":    "Odpoczywasz. Poczekaj chwilę.",
        "MOVEMENT":    "Odpoczywasz. Poczekaj chwilę.",
        "SEARCH":      "Odpoczywasz. Poczekaj chwilę.",
        "ITEM_PICKUP": "Odpoczywasz. Poczekaj chwilę.",
        "EXAMINE":     "Odpoczywasz. Poczekaj chwilę.",
        "SHOP":        "Odpoczywasz. Poczekaj chwilę.",
        "SKILL_ATTEMPT": "Odpoczywasz. Poczekaj chwilę.",
    },
    "NARRATIVE": {
        "FLEE": "Nie ma z czego uciekać.",
    },
}

# ── Resolver routing table ────────────────────────────────────────────────
# Maps (state, action_type) → (resolver_key, new_state_or_None)

_ROUTES: dict[tuple[str, str], tuple[str, str | None]] = {
    ("NARRATIVE", "ATTACK"):          ("combat_resolver", "COMBAT"),
    ("NARRATIVE", "STEALTH_ATTEMPT"): ("stealth_resolver", None),
    ("NARRATIVE", "DIALOGUE"):        ("dialogue_resolver", None),
    ("NARRATIVE", "MOVEMENT"):        ("movement_resolver", None),
    ("NARRATIVE", "SEARCH"):          ("search_resolver", None),
    ("NARRATIVE", "ITEM_USE"):        ("item_resolver", None),
    ("NARRATIVE", "ITEM_PICKUP"):     ("item_resolver", None),
    ("NARRATIVE", "REST"):            ("rest_resolver", "RESTING"),
    ("NARRATIVE", "EXAMINE"):         ("examine_resolver", None),
    ("NARRATIVE", "SKILL_ATTEMPT"):   ("skill_resolver", None),
    ("NARRATIVE", "SHOP"):            ("shop_resolver", "SHOPPING"),

    ("COMBAT", "ATTACK"):             ("combat_resolver", None),
    ("COMBAT", "FLEE"):               ("flee_resolver", None),   # new_state set by resolver
    ("COMBAT", "STEALTH_ATTEMPT"):    ("combat_stealth_resolver", None),
    ("COMBAT", "ITEM_USE"):           ("item_resolver", None),
    ("COMBAT", "SKILL_ATTEMPT"):      ("skill_resolver", None),

    ("SHOPPING", "SHOP"):             ("shop_resolver", "NARRATIVE"),  # leave shop

    ("RESTING", "ATTACK"):            ("combat_resolver", "COMBAT"),   # rest interrupted

    ("SKILL_TEST_PENDING", "SKILL_ATTEMPT"): ("skill_resolver", None),

    ("FEAR_TEST_PENDING", "SKILL_ATTEMPT"):  ("fear_resolver", None),

    ("DEATH_SAVE_PENDING", "SKILL_ATTEMPT"): ("death_save_resolver", None),
}

# For pending states, any action auto-resolves the pending test
_PENDING_AUTO_RESOLVERS: dict[str, str] = {
    "SKILL_TEST_PENDING": "skill_resolver",
    "FEAR_TEST_PENDING":  "fear_resolver",
    "DEATH_SAVE_PENDING": "death_save_resolver",
}


# ── Main WSM class ─────────────────────────────────────────────────────────

class WorldStateMachine:
    """
    Validates ACTION tags and routes them to the correct resolver.
    Instantiate with a DB connection for each request.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── Public interface ───────────────────────────────────────────────────

    def validate_and_route(
        self,
        session_flags: dict,
        action_type: str,
        params: dict[str, str],
        character_id: int,
        campaign_id: int,
    ) -> WSMResult:
        """
        Main entry point. Four-step pipeline:
          1. Pending-state intercept (auto-resolve DEATH_SAVE/FEAR/SKILL_TEST)
          2. State-level permission check
          3. Action-specific validator — returns blocked message or None (valid)
          4. Route to resolver via _ROUTES table + _get_route_flags for extra state

        Returns:
            WSMResult — valid=True with resolver_key, or valid=False with blocked_message
        """
        state = self._get_state(session_flags)

        # ── 1. Pending-state intercept ────────────────────────────────────
        if state in _PENDING_AUTO_RESOLVERS and action_type not in ("SKILL_ATTEMPT",):
            return self._handle_pending_intercept(state, session_flags)

        # ── 2. State-level permission block ───────────────────────────────
        state_block = _STATE_BLOCKS.get(state, {}).get(action_type)
        if state_block:
            return WSMResult.blocked(state_block)

        # ── 3. Action-specific validation ────────────────────────────────
        #    Validators return WSMResult.blocked(msg) on fail, or None on success.
        block = self._run_validator(action_type, state, session_flags, params, character_id, campaign_id)
        if block is not None:
            return block

        # ── 4. Route via table ────────────────────────────────────────────
        route = _ROUTES.get((state, action_type))
        if route:
            resolver_key, new_state = route
            extra_flags = self._get_route_flags(action_type, params)
            return WSMResult.routed(resolver_key, new_state, flags=extra_flags or None)

        logger.warning("wsm_unroutable", state=state, action_type=action_type)
        return WSMResult.blocked("Nie można wykonać tej akcji w aktualnym stanie gry.")

    def _run_validator(self, action_type: str, state: str, flags: dict,
                       params: dict, character_id: int, campaign_id: int) -> WSMResult | None:
        """Run action-specific validator. Returns None if valid, WSMResult if blocked."""
        validator = self._get_validator(action_type)
        if not validator:
            return None
        result = validator(flags, params, character_id, campaign_id)
        if not result.valid:
            return result
        return None

    @staticmethod
    def _get_route_flags(action_type: str, params: dict) -> dict:
        """Extra session_flags to store when routing. Only REST needs this."""
        if action_type == "REST":
            rest_type = params.get("rest_type", "short")
            return {
                "rest_type_in_progress": rest_type,
                "rest_turns_remaining": 2 if rest_type == "short" else 5,
            }
        return {}

    def get_state(self, session_flags: dict) -> str:
        return self._get_state(session_flags)

    def transition_state(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        new_state: str,
        flags_update: dict | None = None,
    ) -> None:
        """Apply a state transition and optional session_flags patch."""
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            logger.error("wsm_session_not_found", session_id=session_id)
            return
        flags = json.loads(row[0] or "{}")
        previous = flags.get("state", "NARRATIVE")
        flags["previous_state"] = previous
        flags["state"] = new_state
        if flags_update:
            flags.update(flags_update)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags), session_id)
        )
        conn.commit()
        logger.info("wsm_state_transition", from_state=previous, to_state=new_state)

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _get_state(session_flags: dict) -> str:
        state = session_flags.get("state", "NARRATIVE")
        if state not in VALID_STATES:
            logger.warning("wsm_invalid_state", state=state)
            return "NARRATIVE"
        return state

    def _handle_pending_intercept(self, state: str, session_flags: dict) -> WSMResult:
        """When in a pending state, any non-SKILL_ATTEMPT action auto-triggers the resolver."""
        resolver = _PENDING_AUTO_RESOLVERS[state]
        if state == "DEATH_SAVE_PENDING":
            return WSMResult.blocked(
                "Jesteś nieprzytomny/a. Musisz wykonać rzut na śmierć przed dalszymi akcjami."
            )
        if state == "FEAR_TEST_PENDING":
            return WSMResult.routed(resolver, flags_update={"_auto_resolve_pending": True})
        if state == "SKILL_TEST_PENDING":
            return WSMResult.routed(resolver, flags_update={"_auto_resolve_pending": True})
        return WSMResult.blocked("Musisz najpierw rozwiązać oczekujący test.")

    def _get_validator(self, action_type: str):
        """Return the validator function for an action type, or None."""
        return {
            "ATTACK":         self._validate_attack,
            "FLEE":           self._validate_flee,
            "DIALOGUE":       self._validate_dialogue,
            "MOVEMENT":       self._validate_movement,
            "REST":           self._validate_rest,
            "ITEM_USE":       self._validate_item_use,
            "ITEM_PICKUP":    self._validate_item_pickup,
            "SHOP":           self._validate_shop,
            "SKILL_ATTEMPT":  self._validate_skill_attempt,
        }.get(action_type)

    # ── Per-action validators ──────────────────────────────────────────────

    def _validate_attack(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        state = self._get_state(flags)

        # NARRATIVE ATTACK: no combat-specific validation needed; routing table starts combat
        if state == "NARRATIVE":
            return WSMResult(valid=True)

        # COMBAT ATTACK — validate target
        if "target" not in params:
            return WSMResult.blocked("Musisz wskazać cel ataku.")

        roster = flags.get("combat_roster", [])
        target_key = params["target"]
        target = next((e for e in roster if e.get("key") == target_key), None)

        if target is None:
            return WSMResult.blocked(f"Cel '{target_key}' nie istnieje w tej walce.")

        if target.get("hp", 1) <= 0:
            name = target.get("name", target_key)
            return WSMResult.blocked(f"{name} jest już martwy/a.")

        if "weapon" in params:
            if not self._character_has_item(character_id, params["weapon"]):
                return WSMResult.blocked(f"Nie masz '{params['weapon']}' w ekwipunku.")

        if self._has_active_condition(character_id, "stunned", flags.get("_current_turn", 0)):
            return WSMResult.blocked("Jesteś ogłuszony/a. Nie możesz atakować w tej turze.")

        return WSMResult(valid=True)

    def _validate_flee(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        # NARRATIVE flee already blocked by state-level check; this handles COMBAT
        location_key = flags.get("current_location_key")
        if location_key:
            exits = self._get_location_exits(location_key)
            if not exits:
                return WSMResult.blocked("Nie ma drogi ucieczki z tego miejsca.")
        return WSMResult(valid=True)

    def _validate_dialogue(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        if "npc_key" not in params:
            return WSMResult.blocked("Wskaż, z kim chcesz rozmawiać.")

        npc_key = params["npc_key"]
        npc = self._get_npc(npc_key)
        if npc is None:
            return WSMResult.blocked(f"Postać '{npc_key}' nie istnieje.")

        if not npc.get("is_active", 1):
            name = npc.get("label", npc_key)
            return WSMResult.blocked(f"{name} nie żyje. Możesz tylko zbadać ciało.")

        location_key = flags.get("current_location_key")
        if location_key and not self._npc_in_location(npc_key, location_key):
            name = npc.get("label", npc_key)
            return WSMResult.blocked(f"{name} nie jest tutaj.")

        return WSMResult(valid=True)

    def _validate_movement(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        # Critical wound blocks ALL movement
        if self._has_active_condition(character_id, "wound_critical", flags.get("_current_turn", 0)):
            return WSMResult.blocked("Jesteś zbyt ciężko ranny/a, by się poruszać.")

        # ── Hex-based movement (new model) ────────────────────────────────
        # If destination is given as hex coords, validate via world_hexes
        dest_q = params.get("destination_q")
        dest_r = params.get("destination_r")
        if dest_q is not None and dest_r is not None:
            dest_hex = self.conn.execute(
                "SELECT q, r, hex_type FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1",
                (int(dest_q), int(dest_r)),
            ).fetchone()
            if not dest_hex:
                return WSMResult.blocked("To miejsce nie istnieje na mapie.")
            # Actual pathfinding happens in resolve_chain_travel;
            # WSM just confirms dest hex exists and movement is legal state-wise
            return WSMResult(valid=True)

        # ── Legacy location-key movement (backward compat) ────────────────
        if "destination_key" not in params:
            return WSMResult.blocked("Wskaż cel podróży.")

        dest_key = params["destination_key"]
        dest = self._get_location(dest_key)
        if dest is None:
            return WSMResult.blocked(f"Lokacja '{dest_key}' nie istnieje.")

        current_key = flags.get("current_location_key")
        if current_key and not self._locations_connected(current_key, dest_key):
            return WSMResult.blocked("Nie można tam dotrzeć z tego miejsca.")

        return WSMResult(valid=True)

    def _validate_rest(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        rest_type = params.get("rest_type", "short")
        if rest_type not in ("short", "long"):
            return WSMResult.blocked("Typ odpoczynku musi być 'krótki' (short) lub 'długi' (long).")

        location_key = flags.get("current_location_key")
        if location_key:
            loc = self._get_location(location_key)
            if loc is not None:
                safe = loc.get("safe_for_rest", 0)
                if safe == 0:
                    return WSMResult.blocked("To miejsce nie jest bezpieczne na odpoczynek. Szukaj schronienia.")
                if rest_type == "long" and safe < 2:
                    return WSMResult.blocked(
                        "To miejsce nadaje się tylko na krótki odpoczynek. "
                        "Długi odpoczynek wymaga bezpiecznego schronienia."
                    )

            if self._enemies_alive_in_location(location_key, campaign_id):
                return WSMResult.blocked("W pobliżu są wrogowie. Nie możesz odpoczywać.")

        return WSMResult(valid=True)

    def _validate_item_use(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        if "item_key" not in params:
            return WSMResult.blocked("Wskaż przedmiot do użycia.")

        item_key = params["item_key"]
        if not self._character_has_item(character_id, item_key):
            return WSMResult.blocked(f"Nie masz '{item_key}' w ekwipunku.")

        return WSMResult(valid=True)

    def _validate_item_pickup(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        if "item_key" not in params:
            return WSMResult.blocked("Wskaż przedmiot do podniesienia.")
        return WSMResult(valid=True)

    def _validate_shop(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        state = self._get_state(flags)

        # From SHOPPING state — leaving (routing table handles SHOPPING→NARRATIVE)
        if state == "SHOPPING":
            return WSMResult(valid=True)

        if "npc_key" not in params:
            return WSMResult.blocked("Wskaż kupca, z którym chcesz handlować.")

        npc_key = params["npc_key"]
        npc = self._get_npc(npc_key)
        if npc is None:
            return WSMResult.blocked(f"Postać '{npc_key}' nie istnieje.")

        if not npc.get("is_shop", 0):
            name = npc.get("label", npc_key)
            return WSMResult.blocked(f"{name} nie jest kupcem.")

        location_key = flags.get("current_location_key")
        if location_key and not self._npc_in_location(npc_key, location_key):
            name = npc.get("label", npc_key)
            return WSMResult.blocked(f"{name} nie jest tutaj.")

        return WSMResult(valid=True)

    def _validate_skill_attempt(self, flags: dict, params: dict, character_id: int, campaign_id: int) -> WSMResult:
        if "skill_key" not in params:
            return WSMResult.blocked("Wskaż umiejętność do użycia.")
        return WSMResult(valid=True)

    # ── DB helpers ─────────────────────────────────────────────────────────

    def _get_npc(self, npc_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT key, label, is_active, is_shop FROM npcs WHERE key = ?",
            (npc_key,)
        ).fetchone()
        return dict(row) if row else None

    def _npc_in_location(self, npc_key: str, location_key: str) -> bool:
        # Check location_npc_assignments (V2 join table)
        row = self.conn.execute(
            "SELECT 1 FROM location_npc_assignments WHERE npc_key = ? AND location_key = ? AND is_active = 1",
            (npc_key, location_key)
        ).fetchone()
        if row:
            return True
        # Fallback: check old npc_keys JSON on game_locations
        loc_row = self.conn.execute(
            "SELECT npc_keys FROM game_locations WHERE key = ?", (location_key,)
        ).fetchone()
        if loc_row and loc_row[0]:
            try:
                keys = json.loads(loc_row[0])
                return npc_key in keys
            except (json.JSONDecodeError, TypeError):
                pass
        return False

    def _get_location(self, location_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT key, label, safe_for_rest, is_active FROM game_locations WHERE key = ?",
            (location_key,)
        ).fetchone()
        return dict(row) if row else None

    def _locations_connected(self, from_key: str, to_key: str) -> bool:
        # Check direct connection (bidirectional)
        row = self.conn.execute(
            """SELECT 1 FROM location_connections
               WHERE ((from_location_key = ? AND to_location_key = ?)
                  OR  (from_location_key = ? AND to_location_key = ? AND is_bidirectional = 1))
               AND is_active = 1""",
            (from_key, to_key, to_key, from_key)
        ).fetchone()
        if row:
            return True
        # Fallback: sub-locations within same parent (macro)
        from_loc = self._get_location(from_key)
        to_loc = self._get_location(to_key)
        if from_loc and to_loc:
            # Both are sub-locations of the same macro → free movement
            from_parent = self.conn.execute(
                "SELECT parent_id FROM game_locations WHERE key = ?", (from_key,)
            ).fetchone()
            to_parent = self.conn.execute(
                "SELECT parent_id FROM game_locations WHERE key = ?", (to_key,)
            ).fetchone()
            if from_parent and to_parent and from_parent[0] and from_parent[0] == to_parent[0]:
                return True
        return False

    def _get_location_exits(self, location_key: str) -> list[str]:
        rows = self.conn.execute(
            """SELECT to_location_key FROM location_connections
               WHERE from_location_key = ? AND is_active = 1
               UNION
               SELECT from_location_key FROM location_connections
               WHERE to_location_key = ? AND is_bidirectional = 1 AND is_active = 1""",
            (location_key, location_key)
        ).fetchall()
        return [r[0] for r in rows]

    def _character_has_item(self, character_id: int, item_key: str) -> bool:
        row = self.conn.execute(
            """SELECT 1 FROM character_inventory
               WHERE character_id = ?
               AND (item_key = ? OR weapon_key = ? OR consumable_key = ?)""",
            (character_id, item_key, item_key, item_key)
        ).fetchone()
        return row is not None

    def _has_active_condition(self, character_id: int, condition_type: str, current_turn: int) -> bool:
        row = self.conn.execute(
            """SELECT 1 FROM character_conditions
               WHERE character_id = ?
               AND condition_type = ?
               AND (expires_at IS NULL OR CAST(expires_at AS INTEGER) > ?)""",
            (character_id, condition_type, current_turn)
        ).fetchone()
        return row is not None

    def _enemies_alive_in_location(self, location_key: str, campaign_id: int) -> bool:
        row = self.conn.execute(
            """SELECT 1 FROM active_combat
               WHERE campaign_id = ?
               AND status = 'active'""",
            (campaign_id,)
        ).fetchone()
        return row is not None


# ── Convenience functions for use without instantiation ───────────────────

def get_session_state(session_flags: dict) -> str:
    """Extract the current state string from session_flags dict."""
    state = session_flags.get("state", "NARRATIVE")
    return state if state in VALID_STATES else "NARRATIVE"


def build_session_flags(state: str = "NARRATIVE", **kwargs) -> dict:
    """Build a minimal valid session_flags dict for a given state."""
    flags = {
        "state": state,
        "state_entered_at_turn": 0,
        "previous_state": None,
        "combat_roster": [],
        "combat_turn_order": [],
        "combat_current_turn_index": 0,
        "pending_test": None,
        "fear_test_pending": None,
        "death_save_successes": 0,
        "death_save_failures": 0,
        "rest_type_in_progress": None,
        "rest_turns_remaining": 0,
        "loot_available": False,
        "last_combat_loot_id": None,
    }
    flags.update(kwargs)
    return flags
