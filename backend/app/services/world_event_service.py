"""#1193 — Wydarzenia regionalne ("żywy świat").

Cienka warstwa modyfikatorów na istniejących systemach — świat regionu żyje
własnym rytmem (jarmark, zaraza, rajdy bandytów, surowa zima/susza) niezależnie
od tego, co robi gracz. Wzorowane na `weather_service` (ten sam styl:
DB_PATH, get_global_flag toggle, defensywne akcesory nie rzucające wyjątków).

Model czasu: **zegar ścienny**. `world_events.ends_at` = `started_at` +
`duration_days` dni (wall-clock). Event jest REGIONALNY (globalny dla regionu,
wspólny dla wszystkich kampanii w tym regionie) — dlatego nie wiąże się z
per-kampanijnym zegarem gry. Wygasanie leniwe przy odczycie + przy day-ticku.

Single source of truth: `get_active_event(conn, region)` — max 1 aktywny event
per region. Wszystkie akcesory modyfikatorów (`price_multiplier`,
`encounter_chance_multiplier`, `travel_hours_multiplier`, `disease_dc`,
`loot_gold_multiplier`) czytają właśnie ją.

Auto-losowanie przy day-ticku jest ZA FLAGĄ `world_events_auto_roll`
(game_config_meta, domyślnie 0 = OFF). Ręczne wylosuj/dodaj/zakończ z panelu
admina działają zawsze, niezależnie od flagi.

Numbers Policy: szansa dzienna, czasy trwania, mnożniki — wartości STARTOWE,
strojone w adminie po obserwacji.
"""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from app.migrations_admin import DB_PATH
from app.services.location_config_service import get_global_flag
from app.services.reputation_service import REGION_DEFAULT

# ─── Stałe konfiguracyjne (Numbers Policy — wartości startowe) ────────────────

AUTO_ROLL_FLAG = "world_events_auto_roll"
DAILY_CHANCE_FLAG = "world_events_daily_chance"
DAILY_CHANCE_DEFAULT = 0.10  # 10% szansy dziennej na event w regionie bez eventu

VALID_STATES = ("active", "ended")
VALID_SOURCES = ("manual", "random")


# ─── DB helper ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _decode(raw: Any, fallback: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    try:
        val = json.loads(raw or "")
        return val if val is not None else fallback
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _norm_region(region: str | None) -> str:
    r = (region or "").strip()
    return r or REGION_DEFAULT


# ─── Toggle + config (game_config_meta) ───────────────────────────────────────

def is_auto_roll_enabled() -> bool:
    """Globalny przełącznik auto-losowania przy day-ticku (domyślnie OFF)."""
    return str(get_global_flag(AUTO_ROLL_FLAG, "0")).strip().lower() in ("1", "true", "on", "yes")


def _daily_chance() -> float:
    raw = get_global_flag(DAILY_CHANCE_FLAG, str(DAILY_CHANCE_DEFAULT))
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return DAILY_CHANCE_DEFAULT


def set_auto_roll(enabled: bool) -> None:
    conn = _conn()
    try:
        conn.execute(
            """INSERT INTO game_config_meta (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (AUTO_ROLL_FLAG, "1" if enabled else "0"),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Templates ────────────────────────────────────────────────────────────────

def _template_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "key": row["key"],
        "type": row["type"],
        "label": row["label"],
        "duration_days_min": int(row["duration_days_min"]),
        "duration_days_max": int(row["duration_days_max"]),
        "modifiers": _decode(row["modifiers_json"], {}),
        "narrative_tags": _decode(row["narrative_tags"], []),
        "weight": int(row["weight"]),
        "is_active": bool(row["is_active"]),
        "region_scope": _template_regions(row),
    }


def _template_regions(row: sqlite3.Row) -> list[str]:
    """SG-9 (#1481): krainy, w których szablon może wypaść. Pusto = wszędzie."""
    try:
        raw = row["region_scope"]
    except (IndexError, KeyError):
        return []  # stara baza sprzed migracji — traktujemy jak globalny
    val = _decode(raw, [])
    if isinstance(val, str):
        val = [v.strip() for v in val.split(",") if v.strip()]
    return [str(v).strip() for v in (val or []) if str(v).strip()]


def list_templates(
    conn: sqlite3.Connection,
    active_only: bool = True,
    region: str | None = None,
) -> list[dict[str, Any]]:
    """Szablony wydarzeń. Z `region` — tylko te dopuszczone w tej krainie.

    SG-9 (#1481): bez filtra „Głębokie Bicie" (stukanie w żyle Rdzenia pod
    Siwymi Graniami) wypadałoby także w Kresach. Szablon bez `region_scope`
    zostaje uniwersalny, więc stare dane działają bez zmian.
    """
    sql = "SELECT * FROM game_config_event_templates"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY type, key"
    rows = conn.execute(sql).fetchall()
    if region:
        want = _norm_region(region)
        rows = [r for r in rows
                if not _template_regions(r) or want in _template_regions(r)]
    return [_template_row_to_dict(r) for r in rows]


def get_template(conn: sqlite3.Connection, template_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM game_config_event_templates WHERE key = ? LIMIT 1",
        (str(template_key),),
    ).fetchone()
    return _template_row_to_dict(row) if row else None


# ─── Wygasanie (leniwe) ───────────────────────────────────────────────────────

def expire_due(conn: sqlite3.Connection) -> int:
    """Flipuje aktywne eventy, którym minął `ends_at`, na state='ended'.

    Zwraca liczbę wygaszonych. Idempotentne — bezpieczne do wołania przed
    każdym odczytem."""
    cur = conn.execute(
        """UPDATE world_events
           SET state = 'ended'
           WHERE state = 'active' AND datetime(ends_at) <= datetime('now')"""
    )
    return cur.rowcount or 0


# ─── Odczyt aktywnego eventu (single source of truth) ─────────────────────────

def _event_row_to_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    tpl = get_template(conn, row["template_key"]) or {}
    return {
        "id": int(row["id"]),
        "region": row["region"],
        "template_key": row["template_key"],
        "type": tpl.get("type") or row["template_key"],
        "label": tpl.get("label") or row["template_key"],
        "modifiers": tpl.get("modifiers") or {},
        "narrative_tags": tpl.get("narrative_tags") or [],
        "started_at": row["started_at"],
        "ends_at": row["ends_at"],
        "state": row["state"],
        "source": row["source"],
    }


def get_active_event(conn: sqlite3.Connection, region: str | None) -> dict[str, Any] | None:
    """Aktywny event w regionie (max 1) lub None. Leniwie wygasza przeterminowane."""
    region = _norm_region(region)
    expire_due(conn)
    row = conn.execute(
        """SELECT * FROM world_events
           WHERE region = ? AND state = 'active'
           ORDER BY started_at DESC LIMIT 1""",
        (region,),
    ).fetchone()
    return _event_row_to_dict(conn, row) if row else None


def list_events(
    conn: sqlite3.Connection,
    region: str | None = None,
    include_ended: bool = False,
) -> list[dict[str, Any]]:
    """Lista eventów (admin). Bez `region` → wszystkie regiony."""
    expire_due(conn)
    sql = "SELECT * FROM world_events WHERE 1=1"
    params: list[Any] = []
    if region:
        sql += " AND region = ?"
        params.append(_norm_region(region))
    if not include_ended:
        sql += " AND state = 'active'"
    sql += " ORDER BY state ASC, started_at DESC"
    return [_event_row_to_dict(conn, r) for r in conn.execute(sql, params).fetchall()]


# ─── Start / koniec eventu ────────────────────────────────────────────────────

def _duration_days(tpl: dict[str, Any], override: int | None) -> int:
    if override is not None and int(override) > 0:
        return int(override)
    lo = max(1, int(tpl.get("duration_days_min") or 2))
    hi = max(lo, int(tpl.get("duration_days_max") or lo))
    return random.randint(lo, hi)


def start_event(
    conn: sqlite3.Connection,
    region: str | None,
    template_key: str,
    source: str = "manual",
    duration_days: int | None = None,
) -> dict[str, Any]:
    """Uruchamia event w regionie. Kończy dowolny inny aktywny event tego regionu
    (max 1 aktywny/region). Zwraca nowy event."""
    region = _norm_region(region)
    tpl = get_template(conn, template_key)
    if not tpl:
        raise ValueError(f"unknown_template:{template_key}")
    if source not in VALID_SOURCES:
        source = "manual"

    # Max 1 aktywny/region — wygaś istniejące PRZED wstawieniem.
    conn.execute(
        "UPDATE world_events SET state = 'ended' WHERE region = ? AND state = 'active'",
        (region,),
    )
    days = _duration_days(tpl, duration_days)
    cur = conn.execute(
        """INSERT INTO world_events (region, template_key, started_at, ends_at, state, source)
           VALUES (?, ?, datetime('now'), datetime('now', ?), 'active', ?)""",
        (region, template_key, f"+{days} days", source),
    )
    row = conn.execute(
        "SELECT * FROM world_events WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _event_row_to_dict(conn, row)


def end_event(conn: sqlite3.Connection, event_id: int) -> bool:
    """Ręczne zakończenie eventu. True gdy coś zmieniono."""
    cur = conn.execute(
        "UPDATE world_events SET state = 'ended' WHERE id = ? AND state = 'active'",
        (int(event_id),),
    )
    return (cur.rowcount or 0) > 0


def roll_event(
    conn: sqlite3.Connection,
    region: str | None,
    source: str = "random",
) -> dict[str, Any] | None:
    """Losuje event dla regionu (ważony `weight`). No-op (None) gdy region ma już
    aktywny event lub brak szablonów. Nie sprawdza szansy dziennej — to robi
    `on_day_tick`; ręczne 'wylosuj' z admina ma zawsze zadziałać."""
    region = _norm_region(region)
    if get_active_event(conn, region) is not None:
        return None
    templates = list_templates(conn, active_only=True, region=region)
    if not templates:
        return None
    weights = [max(1, int(t.get("weight") or 1)) for t in templates]
    chosen = random.choices(templates, weights=weights, k=1)[0]
    return start_event(conn, region, chosen["key"], source=source)


def on_day_tick(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any] | None:
    """Hook przy przekroczeniu dnia gry (z clock_service.advance_clock).

    Zawsze wygasza przeterminowane. Losuje NOWY event tylko gdy:
      - flaga `world_events_auto_roll` = ON,
      - region nie ma aktywnego eventu,
      - rzut < szansa dzienna.
    Zwraca nowo wylosowany event lub None. Defensywne — nie rzuca."""
    try:
        from app.services.reputation_service import resolve_region
        region = resolve_region(conn, int(campaign_id))
        expire_due(conn)
        if not is_auto_roll_enabled():
            return None
        if get_active_event(conn, region) is not None:
            return None
        if random.random() >= _daily_chance():
            return None
        return roll_event(conn, region, source="random")
    except Exception:
        return None


# ─── Akcesory modyfikatorów (czytają aktywny event regionu) ───────────────────

def _active_modifiers(conn: sqlite3.Connection, region: str | None) -> dict[str, Any]:
    ev = get_active_event(conn, region)
    return (ev or {}).get("modifiers") or {}


def price_multiplier(conn: sqlite3.Connection, region: str | None, category: str | None) -> float:
    """Mnożnik ceny w sklepie dla kategorii (np. 'consumable'/'weapon'/'item').

    Kategoria dopasowana wprost, fallback do '*' (wszystkie). 1.0 gdy brak eventu
    lub brak modyfikatora cen. Defensywny — 1.0 przy błędzie."""
    try:
        mods = _active_modifiers(conn, region)
        pm = mods.get("shop_price_mult")
        if not isinstance(pm, dict):
            return 1.0
        cat = str(category or "").strip().lower()
        if cat and cat in pm:
            return float(pm[cat])
        if "*" in pm:
            return float(pm["*"])
        return 1.0
    except Exception:
        return 1.0


def encounter_chance_multiplier(conn: sqlite3.Connection, region: str | None) -> float:
    try:
        mods = _active_modifiers(conn, region)
        return float(mods.get("encounter_chance_mult", 1.0) or 1.0)
    except Exception:
        return 1.0


def travel_hours_multiplier(conn: sqlite3.Connection, region: str | None) -> float:
    try:
        mods = _active_modifiers(conn, region)
        return float(mods.get("travel_hours_mult", 1.0) or 1.0)
    except Exception:
        return 1.0


def loot_gold_multiplier(conn: sqlite3.Connection, region: str | None) -> float:
    try:
        mods = _active_modifiers(conn, region)
        return float(mods.get("loot_gold_mult", 1.0) or 1.0)
    except Exception:
        return 1.0


def disease_dc(conn: sqlite3.Connection, region: str | None) -> int | None:
    """DC testu CON przeciw zarażeniu przy odpoczynku w osadzie regionu, lub None
    gdy region nie ma aktywnej zarazy."""
    try:
        mods = _active_modifiers(conn, region)
        dc = mods.get("rest_disease_dc")
        return int(dc) if dc is not None else None
    except Exception:
        return None


def event_badge(conn: sqlite3.Connection, region: str | None) -> str | None:
    """Emoji-znacznik aktywnego eventu (mapa/UI), lub None."""
    try:
        mods = _active_modifiers(conn, region)
        b = mods.get("badge")
        return str(b) if b else None
    except Exception:
        return None


# ─── Linia WYDARZENIE do promptu narratora ────────────────────────────────────

# Ton dymka per typ eventu (system_events tone — kolor obramowania).
_EVENT_TONE = {
    "jarmark": "success",  # dobra wieść — tanio
    "zaraza": "warning",
    "rajdy": "warning",
    "zima": "info",
    "susza": "info",
}


def notify_if_new(conn: sqlite3.Connection, campaign_id: int) -> None:
    """#1193 — emituje dymek system_events RAZ, gdy w regionie kampanii pojawia
    się nowe wydarzenie (dotąd łatwe do przeoczenia: tylko narracja + ceny).

    Dedupe przez `world_event_seen` (kampania+event). Gated na aktywny bus tury —
    poza turą (podgląd promptu / skrypt) jest no-opem i NIE zużywa powiadomienia.
    Defensywny — nie rzuca."""
    try:
        from app.services import system_events as se
        if se.current_bus() is None:
            return  # nie w turze → nie zużywaj powiadomienia
        from app.services.reputation_service import resolve_region
        region = resolve_region(conn, int(campaign_id))
        ev = get_active_event(conn, region)
        if not ev:
            return
        event_id = int(ev["id"])
        seen = conn.execute(
            "SELECT 1 FROM world_event_seen WHERE campaign_id = ? AND event_id = ? LIMIT 1",
            (int(campaign_id), event_id),
        ).fetchone()
        if seen:
            return
        tags = ev.get("narrative_tags") or []
        tag = str(tags[0]) if tags else ""
        label = ev.get("label") or ev.get("type") or "Wydarzenie"
        badge = (ev.get("modifiers") or {}).get("badge") or "✦"
        tone = _EVENT_TONE.get(str(ev.get("type") or "").lower(), "info")
        text = f"{label} — {tag}" if tag else label
        se.emit("rumor", text, icon=str(badge), tone=tone,
                dedupe_key=f"world_event:{event_id}")
        conn.execute(
            "INSERT OR IGNORE INTO world_event_seen (campaign_id, event_id) VALUES (?, ?)",
            (int(campaign_id), event_id),
        )
    except Exception:
        pass


def build_event_line(
    conn: sqlite3.Connection,
    campaign_id: int,
    region: str | None = None,
) -> str:
    """Linia `WYDARZENIE: <label> — <tag>` do bloku ŚWIAT. Pusty string gdy brak
    eventu. Nie rzuca — błędy → ''. Wzór: `weather_service.build_weather_line`."""
    try:
        if region is None:
            from app.services.reputation_service import resolve_region
            region = resolve_region(conn, int(campaign_id))
        ev = get_active_event(conn, region)
        if not ev:
            return ""
        tags = ev.get("narrative_tags") or []
        tag = str(tags[0]) if tags else ""
        label = ev.get("label") or ev.get("type") or "wydarzenie"
        if tag:
            return f"WYDARZENIE: {label} — {tag}"
        return f"WYDARZENIE: {label}"
    except Exception:
        return ""
