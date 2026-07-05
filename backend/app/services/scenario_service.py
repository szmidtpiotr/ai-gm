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

# session_flags keys owned by the engine — injecting them without the matching
# engine state (e.g. combat_active with no active_combat row) desyncs narrator
# vs mechanics. Stripped from setup.session_flags; use start_combat instead.
_ENGINE_OWNED_FLAG_PREFIXES = ("combat_", "post_flee", "dungeon_run", "pending_skill_test")


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


def _default_combat_starter(campaign_id: int, character_id: int, enemy_keys: list) -> dict:
    from app.services import combat_service

    return combat_service.initiate_combat(campaign_id, character_id, list(enemy_keys))


def prepare_scenario(
    setup: dict[str, Any],
    conn: sqlite3.Connection | None = None,
    combat_starter=None,
) -> dict[str, Any]:
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
      start_combat           — True → real initiate_combat on the clone with
                               scene_enemies (combat UI live from turn one)
      model_id               — LLM override for the campaign (default 'default')
      agent_notes            — what could not be inferred from the issue
    """
    hero_id = int(setup.get("hero_id") or 0)
    if not hero_id:
        raise ScenarioError("hero_id required")

    start_combat = bool(setup.get("start_combat"))
    scene_enemies = list(setup.get("scene_enemies") or [])
    if start_combat and not scene_enemies:
        raise ScenarioError("start_combat requires scene_enemies")

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
        requested_flags = dict(setup.get("session_flags") or {})
        stripped = [k for k in requested_flags
                    if any(k.startswith(p) for p in _ENGINE_OWNED_FLAG_PREFIXES)]
        for k in stripped:
            requested_flags.pop(k)
        flags.update(requested_flags)

        agent_notes = str(setup.get("agent_notes") or "")
        if stripped:
            agent_notes += (("; " if agent_notes else "")
                            + "wycięto flagi silnika z setupu: " + ", ".join(stripped)
                            + " (do walki użyj start_combat)")
        flags["__scenario__"] = {
            "issue_number": issue_number,
            "source_hero_id": hero_id,
            "agent_notes": agent_notes,
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
                json.dumps(scene_enemies, ensure_ascii=False),
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
                VALUES (?, ?, '— start scenariusza testowego —', 'narrative', ?, 1)
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

    # real combat from turn one — the engine owns the state (active_combat row),
    # so the player UI shows live combat buttons/banner, not narrated theater.
    combat_started = False
    if start_combat:
        starter = combat_starter or _default_combat_starter
        try:
            starter(campaign_id, clone_id, scene_enemies)
            combat_started = True
        except Exception as e:
            raise ScenarioError(f"start_combat failed: {e}") from e

    return {
        "campaign_id": campaign_id,
        "character_id": clone_id,
        "source_hero_id": hero_id,
        "combat_started": combat_started,
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

        # engine keeps the row after flee/end with status != 'active' — the
        # header must not report a finished fight as live (#1149 feedback)
        combat = c.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
            (campaign_id,),
        ).fetchone()
        combat_out = dict(combat) if combat else None
        last_combat = c.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? ORDER BY id DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        last_combat_out = dict(last_combat) if last_combat else None

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
        "last_combat": last_combat_out,
        "turns": [dict(t) for t in turns],
        "mechanics": [by_turn[k] for k in sorted(by_turn)],
    }


# ── Kreator (draft) — issue# + opis → setup przez LLM ───────────────────────

_DRAFT_SYSTEM_PROMPT = """Jesteś asystentem QA gry RPG AI-GM. Admin chce przetestować
konkretny element gry. Na podstawie treści GitHub issue i/lub opisu admina zbuduj
setup Sandboxu scenariuszy: sesję ustawioną tak, by testowany element odpalił od
PIERWSZEJ tury.

Zwróć WYŁĄCZNIE poprawny JSON (bez markdown):
{"reply": "<1-3 zdania po polsku co ustawiasz i dlaczego>",
 "setup": {
   "hero_id": <int — wybierz z listy bohaterów; preferuj bohatera testowego/demo>,
   "issue_number": <int lub null>,
   "title": "<krótki tytuł testu>",
   "location_name": "<nazwa miejsca akcji>",
   "location_key": "<klucz z katalogu lokacji lub pomiń>",
   "scene_enemies": ["<TYLKO klucze z katalogu wrogów>"],
   "scene_npcs": ["<nazwy NPC jeśli potrzebne>"],
   "start_combat": <true TYLKO gdy testowany element wymaga AKTYWNEJ walki od pierwszej tury (przyciski walki, ucieczka, obrażenia); wtedy scene_enemies nie może być puste>,
   "session_flags": {},
   "ingame_hours": <0-23>,
   "hero_overrides": {<np. "current_hp": 5 gdy test wymaga rannego bohatera>},
   "gm_plan": {<opcjonalnie np. "scene_goal": "...">},
   "opening_narration": "<2-4 zdania narracji GM po polsku stawiające gracza w środku testowanej sytuacji>",
   "agent_notes": "<czego NIE dało się wywnioskować z issue/opisu — przyjęte założenia>"
 }}

Zasady: scene_enemies wyłącznie z katalogu (puste gdy test bez walki);
session_flags zostaw {} — NIE wymyślaj flag silnika (combat_active itp.),
stan walki ustawia wyłącznie start_combat; nie wymyślaj pól spoza schematu;
wszystko po polsku."""


def _default_fetch_issue(issue_number: int) -> dict[str, Any] | None:
    """Fetch issue title/body from GitHub using GITHUB_PAT (same env as bug_report)."""
    import os

    import httpx

    pat = os.getenv("GITHUB_PAT", "").strip()
    repo = os.getenv("GITHUB_REPO", "szmidtpiotr/ai-gm").strip()
    if not pat:
        return None
    r = httpx.get(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}",
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=15,
    )
    if r.status_code != 200:
        return None
    d = r.json()
    return {"number": issue_number, "title": d.get("title") or "", "body": d.get("body") or ""}


def _default_llm(messages: list[dict[str, str]]) -> str:
    from app.services.llm_service import (
        content_llm_enabled,
        generate_chat,
        resolve_content_llm_config,
    )

    # Prefer the offline content profile (#818), but the Kreator is an
    # interactive admin flow — when that box is down/empty, fall back to the
    # live preset instead of failing.
    if content_llm_enabled():
        try:
            cfg = resolve_content_llm_config()
            out = generate_chat(messages=messages, llm_config=cfg, call_type="scenario_draft")
            if (out or "").strip():
                return out
        except Exception:
            pass
    return generate_chat(messages=messages, llm_config=None, call_type="scenario_draft")


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def draft_scenario_setup(
    issue_number: int | None = None,
    description: str = "",
    conn: sqlite3.Connection | None = None,
    llm=None,
    fetch_issue=None,
) -> dict[str, Any]:
    """Kreator: map an issue and/or admin description onto a prepare_scenario
    setup via LLM. Returns {reply, setup, issue}. The setup is a DRAFT — the
    admin reviews it in the panel before calling prepare_scenario."""
    description = (description or "").strip()
    if not issue_number and not description:
        raise ScenarioError("issue_number or description required")

    c, own = _use(conn)
    try:
        try:
            enemies = c.execute(
                "SELECT key, label, tier FROM game_config_enemies WHERE is_active = 1"
                " ORDER BY key LIMIT 120",
            ).fetchall()
        except sqlite3.OperationalError:
            enemies = []
        try:
            locations = c.execute(
                "SELECT key, label FROM game_locations WHERE is_active = 1"
                " AND key IS NOT NULL ORDER BY id DESC LIMIT 80",
            ).fetchall()
        except sqlite3.OperationalError:
            locations = []
        heroes = c.execute(
            """
            SELECT id, name, user_id,
                   json_extract(sheet_json,'$.archetype') AS archetype,
                   json_extract(sheet_json,'$.level')     AS level
            FROM characters
            WHERE is_active = 1
              AND (name NOT LIKE '[SBX] %' OR name IS NULL)
              AND (name NOT LIKE '[SCN] %' OR name IS NULL)
            ORDER BY (user_id = 1) DESC, id DESC LIMIT 40
            """,
        ).fetchall()
    finally:
        if own:
            c.close()

    issue: dict[str, Any] | None = None
    if issue_number:
        fetcher = fetch_issue or _default_fetch_issue
        issue = fetcher(int(issue_number))

    ctx_lines = [
        "KATALOG WROGÓW (key | label | tier):",
        *[f"- {r['key']} | {r['label']} | {r['tier']}" for r in enemies],
        "",
        "KATALOG LOKACJI (key | label):",
        *[f"- {r['key']} | {r['label']}" for r in locations],
        "",
        "BOHATEROWIE (id | name | level | archetype | user_id):",
        *[f"- {r['id']} | {r['name']} | {r['level']} | {r['archetype']} | u{r['user_id']}"
          for r in heroes],
        "",
    ]
    if issue:
        ctx_lines += [f"GITHUB ISSUE #{issue['number']}: {issue['title']}", issue["body"] or "", ""]
    elif issue_number:
        ctx_lines += [f"(nie udało się pobrać issue #{issue_number} z GitHuba)", ""]
    if description:
        ctx_lines += ["OPIS/INSTRUKCJA ADMINA:", description]

    messages = [
        {"role": "system", "content": _DRAFT_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(ctx_lines)},
    ]

    raw = (llm or _default_llm)(messages)
    try:
        parsed = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, TypeError) as e:
        raise ScenarioError(f"LLM nie zwrócił poprawnego JSON: {e}") from e

    setup = dict(parsed.get("setup") or {})

    # guard: scene_enemies only from the catalog — hallucinated keys are cut
    # and recorded in agent_notes so the admin sees the assumption.
    known = {r["key"] for r in enemies}
    wanted = list(setup.get("scene_enemies") or [])
    kept = [k for k in wanted if k in known]
    dropped = [k for k in wanted if k not in known]
    setup["scene_enemies"] = kept
    if dropped:
        note = str(setup.get("agent_notes") or "")
        setup["agent_notes"] = (note + ("; " if note else "")
                                + f"usunięto nieznane klucze wrogów: {', '.join(dropped)}")

    return {
        "reply": str(parsed.get("reply") or ""),
        "setup": setup,
        "issue": issue,
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
