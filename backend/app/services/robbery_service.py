"""Robbery encounter service — F8 (#468).

When a 'robbery' type encounter fires, the hero loses a configurable percentage
of their gold instead of entering combat. Bandits ambush and steal, then flee.

Config stored in game_config_meta key 'robbery_config' (JSON):
  {"enabled": true, "gold_percent": 20}
"""
import json
import math
import random
from datetime import datetime, timedelta

DEFAULT_ROBBERY_PCT = 20

# U24 (#574) — counterplay constants. Startowe wartości (Numbers Policy):
POVERTY_THRESHOLD_GP = 50          # napad nie odpala się gdy złoto < 50 gp
RATE_LIMIT_HOURS = 24              # max 1 napad / 24h realne / kampania
DEFAULT_DEFENSE_STAT = "WIS"       # domyślna statystyka rzutu obronnego
_DC_LOCK = (8, 12, 16, 20, 24)     # zamek DC z system_prompt.txt

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
        # U26: mutate + journal through the central chokepoint.
        from app.services.economy_service import change_gold
        change_gold(
            conn, char_id, -stolen, "robbery",
            meta={"percent": pct, "gold_stolen": stolen},
        )
        conn.commit()
        # #1379 — strata złota z rabunku była dotąd tylko w prozie; teraz dymek.
        try:
            from app.services import system_events as _se
            _se.emit("gold_loss", f"−{stolen} zł — okradziono cię!")
        except Exception:
            pass

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


# ─── U24 (#574) — counterplay: DC, rzut obronny, granice ─────────────────────


def robbery_defense_dc(level: int) -> int:
    """DC rzutu obronnego wg poziomu bohatera, z zamka {8,12,16,20,24}.

    Startowa drabina (Numbers Policy): lvl 1-2 → 8, 3-4 → 12, 5-6 → 16,
    7-8 → 20, 9+ → 24. Trudniejszy świat wyżej, ale obrona zawsze możliwa
    przy inwestycji w statystykę.
    """
    lvl = max(1, int(level or 1))
    idx = min((lvl - 1) // 2, len(_DC_LOCK) - 1)
    return _DC_LOCK[idx]


def _char_sheet(conn, char_id: int) -> dict:
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["sheet_json"] or "{}")
    except Exception:
        return {}


def roll_robbery_defense(conn, char_id: int, stat: str, dc: int) -> dict:
    """Rzut obronny napadu: d20 + modyfikator statystyki vs DC.

    Mechanika decyduje (backend rzuca, liczy wynik); LLM tylko narruje rezultat.
    Sukces (total >= dc) = unikasz/przeganiasz złodzieja, brak straty.
    """
    from app.services.weapon_rules import stat_modifier

    stat_key = str(stat or DEFAULT_DEFENSE_STAT).upper()
    sheet = _char_sheet(conn, char_id)
    mod = stat_modifier(sheet, stat_key)
    roll = random.randint(1, 20)
    total = roll + mod
    success = total >= int(dc)
    return {
        "roll": roll,
        "modifier": mod,
        "total": total,
        "dc": int(dc),
        "stat": stat_key,
        "success": success,
        "margin": total - int(dc),
    }


def can_trigger_robbery(conn, campaign_id: int, char_id: int, session_flags: dict) -> dict:
    """Bramki napadu (U24): konfiguracja, próg biedy, limit 24h realnych.

    Zwraca {allowed: bool, reason: str}. Wołane przy iniekcji encountera —
    jeśli not allowed, napad w ogóle się nie pojawia (nawet ostrzeżenie).
    """
    cfg = get_robbery_config(conn)
    if not cfg.get("enabled"):
        return {"allowed": False, "reason": "robbery_disabled"}

    row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()
    gold = int(row["gold_gp"] or 0) if row else 0
    if gold < POVERTY_THRESHOLD_GP:
        return {"allowed": False, "reason": "below_poverty_threshold"}

    last = (session_flags or {}).get("last_robbery_at")
    if last:
        try:
            last_dt = datetime.fromisoformat(str(last))
            if datetime.utcnow() - last_dt < timedelta(hours=RATE_LIMIT_HOURS):
                return {"allowed": False, "reason": "rate_limited_24h"}
        except Exception:
            pass

    return {"allowed": True, "reason": "ok"}


def record_robbery_trigger(session_flags: dict) -> dict:
    """Zapisz znacznik czasu napadu (limit 1/24h). Mutuje i zwraca session_flags.

    Wołane przy ROZSTRZYGNIĘCIU napadu (sukces lub porażka konsumuje limit).
    """
    if session_flags is None:
        session_flags = {}
    session_flags["last_robbery_at"] = datetime.utcnow().isoformat()
    return session_flags


def is_robbery_encounter(enc) -> bool:
    """Return True if the encounter dict is a robbery type."""
    if not isinstance(enc, dict):
        return False
    return str(enc.get("encounter_type") or "").lower() == "robbery"
