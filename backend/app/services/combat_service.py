"""
Phase 8A — Active combat state and resolution (solo, SQLite).

Combatant runtime JSON uses hp_current / hp_max; character sheet uses current_hp / max_hp.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.dice import parse_character_sheet, roll_d20

# Tests may monkeypatch this to a temp file path.
COMBAT_DB_PATH = "/data/ai_gm.db"

logger = get_logger(__name__)


def _log_dice_roll_combat_resolve(
    *,
    source: str,
    campaign_id: int,
    result_total: int,
    dc: int,
    hit: bool,
    raw_d20: int | None,
) -> None:
    """Loki-friendly ``dice_roll`` with DC and outcome (Combat System 2 — step 8.2)."""
    if raw_d20 is not None:
        r = int(raw_d20)
        if r == 20:
            outcome = "critical_hit"
        elif r == 1:
            outcome = "critical_miss"
        else:
            outcome = "hit" if hit else "miss"
    else:
        outcome = "hit" if hit else "miss"
    logger.info(
        "dice_roll",
        roll_type="1d20",
        result=int(result_total),
        dc=int(dc),
        outcome=outcome,
        source=source,
        campaign_id=int(campaign_id),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(COMBAT_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _stat_mod(sheet: dict, stat: str) -> int:
    stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
    v = int(stats.get(stat, 10) or 10)
    return (v - 10) // 2


def _player_ac_from_sheet(sheet: dict) -> int:
    d = sheet.get("defense")
    if isinstance(d, dict) and d.get("base") is not None:
        return int(d["base"])
    return 10 + _stat_mod(sheet, "DEX")


def _player_hp_pair(sheet: dict) -> tuple[int, int]:
    cur = int(sheet.get("current_hp", 0) or 0)
    mx = int(sheet.get("max_hp", cur) or cur)
    return cur, max(mx, 1)


def _ability_stats_seven(sheet: dict) -> dict[str, int]:
    """STR–CHA from sheet.stats plus speed (7 numeric fields for combat snapshot)."""
    raw = sheet.get("stats")
    stats = raw if isinstance(raw, dict) else {}
    out: dict[str, int] = {}
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        try:
            out[k] = int(stats.get(k, 10) or 10)
        except (TypeError, ValueError):
            out[k] = 10
    try:
        out["speed"] = int(sheet.get("speed", stats.get("speed", 30)) or 30)
    except (TypeError, ValueError):
        out["speed"] = 30
    return out


def roll_damage_dice(expr: str, mod: int = 0) -> int:
    """Roll NdM + mod; expr like '1d8', 'd6', '2d6'."""
    raw = (expr or "1d4").strip().lower()
    m = re.match(r"^(\d*)d(\d+)$", raw)
    if not m:
        return max(0, mod)
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    total = sum(random.randint(1, sides) for _ in range(max(1, n)))
    return max(0, total + mod)


def _weapon_key_from_sheet(sheet: dict) -> str | None:
    w = sheet.get("equipped_weapon")
    if w:
        return str(w).strip()
    eq = sheet.get("equipped")
    if isinstance(eq, dict):
        if eq.get("weapon_key"):
            return str(eq["weapon_key"]).strip()
    return None


def _load_weapon_row(conn: sqlite3.Connection, key: str | None) -> sqlite3.Row | None:
    if not key:
        return None
    return conn.execute(
        "SELECT key, label, damage_die, linked_stat FROM game_config_weapons WHERE key = ?",
        (key,),
    ).fetchone()


def _default_weapon_key(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT key FROM game_config_weapons ORDER BY key ASC LIMIT 1",
    ).fetchone()
    return str(row["key"]) if row else None


def _enemy_slug(key: str, index: int) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", (key or "enemy").lower())
    return f"{safe}_{index:02d}"


def _fetch_enemy_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, dex_modifier,
               loot_table_key, drop_chance
        FROM game_config_enemies
        WHERE key = ?
        """,
        (key,),
    ).fetchone()


def _infer_template_key_from_combatant_slug(combatant_id: str) -> str | None:
    """Combatant id like bandit_01 → template key bandit (matches initiate_combat slugging)."""
    s = (combatant_id or "").strip()
    m = re.match(r"^(.+)_(\d{2})$", s, re.I)
    if not m:
        return None
    base = m.group(1).strip().strip("_")
    return base.lower() if base else None


def _roll_card_enemy_identity(
    conn: sqlite3.Connection, enemy: dict, combatant_id: str
) -> tuple[str, str]:
    """
    Canonical enemy_key + display name for API / COMBAT_ROLL cards (game_config_enemies.label).
    Repairs legacy/generic combatant.enemy_key (e.g. \"enemy\") using slug inference.
    """
    ek = str(enemy.get("enemy_key") or "").strip()
    nm = str(enemy.get("name") or "").strip()

    def from_row(r: sqlite3.Row) -> tuple[str, str]:
        k = str(r["key"])
        lab = str(r["label"] or r["key"] or "").strip() or k
        return k, lab

    candidates: list[str] = []
    if ek and ek.lower() != "enemy":
        candidates.append(ek)
    inferred = _infer_template_key_from_combatant_slug(combatant_id)
    if inferred:
        candidates.append(inferred)

    seen: set[str] = set()
    for cand in candidates:
        cl = cand.lower()
        if cl in seen:
            continue
        seen.add(cl)
        row = _fetch_enemy_row(conn, cand)
        if row:
            return from_row(row)

    if inferred:
        return inferred, nm or "Nieznany wróg"
    if ek and ek.lower() != "enemy":
        return ek, nm or "Nieznany wróg"
    return (inferred or ek or "unknown"), nm or "Nieznany wróg"


def _parse_loot_pool_column(raw: Any) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _read_loot_pool_from_row(row: sqlite3.Row) -> list[dict[str, Any]]:
    if "loot_pool" not in row.keys():
        return []
    return _parse_loot_pool_column(row["loot_pool"])


def _row_to_combat_dict(row: sqlite3.Row) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "character_id": row["character_id"],
        "round": int(row["round"] or 1),
        "turn_order": json.loads(row["turn_order"] or "[]"),
        "current_turn": row["current_turn"],
        "combatants": json.loads(row["combatants"] or "[]"),
        "status": row["status"],
        "ended_reason": row["ended_reason"],
        "location_tag": row["location_tag"] if "location_tag" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if "loot_pool" in row.keys():
        d["loot_pool"] = _read_loot_pool_from_row(row)
    return d


def load_combat_snapshot(campaign_id: int) -> dict[str, Any] | None:
    """Latest combat row for campaign (any status), or None."""
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_combat WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            return _row_to_combat_dict(row)
    except sqlite3.OperationalError:
        return None


def get_active_combat(campaign_id: int) -> dict[str, Any] | None:
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            return _row_to_combat_dict(row)
    except sqlite3.OperationalError:
        return None


def get_enemy_catalog_for_prompt(conn: sqlite3.Connection) -> str:
    """
    Plain-text list of active enemies for system prompt injection (DB-driven keys).
    Returns "" if none or on read errors.
    """
    max_chars = 1500
    try:
        rows = conn.execute(
            """
            SELECT key, label, hp_base, damage_die, attack_bonus
            FROM game_config_enemies
            WHERE is_active = 1
            ORDER BY hp_base ASC, key ASC
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return ""
    if not rows:
        return ""
    header = (
        "Dostępni wrogowie w tym świecie (używaj ich kluczy w [COMBAT_START:]):\n"
        "Lista pochodzi z bazy — preferuj te klucze zamiast wyłącznie przykładów ze statycznego promptu."
    )
    lines: list[str] = [header]
    for row in rows:
        key = str(row["key"])
        label = str(row["label"] or key)
        hp = int(row["hp_base"] or 0)
        die = str(row["damage_die"] or "1d4")
        atk = int(row["attack_bonus"] if row["attack_bonus"] is not None else 0)
        sign = "+" if atk >= 0 else ""
        lines.append(f"- {key} ({label}) — HP: {hp}, atak: {die}{sign}{atk}")
    out = "\n".join(lines)
    if len(out) <= max_chars:
        return out
    trimmed = out[: max_chars - 40].rstrip()
    return f"{trimmed}\n\n[... skrócono listę wrogów do {max_chars} znaków ...]"


def get_combat_context_for_prompt(campaign_id: int) -> str | None:
    st = get_active_combat(campaign_id)
    if not st or st.get("status") != "active":
        return None
    lines = [
        f"== ACTIVE COMBAT (Round {st['round']}) ==",
        f"Turn: {st['current_turn']}",
        "Combatants:",
    ]
    for c in st.get("combatants") or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "?")
        name = c.get("name", "?")
        hp_c = c.get("hp_current", 0)
        hp_m = c.get("hp_max", 0)
        df = c.get("defense", 0)
        cond = c.get("conditions") or []
        cond_s = ", ".join(str(x) for x in cond) if cond else "[]"
        lines.append(f"- {name} [{cid}]: HP {hp_c}/{hp_m}, DEF {df}, Conditions: {cond_s}")
    lines.append(
        "Rules: player attacks when it is their turn. Enemy attacks resolve after the player "
        "when using the enemy-turn endpoint. DO NOT invent HP values — use only this block."
    )
    return "\n".join(lines)


def log_combat_turn(
    conn: sqlite3.Connection,
    *,
    combat_id: int,
    campaign_id: int,
    turn_number: float,
    actor: str,
    event_type: str,
    roll_value: int | None = None,
    damage: int | None = None,
    hp_after: int | None = None,
    target_id: str | None = None,
    target_name: str | None = None,
    hit: bool | None = None,
    narrative: str | None = None,
) -> None:
    hit_sql: int | None
    if hit is None:
        hit_sql = None
    else:
        hit_sql = 1 if hit else 0
    conn.execute(
        """
        INSERT INTO combat_turns (
            combat_id, campaign_id, turn_number, actor, event_type,
            roll_value, damage, hp_after, target_id, target_name, hit, narrative
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            combat_id,
            campaign_id,
            turn_number,
            actor,
            event_type,
            roll_value,
            damage,
            hp_after,
            target_id,
            target_name,
            hit_sql,
            narrative,
        ),
    )


def _next_combat_log_sequence(conn: sqlite3.Connection, combat_id: int) -> float:
    row = conn.execute(
        "SELECT MAX(turn_number) AS m FROM combat_turns WHERE combat_id = ?",
        (combat_id,),
    ).fetchone()
    mx = row["m"]
    base = float(mx) if mx is not None else 0.0
    return base + 0.001


def _log_combat_end_event(conn: sqlite3.Connection, row: sqlite3.Row, reason: str) -> None:
    cid = int(row["id"])
    camp = int(row["campaign_id"])
    tn = _next_combat_log_sequence(conn, cid)
    evt = "flee" if reason == "fled" else "end"
    log_combat_turn(
        conn,
        combat_id=cid,
        campaign_id=camp,
        turn_number=tn,
        actor="system",
        event_type=evt,
        narrative=f"Walka zakończona: {reason}",
    )
    logger.info(
        "combat_ended",
        combat_id=cid,
        campaign_id=camp,
        ended_reason=reason,
    )


def list_combat_turns_for_campaign(campaign_id: int, limit: int = 50) -> list[dict[str, Any]]:
    snap = load_combat_snapshot(campaign_id)
    if not snap:
        return []
    combat_id = int(snap["id"])
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM combat_turns
            WHERE combat_id = ?
            ORDER BY turn_number ASC, id ASC
            LIMIT ?
            """,
            (combat_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_combat_turns_context_for_prompt(campaign_id: int, last_n: int = 8) -> str | None:
    """Last N combat log rows for LLM (active combat only — caller should gate)."""
    st = get_active_combat(campaign_id)
    if not st or str(st.get("status") or "") != "active":
        return None
    combat_id = int(st["id"])
    with _conn() as conn:
        try:
            rows = conn.execute(
                """
                SELECT actor, event_type, roll_value, damage, hp_after, target_name, hit, narrative
                FROM combat_turns
                WHERE combat_id = ?
                ORDER BY turn_number DESC, id DESC
                LIMIT ?
                """,
                (combat_id, last_n),
            ).fetchall()
        except sqlite3.OperationalError:
            return None
    if not rows:
        return None
    lines = ["== HISTORIA WALKI (ostatnie zdarzenia w silniku) =="]
    for r in reversed(rows):
        h = r["hit"]
        if h == 1:
            hit_str = "TRAFIENIE"
        elif h == 0:
            hit_str = "PUDŁO"
        else:
            hit_str = ""
        dmg = r["damage"]
        hp_a = r["hp_after"]
        dmg_part = ""
        if dmg is not None and hp_a is not None:
            dmg_part = f", {dmg} obrażeń → HP po: {hp_a}"
        elif dmg is not None:
            dmg_part = f", {dmg} obrażeń"
        rv = r["roll_value"]
        rv_s = f"roll={rv}" if rv is not None else ""
        tgt = r["target_name"] or "?"
        lines.append(
            f"[{str(r['actor'] or '').upper()}] {r['event_type']} {rv_s} {hit_str}{dmg_part} cel={tgt}".strip()
        )
    return "\n".join(lines)


def _save_combat_row(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    character_id: int,
    round_n: int,
    turn_order: list[str],
    current_turn: str,
    combatants: list[dict],
    status: str = "active",
    ended_reason: str | None = None,
    location_tag: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO active_combat (
          campaign_id, character_id, round, turn_order, current_turn, combatants,
          status, ended_reason, location_tag, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(campaign_id) DO UPDATE SET
          character_id = excluded.character_id,
          round = excluded.round,
          turn_order = excluded.turn_order,
          current_turn = excluded.current_turn,
          combatants = excluded.combatants,
          status = excluded.status,
          ended_reason = excluded.ended_reason,
          location_tag = excluded.location_tag,
          updated_at = excluded.updated_at
        """,
        (
            campaign_id,
            character_id,
            round_n,
            json.dumps(turn_order, ensure_ascii=False),
            current_turn,
            json.dumps(combatants, ensure_ascii=False),
            status,
            ended_reason,
            location_tag,
            _now_iso(),
        ),
    )


def initiate_combat(campaign_id: int, character_id: int, enemy_keys: list[str]) -> dict[str, Any]:
    if not enemy_keys:
        raise ValueError("enemy_keys required")

    with _conn() as conn:
        camp = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not camp:
            raise ValueError("campaign not found")

        ch = conn.execute(
            "SELECT id, name, sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (character_id, campaign_id),
        ).fetchone()
        if not ch:
            raise ValueError("character not found")

        sheet = parse_character_sheet(ch["sheet_json"])
        hp_cur, hp_max = _player_hp_pair(sheet)
        ac = _player_ac_from_sheet(sheet)
        dex_mod = _stat_mod(sheet, "DEX")
        init_player = roll_d20() + dex_mod
        ability_stats = _ability_stats_seven(sheet)

        combatants: list[dict[str, Any]] = [
            {
                "id": "player",
                "type": "player",
                "name": (ch["name"] or "Hero").strip(),
                "hp_current": hp_cur,
                "hp_max": hp_max,
                "defense": ac,
                "stats": ability_stats,
                "initiative_roll": init_player,
                "conditions": [],
            }
        ]

        resolved_enemies: list[tuple[str, sqlite3.Row]] = []
        for ek in enemy_keys:
            er = _fetch_enemy_row(conn, ek)
            if not er:
                logger.warning(
                    "combat_unknown_enemy_key",
                    enemy_key=ek,
                    campaign_id=campaign_id,
                    message="[COMBAT] unknown enemy key, skipping",
                )
                continue
            resolved_enemies.append((ek, er))

        if not resolved_enemies:
            raise ValueError("no valid enemy keys after filtering unknown templates")

        turn_slots: list[tuple[str, int, int]] = [("player", init_player, 0)]
        idx = 0
        for ek, er in resolved_enemies:
            idx += 1
            slug = _enemy_slug(ek, idx)
            hp_max_e = int(er["hp_base"] or 1)
            ac_e = int(er["ac_base"] or 10)
            dex_e_mod = int(er["dex_modifier"] or 0)
            init_e = roll_d20() + dex_e_mod
            combatants.append(
                {
                    "id": slug,
                    "type": "enemy",
                    "enemy_key": er["key"],
                    "name": (er["label"] or er["key"]).strip(),
                    "hp_current": hp_max_e,
                    "hp_max": hp_max_e,
                    "defense": ac_e,
                    "attack_bonus": int(er["attack_bonus"] or 0),
                    "dex_modifier": int(er["dex_modifier"] or 0),
                    "damage_dice": (er["damage_die"] or "1d6").strip().lower(),
                    "damage_stat": "STR",
                    "initiative_roll": init_e,
                    "conditions": [],
                    "loot_table_key": er["loot_table_key"],
                    "drop_chance": float(er["drop_chance"] if er["drop_chance"] is not None else 1.0),
                }
            )
            turn_slots.append((slug, init_e, idx))

        # Sort: highest initiative first; ties: player wins (lower tie-break value sorts first after negating init)
        turn_slots.sort(key=lambda t: (-t[1], 0 if t[0] == "player" else 1))
        turn_order = [t[0] for t in turn_slots]
        current = turn_order[0] if turn_order else "player"

        conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        _save_combat_row(
            conn,
            campaign_id,
            character_id=character_id,
            round_n=1,
            turn_order=turn_order,
            current_turn=current,
            combatants=combatants,
            status="active",
            ended_reason=None,
            location_tag=None,
        )
        conn.commit()

        id_row = conn.execute(
            "SELECT id FROM active_combat WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if id_row:
            combat_id_int = int(id_row["id"])
            log_combat_turn(
                conn,
                combat_id=combat_id_int,
                campaign_id=campaign_id,
                turn_number=0.0,
                actor="system",
                event_type="start",
                narrative=f"Walka rozpoczęta. Wrogowie: {', '.join(k for k, _ in resolved_enemies)}",
            )
            for actor_id, init_total, _tie in turn_slots:
                tn = _next_combat_log_sequence(conn, combat_id_int)
                log_combat_turn(
                    conn,
                    combat_id=combat_id_int,
                    campaign_id=campaign_id,
                    turn_number=tn,
                    actor=str(actor_id),
                    event_type="initiative",
                    roll_value=int(init_total),
                    narrative=f"Inicjatywa: {actor_id} → wynik {int(init_total)}",
                )
        conn.commit()

    out = get_active_combat(campaign_id)
    if not out:
        raise RuntimeError("failed to load combat after insert")
    started_keys = [k for k, _ in resolved_enemies]
    logger.info(
        "combat_start",
        campaign_id=campaign_id,
        enemy=",".join(started_keys),
        enemy_keys=started_keys,
        combat_id=out.get("id"),
    )
    return out


def _find_combatant(combatants: list[dict], cid: str) -> dict | None:
    for c in combatants:
        if c.get("id") == cid:
            return c
    return None


def _living_enemy_ids(combatants: list[dict]) -> list[str]:
    out = []
    for c in combatants:
        if c.get("type") != "enemy":
            continue
        if int(c.get("hp_current", 0) or 0) > 0:
            out.append(str(c["id"]))
    return out


def _all_enemies_dead(combatants: list[dict]) -> bool:
    for c in combatants:
        if c.get("type") != "enemy":
            continue
        if int(c.get("hp_current", 0) or 0) > 0:
            return False
    return True


def compute_player_attack_dodge_outcome(
    attack_total: int,
    dodge_roll_raw: int,
    dex_modifier: int,
    player_raw_d20: int | None,
) -> tuple[bool, bool, int]:
    """
    Player attack total vs enemy d20+dex dodge. Returns (dodged, hit, dodge_total).
    nat1: auto miss (no hit). nat20: auto hit (not dodged). Else: defender wins ties
    (dodged when dodge_total >= attack_total).
    """
    dodge_total = int(dodge_roll_raw) + int(dex_modifier or 0)
    atk = int(attack_total)
    if player_raw_d20 is not None:
        pr = int(player_raw_d20)
        if pr == 1:
            return True, False, dodge_total
        if pr == 20:
            return False, True, dodge_total
    dodged = dodge_total >= atk
    return dodged, (not dodged), dodge_total


def resolve_attack(
    campaign_id: int,
    roll_result: int,
    attacker: str = "player",
    raw_d20: int | None = None,
) -> dict[str, Any]:
    """
    attacker: 'player' uses roll_result as total attack vs enemy dodge roll.
    attacker: 'enemy' ignores roll_result; rolls d20+attack_bonus internally vs player AC.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")

        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        loot_pool_accum: list[dict[str, Any]] = _read_loot_pool_from_row(row)
        ch_id = int(row["character_id"])
        character = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id = ?",
            (ch_id,),
        ).fetchone()
        if not character:
            raise ValueError("character missing")

        sheet = parse_character_sheet(character["sheet_json"])
        out: dict[str, Any] = {"attacker": attacker, "hit": False}

        if attacker == "player":
            living = _living_enemy_ids(combatants)
            if not living:
                out["message"] = "no living enemies"
                out["combat_state"] = _row_to_combat_dict(row)
                return out

            order = json.loads(row["turn_order"] or "[]")
            target_id = None
            for tid in order:
                if tid in living:
                    target_id = tid
                    break
            if not target_id:
                target_id = living[0]

            enemy = _find_combatant(combatants, target_id)
            if not enemy:
                raise ValueError("enemy combatant missing")

            card_key, card_name = _roll_card_enemy_identity(conn, enemy, str(target_id))
            old_ek = str(enemy.get("enemy_key") or "").strip().lower()
            if old_ek in ("", "enemy"):
                enemy["enemy_key"] = card_key
            old_nm = str(enemy.get("name") or "").strip().lower()
            if old_nm in ("", "wróg", "wrog", "enemy"):
                enemy["name"] = card_name

            player_raw = int(raw_d20) if raw_d20 is not None else None
            player_nat20 = player_raw == 20
            player_nat1 = player_raw == 1
            dodge_roll: dict[str, Any] | None = None
            dodged = False
            hit = False
            if player_nat1:
                hit = False
                dodged = True
            else:
                raw_dodge = roll_d20()
                dex_mod = int(enemy.get("dex_modifier") or 0)
                dodged, hit, dodge_total = compute_player_attack_dodge_outcome(
                    int(roll_result),
                    int(raw_dodge),
                    dex_mod,
                    player_raw,
                )
                dodge_roll = {
                    "raw": raw_dodge,
                    "modifier": dex_mod,
                    "total": dodge_total,
                    "dodged": dodged,
                    "player_roll": int(roll_result),
                    "verdict": (
                        "hit"
                        if player_nat20
                        else (
                            "perfect_dodge"
                            if raw_dodge == 20
                            else (
                                "fumble_dodge"
                                if raw_dodge == 1
                                else ("dodged" if dodged else "hit")
                            )
                        )
                    ),
                }
            out["hit"] = hit
            out["dodged"] = dodged
            out["target_id"] = target_id
            out["target_name"] = card_name
            out["enemy_key"] = card_key
            out["attack_total"] = int(roll_result)
            out["player_raw_d20"] = player_raw
            out["player_nat20"] = player_nat20
            out["player_nat1"] = player_nat1
            if dodge_roll is not None:
                out["dodge_roll"] = dodge_roll

            enemy_ac = int(enemy.get("defense", 0) or 0)
            _log_dice_roll_combat_resolve(
                source="combat_attack",
                campaign_id=campaign_id,
                result_total=int(roll_result),
                dc=enemy_ac,
                hit=bool(hit),
                raw_d20=player_raw,
            )

            loot: list[dict] = []
            dmg = 0
            if hit:
                wkey = _weapon_key_from_sheet(sheet) or _default_weapon_key(conn)
                wrow = _load_weapon_row(conn, wkey)
                die = "1d6"
                stat = "STR"
                if wrow:
                    die = (wrow["damage_die"] or "1d6").strip().lower()
                    stat = (wrow["linked_stat"] or "STR").upper()
                mod = _stat_mod(sheet, stat)
                dmg = roll_damage_dice(die, mod)
                out["damage"] = dmg
                prev_hp = int(enemy.get("hp_current", 0) or 0)
                next_hp = max(0, prev_hp - dmg)
                enemy["hp_current"] = next_hp
                out["target_hp_remaining"] = next_hp
                dead = next_hp <= 0
                out["enemy_dead"] = dead
                if dead:
                    enemy["dead"] = True
                    ek = str(enemy.get("enemy_key") or "")
                    if ek:
                        from app.services.game_engine import resolve_enemy_loot

                        loot = resolve_enemy_loot(ek)
                    else:
                        loot = []
                    out["loot"] = loot
                    loot_pool_accum.extend(loot)
                    cid_death = int(row["id"])
                    death_tn = _next_combat_log_sequence(conn, cid_death)
                    ename = str(enemy.get("name") or card_name or "Wróg")
                    log_combat_turn(
                        conn,
                        combat_id=cid_death,
                        campaign_id=campaign_id,
                        turn_number=death_tn,
                        actor=str(target_id),
                        event_type="death",
                        roll_value=None,
                        damage=int(out.get("damage") or 0),
                        hp_after=int(enemy.get("hp_current", 0) or 0),
                        target_id=target_id,
                        target_name=str(enemy.get("name") or "") or None,
                        hit=None,
                        narrative=f"{ename} pada — wróg nie żyje.",
                    )
                    if _all_enemies_dead(combatants):
                        cid = int(row["id"])
                        tn = _next_combat_log_sequence(conn, cid)
                        log_combat_turn(
                            conn,
                            combat_id=cid,
                            campaign_id=campaign_id,
                            turn_number=tn,
                            actor="player",
                            event_type="attack",
                            roll_value=int(roll_result),
                            damage=int(out.get("damage") or 0),
                            hp_after=int(enemy.get("hp_current", 0) or 0),
                            target_id=target_id,
                            target_name=str(enemy.get("name") or "") or None,
                            hit=True,
                            narrative=None,
                        )
                        _persist_combatants_and_maybe_end(
                            conn,
                            row,
                            combatants,
                            status="ended",
                            ended_reason="victory",
                            loot_pool=loot_pool_accum,
                        )
                        conn.commit()
                        out["combat_state"] = load_combat_snapshot(campaign_id)
                        return out
            else:
                out["damage"] = 0
                out["target_hp_remaining"] = int(enemy.get("hp_current", 0) or 0)
                out["enemy_dead"] = False
                out["loot"] = []

            cid = int(row["id"])
            tn = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn,
                combat_id=cid,
                campaign_id=campaign_id,
                turn_number=tn,
                actor="player",
                event_type="attack",
                roll_value=int(roll_result),
                damage=int(out.get("damage") or 0),
                hp_after=int(enemy.get("hp_current", 0) or 0),
                target_id=target_id,
                target_name=str(enemy.get("name") or "") or None,
                hit=bool(hit),
                narrative=None,
            )

            _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
            conn.commit()
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

        # enemy attacks player
        if attacker != "enemy":
            raise ValueError("invalid attacker")

        order = json.loads(row["turn_order"] or "[]")
        cur = row["current_turn"]
        if str(cur) == "player":
            out["message"] = "enemy attack only when current turn is an enemy"
            out["combat_state"] = _row_to_combat_dict(row)
            return out

        enemy = _find_combatant(combatants, str(cur))
        if not enemy or enemy.get("type") != "enemy":
            raise ValueError("current turn is not a valid enemy")

        raw = roll_d20()
        atk_b = int(enemy.get("attack_bonus") or 0)
        attack_roll = raw + atk_b
        p = _find_combatant(combatants, "player")
        if not p:
            raise ValueError("player combatant missing")
        pac = int(p.get("defense", _player_ac_from_sheet(sheet)))
        p["defense"] = pac
        hit = attack_roll >= pac
        out["hit"] = hit
        out["attack_roll"] = attack_roll
        out["raw_d20"] = raw
        out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip()
        out["target_ac"] = pac

        _log_dice_roll_combat_resolve(
            source="combat_enemy",
            campaign_id=campaign_id,
            result_total=int(attack_roll),
            dc=int(pac),
            hit=bool(hit),
            raw_d20=int(raw),
        )

        dmg = 0
        if hit:
            expr = (enemy.get("damage_dice") or "1d6").strip().lower()
            dmg = roll_damage_dice(expr, 0)
            out["damage"] = dmg
            prev = int(p.get("hp_current", 0) or 0)
            next_hp = max(0, prev - dmg)
            p["hp_current"] = next_hp
            sheet["current_hp"] = next_hp
            out["player_hp_remaining"] = next_hp
            incap = next_hp <= 0
            out["player_incapacitated"] = incap
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), ch_id),
            )
        else:
            out["damage"] = 0
            out["player_hp_remaining"] = int(p.get("hp_current", 0) or 0)
            out["player_incapacitated"] = False

        cid = int(row["id"])
        tn = _next_combat_log_sequence(conn, cid)
        log_combat_turn(
            conn,
            combat_id=cid,
            campaign_id=campaign_id,
            turn_number=tn,
            actor="enemy",
            event_type="attack",
            roll_value=int(attack_roll),
            damage=int(out.get("damage") or 0),
            hp_after=int(p.get("hp_current", 0) or 0),
            target_id="player",
            target_name=str(p.get("name") or "Gracz"),
            hit=bool(hit),
            narrative=json.dumps(
                {
                    "raw_d20": int(raw),
                    "attack_roll": int(attack_roll),
                    "target_ac": int(pac),
                    "enemy_name": str(enemy.get("name") or enemy.get("enemy_key") or "Wróg"),
                },
                ensure_ascii=False,
            ),
        )

        _persist_combatants(conn, row, combatants)
        conn.commit()
        out["combat_state"] = load_combat_snapshot(campaign_id)

    if attacker == "enemy" and out.get("player_incapacitated"):
        end_combat(campaign_id, "player_dead", defeated_by=out.get("enemy_name"))
        out["defeated_by"] = out.get("enemy_name")
        out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def resolve_player_attack(
    campaign_id: int,
    roll_result: int,
    raw_d20: int | None = None,
) -> dict[str, Any]:
    """Step 4.1 — alias for :func:`resolve_attack` with ``attacker='player'`` (dodge, damage, HP)."""
    return resolve_attack(campaign_id, roll_result, attacker="player", raw_d20=raw_d20)


def resolve_enemy_attack(
    campaign_id: int,
    roll_result: int | None = None,
    raw_d20: int | None = None,
) -> dict[str, Any]:
    """Step 4.2 — alias for :func:`resolve_attack` with ``attacker='enemy'``. ``roll_result`` / ``raw_d20`` ignored."""
    _ = (roll_result, raw_d20)
    return resolve_attack(campaign_id, 0, attacker="enemy", raw_d20=None)


def _persist_combatants(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    combatants: list[dict],
    *,
    loot_pool: list[dict[str, Any]] | None = None,
) -> None:
    if loot_pool is not None and "loot_pool" in row.keys():
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, loot_pool = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (
                json.dumps(combatants, ensure_ascii=False),
                json.dumps(loot_pool, ensure_ascii=False),
                _now_iso(),
                row["campaign_id"],
            ),
        )
    else:
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (json.dumps(combatants, ensure_ascii=False), _now_iso(), row["campaign_id"]),
        )


def _persist_combatants_and_maybe_end(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    combatants: list[dict],
    *,
    status: str,
    ended_reason: str | None,
    loot_pool: list[dict[str, Any]] | None = None,
) -> None:
    if loot_pool is not None and "loot_pool" in row.keys():
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, status = ?, ended_reason = ?, loot_pool = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (
                json.dumps(combatants, ensure_ascii=False),
                status,
                ended_reason,
                json.dumps(loot_pool, ensure_ascii=False),
                _now_iso(),
                row["campaign_id"],
            ),
        )
    else:
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, status = ?, ended_reason = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (
                json.dumps(combatants, ensure_ascii=False),
                status,
                ended_reason,
                _now_iso(),
                row["campaign_id"],
            ),
        )
    if str(status) == "ended":
        _log_combat_end_event(conn, row, str(ended_reason or "ended"))


def get_current_actor(conn: sqlite3.Connection | None, campaign_id: int) -> str | None:
    """Step 3.2 — whose turn: ``active_combat.current_turn`` (conn unused; combat DB is separate)."""
    _ = conn
    st = get_active_combat(campaign_id)
    if not st:
        return None
    ct = st.get("current_turn")
    if ct is None or str(ct).strip() == "":
        return None
    return str(ct)


def is_combat_active(conn: sqlite3.Connection | None, campaign_id: int) -> bool:
    """Step 3.2 — True if there is active combat for this campaign."""
    _ = conn
    return get_active_combat(campaign_id) is not None


def _advance_turn_impl(campaign_id: int) -> str:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")

        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        order: list[str] = json.loads(row["turn_order"] or "[]")
        if _all_enemies_dead(combatants):
            _persist_combatants_and_maybe_end(conn, row, combatants, status="ended", ended_reason="victory")
            conn.commit()
            return "ended"

        living: list[str] = []
        for tid in order:
            c = _find_combatant(combatants, tid)
            if not c:
                continue
            if int(c.get("hp_current", 0) or 0) <= 0:
                continue
            living.append(tid)

        if len(living) <= 1:
            _persist_combatants_and_maybe_end(conn, row, combatants, status="ended", ended_reason="victory")
            conn.commit()
            return "ended"

        cur = row["current_turn"]
        rnd = int(row["round"] or 1)
        cur_s = str(cur)
        if cur_s in living:
            i = living.index(cur_s)
        else:
            i = -1
        next_i = (i + 1) % len(living)
        new_turn = living[next_i]
        first_in_order = order[0] if order else living[0]
        if str(cur) != str(first_in_order) and str(new_turn) == str(first_in_order):
            rnd += 1

        conn.execute(
            """
            UPDATE active_combat
            SET current_turn = ?, round = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (new_turn, rnd, _now_iso(), campaign_id),
        )
        conn.commit()
        return str(new_turn)


def advance_turn(
    first: int | sqlite3.Connection | None,
    second: int | None = None,
) -> str | None:
    """
    Step 3.2 — advance to next living actor; bump ``round`` after a full cycle.

    - Legacy: ``advance_turn(campaign_id: int) -> str`` (raises ``ValueError`` if no combat).
    - Doc API: ``advance_turn(conn, campaign_id) -> str | None`` — ``conn`` is reserved for
      callers sharing a narrative DB handle; combat state still uses ``COMBAT_DB_PATH``.
      Returns ``None`` if there is no active combat (instead of raising).
    """
    if second is None:
        if not isinstance(first, int):
            raise TypeError("advance_turn(campaign_id): campaign_id must be int")
        return _advance_turn_impl(first)
    if not isinstance(second, int):
        raise TypeError("advance_turn(conn, campaign_id): campaign_id must be int")
    if first is not None and not isinstance(first, sqlite3.Connection):
        raise TypeError("advance_turn(conn, campaign_id): conn must be sqlite3.Connection or None")
    try:
        return _advance_turn_impl(second)
    except ValueError:
        return None


def end_combat(campaign_id: int, reason: str, *, defeated_by: str | None = None) -> None:
    """End combat row (``status='ended'``, ``ended_reason``). For ``player_dead``, also ends solo campaign via :func:`solo_death_service.end_solo_campaign_on_death`."""
    char_id: int | None = None
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM active_combat
            WHERE campaign_id = ? AND status = 'active'
            """,
            (campaign_id,),
        ).fetchone()
        if row:
            _log_combat_end_event(conn, row, reason)
            char_id = int(row["character_id"])
        conn.execute(
            """
            UPDATE active_combat
            SET status = 'ended', ended_reason = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (reason, _now_iso(), campaign_id),
        )
        conn.commit()

    if reason != "player_dead" or char_id is None:
        return

    from app.services.admin_config import DB_PATH
    from app.services.solo_death_service import end_solo_campaign_on_death

    label = (defeated_by or "").strip() or "wróg"
    death_reason = f"Poległ w walce z: {label}"

    nconn: sqlite3.Connection | None = None
    try:
        nconn = sqlite3.connect(DB_PATH)
        nconn.row_factory = sqlite3.Row
        ch = nconn.execute(
            """
            SELECT id, name, sheet_json, user_id FROM characters
            WHERE id = ? AND campaign_id = ?
            """,
            (char_id, campaign_id),
        ).fetchone()
        if not ch:
            logger.warning(
                "combat_player_dead_no_character",
                campaign_id=campaign_id,
                character_id=char_id,
            )
            return
        camp = nconn.execute(
            "SELECT status FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if camp and str(camp["status"] or "").lower() == "ended":
            return
        end_solo_campaign_on_death(
            nconn,
            campaign_id=campaign_id,
            character_row=ch,
            death_reason=death_reason,
        )
    except Exception as e:
        logger.error(
            "combat_player_dead_solo_death_failed",
            campaign_id=campaign_id,
            error_message=str(e),
            exc_info=True,
        )
    finally:
        if nconn is not None:
            nconn.close()
