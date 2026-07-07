"""
Suggested Actions — T33 Hybrid Input UI

Builds a context-aware list of quick-action buttons returned with each turn response.
These buttons allow the player to act without typing free text.

Rule-based actions are generated from DB state (locations, NPCs, inventory, combat).
LLM-suggested actions (from GM JSON `suggested_actions` field) are merged in after.
"""

from __future__ import annotations

import json
import sqlite3
import structlog
from dataclasses import dataclass, field
from typing import Optional

logger = structlog.get_logger()

MAX_ACTIONS = 5


@dataclass
class SuggestedAction:
    label: str            # Polish display text
    action: str           # structured action string sent on click
    enabled: bool = True
    reason: Optional[str] = None   # tooltip when disabled
    icon: Optional[str] = None
    type: Optional[str] = None    # "travel" for travel pills (UI highlighting)

    def to_dict(self) -> dict:
        d: dict = {"label": self.label, "action": self.action, "enabled": self.enabled}
        if self.reason:
            d["reason"] = self.reason
        if self.icon:
            d["icon"] = self.icon
        if self.type:
            d["type"] = self.type
        return d


def build_suggested_actions(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    game_state: str | None,
    session_flags: dict,
    llm_suggested: list[dict] | None = None,
    travel_hint: str | None = None,
) -> list[dict]:
    """
    Build up to MAX_ACTIONS quick-action buttons for the player UI.

    Returns a list of dicts (JSON-serialisable).
    Never raises — returns [] on any error.
    """
    try:
        state = (game_state or "").upper()
        if state in ("COMBAT",):
            actions = _build_combat_actions(conn, character_id)
        elif state in ("NARRATIVE", "DIALOGUE", ""):
            actions = _build_narrative_actions(conn, campaign_id, session_flags)
        else:
            actions = []

        # Merge LLM-suggested actions (appended after rule-based, dedup by action string)
        if llm_suggested:
            seen = {a.action for a in actions}
            for item in llm_suggested:
                if not isinstance(item, dict):
                    continue
                action_str = str(item.get("action") or "").strip()
                label_str = str(item.get("label") or "").strip()
                if not action_str or not label_str:
                    continue
                if action_str in seen:
                    continue
                seen.add(action_str)
                actions.append(SuggestedAction(
                    label=label_str,
                    action=action_str,
                    enabled=bool(item.get("enabled", True)),
                    reason=item.get("reason"),
                    icon=item.get("icon"),
                ))

        # Cap at MAX_ACTIONS
        actions = actions[:MAX_ACTIONS]
        return [a.to_dict() for a in actions]

    except Exception as exc:
        logger.warning("suggested_actions_error", error=str(exc))
        return []


# ── PT12 (#1122): travel-interrupt decision buttons ──────────────────────────

# Set by resolve_chain_travel (encounter/dusk/forced_camp) and by turn_pipeline
# after it prompts the player (…_prompted). Any of these means "journey paused".
_TRAVEL_INTERRUPT_REASONS = {
    "encounter", "dusk", "forced_camp",
    "encounter_prompted", "dusk_prompted", "forced_camp_prompted",
}


def _build_travel_interrupt_actions(session_flags: dict) -> list[SuggestedAction]:
    """PT12: when a journey is interrupted, show three mechanical decision buttons —
    Kontynuuj podróż / Odpocznij / Rozbij obóz. Clicking bypasses the LLM (see
    frontend TRAVEL_RESUME + /travel-resume endpoint). forced_camp = hero collapsed,
    so Kontynuuj podróż is disabled until they rest.
    """
    tp = session_flags.get("travel_plan")
    if not isinstance(tp, dict):
        return []
    reason = str(tp.get("interrupt_reason") or "")
    if reason not in _TRAVEL_INTERRUPT_REASONS:
        return []
    can_resume = not reason.startswith("forced_camp")
    return [
        SuggestedAction(
            label="Kontynuuj podróż",
            action="TRAVEL_RESUME",
            enabled=can_resume,
            reason=None if can_resume else "Padłeś ze zmęczenia — najpierw odpocznij.",
            icon="🧭",
            type="travel",
        ),
        SuggestedAction(label="Odpocznij", action="REST:long", enabled=True, icon="😴"),
        SuggestedAction(label="Rozbij obóz", action="BUILD_CAMP", enabled=True, icon="🔥"),
    ]


# ── NARRATIVE / DIALOGUE state ────────────────────────────────────────────────

def _build_narrative_actions(
    conn: sqlite3.Connection,
    campaign_id: int,
    session_flags: dict,
) -> list[SuggestedAction]:
    """Priority: NPCs first, exits, SEARCH, REST — capped at MAX_ACTIONS."""
    # PM4 #1223: gdy czeka wybór trasy (pending_travel_choice, ustawiony przez
    # _pm4_maybe_prompt) — pokaż 2 klikalne opcje zamiast pytania tekstem. Tekst
    # akcji trafia w detect_route_choice (wprost/przełaj→direct, trakt→road).
    _ptc = session_flags.get("pending_travel_choice")
    if isinstance(_ptc, dict) and _ptc.get("destination"):
        _lbl = str(_ptc.get("label") or "cel").strip() or "cel"
        return [
            SuggestedAction(
                label="Na wprost, przełajem",
                action=f"Idę na wprost, przełajem do {_lbl}.",
                enabled=True, icon="🌲", type="route_choice",
            ),
            SuggestedAction(
                label="Trzymam się traktu",
                action=f"Idę traktem do {_lbl}.",
                enabled=True, icon="🛤️", type="route_choice",
            ),
        ]

    # PT12 (#1122): a paused journey replaces the normal pills with 3 decision buttons.
    interrupt = _build_travel_interrupt_actions(session_flags)
    if interrupt:
        return interrupt[:MAX_ACTIONS]

    actions: list[SuggestedAction] = []

    # PT-F7 #1141: derive from current_location_id (single source), not the old mirror.
    from app.services.location_state_service import get_current_location_key
    current_loc_key = get_current_location_key(conn, campaign_id) or ""
    turns_at_location = int(session_flags.get("turns_at_location", 0) or 0)

    # U32 — travel pills from real hex data
    # Quest target pills: always (when active beat has visit_location)
    # Neighbor pills: only when turns_at_location >= 5 (escalation threshold)
    travel_pills = _build_travel_pills(
        conn, campaign_id, session_flags,
        include_neighbors=(turns_at_location >= 5),
    )
    if travel_pills:
        actions.extend(travel_pills[:2])

    # Podróż wstrzymana (po obozie/odpoczynku): interrupt_reason zdjęty, ale cel
    # nadal w travel_plan → pozwól WZNOWIĆ. Bez tego po „Rozbij obóz→Odpocznij"
    # gracz nie miał jak wrócić na trasę.
    _tp = session_flags.get("travel_plan")
    if (
        isinstance(_tp, dict)
        and not _tp.get("interrupt_reason")
        and (_tp.get("destination_hex") or _tp.get("destination_key"))
        and len(actions) < MAX_ACTIONS
    ):
        _dl = str(_tp.get("destination_label") or "").strip()
        if _dl.startswith("hex (") or not _dl:
            _dl = ""
        actions.insert(0, SuggestedAction(
            label=f"Kontynuuj podróż{(' → ' + _dl) if _dl else ''}",
            action="TRAVEL_RESUME",
            enabled=True,
            icon="🧭",
            type="travel",
        ))

    # Bezpieczeństwo liczone raz (potrzebne wcześnie, by REST nie wypadł przez cap).
    current_hex = session_flags.get("current_hex") or {}
    hex_q = current_hex.get("q")
    hex_r = current_hex.get("r")
    has_hex = hex_q is not None and hex_r is not None
    safe = _is_safe_for_rest(conn, current_loc_key) or (has_hex and _is_hex_safe_for_rest(conn, hex_q, hex_r))

    # 0) REST wysoko, gdy tu bezpiecznie — w osadzie/gospodzie „Odpocznij" to główna
    # akcja i nie może wypaść przez cap MAX_ACTIONS zajęty przez NPC/wyjścia/SEARCH.
    if safe and len(actions) < MAX_ACTIONS:
        actions.append(SuggestedAction(label="Odpocznij", action="REST:long", enabled=True))

    # 1) NPCs present at current location
    if current_loc_key and len(actions) < MAX_ACTIONS:
        npc_actions = _get_npc_actions(conn, current_loc_key)
        remaining = MAX_ACTIONS - len(actions)
        actions.extend(npc_actions[:min(2, remaining)])

    # 2) Movement exits (max 2)
    if current_loc_key and len(actions) < MAX_ACTIONS:
        exit_actions = _get_exit_actions(conn, current_loc_key)
        remaining = MAX_ACTIONS - len(actions)
        actions.extend(exit_actions[:min(2, remaining)])

    # 3) SEARCH — always available
    if len(actions) < MAX_ACTIONS:
        actions.append(SuggestedAction(
            label="Przeszukaj okolicę",
            action="SEARCH",
            enabled=True,
        ))

    # 4) REST (fallback) — gdy nie dodane wyżej (np. niebezpieczna lokacja): pokaż
    # wyłączone „Odpocznij" z powodem, chyba że już jest na liście.
    if len(actions) < MAX_ACTIONS and not any(a.action == "REST:long" for a in actions):
        actions.append(SuggestedAction(
            label="Odpocznij",
            action="REST:long",
            enabled=safe,
            reason="Nie możesz tu bezpiecznie odpocząć" if not safe else None,
        ))

    # 5) BUILD_CAMP — only when unsafe AND has hex position (consistent with world_service.build_camp check)
    if len(actions) < MAX_ACTIONS and not safe and has_hex:
        actions.append(SuggestedAction(
            label="Rozbij obóz",
            action="BUILD_CAMP",
            enabled=True,
            icon="🔥",
            reason="Tymczasowy obóz pozwoli odpocząć, ale ściągnie więcej spotkań.",
        ))

    return actions


# ── U32: Travel pills from real hex data ─────────────────────────────────────

def _build_travel_pills(
    conn: sqlite3.Connection,
    campaign_id: int,
    session_flags: dict,
    include_neighbors: bool = True,
    max_neighbors: int = 3,
) -> list[SuggestedAction]:
    """U32: Build travel pills from neighboring hexes and quest beat targets.

    Quest target pills (visit_location beats): always included.
    Neighbor pills: only when include_neighbors=True (turns_at_location >= 5).
    Returns SuggestedAction list with type='travel'.
    """
    pills: list[SuggestedAction] = []
    current_hex = session_flags.get("current_hex") or {}
    q = current_hex.get("q")
    r = current_hex.get("r")
    if q is None or r is None:
        return pills

    try:
        q_int = int(q)
        r_int = int(r)
    except (TypeError, ValueError):
        return pills

    seen_actions: set[str] = set()

    # 1) Quest target pills — active unvisited beats with objective_type=visit_location
    try:
        camp_row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if camp_row and camp_row[0]:
            plan = json.loads(camp_row[0])
            for act in plan.get("acts", []):
                for beat in act.get("key_beats", []):
                    if not isinstance(beat, dict):
                        continue
                    if beat.get("visited"):
                        continue
                    if beat.get("objective_type") != "visit_location":
                        continue
                    obj_val = (beat.get("objective_value") or "").strip()
                    if not obj_val:
                        continue
                    # Find hex for this location (by label or key)
                    hex_row = conn.execute(
                        """SELECT wh.q, wh.r FROM world_hexes wh
                           JOIN game_locations gl ON gl.key = wh.location_key
                           WHERE (gl.label = ? OR gl.key = ?)
                             AND wh.is_active = 1
                           LIMIT 1""",
                        (obj_val, obj_val),
                    ).fetchone()
                    if not hex_row:
                        continue
                    tq, tr = int(hex_row[0]), int(hex_row[1])
                    if tq == q_int and tr == r_int:
                        continue  # already here
                    action_key = f"TRAVEL:{tq}:{tr}"
                    if action_key in seen_actions:
                        continue
                    seen_actions.add(action_key)
                    pills.append(SuggestedAction(
                        label=f"📜 → {obj_val}",
                        action=action_key,
                        enabled=True,
                        type="travel",
                    ))
    except Exception as exc:
        logger.warning("travel_pills_quest_error", error=str(exc))

    # 2) Neighbor hex pills — only when stagnation threshold reached
    if not include_neighbors:
        return pills

    try:
        # Compute hex_neighbors inline (axial coords, 6 directions)
        _directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
        neighbors = [(q_int + dq, r_int + dr) for dq, dr in _directions]

        added = 0
        for nq, nr in neighbors:
            if added >= max_neighbors:
                break
            action_key = f"TRAVEL:{nq}:{nr}"
            if action_key in seen_actions:
                continue
            # Only show hexes that exist in world_hexes
            row = conn.execute(
                "SELECT label, location_key, hex_type FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
                (nq, nr),
            ).fetchone()
            if not row:
                continue
            # Priority: location label > hex label > hex_type name in Polish > skip (never show raw coords)
            dest_label: Optional[str] = None
            loc_key = row[1] if row[1] else None
            if loc_key:
                loc_row = conn.execute(
                    "SELECT label FROM game_locations WHERE key=? AND is_active=1 LIMIT 1",
                    (loc_key,),
                ).fetchone()
                if loc_row and loc_row[0]:
                    dest_label = str(loc_row[0])
            if not dest_label and row[0]:
                dest_label = str(row[0])
            if not dest_label:
                dest_label = _HEX_TYPE_POLISH.get(str(row[2] or "").lower())
            if not dest_label:
                continue  # no useful label — skip this pill
            seen_actions.add(action_key)
            pills.append(SuggestedAction(
                label=f"→ {dest_label} (1h)",
                action=action_key,
                enabled=True,
                icon="🗺",
                type="travel",
            ))
            added += 1
    except Exception as exc:
        logger.warning("travel_pills_neighbors_error", error=str(exc))

    return pills


# Polish terrain names for hex_type fallback (U32 — never show raw coords to player)
_HEX_TYPE_POLISH: dict[str, str] = {
    "plains":    "Równiny",
    "forest":    "Las",
    "hills":     "Wzgórza",
    "mountains": "Góry",
    "swamp":     "Bagna",
    "desert":    "Pustynia",
    "tundra":    "Tundra",
    "coast":     "Wybrzeże",
    "sea":       "Morze",
    "river":     "Rzeka",
    "road":      "Gościniec",
    "dungeon":   "Loch",
    "ruins":     "Ruiny",
    "village":   "Wioska",
    "city":      "Miasto",
    "castle":    "Zamek",
    "cave":      "Jaskinia",
    "temple":    "Świątynia",
}


def _get_npc_actions(conn: sqlite3.Connection, location_key: str) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    try:
        # Try location_npc_assignments join table first
        rows = conn.execute(
            """
            SELECT n.key, n.label
            FROM location_npc_assignments lna
            JOIN npcs n ON n.key = lna.npc_key
            WHERE lna.location_key = ? AND lna.is_active = 1
            LIMIT 2
            """,
            (location_key,),
        ).fetchall()
        for row in rows:
            npc_key = str(row["key"] or "")
            npc_name = str(row["label"] or npc_key)
            actions.append(SuggestedAction(
                label=f"Porozmawiaj z {npc_name}",
                action=f"DIALOGUE:{npc_key}",
                enabled=True,
            ))
        if actions:
            return actions

        # Fallback: parse npc_keys JSON from game_locations
        loc_row = conn.execute(
            "SELECT npc_keys FROM game_locations WHERE key = ? LIMIT 1",
            (location_key,),
        ).fetchone()
        if loc_row:
            npc_keys_raw = loc_row["npc_keys"] if "npc_keys" in loc_row.keys() else None
            if npc_keys_raw:
                npc_keys = json.loads(npc_keys_raw) if isinstance(npc_keys_raw, str) else npc_keys_raw
                if isinstance(npc_keys, list):
                    for npc_key in npc_keys[:2]:
                        npc_key = str(npc_key).strip()
                        if not npc_key:
                            continue
                        # Try to get name
                        nr = conn.execute(
                            "SELECT label FROM npcs WHERE key = ? LIMIT 1",
                            (npc_key,),
                        ).fetchone()
                        npc_name = str(nr["label"]) if nr else npc_key
                        actions.append(SuggestedAction(
                            label=f"Porozmawiaj z {npc_name}",
                            action=f"DIALOGUE:{npc_key}",
                            enabled=True,
                        ))
    except Exception as exc:
        logger.warning("npc_actions_error", error=str(exc))
    return actions


def _get_exit_actions(conn: sqlite3.Connection, location_key: str) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    try:
        rows = conn.execute(
            """
            SELECT lc.to_location_key, gl.label
            FROM location_connections lc
            LEFT JOIN game_locations gl ON gl.key = lc.to_location_key
            WHERE lc.from_location_key = ?
            LIMIT 2
            """,
            (location_key,),
        ).fetchall()
        for row in rows:
            dest_key = str(row["to_location_key"] or "")
            dest_name = str(row["label"] or dest_key)
            if not dest_key:
                continue
            actions.append(SuggestedAction(
                label=f"Idź do {dest_name}",
                action=f"MOVEMENT:{dest_key}",
                enabled=True,
            ))
    except Exception as exc:
        logger.warning("exit_actions_error", error=str(exc))
    return actions


def _is_safe_for_rest(conn: sqlite3.Connection, location_key: str) -> bool:
    if not location_key:
        return False
    try:
        row = conn.execute(
            "SELECT safe_for_rest FROM game_locations WHERE key = ? LIMIT 1",
            (location_key,),
        ).fetchone()
        if row and "safe_for_rest" in row.keys():
            if bool(row["safe_for_rest"]):
                return True
        # #1063 Opcja B: osada bez własnej flagi, ale z sub-lokacją inn/tavern.
        from app.services.world_service import settlement_lodging
        return settlement_lodging(conn, location_key) is not None
    except Exception as exc:
        logger.warning("safe_for_rest_error", error=str(exc))
    return False


def _is_hex_safe_for_rest(conn: sqlite3.Connection, q, r) -> bool:
    """Mirror of world_service.build_camp safety check: hex's assigned location."""
    try:
        hex_row = conn.execute(
            "SELECT location_key FROM world_hexes WHERE q=? AND r=? AND is_active=1",
            (q, r),
        ).fetchone()
        if hex_row and hex_row["location_key"]:
            loc_row = conn.execute(
                "SELECT safe_for_rest FROM game_locations WHERE key=? AND is_active=1",
                (hex_row["location_key"],),
            ).fetchone()
            if loc_row:
                return bool(loc_row["safe_for_rest"])
    except Exception as exc:
        logger.warning("hex_safe_for_rest_error", error=str(exc))
    return False


# ── COMBAT state ──────────────────────────────────────────────────────────────

def _build_combat_actions(
    conn: sqlite3.Connection,
    character_id: int,
) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []

    # 1) Attack — always enabled
    actions.append(SuggestedAction(
        label="Atakuj",
        action="ATTACK",
        enabled=True,
        icon="⚔",
    ))

    # 2) Flee — depends on location enclosed flag
    not_enclosed = _can_flee(conn, character_id)
    actions.append(SuggestedAction(
        label="Uciekaj",
        action="FLEE",
        enabled=not_enclosed,
        reason="Brak drogi ucieczki" if not not_enclosed else None,
        icon="🏃",
    ))

    # 3) Use item — depends on inventory
    has_items = _has_usable_items(conn, character_id)
    actions.append(SuggestedAction(
        label="Użyj przedmiotu",
        action="ITEM_USE",
        enabled=has_items,
        reason="Brak przedmiotów" if not has_items else None,
        icon="🧪",
    ))

    return actions


def _can_flee(conn: sqlite3.Connection, character_id: int) -> bool:
    """Return True if character can flee (location is not enclosed)."""
    try:
        # Get character's current location via campaign
        row = conn.execute(
            """
            SELECT gl.enclosed
            FROM characters c
            JOIN campaigns camp ON camp.id = c.campaign_id
            JOIN game_sessions gs ON gs.campaign_id = camp.id
            LEFT JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE c.id = ?
            LIMIT 1
            """,
            (character_id,),
        ).fetchone()
        if row and "enclosed" in row.keys() and row["enclosed"] is not None:
            return not bool(row["enclosed"])
    except Exception as exc:
        logger.warning("can_flee_error", error=str(exc))
    # Safe default: can flee
    return True


def _has_usable_items(conn: sqlite3.Connection, character_id: int) -> bool:
    """Return True if character has any inventory items (excluding narrative-only)."""
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM character_inventory
            WHERE character_id = ?
              AND item_key NOT IN ('__narrative__')
            """,
            (character_id,),
        ).fetchone()
        if row:
            return int(row["cnt"] or 0) > 0
    except Exception as exc:
        logger.warning("has_usable_items_error", error=str(exc))
    return False
