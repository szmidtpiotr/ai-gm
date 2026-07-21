"""Pula plotek per region (#1190 R2).

Admin- i AI-authored plotki przypisane do REGIONU (nie kampanii) — ambient świat.
Gdy bohater nadstawia ucha w karczmie, pula jego regionu zasila `character_rumors`
(kopia na usłyszenie, żeby confirm/debunk działały per bohater). Cel plotki zawsze
z ZAMKNIĘTEGO słownika (lokacje/lochy planu — lekcja #1294), nigdy free-text LLM.

Każde wejście jest DB-error tolerant: awaria tutaj nie może zepsuć tury ani admina.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from app.core.logging import get_logger
from app.core.db_runtime import resolve_db_path

logger = get_logger(__name__)

WR_DB_PATH = resolve_db_path()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(WR_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Regiony (dla dropdownu admina) ────────────────────────────────────────────

def list_regions(conn: sqlite3.Connection | None = None) -> list[str]:
    """Regiony świata (overworld). Kolejność alfabetyczna, puste odfiltrowane."""
    own = conn is None
    c = conn or _conn()
    try:
        rows = c.execute(
            "SELECT DISTINCT region FROM world_hexes "
            "WHERE region IS NOT NULL AND region != '' AND COALESCE(map_level,0)=0 "
            "ORDER BY region"
        ).fetchall()
        return [r["region"] for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        if own:
            c.close()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_world_rumors(region: str | None = None,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    own = conn is None
    c = conn or _conn()
    try:
        if region:
            rows = c.execute(
                "SELECT * FROM world_rumors WHERE region = ? ORDER BY id DESC", (region,)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM world_rumors ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        if own:
            c.close()


def create_world_rumor(region: str, rumor_text: str, truth_flag: int = 1,
                       target_type: str | None = None, target_key: str | None = None,
                       created_by: str = "manual",
                       conn: sqlite3.Connection | None = None) -> Optional[int]:
    if not region or not (rumor_text or "").strip():
        return None
    own = conn is None
    c = conn or _conn()
    try:
        cur = c.execute(
            "INSERT INTO world_rumors (region, rumor_text, truth_flag, target_type, "
            "target_key, created_by, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (region, rumor_text.strip(), 1 if truth_flag else 0,
             target_type or None, target_key or None, created_by),
        )
        if own:
            c.commit()
        return int(cur.lastrowid)
    except sqlite3.OperationalError as e:
        logger.warning("world_rumor_create_failed", error=str(e))
        return None
    finally:
        if own:
            c.close()


def delete_world_rumor(rumor_id: Any, conn: sqlite3.Connection | None = None) -> bool:
    try:
        rid = int(rumor_id)
    except (TypeError, ValueError):
        return False
    own = conn is None
    c = conn or _conn()
    try:
        c.execute("DELETE FROM world_rumors WHERE id = ?", (rid,))
        if own:
            c.commit()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        if own:
            c.close()


# ── Draw dla bohatera (używane przez rumor_service.eavesdrop_rumor) ───────────

def draw_for_region(conn: sqlite3.Connection, character_id: int,
                    region: str | None) -> Optional[dict[str, Any]]:
    """Zwróć aktywną plotkę z puli regionu, której ten bohater jeszcze NIE słyszał
    (brak world_rumor_id w character_rumors). None gdy brak. Nie mutuje."""
    if not region:
        return None
    try:
        heard = {
            r["world_rumor_id"]
            for r in conn.execute(
                "SELECT world_rumor_id FROM character_rumors "
                "WHERE character_id = ? AND world_rumor_id IS NOT NULL",
                (character_id,),
            ).fetchall()
        }
        rows = conn.execute(
            "SELECT * FROM world_rumors WHERE region = ? AND COALESCE(is_active,1)=1 "
            "ORDER BY id",
            (region,),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    fresh = [dict(r) for r in rows if r["id"] not in heard]
    if not fresh:
        return None
    import random
    return random.choice(fresh)


# ── Fakty świata dla generatora AI ────────────────────────────────────────────

def _region_facts(conn: sqlite3.Connection, region: str) -> dict[str, Any]:
    """Zbierz zamknięty słownik faktów regionu dla LLM: lokacje, lochy, aktywny
    event. Klucze celów są WALIDOWALNE (LLM może użyć tylko tych albo żadnego)."""
    facts: dict[str, Any] = {"locations": [], "dungeons": [], "event": None}
    try:
        locs = conn.execute(
            "SELECT gl.key, gl.label FROM game_locations gl "
            "JOIN world_hexes wh ON wh.q = gl.world_hex_q AND wh.r = gl.world_hex_r "
            "WHERE wh.region = ? AND COALESCE(wh.map_level,0)=0 "
            "AND COALESCE(gl.is_active,1)=1 LIMIT 40",
            (region,),
        ).fetchall()
        facts["locations"] = [{"key": r["key"], "label": r["label"] or r["key"]} for r in locs]
    except sqlite3.OperationalError:
        pass
    try:
        dungs = conn.execute(
            "SELECT key, label FROM game_dungeons WHERE COALESCE(is_active,1)=1 LIMIT 20"
        ).fetchall()
        facts["dungeons"] = [{"key": r["key"], "label": r["label"] or r["key"]} for r in dungs]
    except sqlite3.OperationalError:
        pass
    try:
        from app.services import world_event_service as _wes
        ev = _wes.get_active_event(conn, region)
        if ev:
            facts["event"] = ev.get("label") or ev.get("title") or ev.get("name")
    except Exception:
        pass
    return facts


def _valid_target(facts: dict[str, Any], ttype: str | None, tkey: str | None):
    """Waliduj cel LLM vs zamknięty słownik. Zwróć (ttype, tkey) lub (None, None)."""
    if not ttype or not tkey:
        return None, None
    pool = {"location": facts.get("locations", []), "dungeon": facts.get("dungeons", [])}
    keys = {x["key"] for x in pool.get(ttype, [])}
    return (ttype, tkey) if tkey in keys else (None, None)


def generate_ai_rumors(region: str, count: int = 5,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """#1190 R3 — LLM generuje `count` plotek z faktów regionu (część celowo fałszywych).
    Cel z zamkniętego słownika (walidowany) albo brak. Zwraca {created, items, error?}."""
    own = conn is None
    c = conn or _conn()
    try:
        facts = _region_facts(c, region)
        if not facts["locations"] and not facts["dungeons"] and not facts["event"]:
            return {"created": 0, "items": [], "error": "Brak faktów świata dla tego regionu."}

        from app.services.llm_service import (
            content_llm_enabled, generate_chat, resolve_content_llm_config,
        )
        from app.services.world_naming_service import naming_prompt_block
        loc_lines = "\n".join(f"  - lokacja {l['key']}: {l['label']}" for l in facts["locations"])
        dun_lines = "\n".join(f"  - loch {d['key']}: {d['label']}" for d in facts["dungeons"])
        ev_line = f"Aktywne wydarzenie w regionie: {facts['event']}\n" if facts["event"] else ""
        sys_prompt = (
            "Jesteś generatorem karczemnych plotek do gry fantasy (świat Kresy, słowiańsko-"
            "germański klimat). Tworzysz krótkie, barwne plotki po polsku, jakie gracz mógłby "
            "usłyszeć przy kuflu. CZĘŚĆ plotek ma być CELOWO FAŁSZYWA (bujda, przesada, plotka "
            "uszyta pod naiwniaka) — świat nie jest wiarygodny w 100%.\n\n"
            "ZASADY:\n"
            "- Każda plotka odnosi się do JEDNEGO faktu z listy poniżej albo jest ogólnym niepokojem.\n"
            "- Jeśli plotka wskazuje konkretne miejsce z listy, podaj jego target_type "
            "('location'/'dungeon') i target_key DOKŁADNIE z listy. W przeciwnym razie zostaw null.\n"
            "- NIE wymyślaj kluczy spoza listy.\n"
            "- Około 40% plotek ma truth=false.\n"
            'Zwróć WYŁĄCZNIE JSON: {"rumors":[{"text":"...","truth":true,'
            '"target_type":null,"target_key":null}, ...]}\n\n'
            # #1527 — plotka nazywa ludzi i miejsca; bez konwencji model wkłada
            # graczowi do ucha „Agnieszkę Kowalską" z karczmy na Kresach.
            + naming_prompt_block(c, region)
        )
        user_prompt = (
            f"Region: {region}\n{ev_line}"
            f"Znane miejsca (używaj tylko tych kluczy):\n{loc_lines or '  (brak)'}\n"
            f"{dun_lines}\n\nWygeneruj {count} plotek."
        )
        cfg = resolve_content_llm_config() if content_llm_enabled() else None
        raw = generate_chat(
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": user_prompt}],
            llm_config=cfg, call_type="world_rumor_gen",
        )
        data = _parse_rumors_json(raw)
        created, items = 0, []
        for r in data[:count]:
            text = (r.get("text") or "").strip()
            if not text:
                continue
            truth = 0 if r.get("truth") is False else 1
            tt, tk = _valid_target(facts, r.get("target_type"), r.get("target_key"))
            rid = create_world_rumor(region, text, truth, tt, tk, created_by="ai", conn=c)
            if rid:
                created += 1
                items.append({"id": rid, "rumor_text": text, "truth_flag": truth,
                              "target_type": tt, "target_key": tk})
        if own:
            c.commit()
        return {"created": created, "items": items}
    except Exception as e:
        logger.warning("world_rumor_ai_gen_failed", region=region, error=str(e))
        return {"created": 0, "items": [], "error": str(e)}
    finally:
        if own:
            c.close()


def _parse_rumors_json(raw: str) -> list[dict[str, Any]]:
    """Wyłuskaj listę plotek z odpowiedzi LLM (toleruje ```json i tekst dookoła)."""
    if not raw:
        return []
    txt = raw.strip()
    if "```" in txt:
        # wytnij pierwszy blok kodu
        parts = txt.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                txt = p
                break
    # znajdź pierwszy { ... } albo [ ... ]
    try:
        start = min([i for i in (txt.find("{"), txt.find("[")) if i >= 0])
    except ValueError:
        return []
    snippet = txt[start:]
    try:
        obj = json.loads(snippet)
    except json.JSONDecodeError:
        # spróbuj domknąć do ostatniego nawiasu
        for end in range(len(snippet), 0, -1):
            try:
                obj = json.loads(snippet[:end])
                break
            except json.JSONDecodeError:
                continue
        else:
            return []
    if isinstance(obj, dict):
        return obj.get("rumors") or obj.get("items") or []
    return obj if isinstance(obj, list) else []
