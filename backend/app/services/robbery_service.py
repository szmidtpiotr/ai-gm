"""Robbery encounter service — F8 (#468).

When a 'robbery' type encounter fires, the hero loses a configurable percentage
of their gold instead of entering combat. Bandits ambush and steal, then flee.

Config stored in game_config_meta key 'robbery_config' (JSON):
  {"enabled": true, "gold_percent": 20}
"""
import json
import math

DEFAULT_ROBBERY_PCT = 20

_META_KEY = "robbery_config"
_DEFAULT_CFG = {"enabled": True, "gold_percent": DEFAULT_ROBBERY_PCT}


def get_robbery_config(conn) -> dict:
    """Return current robbery config. Defaults: enabled=True, gold_percent=20."""
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ?", (_META_KEY,)
        ).fetchone()
        if row and row["value"]:
            stored = json.loads(row["value"])
            return {**_DEFAULT_CFG, **stored}
    except Exception:
        pass
    return dict(_DEFAULT_CFG)


def set_robbery_config(conn, *, enabled: bool | None = None, gold_percent: int | None = None) -> dict:
    """Update robbery config fields. Returns the new config."""
    cfg = get_robbery_config(conn)
    if enabled is not None:
        cfg["enabled"] = bool(enabled)
    if gold_percent is not None:
        cfg["gold_percent"] = max(0, min(100, int(gold_percent)))
    conn.execute(
        "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
        (_META_KEY, json.dumps(cfg)),
    )
    conn.commit()
    return cfg


def apply_robbery(conn, char_id: int) -> dict:
    """Deduct robbery gold from character. Returns {ok, gold_stolen, narrative_hint}."""
    cfg = get_robbery_config(conn)
    if not cfg.get("enabled"):
        return {"ok": False, "reason": "robbery_disabled"}

    pct = int(cfg.get("gold_percent") or DEFAULT_ROBBERY_PCT)

    row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()
    gold = int(row["gold_gp"] or 0) if row else 0

    stolen = math.floor(gold * pct / 100)

    if stolen > 0:
        conn.execute(
            "UPDATE characters SET gold_gp = gold_gp - ? WHERE id = ?",
            (stolen, char_id),
        )
        conn.execute(
            "INSERT INTO character_gold_log (character_id, delta, source, meta_json) VALUES (?, ?, ?, ?)",
            (char_id, -stolen, "robbery", json.dumps({"percent": pct, "gold_stolen": stolen})),
        )
        conn.commit()

    narrative_hint = (
        f"Bandyci napadli cię i skradli {stolen} złota ({pct}% twojego majątku). "
        f"Uciekli zanim zdążyłeś zareagować."
    )

    return {
        "ok": True,
        "gold_stolen": stolen,
        "gold_remaining": gold - stolen,
        "percent": pct,
        "narrative_hint": narrative_hint,
    }


def is_robbery_encounter(enc) -> bool:
    """Return True if the encounter dict is a robbery type."""
    if not isinstance(enc, dict):
        return False
    return str(enc.get("encounter_type") or "").lower() == "robbery"
