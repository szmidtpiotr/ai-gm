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
        # PT-F6 #1140: also validate stat (vs the 7 canonical stats) and npc_key
        # (vs npcs) — AI-authored social encounters could hallucinate these before.
        stat = payload.get("stat")
        if stat and str(stat).upper() not in STATS:
            raise ValueError(f"stat '{stat}' spoza dozwolonych ({', '.join(STATS)})")
        npc_key = payload.get("npc_key")
        if npc_key:
            try:
                valid_npc = _existing_keys(conn, "npcs")
            except Exception:
                valid_npc = set()
            if valid_npc and npc_key not in valid_npc:
                raise ValueError(f"npc_key '{npc_key}' spoza npcs")
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


# ── BL-A3 (#1329) — anti-repeat w torze katalogu ─────────────────────────────
REPEAT_WEIGHT_PENALTY = 0.25   # kara wagi dla rekordu obecnego w historii spotkań


def _combat_signature(row: sqlite3.Row) -> str:
    """Sygnatura combatu z payloadu = posortowany, unikalny zestaw enemy_key ('a+b')."""
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except (TypeError, ValueError):
        return ""
    keys = sorted({
        str(e.get("enemy_key") or "").strip()
        for e in (payload.get("enemies") or []) if e.get("enemy_key")
    })
    return "+".join(k for k in keys if k)


def _weighted_pick_penalized(
    rows: list[sqlite3.Row], rng, penalty_keys: set, penalty: float
) -> Optional[sqlite3.Row]:
    """Jak _weighted_pick, ale rekord z enemy_key w penalty_keys dostaje wagę ×penalty."""
    pool = [r for r in rows if float(r["weight"]) > 0]
    if not pool:
        return None

    def _eff(row: sqlite3.Row) -> float:
        w = float(row["weight"])
        sig = _combat_signature(row)
        if sig and any(k in penalty_keys for k in sig.split("+")):
            w *= penalty
        return max(0.0, w)

    weights = [_eff(r) for r in pool]
    total = sum(weights)
    if total <= 0:  # kara wyzerowała wszystko → wróć do surowych wag
        weights = [float(r["weight"]) for r in pool]
        total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for row, w in zip(pool, weights):
        acc += w
        if r < acc:
            return row
    return pool[-1]


def draw_combat(
    conn: sqlite3.Connection, biome: str, level: int, rng=random,
    recent_sigs: Optional[list] = None,
) -> Optional[dict]:
    """Wylosuj encounter combat dla biomu/poziomu. Pusto → None (fallback do hardcode).

    BL-A3 (#1329): `recent_sigs` (sygnatury ostatnich spotkań, index 0 = ostatnie)
    → twarda blokada rekordu o sygnaturze identycznej z OSTATNIM spotkaniem (chyba
    że brak alternatyw) + kara wagi ×REPEAT_WEIGHT_PENALTY dla rekordów z historii.
    """
    try:
        rows = conn.execute(
            """SELECT * FROM game_config_encounters
               WHERE kind='combat' AND is_active=1 AND biome=?
                 AND level_min<=? AND level_max>=?""",
            (biome, int(level), int(level)),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    recent_sigs = recent_sigs or []
    if not recent_sigs:
        picked = _weighted_pick(rows, rng)
        return _row_to_dict(picked) if picked else None
    last_sig = recent_sigs[0]
    penalty_keys: set = set()
    for s in recent_sigs:
        penalty_keys.update(str(s).split("+"))
    # twarda blokada powtórki z rzędu (chyba że to jedyna opcja)
    eligible = [r for r in rows if _combat_signature(r) != last_sig] if last_sig else rows
    if not eligible:
        eligible = rows
    picked = _weighted_pick_penalized(eligible, rng, penalty_keys, REPEAT_WEIGHT_PENALTY)
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


def increment_times_used(conn: sqlite3.Connection, key: str) -> None:
    """PT-D4d (#1133) — podbij licznik użyć rekordu przy realnym doborze. Bezpieczne
    (brak tabeli/rekordu → no-op). Commituje samodzielnie."""
    if not key:
        return
    try:
        conn.execute(
            "UPDATE game_config_encounters SET times_used = times_used + 1 WHERE key = ?",
            (key,),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass


# ── Autoring AI w Kuźni (PT-D4b #1131) ───────────────────────────────────────
#
# Anty-halucynacja przez FK-enum: AI dostaje listę dozwolonych kluczy jako enum
# (wzór Smart Entry) i tylko wybiera — nie wymyśla. Walidacja przy zapisie odrzuca
# klucze spoza katalogu. Free-text tylko dla otoczki (title/scene_setup/gm_notes).
#
# Numbers Policy (epik #1129): DC w skali 8-24, cap złota — STARTING VALUES,
# Sandbox-tunable. Globalne stałe (split 0.5, cap 50) w kodzie, NIE w katalogu.

DC_MIN = 8
DC_MAX = 24
GOLD_PCT_CAP = 50            # cap % złota z encountera (epik Numbers Policy)
STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"]
_MAX_BATCH = 20             # bezpiecznik batcha


def _list_keys_labels(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        rows = conn.execute(f"SELECT key, label FROM {table} ORDER BY label").fetchall()
        return [{"key": r[0], "label": r[1]} for r in rows]
    except sqlite3.OperationalError:
        return []


def allowed_enums(conn: sqlite3.Connection, kind: str) -> dict:
    """Dozwolone klucze FK jako enum (anty-halucynacja).

    combat → enemy_key z game_config_enemies.
    social → skill z game_config_skills + opcj. npc_key z npcs.
    """
    if kind == "combat":
        return {"enemy_key": _list_keys_labels(conn, "game_config_enemies")}
    if kind == "social":
        return {
            "skill": _list_keys_labels(conn, "game_config_skills"),
            "npc_key": _list_keys_labels(conn, "npcs"),
        }
    raise ValueError(f"nieznany kind '{kind}' (dozwolone: combat|social)")


def build_schema(conn: sqlite3.Connection, kind: str) -> dict:
    """Pola formularza + dozwolone enumy dla danego kind (wzór Smart Entry)."""
    enums = allowed_enums(conn, kind)
    if kind == "combat":
        fields = [
            {"name": "title", "label": "Tytuł", "type": "text", "required": True, "free_text": True},
            {"name": "biome", "label": "Biom", "type": "text", "required": True},
            {"name": "level_min", "label": "Poziom min", "type": "int", "required": False},
            {"name": "level_max", "label": "Poziom max", "type": "int", "required": False},
            {"name": "weight", "label": "Waga losowania", "type": "float", "required": False},
            {"name": "enemies", "label": "Wrogowie", "type": "fk_list", "required": True, "enum_ref": "enemy_key"},
            {"name": "scene_setup", "label": "Opis sceny", "type": "textarea", "required": False, "free_text": True},
            {"name": "gm_notes", "label": "Notatki MG", "type": "textarea", "required": False, "free_text": True},
            {"name": "gold_pct", "label": f"Nagroda złota (%, max {GOLD_PCT_CAP})", "type": "int", "required": False, "max": GOLD_PCT_CAP},
        ]
    elif kind == "social":
        fields = [
            {"name": "title", "label": "Tytuł", "type": "text", "required": True, "free_text": True},
            {"name": "subtype", "label": "Subtyp sub-lokacji", "type": "text", "required": True},
            {"name": "weight", "label": "Waga losowania", "type": "float", "required": False},
            {"name": "stat", "label": "Cecha", "type": "enum", "required": True, "enum": STATS},
            {"name": "skill", "label": "Umiejętność", "type": "fk", "required": True, "enum_ref": "skill"},
            {"name": "dc", "label": f"DC ({DC_MIN}-{DC_MAX})", "type": "int", "required": True, "min": DC_MIN, "max": DC_MAX},
            {"name": "resolution_kind", "label": "Rozstrzygnięcie", "type": "enum", "required": True, "enum": ["pickpocket", "soft"]},
            {"name": "npc_key", "label": "NPC (opcjonalnie)", "type": "fk", "required": False, "enum_ref": "npc_key"},
            {"name": "soft_outcome", "label": "Wynik soft", "type": "textarea", "required": False, "free_text": True},
            {"name": "flavor", "label": "Flavor", "type": "text", "required": False, "free_text": True},
            {"name": "scene_setup", "label": "Opis sceny", "type": "textarea", "required": False, "free_text": True},
            {"name": "gm_notes", "label": "Notatki MG", "type": "textarea", "required": False, "free_text": True},
        ]
    else:
        raise ValueError(f"nieznany kind '{kind}' (dozwolone: combat|social)")
    return {"kind": kind, "fields": fields, "enums": enums}


def _clamp_int(val, lo: int, hi: int, default: int) -> int:
    try:
        val = int(val)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, val))


def normalize_payload(kind: str, payload: dict) -> dict:
    """Egzekwuj skalę DC 8-24 i cap złota. Zwraca oczyszczony payload (nie mutuje wejścia)."""
    payload = dict(payload or {})
    if kind == "social" and payload.get("dc") is not None:
        payload["dc"] = _clamp_int(payload["dc"], DC_MIN, DC_MAX, DC_MIN)
    rewards = payload.get("rewards")
    if isinstance(rewards, dict) and rewards.get("gold_pct") is not None:
        rewards = dict(rewards)
        rewards["gold_pct"] = _clamp_int(rewards["gold_pct"], 0, GOLD_PCT_CAP, 0)
        payload["rewards"] = rewards
    if payload.get("gold_pct") is not None:
        payload["gold_pct"] = _clamp_int(payload["gold_pct"], 0, GOLD_PCT_CAP, 0)
    return payload


def _slug(text: str) -> str:
    import re
    s = (text or "encounter").lower().strip()
    s = re.sub(r"[ąćęłńóśźż]", lambda m: {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z"}.get(m.group(), m.group()), s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:48] or "encounter"


def _draft_key(conn: sqlite3.Connection, draft: dict) -> str:
    base = f"ai_{draft.get('kind', 'x')}_{_slug(draft.get('title', ''))}"
    key = base
    i = 2
    while conn.execute(
        "SELECT 1 FROM game_config_encounters WHERE key=?", (key,)
    ).fetchone():
        key = f"{base}_{i}"
        i += 1
    return key


def save_encounter_from_draft(
    conn: sqlite3.Connection, draft: dict, *, source: str = "ai_forge"
) -> str:
    """Zwaliduj (FK + DC/gold) i zapisz draft do katalogu. Rzuca ValueError na złe dane.

    Klucze FK spoza katalogu → ValueError (router mapuje na 400).
    """
    kind = draft.get("kind")
    if kind not in ("combat", "social"):
        raise ValueError("kind musi być 'combat' lub 'social'")
    payload = normalize_payload(kind, draft.get("payload") or {})
    key = draft.get("key") or _draft_key(conn, draft)
    insert_encounter(
        conn,
        key=key,
        kind=kind,
        biome=draft.get("biome"),
        subtype=draft.get("subtype"),
        level_min=draft.get("level_min", 1),
        level_max=draft.get("level_max", 99),
        weight=draft.get("weight", 100.0),
        trigger_types=draft.get("trigger_types"),
        region_tag=draft.get("region_tag"),
        faction_tag=draft.get("faction_tag"),
        payload=payload,
        source=source,
        quality_rating=draft.get("quality_rating", 3),
        validate=True,
        replace=bool(draft.get("replace")),
    )
    return key


def _extract_json(text: str) -> Optional[dict]:
    import re
    cands: list[str] = []
    m = re.search(r"```json\s*\n?(.*?)```", text or "", re.DOTALL)
    if m:
        cands.append(m.group(1).strip())
    s = (text or "").strip()
    if s.startswith("{"):
        cands.append(s)
    m2 = re.search(r"\{.*\}", text or "", re.DOTALL)
    if m2:
        cands.append(m2.group(0))
    for c in cands:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            pass
    return None


def _build_generate_prompt(
    conn: sqlite3.Connection, kind: str, *, biome=None, subtype=None, level=None
) -> str:
    enums = allowed_enums(conn, kind)
    if kind == "combat":
        keys = ", ".join(e["key"] for e in enums["enemy_key"])
        return (
            "Jesteś projektantem encounterów BOJOWYCH do mrocznego fantasy RPG (WFRP-inspired).\n"
            f"BIOM: {biome or 'dowolny'}. POZIOM bohatera: {level or 'dowolny'}.\n\n"
            "ANTY-HALUCYNACJA (zasada absolutna): pole enemy_key MUSI pochodzić z tej "
            "listy istniejących wrogów — NIE wymyślaj nowych kluczy:\n"
            f"[{keys}]\n\n"
            "Zwróć TYLKO obiekt JSON w bloku ```json:\n"
            '{"kind":"combat","title":"...","biome":"' + (biome or "forest") + '",'
            '"level_min":1,"level_max":5,"weight":100,'
            '"payload":{"enemies":[{"enemy_key":"<klucz z listy>","count":2}],'
            '"scene_setup":"...","gm_notes":"...","rewards":{"gold_pct":20}}}\n\n'
            "Free-text WYŁĄCZNIE: title, scene_setup, gm_notes. "
            "enemy_key tylko z listy. gold_pct maks " + str(GOLD_PCT_CAP) + "."
        )
    if kind == "social":
        skills = ", ".join(s["key"] for s in enums["skill"])
        return (
            "Jesteś projektantem zdarzeń SPOŁECZNYCH do mrocznego fantasy RPG.\n"
            f"SUBTYP sub-lokacji: {subtype or 'dowolny'}.\n\n"
            "ANTY-HALUCYNACJA (zasada absolutna): pole skill MUSI pochodzić z tej "
            "listy istniejących umiejętności — NIE wymyślaj nowych:\n"
            f"[{skills}]\n\n"
            "Zwróć TYLKO obiekt JSON w bloku ```json:\n"
            '{"kind":"social","title":"...","subtype":"' + (subtype or "market") + '",'
            '"weight":100,"payload":{"stat":"DEX","skill":"<klucz z listy>","dc":12,'
            '"resolution_kind":"soft","soft_outcome":"...","flavor":"..."}}\n\n'
            "Free-text WYŁĄCZNIE: title, soft_outcome, flavor. "
            "skill tylko z listy. stat z: " + ", ".join(STATS) + ". "
            f"DC w skali {DC_MIN}-{DC_MAX}."
        )
    raise ValueError(f"nieznany kind '{kind}'")


def generate_encounter_drafts(
    conn: sqlite3.Connection,
    kind: str,
    count: int = 1,
    *,
    biome=None,
    subtype=None,
    level=None,
    generate_fn=None,
) -> list[dict]:
    """Wygeneruj N draftów encounterów przez LLM (schema-constrained, FK-enum).

    Zwraca listę draftów `status='pending'` — NIE zapisuje do katalogu (akceptacja
    w panelu C). Każdy draft ma `fk_valid` (czy referencje FK są realne). Drafty
    bez poprawnego JSON są pomijane. `generate_fn(messages)->str` wstrzykiwalne w testach.
    """
    if kind not in ("combat", "social"):
        raise ValueError(f"nieznany kind '{kind}' (dozwolone: combat|social)")
    if generate_fn is None:
        from app.services.llm_service import generate_chat
        generate_fn = lambda messages: generate_chat(messages=messages)  # noqa: E731

    prompt = _build_generate_prompt(conn, kind, biome=biome, subtype=subtype, level=level)
    n = max(1, min(int(count or 1), _MAX_BATCH))
    drafts: list[dict] = []
    for i in range(n):
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Wygeneruj encounter #{i + 1}. Zwróć sam obiekt JSON."},
        ]
        try:
            raw = generate_fn(messages)
        except Exception:
            continue
        obj = _extract_json(raw or "")
        if not obj:
            continue
        obj["kind"] = kind
        obj["payload"] = normalize_payload(kind, obj.get("payload") or {})
        try:
            validate_fk(conn, kind=kind, payload=obj["payload"])
            obj["fk_valid"] = True
        except ValueError:
            obj["fk_valid"] = False
        obj["status"] = "pending"
        obj.setdefault("source", "ai_forge")
        drafts.append(obj)
    return drafts


# ── Konwersacyjny autoring (mini-czat w Katalogu, #1132 opcja B) ─────────────
# Admin OPISUJE encounter własnymi słowami; agent dopytuje i buduje draft z tym
# samym kontraktem FK-enum co generate. Wzór {reply, draft} jak Smart Entry.

def _build_chat_prompt(
    conn: sqlite3.Connection, kind: str, *, biome=None, subtype=None, level=None
) -> str:
    base = _build_generate_prompt(conn, kind, biome=biome, subtype=subtype, level=level)
    return (
        base
        + "\n\nTRYB ROZMOWY: Rozmawiasz z adminem, który OPISUJE encounter własnymi "
        "słowami. Dopytaj krótko TYLKO gdy brakuje kluczowej informacji; gdy masz "
        "dość, zbuduj kompletny draft. ZAWSZE odpowiadaj JEDNYM obiektem JSON w bloku "
        "```json o kształcie:\n"
        '{"reply":"krótka odpowiedź do admina po polsku","draft": <obiekt encountera '
        "jak wyżej ALBO null gdy jeszcze dopytujesz>}\n"
        "draft=null dopóki nie masz dość informacji. Gdy draft jest gotowy, w reply "
        "napisz jednym zdaniem co złożyłeś i poproś o akceptację. Zasada anty-halucynacji "
        "oraz limity (klucze FK z listy, skala DC, cap złota) obowiązują też w tym trybie."
    )


def chat_encounter_draft(
    conn: sqlite3.Connection,
    kind: str,
    messages: list[dict],
    *,
    biome=None,
    subtype=None,
    level=None,
    generate_fn=None,
) -> dict:
    """Jedna tura konwersacyjnego autoringu encountera.

    `messages` = historia [{role:'user'|'assistant', content}]. Zwraca
    `{reply, draft|None, fk_valid|None}`. Draft (gdy agent go zbuduje) jest
    znormalizowany + zwalidowany FK — identycznie jak w `generate_encounter_drafts`,
    więc wpada w ten sam przepływ akceptacji panelu. `generate_fn(messages)->str`
    wstrzykiwalne w testach.
    """
    if kind not in ("combat", "social"):
        raise ValueError(f"nieznany kind '{kind}' (dozwolone: combat|social)")
    if generate_fn is None:
        from app.services.llm_service import generate_chat
        generate_fn = lambda m: generate_chat(messages=m)  # noqa: E731

    convo = [{"role": "system", "content": _build_chat_prompt(
        conn, kind, biome=biome, subtype=subtype, level=level)}]
    for m in (messages or []):
        role = (m or {}).get("role")
        content = str((m or {}).get("content") or "").strip()
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})

    out = {"reply": "", "draft": None, "fk_valid": None}
    try:
        raw = generate_fn(convo)
    except Exception:
        out["reply"] = "Agent nie odpowiedział — spróbuj ponownie."
        return out

    obj = _extract_json(raw or "") or {}
    out["reply"] = str(obj.get("reply") or "").strip() or (raw or "").strip()[:600]
    draft = obj.get("draft")
    if isinstance(draft, dict) and draft:
        draft["kind"] = kind
        draft["payload"] = normalize_payload(kind, draft.get("payload") or {})
        try:
            validate_fk(conn, kind=kind, payload=draft["payload"])
            draft["fk_valid"] = True
        except ValueError:
            draft["fk_valid"] = False
        draft["status"] = "pending"
        draft.setdefault("source", "ai_forge")
        out["draft"] = draft
        out["fk_valid"] = draft["fk_valid"]
    return out


# ── Panel Kuźnia: lista / delete (PT-D4c #1132) ──────────────────────────────

def list_catalog(
    conn: sqlite3.Connection,
    *,
    kind: Optional[str] = None,
    biome: Optional[str] = None,
    subtype: Optional[str] = None,
) -> list[dict]:
    """Lista rekordów katalogu dla panelu (filtr kind/biome/subtype).

    Każdy rekord ma pola surowe + `title` wyciągnięty z payloadu (nagłówek karty).
    Sortowanie: kind, biome/subtype, key — deterministyczne dla UI.
    """
    where, params = [], []
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if biome:
        where.append("biome = ?")
        params.append(biome)
    if subtype:
        where.append("subtype = ?")
        params.append(subtype)
    sql = "SELECT * FROM game_config_encounters"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY kind, COALESCE(biome, subtype, ''), key"
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    out: list[dict] = []
    for row in rows:
        d = _row_to_dict(row)
        payload = d.get("payload") or {}
        d["title"] = payload.get("title") or d["key"]
        d.pop("payload_json", None)
        out.append(d)
    return out


def delete_encounter(conn: sqlite3.Connection, key: str) -> bool:
    """Usuń rekord katalogu po kluczu. Zwraca True gdy coś usunięto (idempotentne)."""
    cur = conn.execute("DELETE FROM game_config_encounters WHERE key = ?", (key,))
    conn.commit()
    return cur.rowcount > 0


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
                faction_tag=ed.get("faction_tag"),  # PT-F6 #1140 — guard_check → straż
                source="seed",
            )

    # PT-F6 #1140: backfill faction_tag on catalogs seeded before this fix (guard_check
    # rows created with NULL faction_tag → PT-D5 friendly/hostile branches were dead).
    for _ek, _ed in ses._EVENT_DEFS.items():
        _ft = _ed.get("faction_tag")
        if _ft:
            conn.execute(
                "UPDATE game_config_encounters SET faction_tag = ? "
                "WHERE key = ? AND kind = 'social' AND (faction_tag IS NULL OR faction_tag = '')",
                (_ft, _ek),
            )
    conn.commit()

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
