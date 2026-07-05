"""Scenario Sandbox (#1211) — deterministic session setup for testing one
specific game element, plus a per-turn mechanics log.

An agent (Claude) or an admin maps a GitHub issue onto a structured `setup`
dict and calls `prepare_scenario`. The service builds a fully isolated,
disposable play session positioned exactly at the element under test:

- clones the chosen hero (name prefix ``[SCN] ``, ``__scenario_clone__`` in
  sheet_json) — the original hero is NEVER modified;
- creates a disposable campaign titled ``[SBX-SCN] …`` (one live scenario per
  user — a new prepare purges the user's previous scenario campaign+clone);
- seeds the scene: enemies/NPCs, session flags, in-game hour, location,
  optional GM plan and an opening GM narration so the conversation is
  playable from turn one.

`get_scenario_state` powers the side mechanics log: turn_decisions,
dice_rolls and state_changes grouped per turn, so a tester sees WHY the
engine did what it did, not just the narration.

Combat Sandbox clones (``[SBX] ``, router sandbox.py) are never touched.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

DB_PATH = Path("/data/ai_gm.db")

SCN_CAMPAIGN_PREFIX = "[SBX-SCN]"
SCN_CLONE_PREFIX = "[SCN] "

# sheet_json keys an override may replace; anything else in hero_overrides is
# ignored so a typo cannot corrupt the clone's sheet structure.
_SHEET_OVERRIDE_KEYS = {
    "level", "current_hp", "max_hp", "current_mana", "max_mana",
    "conditions", "arcane_points", "stats", "skills",
}


class ScenarioError(Exception):
    """Setup impossible (missing hero, bad payload). Router maps to 4xx."""


def _open() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _use(conn: sqlite3.Connection | None) -> tuple[sqlite3.Connection, bool]:
    if conn is not None:
        return conn, False
    return _open(), True


# ── purge ────────────────────────────────────────────────────────────────────


def _purge_prior_scenarios(c: sqlite3.Connection, user_id: int) -> int:
    """Drop the user's previous scenario campaigns, their clones and all
    per-campaign rows (turns, session, traces, combat). Combat-sandbox data
    (``[SANDBOX]`` campaigns, ``[SBX] `` clones) is left alone."""
    camps = c.execute(
        "SELECT id FROM campaigns WHERE owner_user_id = ? AND title LIKE ?",
        (user_id, f"{SCN_CAMPAIGN_PREFIX}%"),
    ).fetchall()
    for row in camps:
        cid = int(row["id"])
        for tbl in (
            "combat_loot", "active_combat", "campaign_turns",
            "dice_rolls", "state_changes", "turn_decisions",
        ):
            try:
                c.execute(f"DELETE FROM {tbl} WHERE campaign_id = ?", (cid,))
            except sqlite3.OperationalError:
                pass  # optional trace table absent in minimal schemas
        c.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (cid,))
        c.execute("DELETE FROM campaigns WHERE id = ?", (cid,))

    clones = c.execute(
        "SELECT id FROM characters WHERE user_id = ? AND name LIKE ?",
        (user_id, f"{SCN_CLONE_PREFIX}%"),
    ).fetchall()
    for row in clones:
        clone_id = int(row["id"])
        c.execute("DELETE FROM character_inventory WHERE character_id = ?", (clone_id,))
        c.execute("DELETE FROM character_spells WHERE character_id = ?", (clone_id,))
        c.execute("DELETE FROM characters WHERE id = ?", (clone_id,))
    return len(camps)


# ── clone ────────────────────────────────────────────────────────────────────


def _clone_hero(
    c: sqlite3.Connection,
    source_hero_id: int,
    campaign_id: int,
    hero_overrides: dict[str, Any],
    location_name: str | None,
) -> int:
    orig = c.execute(
        "SELECT * FROM characters WHERE id = ? AND is_active = 1",
        (source_hero_id,),
    ).fetchone()
    if not orig:
        raise ScenarioError("hero not found")

    sheet = json.loads(orig["sheet_json"] or "{}")
    for key, val in (hero_overrides or {}).items():
        if key in _SHEET_OVERRIDE_KEYS:
            sheet[key] = val
    sheet["__scenario_clone__"] = True
    sheet["__scenario_source_id__"] = int(source_hero_id)

    gold_gp = hero_overrides.get("gold_gp", orig["gold_gp"]) if hero_overrides else orig["gold_gp"]
    location = location_name or orig["location"]

    cur = c.execute(
        """
        INSERT INTO characters
            (campaign_id, user_id, name, system_id, sheet_json, location, is_active,
             created_at, backstory, appearance, personality, motivation, note,
             gold, gold_gp, hero_status, visited_location_keys, status)
        SELECT ?, user_id, ?, system_id, ?, ?, 1,
               datetime('now'), backstory, appearance, personality, motivation, note,
               gold, ?, hero_status, visited_location_keys, 'in_campaign'
        FROM characters WHERE id = ?
        """,
        (
            campaign_id,
            f"{SCN_CLONE_PREFIX}{orig['name']}",
            json.dumps(sheet, ensure_ascii=False),
            location,
            gold_gp,
            source_hero_id,
        ),
    )
    clone_id = int(cur.lastrowid)

    c.execute(
        """
        INSERT INTO character_inventory
            (character_id, item_key, weapon_key, consumable_key, quantity, equipped,
             slot, acquired_at, source, meta_json, label)
        SELECT ?, item_key, weapon_key, consumable_key, quantity, equipped,
               slot, acquired_at, source, meta_json, label
        FROM character_inventory WHERE character_id = ?
        """,
        (clone_id, source_hero_id),
    )
    c.execute(
        """
        INSERT INTO character_spells (character_id, spell_key, rank, use_count)
        SELECT ?, spell_key, rank, use_count
        FROM character_spells WHERE character_id = ?
        """,
        (clone_id, source_hero_id),
    )
    return clone_id


# ── public API ───────────────────────────────────────────────────────────────


def prepare_scenario(setup: dict[str, Any], conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Build an isolated, playable session positioned at the element under test.

    setup:
      hero_id (required)     — source hero to clone; never modified
      issue_number, title    — campaign label ``[SBX-SCN] #NNN — title``
      location_name          — clone's location text (and ŚWIAT block context)
      location_key           — optional game_locations.key → current_location_id
      scene_enemies          — list[str] → game_sessions.scene_enemies
      scene_npcs             — list[str] → game_sessions.scene_npcs
      session_flags          — dict merged into session_flags
      ingame_hours           — clock (default 9)
      hero_overrides         — sheet overrides (whitelist) + gold_gp
      gm_plan                — dict → campaigns.gm_plan_json
      opening_narration      — first GM turn text (playable from turn one)
      model_id               — LLM override for the campaign (default 'default')
      agent_notes            — what could not be inferred from the issue
    """
    hero_id = int(setup.get("hero_id") or 0)
    if not hero_id:
        raise ScenarioError("hero_id required")

    c, own = _use(conn)
    try:
        orig = c.execute(
            "SELECT id, user_id, name FROM characters WHERE id = ? AND is_active = 1",
            (hero_id,),
        ).fetchone()
        if not orig:
            raise ScenarioError("hero not found")
        user_id = int(orig["user_id"])

        _purge_prior_scenarios(c, user_id)

        issue_number = setup.get("issue_number")
        title_bits = [SCN_CAMPAIGN_PREFIX]
        if issue_number:
            title_bits.append(f"#{int(issue_number)}")
        title_bits.append("—")
        title_bits.append(str(setup.get("title") or "Scenariusz testowy"))
        title = " ".join(title_bits)

        cur = c.execute(
            """
            INSERT INTO campaigns
                (title, system_id, model_id, owner_user_id, language, mode, status, gm_plan_json)
            VALUES (?, 'fantasy', ?, ?, 'pl', 'scenario', 'active', ?)
            """,
            (
                title,
                str(setup.get("model_id") or "default"),
                user_id,
                json.dumps(setup.get("gm_plan") or {}, ensure_ascii=False),
            ),
        )
        campaign_id = int(cur.lastrowid)

        clone_id = _clone_hero(
            c, hero_id, campaign_id,
            dict(setup.get("hero_overrides") or {}),
            setup.get("location_name"),
        )

        # session row — the scene the engine wakes up in
        flags: dict[str, Any] = {"state": "NARRATIVE"}
        flags.update(dict(setup.get("session_flags") or {}))
        flags["__scenario__"] = {
            "issue_number": issue_number,
            "source_hero_id": hero_id,
            "agent_notes": str(setup.get("agent_notes") or ""),
        }

        current_location_id = None
        loc_key = setup.get("location_key")
        if loc_key:
            loc = c.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1",
                (str(loc_key),),
            ).fetchone()
            if loc:
                current_location_id = int(loc["id"])

        c.execute(
            """
            INSERT INTO game_sessions
                (id, campaign_id, session_flags, scene_enemies, scene_npcs,
                 ingame_hours, current_location_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                uuid.uuid4().hex,
                campaign_id,
                json.dumps(flags, ensure_ascii=False),
                json.dumps(list(setup.get("scene_enemies") or []), ensure_ascii=False),
                json.dumps(list(setup.get("scene_npcs") or []), ensure_ascii=False),
                int(setup.get("ingame_hours") or 9),
                current_location_id,
            ),
        )

        opening = str(setup.get("opening_narration") or "").strip()
        if opening:
            c.execute(
                """
                INSERT INTO campaign_turns
                    (campaign_id, character_id, user_text, route, assistant_text, turn_number)
                VALUES (?, ?, '[SCENARIO] start', 'narrative', ?, 1)
                """,
                (campaign_id, clone_id, opening),
            )

        c.commit()

        clone = c.execute(
            "SELECT id, name, sheet_json, gold_gp, location FROM characters WHERE id = ?",
            (clone_id,),
        ).fetchone()
        sheet = json.loads(clone["sheet_json"] or "{}")
    finally:
        if own:
            c.close()

    return {
        "campaign_id": campaign_id,
        "character_id": clone_id,
        "source_hero_id": hero_id,
        "title": title,
        "hero": {
            "id": clone["id"],
            "name": clone["name"],
            "archetype": sheet.get("archetype"),
            "level": int(sheet.get("level") or 1),
            "hp": int(sheet.get("current_hp") or sheet.get("max_hp") or 0),
            "max_hp": int(sheet.get("max_hp") or 0),
            "mana": int(sheet.get("current_mana") or 0),
            "max_mana": int(sheet.get("max_mana") or 0),
            "gold_gp": clone["gold_gp"] or 0,
            "location": clone["location"],
        },
    }


def get_scenario_state(
    campaign_id: int,
    since_turn: int = 0,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Side mechanics log: campaign + hero + session snapshot, active combat if
    any, and per-turn engine trace (decision, dice rolls, state changes) for
    turns > since_turn."""
    c, own = _use(conn)
    try:
        camp = c.execute(
            "SELECT id, title, status, mode, owner_user_id, gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise ScenarioError("campaign not found")

        hero = c.execute(
            "SELECT id, name, sheet_json, gold_gp, location FROM characters"
            " WHERE campaign_id = ? AND name LIKE ? LIMIT 1",
            (campaign_id, f"{SCN_CLONE_PREFIX}%"),
        ).fetchone()
        hero_out: dict[str, Any] | None = None
        if hero:
            sheet = json.loads(hero["sheet_json"] or "{}")
            hero_out = {
                "id": hero["id"],
                "name": hero["name"],
                "hp": int(sheet.get("current_hp") or 0),
                "max_hp": int(sheet.get("max_hp") or 0),
                "mana": int(sheet.get("current_mana") or 0),
                "conditions": sheet.get("conditions") or [],
                "gold_gp": hero["gold_gp"] or 0,
                "location": hero["location"],
            }

        gs = c.execute(
            "SELECT session_flags, scene_enemies, scene_npcs, ingame_hours,"
            " current_location_id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        session_out: dict[str, Any] = {}
        scenario_meta: dict[str, Any] = {}
        if gs:
            flags = json.loads(gs["session_flags"] or "{}")
            scenario_meta = flags.get("__scenario__") or {}
            session_out = {
                "session_flags": flags,
                "scene_enemies": json.loads(gs["scene_enemies"] or "[]"),
                "scene_npcs": json.loads(gs["scene_npcs"] or "[]"),
                "ingame_hours": gs["ingame_hours"],
                "current_location_id": gs["current_location_id"],
            }

        combat = c.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        combat_out = dict(combat) if combat else None

        def _rows(table: str) -> list[dict[str, Any]]:
            try:
                return [
                    dict(r) for r in c.execute(
                        f"SELECT * FROM {table} WHERE campaign_id = ? AND turn_number > ?"
                        " ORDER BY turn_number, id",
                        (campaign_id, since_turn),
                    ).fetchall()
                ]
            except sqlite3.OperationalError:
                return []

        decisions = _rows("turn_decisions")
        rolls = _rows("dice_rolls")
        changes = _rows("state_changes")

        by_turn: dict[int, dict[str, Any]] = {}

        def _bucket(n: int) -> dict[str, Any]:
            return by_turn.setdefault(
                n, {"turn_number": n, "decision": None, "dice_rolls": [], "state_changes": []},
            )

        for d in decisions:
            _bucket(int(d["turn_number"] or 0))["decision"] = d
        for r in rolls:
            _bucket(int(r["turn_number"] or 0))["dice_rolls"].append(r)
        for s in changes:
            _bucket(int(s["turn_number"] or 0))["state_changes"].append(s)

        turns = c.execute(
            "SELECT turn_number, user_text, assistant_text, route, created_at"
            " FROM campaign_turns WHERE campaign_id = ? AND turn_number > ?"
            " ORDER BY turn_number",
            (campaign_id, since_turn),
        ).fetchall()
    finally:
        if own:
            c.close()

    return {
        "campaign": {
            "id": camp["id"],
            "title": camp["title"],
            "status": camp["status"],
            "mode": camp["mode"],
            "owner_user_id": camp["owner_user_id"],
        },
        "scenario": scenario_meta,
        "hero": hero_out,
        "session": session_out,
        "active_combat": combat_out,
        "turns": [dict(t) for t in turns],
        "mechanics": [by_turn[k] for k in sorted(by_turn)],
    }


def list_scenarios(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Active scenario campaigns with their clone + issue tag, newest first."""
    c, own = _use(conn)
    try:
        camps = c.execute(
            "SELECT id, title, status, owner_user_id, created_at FROM campaigns"
            " WHERE title LIKE ? ORDER BY id DESC",
            (f"{SCN_CAMPAIGN_PREFIX}%",),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for camp in camps:
            cid = int(camp["id"])
            gs = c.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            meta = {}
            if gs:
                meta = (json.loads(gs["session_flags"] or "{}")).get("__scenario__") or {}
            clone = c.execute(
                "SELECT id, name FROM characters WHERE campaign_id = ? AND name LIKE ? LIMIT 1",
                (cid, f"{SCN_CLONE_PREFIX}%"),
            ).fetchone()
            turn_count = c.execute(
                "SELECT COUNT(*) AS n FROM campaign_turns WHERE campaign_id = ?", (cid,),
            ).fetchone()["n"]
            out.append({
                "campaign_id": cid,
                "title": camp["title"],
                "status": camp["status"],
                "owner_user_id": camp["owner_user_id"],
                "created_at": camp["created_at"],
                "issue_number": meta.get("issue_number"),
                "agent_notes": meta.get("agent_notes") or "",
                "character_id": clone["id"] if clone else None,
                "character_name": clone["name"] if clone else None,
                "turn_count": turn_count,
            })
    finally:
        if own:
            c.close()
    return out
