"""PT-D4a (#1130) — kanoniczny katalog encounterów w bazie.

Jedna tabela `game_config_encounters` (combat + social, rozróżniane kolumną `kind`),
zaseedowana z obecnego hardcode (`GENERIC_ENCOUNTERS` + `_EVENT_DEFS`/`_SUBTYPE_EVENTS`).
Silniki losują z niej wg wag (pod-task D); przy pustym katalogu draw_* zwraca None,
a silnik używa dotychczasowego hardcode (zero regresji).

Zasada nadrzędna: **dane w bazie, reguły w kodzie**. Ten serwis dostarcza wyłącznie
treść + tuning (biome/level/weight/DC per rekord). Rozstrzyganie (split 50/50,
d20+stat+skill, eskalacja Nat 1, kieszonkowiec) zostaje w silnikach/Sandbox.

Anty-halucynacja: `validate_fk` odrzuca payloady referencujące nieistniejące byty
(combat → enemy_key∈game_config_enemies, social → skill∈game_config_skills).

Funkcje przyjmują `conn` (jak encounter_config_service) — czyste, testowalne na
in-memory sqlite bez dotykania /data/ai_gm.db.
"""
from __future__ import annotations

import json
import random
import sqlite3
from typing import Optional

from app.migrations_admin import DB_PATH


# ── Schemat ───────────────────────────────────────────────────────────────────

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS game_config_encounters (
    key           TEXT PRIMARY KEY,
    kind          TEXT NOT NULL DEFAULT 'combat',   -- 'combat' | 'social'
    biome         TEXT,                              -- combat: dopasowanie po biomie
    subtype       TEXT,                              -- social: subtyp sub-lokacji
    level_min     INTEGER NOT NULL DEFAULT 1,
    level_max     INTEGER NOT NULL DEFAULT 99,
    weight        REAL NOT NULL DEFAULT 1.0,         -- waga losowania (relatywna)
    trigger_types TEXT,                              -- json list
    region_tag    TEXT,
    faction_tag   TEXT,                              -- nullable, pod #1103
    payload_json  TEXT,                              -- treść wg kind (patrz niżej)
    is_active     INTEGER NOT NULL DEFAULT 1,
    source        TEXT NOT NULL DEFAULT 'seed',
    quality_rating INTEGER NOT NULL DEFAULT 3,
    times_used    INTEGER NOT NULL DEFAULT 0
)
"""


def ensure_catalog_schema(conn: sqlite3.Connection) -> None:
    """Utwórz tabelę game_config_encounters jeśli nie istnieje (idempotentne)."""
    conn.execute(_CREATE_SQL)
    conn.commit()


# ── Walidacja FK (anty-halucynacja) ──────────────────────────────────────────

def _existing_keys(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[0] for row in conn.execute(f"SELECT key FROM {table}")}
    except sqlite3.OperationalError:
        return set()


def validate_fk(conn: sqlite3.Connection, *, kind: str, payload: dict) -> None:
    """Odrzuć payload referencujący nieistniejące byty. Rzuca ValueError.

    combat → każdy enemies[].enemy_key musi być w game_config_enemies.
    social → skill musi być w game_config_skills.
    """
    payload = payload or {}
    if kind == "combat":
        enemies = payload.get("enemies") or []
        if not enemies:
            return  # napady/robbery bez wrogów — brak FK do sprawdzenia
        valid = _existing_keys(conn, "game_config_enemies")
        for e in enemies:
            ek = e.get("enemy_key")
            if ek and ek not in valid:
                raise ValueError(f"enemy_key '{ek}' spoza game_config_enemies")
    elif kind == "social":
        skill = payload.get("skill")
        if skill:
            valid = _existing_keys(conn, "game_config_skills")
            if skill not in valid:
                raise ValueError(f"skill '{skill}' spoza game_config_skills")
    else:
        raise ValueError(f"nieznany kind '{kind}' (dozwolone: combat|social)")


# ── Zapis ─────────────────────────────────────────────────────────────────────

def insert_encounter(
    conn: sqlite3.Connection,
    *,
    key: str,
    kind: str,
    biome: Optional[str] = None,
    subtype: Optional[str] = None,
    level_min: int = 1,
    level_max: int = 99,
    weight: float = 100.0,
    trigger_types: Optional[list] = None,
    region_tag: Optional[str] = None,
    faction_tag: Optional[str] = None,
    payload: Optional[dict] = None,
    is_active: int = 1,
    source: str = "seed",
    quality_rating: int = 3,
    times_used: int = 0,
    validate: bool = False,
    replace: bool = False,
) -> None:
    """Wstaw encounter. `validate=True` egzekwuje FK. Idempotencja: INSERT OR IGNORE
    (chyba że replace=True → INSERT OR REPLACE)."""
    payload = payload or {}
    if validate:
        validate_fk(conn, kind=kind, payload=payload)
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(
        f"""{verb} INTO game_config_encounters
            (key, kind, biome, subtype, level_min, level_max, weight, trigger_types,
             region_tag, faction_tag, payload_json, is_active, source, quality_rating, times_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            key, kind, biome, subtype, int(level_min), int(level_max), float(weight),
            json.dumps(trigger_types or [], ensure_ascii=False),
            region_tag, faction_tag,
            json.dumps(payload, ensure_ascii=False),
            int(is_active), source, int(quality_rating), int(times_used),
        ),
    )
    conn.commit()


# ── Losowanie wg wag ──────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["payload"] = json.loads(d.get("payload_json") or "{}")
    try:
        d["trigger_types"] = json.loads(d.get("trigger_types") or "[]")
    except (TypeError, ValueError):
        d["trigger_types"] = []
    return d


def _weighted_pick(rows: list[sqlite3.Row], rng) -> Optional[sqlite3.Row]:
    """Wylosuj wiersz proporcjonalnie do `weight`. Pomija weight<=0. None gdy brak."""
    pool = [r for r in rows if float(r["weight"]) > 0]
    if not pool:
        return None
    total = sum(float(r["weight"]) for r in pool)
    r = rng.random() * total
    acc = 0.0
    for row in pool:
        acc += float(row["weight"])
        if r < acc:
            return row
    return pool[-1]


def draw_combat(
    conn: sqlite3.Connection, biome: str, level: int, rng=random
) -> Optional[dict]:
    """Wylosuj encounter combat dla biomu/poziomu. Pusto → None (fallback do hardcode)."""
    try:
        rows = conn.execute(
            """SELECT * FROM game_config_encounters
               WHERE kind='combat' AND is_active=1 AND biome=?
                 AND level_min<=? AND level_max>=?""",
            (biome, int(level), int(level)),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    picked = _weighted_pick(rows, rng)
    return _row_to_dict(picked) if picked else None


def draw_social(
    conn: sqlite3.Connection, subtype: str, rng=random
) -> Optional[dict]:
    """Wylosuj zdarzenie social dla subtypu. Pusto → None (fallback do hardcode)."""
    try:
        rows = conn.execute(
            """SELECT * FROM game_config_encounters
               WHERE kind='social' AND is_active=1 AND subtype=?""",
            (subtype,),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    picked = _weighted_pick(rows, rng)
    return _row_to_dict(picked) if picked else None


# ── Seed z obecnego hardcode ─────────────────────────────────────────────────

def seed_catalog(conn: sqlite3.Connection) -> int:
    """Zaseeduj katalog z hardcode (idempotentne). Zwraca liczbę wierszy po seedzie.

    combat ← GENERIC_ENCOUNTERS (jeden wiersz per biom: key = `{base}__{biome}`)
    social ← _SUBTYPE_EVENTS × _EVENT_DEFS (key = event_key, subtype z mapy)
    """
    from app.services.encounter_seed_service import GENERIC_ENCOUNTERS
    from app.services import social_encounter_service as ses

    ensure_catalog_schema(conn)

    # combat
    for e in GENERIC_ENCOUNTERS:
        weight = float(e.get("trigger_probability", 0.2)) * 100.0
        base_payload = {
            "enemies": e.get("enemies", []),
            "scene_setup": e.get("description", ""),
            "title": e.get("title", ""),
        }
        if e.get("encounter_type"):
            base_payload["encounter_type"] = e["encounter_type"]
        if e.get("defense_stat"):
            base_payload["defense_stat"] = e["defense_stat"]
        for biome in e.get("biomes", []):
            insert_encounter(
                conn,
                key=f"{e['key']}__{biome}",
                kind="combat",
                biome=biome,
                level_min=e.get("level_min", 1),
                level_max=e.get("level_max", 99),
                weight=weight,
                trigger_types=e.get("trigger_types", []),
                payload=base_payload,
                source="seed",
            )

    # social
    for subtype, event_keys in ses._SUBTYPE_EVENTS.items():
        for ev_key in event_keys:
            ed = ses._EVENT_DEFS.get(ev_key, {})
            resolution_kind = "pickpocket" if ed.get("kind") == "pickpocket" else "soft"
            payload = {
                "stat": ed.get("stat"),
                "skill": ed.get("skill"),
                "dc": ed.get("dc"),
                "resolution_kind": resolution_kind,
                "flavor": ev_key,
            }
            insert_encounter(
                conn,
                key=ev_key,
                kind="social",
                subtype=subtype,
                weight=100.0,
                payload=payload,
                source="seed",
            )

    return conn.execute("SELECT COUNT(*) FROM game_config_encounters").fetchone()[0]


# ── Wygodne wrappery (otwierają DB_PATH gdy conn=None) ────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed_catalog_default() -> int:
    """Seed na produkcyjnej bazie (używane przez migrację/skrypt)."""
    conn = _conn()
    try:
        return seed_catalog(conn)
    finally:
        conn.close()
