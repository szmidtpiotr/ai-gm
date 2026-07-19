"""
Resurrection Service — Stage 11 (issue #64, redesigned global config)

Config is GLOBAL (one setting for all players), stored as JSON in
game_config_meta key='resurrection_config'. Admins set it once in the
System panel → Resurrection tab. Each user's individual "lives remaining"
is still tracked per-user in users.resurrection_uses_remaining.

Cost modes
----------
xp_revert         — claw back the last N XP grants until ≥ cost_value XP is
                    reverted; recompute level; revoke any skill ranks /
                    spells / arcane-point spends made above the new level.
gold_percent      — lose cost_value % of current gold.
gold_recent_days  — sum gold *gains* in the last cost_value game days, then
                    lose min(that_sum, current_gold * cap_percent / 100).
                    Only positive deltas counted; expenses are not charged.
item_loss         — remove one randomly chosen equipped functional item
                    (weapon / armor with DR>0 / consumable with effect_json).
                    Quest-marked items excluded. If pool empty → free.
admin_free        — no cost (default).

All modes share these post-revive effects:
- HP restored to max_hp // 2
- status flips 'dead' → 'active'
- death_saves_failed, short_rests_used reset to 0
- dungeon cooldowns wiped (character_dungeon_runs rows deleted)
- resurrection_uses_remaining decremented if not NULL
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from typing import Any

import structlog
from app.services.combat_service import is_combat_active, end_combat
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

logger = structlog.get_logger()

VALID_MODES = (
    "xp_revert",
    "gold_percent",
    "gold_recent_days",
    "item_loss",
    "admin_free",
)


# ── Global config (game_config_meta key='resurrection_config') ───────────

_GLOBAL_CONFIG_KEY = "resurrection_config"
_GLOBAL_CONFIG_DEFAULT: dict[str, Any] = {
    "enabled": False,
    "mode": "admin_free",
    "value": 25,
    "cap_percent": 50,
    "default_uses": None,  # None = unlimited by default for every player
}


def get_global_resurrection_config(conn: sqlite3.Connection) -> dict[str, Any]:
    """Read the global resurrection config from game_config_meta."""
    row = conn.execute(
        "SELECT value FROM game_config_meta WHERE key = ?",
        (_GLOBAL_CONFIG_KEY,),
    ).fetchone()
    if not row or not row["value"]:
        return dict(_GLOBAL_CONFIG_DEFAULT)
    try:
        stored = json.loads(row["value"])
        cfg = dict(_GLOBAL_CONFIG_DEFAULT)
        cfg.update(stored)
        return cfg
    except (json.JSONDecodeError, TypeError):
        return dict(_GLOBAL_CONFIG_DEFAULT)


def set_global_resurrection_config(
    conn: sqlite3.Connection,
    *,
    enabled: bool | None = None,
    mode: str | None = None,
    value: int | None = None,
    cap_percent: int | None = None,
    default_uses: int | None | str = "__noop__",
) -> dict[str, Any]:
    """Upsert the global resurrection config in game_config_meta."""
    if mode is not None and mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Allowed: {VALID_MODES}")
    cfg = get_global_resurrection_config(conn)
    if enabled is not None:
        cfg["enabled"] = bool(enabled)
    if mode is not None:
        cfg["mode"] = mode
    if value is not None:
        cfg["value"] = int(value)
    if cap_percent is not None:
        cfg["cap_percent"] = max(0, min(100, int(cap_percent)))
    if default_uses != "__noop__":
        cfg["default_uses"] = None if default_uses is None else int(default_uses)
    conn.execute(
        """
        INSERT INTO game_config_meta (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (_GLOBAL_CONFIG_KEY, json.dumps(cfg, ensure_ascii=False)),
    )
    conn.commit()
    return cfg


# ── Per-user uses_remaining helper ────────────────────────────────────────


def get_user_uses_remaining(user_id: int, conn: sqlite3.Connection) -> int | None:
    """Return this user's resurrection_uses_remaining (None = unlimited)."""
    row = conn.execute(
        "SELECT resurrection_uses_remaining FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise LookupError(f"User {user_id} not found")
    return row["resurrection_uses_remaining"]


def set_user_uses_remaining(
    user_id: int, conn: sqlite3.Connection, uses: int | None
) -> int | None:
    """Set per-user resurrection uses_remaining. None = unlimited."""
    conn.execute(
        "UPDATE users SET resurrection_uses_remaining = ? WHERE id = ?",
        (uses, user_id),
    )
    conn.commit()
    return uses


# Legacy compat shim — kept so existing tests and admin endpoints that
# call get_user_resurrection_config don't break before refactor is complete.
def get_user_resurrection_config(user_id: int, conn: sqlite3.Connection) -> dict[str, Any]:
    """Return global config merged with per-user uses_remaining."""
    cfg = get_global_resurrection_config(conn)
    cfg["uses_remaining"] = get_user_uses_remaining(user_id, conn)
    return cfg


# ── Per-mode cost calculators ─────────────────────────────────────────────


def _get_current_gold(character_id: int, conn: sqlite3.Connection) -> int:
    """Canonical gold lives in characters.gold_gp."""
    row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (character_id,)).fetchone()
    return int(row["gold_gp"] or 0) if row else 0


def _calc_cost_gold_percent(character_id: int, cfg: dict, conn: sqlite3.Connection) -> dict:
    cur_gold = _get_current_gold(character_id, conn)
    pct = max(0, min(100, cfg["value"]))
    lost = (cur_gold * pct) // 100
    return {"mode": "gold_percent", "gold_lost": lost, "percent": pct, "current_gold": cur_gold}


def _calc_cost_gold_recent_days(
    cfg: dict, character_id: int, current_day: int, conn: sqlite3.Connection
) -> dict:
    cur_gold = _get_current_gold(character_id, conn)
    window_days = max(1, cfg["value"])
    cap_pct = max(0, min(100, cfg["cap_percent"]))
    cutoff_day = current_day - window_days
    row = conn.execute(
        """
        SELECT COALESCE(SUM(delta), 0) AS gains
        FROM character_gold_log
        WHERE character_id = ?
          AND reverted_at IS NULL
          AND delta > 0
          AND game_clock_day > ?
        """,
        (character_id, cutoff_day),
    ).fetchone()
    recent_gains = int(row["gains"] if row else 0)
    cap = (cur_gold * cap_pct) // 100
    lost = min(recent_gains, cap)
    return {
        "mode": "gold_recent_days",
        "gold_lost": lost,
        "recent_gains_in_window": recent_gains,
        "cap": cap,
        "cap_percent": cap_pct,
        "window_days": window_days,
        "current_gold": cur_gold,
    }


def _calc_cost_xp_revert(
    cfg: dict, character_id: int, sheet: dict, conn: sqlite3.Connection
) -> dict:
    target_xp = max(1, cfg["value"])
    rows = conn.execute(
        """
        SELECT id, amount FROM character_xp_grants
        WHERE character_id = ?
          AND amount > 0
          AND reverted_at IS NULL
        ORDER BY id DESC
        """,
        (character_id,),
    ).fetchall()
    selected: list[int] = []
    reverted_amount = 0
    for r in rows:
        if reverted_amount >= target_xp:
            break
        selected.append(int(r["id"]))
        reverted_amount += int(r["amount"])
    return {
        "mode": "xp_revert",
        "xp_lost": reverted_amount,
        "target_xp": target_xp,
        "grant_ids_to_revert": selected,
        "grants_count": len(selected),
        "current_xp": int(sheet.get("xp") or 0),
    }


def _eligible_item_loss_pool(character_id: int, conn: sqlite3.Connection) -> list[dict]:
    """Equipped + has effect. Excludes quest-marked items.

    We treat 'functional' as: equipped in any anatomical slot AND either
    a weapon (any weapon is functional) OR armor with ac_bonus > 0 OR
    a consumable / item with non-empty effect_json. Cosmetic items and
    quest-marked rows are excluded.
    """
    # character_inventory uses (item_key | weapon_key | consumable_key) +
    # `equipped` boolean + `slot` text. is_quest_item lives in meta_json (if at all).
    rows = conn.execute(
        """
        SELECT ci.id AS inv_id, ci.item_key, ci.weapon_key, ci.consumable_key,
               ci.slot, ci.quantity, ci.meta_json,
               COALESCE(ci.label, w.label, i.label, c.label,
                        ci.weapon_key, ci.item_key, ci.consumable_key) AS label,
               CASE
                 WHEN ci.weapon_key IS NOT NULL THEN 'weapon'
                 WHEN ci.item_key IS NOT NULL THEN 'item'
                 WHEN ci.consumable_key IS NOT NULL THEN 'consumable'
                 ELSE 'unknown'
               END AS kind,
               i.effect_json AS item_effect,
               i.ac_bonus AS item_ac_bonus,
               c.effect_type AS cons_effect_type
        FROM character_inventory ci
        LEFT JOIN game_config_weapons w ON w.key = ci.weapon_key
        LEFT JOIN game_config_items i ON i.key = ci.item_key
        LEFT JOIN game_config_consumables c ON c.key = ci.consumable_key
        WHERE ci.character_id = ?
          AND ci.equipped = 1
          AND ci.slot IS NOT NULL
          AND ci.slot != ''
        """,
        (character_id,),
    ).fetchall()
    pool: list[dict] = []
    for r in rows:
        # Quest-marked items are flagged via meta_json — exclude them
        meta = r["meta_json"]
        if meta:
            try:
                if bool(json.loads(meta).get("is_quest_item")):
                    continue
            except Exception:
                pass
        kind = r["kind"]
        functional = False
        if kind == "weapon":
            functional = True
        elif kind == "item":
            functional = bool(r["item_effect"]) or int(r["item_ac_bonus"] or 0) > 0
        elif kind == "consumable":
            # Any non-empty effect_type means the consumable does something
            functional = bool(r["cons_effect_type"])
        if functional:
            pool.append({
                "inv_id": int(r["inv_id"]),
                "item_key": r["item_key"] or r["weapon_key"] or r["consumable_key"],
                "label": r["label"],
                "slot": r["slot"],
                "kind": kind,
            })
    return pool


def _calc_cost_item_loss(character_id: int, conn: sqlite3.Connection) -> dict:
    pool = _eligible_item_loss_pool(character_id, conn)
    return {
        "mode": "item_loss",
        "eligible_count": len(pool),
        "eligible_items": [{"label": p["label"], "slot": p["slot"]} for p in pool],
        "fallback_to_free": len(pool) == 0,
    }


# ── Public preview ────────────────────────────────────────────────────────


def cost_preview(
    character_id: int, user_id: int, conn: sqlite3.Connection
) -> dict[str, Any]:
    """Compute the cost of resurrecting without applying it.

    Returns a structured dict the frontend renders into the confirmation modal.
    """
    cfg = get_global_resurrection_config(conn)
    uses_remaining = get_user_uses_remaining(user_id, conn)
    char = conn.execute(
        "SELECT id, campaign_id, sheet_json, status FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not char:
        raise LookupError(f"Character {character_id} not found")
    sheet = json.loads(char["sheet_json"] or "{}")

    if not cfg["enabled"]:
        return {"enabled": False, "reason": "resurrection_disabled", "config": cfg}
    if uses_remaining is not None and int(uses_remaining) <= 0:
        return {"enabled": False, "reason": "no_uses_remaining", "config": cfg, "uses_remaining": 0}

    mode = cfg["mode"]
    if mode == "admin_free":
        cost = {"mode": "admin_free", "free": True}
    elif mode == "gold_percent":
        cost = _calc_cost_gold_percent(character_id, cfg, conn)
    elif mode == "gold_recent_days":
        from app.services.clock_service import get_clock_state
        day = int(get_clock_state(int(char["campaign_id"]), conn=conn)["day"]) if char["campaign_id"] else 1
        cost = _calc_cost_gold_recent_days(cfg, character_id, day, conn)
    elif mode == "xp_revert":
        cost = _calc_cost_xp_revert(cfg, character_id, sheet, conn)
    elif mode == "item_loss":
        cost = _calc_cost_item_loss(character_id, conn)
    else:
        raise ValueError(f"Unknown cost mode: {mode}")

    return {"enabled": True, "config": cfg, "uses_remaining": uses_remaining, "cost": cost}


# ── Apply ─────────────────────────────────────────────────────────────────


def _apply_xp_revert(
    character_id: int, sheet: dict, grant_ids: list[int], reverted_amount: int,
    conn: sqlite3.Connection
) -> dict:
    """Mark grants as reverted, subtract XP, recompute level, revoke purchases.

    Purchases revoked: any character_spells row with `purchased_after_xp_total`
    > the new total. We also reset arcane_points_spent_after to match.
    """
    if not grant_ids:
        return {"xp_subtracted": 0, "new_level": int(sheet.get("level") or 1), "revoked": {}}

    placeholders = ",".join("?" * len(grant_ids))
    conn.execute(
        f"UPDATE character_xp_grants SET reverted_at = datetime('now') WHERE id IN ({placeholders})",
        grant_ids,
    )

    old_xp = int(sheet.get("xp") or 0)
    new_xp = max(0, old_xp - reverted_amount)
    sheet["xp"] = new_xp

    # Recompute level using configurable thresholds (F18)
    from app.services.xp_service import get_xp_level_thresholds, level_from_xp
    old_level = int(sheet.get("level") or 1)
    try:
        thresholds = get_xp_level_thresholds(conn)
    except Exception:
        thresholds = None
    new_level = max(1, level_from_xp(new_xp, thresholds))
    level_dropped = max(0, old_level - new_level)
    sheet["level"] = new_level

    # Recompute max_hp at the new level (archetype_base + CON_mod × level)
    try:
        from app.services.vitality_service import calculate_hp, calculate_mana
        arc = str(sheet.get("archetype") or "warrior")
        stats = sheet.get("stats") or {}
        con = int(stats.get("CON") or stats.get("con") or 10)
        int_stat = int(stats.get("INT") or stats.get("int") or 10)
        sheet["max_hp"] = calculate_hp(arc, con, new_level)
        sheet["max_mana"] = calculate_mana(arc, int_stat, new_level)
    except Exception as e:
        logger.warning("recompute_max_hp_failed", error=str(e))

    revoked: dict[str, Any] = {"levels_lost": level_dropped}

    # Revoke spells / skill ranks bought above the new level.
    # Skill ranks are stored in sheet.skills as dicts {rank: N}. We can't track
    # per-rank purchase history retroactively without a journal, so for now we
    # clamp every skill rank to <= new_level (since you can buy at most 1 rank
    # per level for free advancement). This is a coarse but safe rollback.
    skills_revoked: list[dict] = []
    skills = sheet.get("skills") or {}
    if isinstance(skills, dict):
        for skill_key, sk_data in list(skills.items()):
            if not isinstance(sk_data, dict):
                continue
            cur_rank = int(sk_data.get("rank") or 0)
            if cur_rank > new_level:
                skills_revoked.append({"skill": skill_key, "old_rank": cur_rank, "new_rank": new_level})
                sk_data["rank"] = new_level
    revoked["skills"] = skills_revoked

    # Spells: remove character_spells rows that have learned_at_level > new_level.
    try:
        spell_rows = conn.execute(
            """
            SELECT id, spell_key, rank, learned_at_level
            FROM character_spells
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        spells_revoked = []
        for sr in spell_rows:
            if sr["learned_at_level"] is not None and int(sr["learned_at_level"]) > new_level:
                spells_revoked.append({"spell": sr["spell_key"], "learned_at": int(sr["learned_at_level"])})
                conn.execute("DELETE FROM character_spells WHERE id = ?", (sr["id"],))
        revoked["spells"] = spells_revoked
    except sqlite3.OperationalError:
        # character_spells table may not exist on bare-bones test DBs
        revoked["spells"] = []

    return {
        "xp_subtracted": reverted_amount,
        "new_xp": new_xp,
        "new_level": new_level,
        "old_level": old_level,
        "revoked": revoked,
    }


def _apply_gold_loss(
    character_id: int, amount: int, source: str,
    current_day: int, conn: sqlite3.Connection
) -> int:
    """Subtract `amount` from characters.gold_gp and journal it. Returns actual lost."""
    cur = _get_current_gold(character_id, conn)
    lost = max(0, min(cur, amount))
    if lost == 0:
        return 0
    conn.execute(
        "UPDATE characters SET gold_gp = gold_gp - ? WHERE id = ?",
        (lost, character_id),
    )
    conn.execute(
        """
        INSERT INTO character_gold_log
            (character_id, delta, source, game_clock_day, meta_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (character_id, -lost, source, current_day, json.dumps({"resurrection": True})),
    )
    return lost


def _apply_item_loss(
    character_id: int, conn: sqlite3.Connection
) -> dict | None:
    """Pick one functional item at random and remove it. Returns the lost item or None."""
    pool = _eligible_item_loss_pool(character_id, conn)
    if not pool:
        return None
    pick = random.choice(pool)
    # Column is `quantity`, not `qty`
    row = conn.execute(
        "SELECT quantity FROM character_inventory WHERE id = ?",
        (pick["inv_id"],),
    ).fetchone()
    qty = int(row["quantity"] if row else 1)
    if qty <= 1:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (pick["inv_id"],))
    else:
        conn.execute(
            "UPDATE character_inventory SET quantity = quantity - 1 WHERE id = ?",
            (pick["inv_id"],),
        )
    return pick


RESURRECTION_NARRATIVE_SYSTEM = """Jesteś Mistrzem Gry w grze RPG (samonarracja, tekst dla gracza).
Bohater właśnie wrócił do życia po śmierci. Napisz krótką narrację (3-6 zdań) opisującą:
- przebudzenie / powrót do życia,
- miejsce w którym się znajduje,
- jego stan (rany, blizny, koszt wskrzeszenia — wpleć naturalnie, bez liczb/JSON),
- zaczep zachęcający do dalszego działania.
Ton dopasuj do kosztu: darmowe wskrzeszenie = łagodniejszy, spokojniejszy ton; bolesne
(utrata złota/przedmiotu/PD) = cięższy, bardziej dramatyczny ton.
Pisz w języku podanym przez użytkownika. Bez nagłówków markdown, bez list, bez staty."""


def _describe_cost_for_narration(cost_applied: dict[str, Any]) -> str:
    mode = cost_applied.get("mode")
    if cost_applied.get("free") or mode == "admin_free":
        return "wskrzeszenie nie kosztowało nic"
    if mode in ("gold_percent", "gold_recent_days"):
        gold = cost_applied.get("gold_lost") or 0
        if gold:
            return f"utracono {gold} sztuk złota"
        return "wskrzeszenie nie kosztowało nic (brak złota do odjęcia)"
    if mode == "xp_revert":
        xp = cost_applied.get("xp_subtracted") or 0
        if xp:
            return f"cofnięto {xp} punktów doświadczenia"
        return "wskrzeszenie nie kosztowało nic (brak PD do cofnięcia)"
    if mode == "item_loss":
        if cost_applied.get("fell_back_to_free"):
            return "wskrzeszenie nie kosztowało nic (brak przedmiotów do utraty)"
        item = cost_applied.get("item_lost") or {}
        label = item.get("label") or "przedmiot"
        return f"utracono przedmiot: {label}"
    return "nieznany koszt"


def generate_resurrection_narration_llm(
    *,
    name: str,
    class_label: str,
    death_reason: str,
    epitaph: str,
    location: str,
    cost_applied: dict[str, Any],
    revived_hp: int,
    max_hp: int,
    language: str,
    user_id: int,
    model: str,
) -> str:
    cost_desc = _describe_cost_for_narration(cost_applied)
    user_content = (
        f"Język odpowiedzi: {language or 'pl'}\n"
        f"Imię: {name}\n"
        f"Klasa: {class_label}\n"
        f"Powód śmierci: {death_reason or 'nieznany'}\n"
        f"Epitafium: {epitaph or '(brak)'}\n"
        f"Lokacja: {location or 'nieznane miejsce'}\n"
        f"Koszt wskrzeszenia: {cost_desc}\n"
        f"HP po wskrzeszeniu: {revived_hp}/{max_hp}\n\n"
        "Napisz narrację powrotu do życia."
    )
    messages = [
        {"role": "system", "content": RESURRECTION_NARRATIVE_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    llm_config = get_user_llm_settings_full(user_id)
    try:
        text = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
    except Exception as e:
        logger.warning("resurrection_narration_llm_failed", error_message=str(e))
        text = ""
    if not text:
        text = f"{name} otwiera oczy. Świat wraca powoli — {location or 'nieznane miejsce'} czeka."
    return text


def _insert_resurrection_turn(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    assistant_text: str,
) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(turn_number), 0) AS max_turn FROM campaign_turns WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    turn_number = int(row["max_turn"] or 0) + 1
    conn.execute(
        """
        INSERT INTO campaign_turns (
            campaign_id, character_id, user_text, route, assistant_text, turn_number
        )
        VALUES (?, ?, ?, 'narrative', ?, ?)
        """,
        (campaign_id, character_id, "[Wskrzeszenie] Bohater wraca do życia.", assistant_text, turn_number),
    )
    return turn_number


def apply_resurrection(
    character_id: int,
    user_id: int,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Run the configured cost mode (or free if force=True) and revive the hero.

    Raises:
        PermissionError if disabled and not force
        RuntimeError    if no uses remaining and not force
    """
    cfg = get_global_resurrection_config(conn)
    uses_remaining = get_user_uses_remaining(user_id, conn)
    char = conn.execute(
        "SELECT id, campaign_id, sheet_json, status FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not char:
        raise LookupError(f"Character {character_id} not found")

    # `name`/`location` aren't in every legacy test fixture — fetch defensively so
    # this never breaks the revive itself.
    char_name = "Bohater"
    char_location = ""
    try:
        extra_row = conn.execute(
            "SELECT name, location FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if extra_row:
            char_name = extra_row["name"] or char_name
            char_location = extra_row["location"] or ""
    except sqlite3.OperationalError:
        pass

    if not force:
        if not cfg["enabled"]:
            raise PermissionError("Resurrection is disabled")
        if uses_remaining is not None and int(uses_remaining) <= 0:
            raise RuntimeError("No resurrection uses remaining")

    sheet = json.loads(char["sheet_json"] or "{}")
    campaign_id = int(char["campaign_id"]) if char["campaign_id"] else None
    from app.services.clock_service import get_clock_state
    current_day = int(get_clock_state(campaign_id, conn=conn)["day"]) if campaign_id else 1

    # Capture death context BEFORE the revive UPDATE below clears it from `campaigns`.
    camp_row = None
    if campaign_id:
        try:
            camp_row = conn.execute(
                "SELECT title, system_id, model_id, language, owner_user_id, death_reason, epitaph"
                " FROM campaigns WHERE id = ?",
                (campaign_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            camp_row = None

    cost_applied: dict[str, Any] = {"mode": "admin_free" if force else cfg["mode"]}

    if force or cfg["mode"] == "admin_free":
        cost_applied["free"] = True
    elif cfg["mode"] == "gold_percent":
        calc = _calc_cost_gold_percent(character_id, cfg, conn)
        lost = _apply_gold_loss(character_id, calc["gold_lost"], "resurrection_gold_percent", current_day, conn)
        cost_applied.update({"gold_lost": lost, "percent": calc["percent"]})
    elif cfg["mode"] == "gold_recent_days":
        calc = _calc_cost_gold_recent_days(cfg, character_id, current_day, conn)
        lost = _apply_gold_loss(character_id, calc["gold_lost"], "resurrection_gold_recent", current_day, conn)
        cost_applied.update({
            "gold_lost": lost,
            "window_days": calc["window_days"],
            "cap_percent": calc["cap_percent"],
        })
    elif cfg["mode"] == "xp_revert":
        calc = _calc_cost_xp_revert(cfg, character_id, sheet, conn)
        result = _apply_xp_revert(character_id, sheet, calc["grant_ids_to_revert"], calc["xp_lost"], conn)
        cost_applied.update(result)
    elif cfg["mode"] == "item_loss":
        lost_item = _apply_item_loss(character_id, conn)
        if lost_item is None:
            cost_applied.update({"fell_back_to_free": True, "reason": "no_eligible_items"})
        else:
            cost_applied.update({"item_lost": {"label": lost_item["label"], "slot": lost_item["slot"]}})
    else:
        raise ValueError(f"Unknown cost mode: {cfg['mode']}")

    # ── Revive: HP, status, death flags, cooldowns ───────────────────────
    # #1466 — recompute max_hp/mana from the formula before reviving, so a
    # resurrected hero's max is identical to the same hero levelled via rest
    # (path-independent). A drifted max never persists through a revive.
    from app.services.vitality_service import recompute_max_hp, recompute_max_mana
    _arch = str(sheet.get("archetype") or "warrior").strip().lower()
    _lvl = int(sheet.get("level") or 1)
    _stats = sheet.get("stats") or {}
    _con = int(_stats.get("CON", 10) or 10)
    _int = int(_stats.get("INT", 10) or 10)
    sheet["max_hp"] = recompute_max_hp(_arch, _con, _lvl)
    sheet["max_mana"] = recompute_max_mana(_arch, _int, _lvl)
    max_hp = int(sheet.get("max_hp") or 1)
    revive_hp = max(1, max_hp // 2)
    sheet["current_hp"] = revive_hp
    sheet["death_saves_failed"] = 0
    sheet["short_rests_used"] = 0
    # Cooldown stamp (#1102) — lets the /resurrect gate reject a rapid repeat
    # even when some other writer later stomps current_hp back to a
    # dead-looking value.
    sheet["last_resurrected_at"] = datetime.now(timezone.utc).isoformat()
    # Clear any death-tagged conditions
    if isinstance(sheet.get("conditions"), list):
        sheet["conditions"] = [c for c in sheet["conditions"] if c not in ("dead", "unconscious", "dying")]

    conn.execute(
        "UPDATE characters SET sheet_json = ?, status = 'active' WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    # Reactivate campaign if it was ended by solo death service
    if campaign_id:
        try:
            conn.execute(
                "UPDATE campaigns SET status='active', death_reason=NULL, ended_at=NULL, epitaph=NULL"
                " WHERE id = ? AND status='ended'",
                (campaign_id,),
            )
        except sqlite3.OperationalError:
            pass

    # Wipe dungeon cooldown rows
    try:
        conn.execute("DELETE FROM character_dungeon_runs WHERE character_id = ?", (character_id,))
    except sqlite3.OperationalError:
        pass

    # Decrement per-user uses_remaining (only when not force-bypass)
    if not force and uses_remaining is not None:
        conn.execute(
            "UPDATE users SET resurrection_uses_remaining = MAX(0, resurrection_uses_remaining - 1) WHERE id = ?",
            (user_id,),
        )

    conn.commit()

    # End any active combat so the revived hero doesn't re-enter an enemy turn mid-fight.
    # Reason "resurrected" avoids triggering the player_dead / solo_death chain.
    if campaign_id:
        try:
            if is_combat_active(None, campaign_id):
                end_combat(campaign_id, "resurrected")
        except Exception as e:
            logger.warning("end_combat_on_resurrect_failed", error=str(e), campaign_id=campaign_id)

    logger.info(
        "hero_resurrected",
        character_id=character_id,
        user_id=user_id,
        force=force,
        mode=cost_applied.get("mode"),
        revived_hp=revive_hp,
    )

    # Auto-narrate the "return to life" turn so the player isn't left facing a
    # silent chat window (#1072). Best-effort — a failure here must not undo
    # the revive that already happened above.
    narration_text: str | None = None
    narration_turn_number: int | None = None
    if campaign_id and camp_row:
        try:
            owner_id = int(camp_row["owner_user_id"] or user_id)
            llm_config = get_user_llm_settings_full(owner_id)
            model = (llm_config.get("model") or "").strip() or str(camp_row["model_id"] or "").strip() or "gemma3:1b"
            narration_text = generate_resurrection_narration_llm(
                name=char_name.strip(),
                class_label=str(sheet.get("archetype") or sheet.get("class") or "adventurer").strip(),
                death_reason=str(camp_row["death_reason"] or ""),
                epitaph=str(camp_row["epitaph"] or ""),
                location=char_location.strip(),
                cost_applied=cost_applied,
                revived_hp=revive_hp,
                max_hp=max_hp,
                language=str(camp_row["language"] or "pl"),
                user_id=owner_id,
                model=model,
            )
            narration_turn_number = _insert_resurrection_turn(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                assistant_text=narration_text,
            )
            conn.commit()
        except Exception as e:
            logger.warning("resurrection_narration_failed", error=str(e), campaign_id=campaign_id)

    uses_after = (uses_remaining - 1) if (not force and uses_remaining is not None) else uses_remaining
    return {
        "character_id": character_id,
        "force": force,
        "cost_applied": cost_applied,
        "revived_hp": revive_hp,
        "max_hp": max_hp,
        "uses_remaining_after": uses_after,
        "narration": narration_text,
        "narration_turn_number": narration_turn_number,
    }
