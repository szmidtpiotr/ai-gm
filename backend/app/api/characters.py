import json
import logging
import os
import random
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

DB_PATH = "/data/ai_gm.db"
HIDDEN_POTENTIALS = ["blessed", "cursed", "gifted", "hollow"]
logger = logging.getLogger(__name__)

router = APIRouter()


class CharacterCreateRequest(BaseModel):
    user_id: int
    name: str
    system_id: str
    sheet_json: dict = {}
    location: str | None = None
    is_active: int = 1


class CharacterSheetPatchRequest(BaseModel):
    sheet_json: dict


def _deep_merge_dicts(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key, value in incoming.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _stat_modifier(value: int) -> int:
    return (int(value) - 10) // 2


def _build_character_sheet(base_sheet: dict, archetype: str | None = None) -> dict:
    sheet = dict(base_sheet or {})
    source_stats = dict(sheet.get("stats") or {})
    stats = {}
    for upper_key in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"):
        lower_key = upper_key.lower()
        stats[upper_key] = int(source_stats.get(upper_key, source_stats.get(lower_key, 10)))
    skills = dict(sheet.get("skills") or {})

    normalized_archetype = (archetype or sheet.get("archetype") or "").strip().lower()
    if normalized_archetype not in ("warrior", "mage"):
        normalized_archetype = "warrior"
    sheet["archetype"] = normalized_archetype

    # Archetype bonuses on top of existing values.
    if normalized_archetype == "warrior":
        stats["STR"] = int(stats.get("STR", 10)) + 2
        stats["CON"] = int(stats.get("CON", 10)) + 1
        skills["athletics"] = max(int(skills.get("athletics", 0)), 2)
        skills["melee_attack"] = max(int(skills.get("melee_attack", 0)), 2)
        skills["intimidation"] = max(int(skills.get("intimidation", 0)), 1)
    else:
        stats["INT"] = int(stats.get("INT", 10)) + 2
        stats["WIS"] = int(stats.get("WIS", 10)) + 1
        skills["arcana"] = max(int(skills.get("arcana", 0)), 2)
        skills["lore"] = max(int(skills.get("lore", 0)), 2)
        skills["spell_attack"] = max(int(skills.get("spell_attack", 0)), 1)

    # Keep stat values inside the defined 1-20 range.
    for stat_key in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"):
        stats[stat_key] = max(1, min(20, int(stats.get(stat_key, 10))))

    con_mod = _stat_modifier(stats["CON"])
    int_mod = _stat_modifier(stats["INT"])

    if normalized_archetype == "warrior":
        hp = 12 + con_mod
        sheet["current_hp"] = hp
        sheet["max_hp"] = hp
        sheet["current_mana"] = 0
        sheet["max_mana"] = 0
    else:
        hp = 6 + con_mod
        mana = 8 + int_mod
        sheet["current_hp"] = hp
        sheet["max_hp"] = hp
        sheet["current_mana"] = mana
        sheet["max_mana"] = mana

    if "hidden_potential" not in sheet:
        sheet["hidden_potential"] = random.choice(HIDDEN_POTENTIALS)

    sheet["stats"] = stats
    sheet["skills"] = skills
    return sheet


def _strip_hidden_fields(sheet: dict) -> dict:
    sanitized = dict(sheet or {})
    sanitized.pop("hidden_potential", None)
    return sanitized


OPENING_SYSTEM_PROMPT = """Jesteś Mistrzem Gry w tekstowej grze RPG osadzonej w mrocznym, brudnym świecie fantasy.
Odpowiadasz WYŁĄCZNIE po polsku.

## ZASADY NARRACJI
- Prowadź przygodę w klimacie mrocznego, realistycznego fantasy: przemoc ma konsekwencje, świat jest okrutny i niesprawiedliwy, ale pełen tajemnic i możliwości.
- Narruj w drugiej osobie liczby pojedynczej ("widzisz", "czujesz", "robisz").
- Opisuj sceny żywo i szczegółowo: zapachy, dźwięki, faktury, emocje postaci drugoplanowych.
- Zachowuj ścisłą spójność świata - pamiętaj co gracz zrobił, co powiedział, co się wydarzyło.
- Każda decyzja gracza ma realne konsekwencje - nagradzaj kreatywność, karw nieostrożność.

## KLASYFIKACJA INPUTU GRACZA - wykonaj ZAWSZE jako pierwszy krok
Przed napisaniem odpowiedzi oceń, czym jest wiadomość gracza:

1. DIALOG - gracz mówi coś do NPC lub świata (zaczyna od cudzysłowu lub "mówię/pytam/krzyczę")
   -> Odpowiedz narracją i reakcją NPC. Brak rzutu.

2. AKCJA ZWYKŁA - gracz robi coś bezpiecznego lub pewnego (ogląda okolicę, idzie drogą, pakuje rzeczy)
   -> Opisz wynik bezpośrednio. Brak rzutu.

3. AKCJA RYZYKOWNA - gracz robi coś, co może się nie powieść lub być niebezpieczne
   (skrada się, skacze przez przepaść, atakuje, przekonuje wroga, otwiera pułapkę, leczy ranę w polu)
   -> Opisz próbę, opisz napięcie, a jako OSTATNIĄ linię odpowiedzi dodaj cue do rzutu.

## FORMAT CUE DO RZUTU - BEZWZGLĘDNIE OBOWIĄZUJĄCY
Dla akcji ryzykownych, ostatnia linia odpowiedzi MUSI być jednym z poniższych (dokładnie, bez znaków interpunkcyjnych, bez markdown):

Roll Stealth d20
Roll Athletics d20
Roll Initiative d20
Roll Attack d20
Roll Awareness d20
Roll Persuasion d20
Roll Intimidation d20
Roll Survival d20
Roll Lore d20
Roll Arcana d20
Roll Medicine d20
Roll Investigation d20
Roll Dex Save d20
Roll Str Save d20
Roll Con Save d20
Roll Int Save d20
Roll Wis Save d20
Roll Cha Save d20

NIE wolno używać innych nazw, nie wolno dodawać komentarzy po cue, nie wolno używać markdown w tej linii.

## ZASADY IMMERSJI - BEZWZGLĘDNE ZAKAZY
- NIGDY nie wypisuj graczowi ponumerowanych opcji do wyboru (1. Opcja A / 2. Opcja B).
- NIGDY nie kończ odpowiedzi pytaniem "Co robisz?" - gracz sam zdecyduje.
- NIGDY nie wychodź z narracji, by komentować mechaniki gry jako narrator.
- NIGDY nie powtarzaj w kółko tego samego opisu ani tej samej struktury odpowiedzi.
- Nie używaj nagłówków markdown (###) w normalnej narracji - używaj ich tylko dla prologów i kluczowych momentów.

## ZASADY PIERWSZEJ TURY (OTWARCIE SESJI)
Jeśli to pierwsza wiadomość sesji i zawiera informacje o postaci (imię, klasa, tło):
- Zbuduj scenę otwierającą BEZPOŚREDNIO z informacji o backstory i motivacji postaci.
- NIE otwieraj w tawernie, na targu, ani w innej generycznej lokacji, chyba że backstory to sugeruje.
- Opisz miejsce, moment, nastrój - coś co natychmiast wciąga w historię tej konkretnej postaci.
- Scena powinna zawierać jeden konkretny element do zbadania lub decyzję do podjęcia.

## MECHANIKA RZUTÓW - wiedza kontekstowa
- Gracz rzuca d20 + modyfikator ze swojego arkusza.
- DC: Łatwe 8 / Średnie 12 / Trudne 16 / Ekstremalne 20 / Legendarne 24+
- Nat 20 = automatyczny sukces z dodatkowym efektem dramatycznym
- Nat 1 = automatyczna porażka z komplikacją narracyjną
- Po otrzymaniu wyniku rzutu: opisz konsekwencje narracyjnie, bez podawania liczb."""


@router.get("/campaigns/{campaign_id}/characters")
def list_characters(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    campaign = conn.execute(
        "SELECT id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    rows = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE campaign_id = ?
        ORDER BY id ASC
        """,
        (campaign_id,),
    ).fetchall()

    conn.close()

    characters = []
    for row in rows:
        item = dict(row)
        try:
            item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
        except Exception:
            item["sheet_json"] = {}
        item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])
        characters.append(item)

    return {"characters": characters}


@router.get("/characters/{character_id}")
def get_character(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])

    return item


@router.get("/characters/{character_id}/sheet")
def get_character_sheet(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        sheet_json = {}
    return {"sheet_json": _strip_hidden_fields(sheet_json)}


@router.patch("/characters/{character_id}/sheet")
def patch_character_sheet(character_id: int, req: CharacterSheetPatchRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        existing_sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        existing_sheet_json = {}

    merged_sheet_json = _deep_merge_dicts(existing_sheet_json, req.sheet_json)

    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(merged_sheet_json, ensure_ascii=False), character_id),
    )
    conn.commit()

    updated_row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not updated_row:
        raise HTTPException(status_code=500, detail="Character updated but could not be loaded")

    item = dict(updated_row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])

    return item


@router.post("/campaigns/{campaign_id}/characters")
def create_character(campaign_id: int, req: CharacterCreateRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    campaign = conn.execute(
        """
        SELECT id, system_id, model_id, language
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    if req.system_id != campaign["system_id"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"system_id mismatch: campaign uses '{campaign['system_id']}'"
        )

    # Insert first, then auto-build sheet values as part of creation flow.
    cur.execute(
        """
        INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json, location, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            campaign_id,
            req.user_id,
            req.name,
            req.system_id,
            json.dumps(req.sheet_json, ensure_ascii=False),
            req.location,
            req.is_active,
        ),
    )
    conn.commit()

    character_id = cur.lastrowid

    created_sheet = _build_character_sheet(req.sheet_json, req.sheet_json.get("archetype"))
    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(created_sheet, ensure_ascii=False), character_id),
    )
    conn.commit()

    opening_message = None
    try:
        sheet = created_sheet or {}
        archetype = str(sheet.get("archetype", "warrior")).strip().lower()
        name = (req.name or "").strip() or "Bohater"
        stats = sheet.get("stats", {}) or {}
        skills = sheet.get("skills", {}) or {}
        hp = sheet.get("max_hp", "?")
        mana = sheet.get("max_mana", 0)
        location = req.location or "nieznane miejsce"
        background = str(sheet.get("background") or "").strip()

        stat_lines = ", ".join(f"{k}:{v}" for k, v in stats.items()) if stats else ""
        skill_lines = ", ".join(
            f"{k}:{v}" for k, v in skills.items() if isinstance(v, (int, float)) and v > 0
        ) if skills else ""
        archetype_label = "Mag" if archetype == "mage" else "Wojownik"

        char_summary = (
            f"Postać: {name}, Archetyp: {archetype_label}, "
            f"HP: {hp}"
            + (f", Mana: {mana}" if mana else "")
            + (f", Statystyki: {stat_lines}" if stat_lines else "")
            + (f", Umiejętności: {skill_lines}" if skill_lines else "")
            + (f", Tło: {background}" if background else "")
            + f", Lokalizacja startowa: {location}."
        )

        opening_prompt = (
            f"{char_summary}\n\n"
            "To jest pierwsza chwila przygody. Zacznij sesję od klimatycznego opisu miejsca, "
            "w którym bohater się znajduje. Nie pytaj gracza o plany - po prostu opisz scenę "
            "i zostaw otwarte zakończenie zachęcające do działania."
        )

        messages = [
            {"role": "system", "content": OPENING_SYSTEM_PROMPT},
            {"role": "user", "content": opening_prompt},
        ]

        model = str(campaign["model_id"] or "").strip() or "gemma3:1b"
        settings_conn = sqlite3.connect(DB_PATH)
        settings_conn.row_factory = sqlite3.Row
        try:
            model_row = settings_conn.execute(
                "SELECT value FROM settings WHERE key = 'model' LIMIT 1"
            ).fetchone()
            if model_row and model_row["value"]:
                model = str(model_row["value"]).strip()
            elif os.getenv("LLM_MODEL"):
                model = os.getenv("LLM_MODEL", "gemma3:1b").strip() or "gemma3:1b"
        except Exception:
            # settings table may not exist; keep fallback model
            pass
        finally:
            settings_conn.close()

        llm_config = get_user_llm_settings_full(req.user_id)
        # Prefer per-user model selection when generating the opening message.
        model = llm_config.get("model") or model
        opening_message = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip() or None

        if opening_message:
            next_turn_row = conn.execute(
                """
                SELECT COALESCE(MAX(turn_number), 0) + 1 AS next_turn
                FROM campaign_turns
                WHERE campaign_id = ?
                """,
                (campaign_id,),
            ).fetchone()
            next_turn_number = int(next_turn_row["next_turn"] or 1)
            conn.execute(
                """
                INSERT INTO campaign_turns (
                    campaign_id, character_id, user_text, route, assistant_text, turn_number
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (campaign_id, character_id, "", "narrative", opening_message, next_turn_number),
            )
            conn.commit()
    except Exception as e:
        logger.warning("[create_character] opening message failed (non-fatal): %s", str(e))
        opening_message = None

    row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=500, detail="Character created but could not be loaded")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])
    item["opening_message"] = opening_message

    return item