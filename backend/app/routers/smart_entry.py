"""
Smart Entry Agent Router — Phase 08 Task 33 (v2)

Admin endpoints for an AI-assisted record creation/editing agent.
v2: Form-first flow — LLM fills JSON draft in one shot instead of Q&A.
"""

import json
import re
import sqlite3
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.llm_service import (
    content_llm_enabled,
    generate_chat,
    resolve_content_llm_config,
)

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin/smart-entry", tags=["admin-smart-entry"])

# ── Session store ─────────────────────────────────────────────────────────────

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 1800  # 30 minutes


def _purge_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_active"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str) -> dict:
    _purge_expired()
    if session_id not in _sessions:
        _sessions[session_id] = {
            "table": None,
            "history": [],
            "draft": {},
            "target_key": None,
            "last_active": time.time(),
        }
    else:
        _sessions[session_id]["last_active"] = time.time()
    return _sessions[session_id]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ── Table permissions ─────────────────────────────────────────────────────────

WRITABLE_TABLES = {
    "game_config_weapons",
    "game_config_items",
    "game_config_consumables",
    "game_config_enemies",
    "game_config_spells",
    "game_locations",
    "game_config_recipes",
}

READ_ONLY_TABLES = {
    "game_config_skills",
    "game_config_archetypes",
    "characters",
    "campaigns",
    "users",
}


def _assert_writable(table: str) -> None:
    if table in READ_ONLY_TABLES or table not in WRITABLE_TABLES:
        raise HTTPException(
            status_code=403,
            detail=f"Table '{table}' is read-only or not supported for Smart Entry.",
        )


# ── Schema descriptors ────────────────────────────────────────────────────────

SCHEMA_DESCRIPTORS: dict[str, dict] = {
    "game_config_weapons": {
        "required": ["key", "label", "damage_die", "weapon_type", "linked_stat"],
        "optional": ["weapon_slot", "two_handed", "value_gp", "allowed_classes", "description", "note", "targeting", "weight_kg", "effect_json"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tej broni, np. 'cursed_sword'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ta broń (wyświetlana nazwa)?",
            },
            "damage_die": {
                "type": "single_choice",
                "question": "Jak duże obrażenia zadaje?",
                "options": [
                    {"label": "d4", "description": "Lekka broń"},
                    {"label": "d6", "description": "Standardowa broń"},
                    {"label": "d8", "description": "Solidna broń"},
                    {"label": "d10", "description": "Ciężka broń"},
                    {"label": "d12", "description": "Broń dwuręczna lub potężna"},
                ],
            },
            "weapon_type": {
                "type": "single_choice",
                "question": "Jaki to rodzaj broni?",
                "options": [
                    {"label": "melee", "description": "Broń do walki wręcz"},
                    {"label": "ranged", "description": "Broń miotana lub strzelecka"},
                    {"label": "spell", "description": "Broń magiczna / zaklęcie"},
                ],
            },
            "linked_stat": {
                "type": "single_choice",
                "question": "Na jaki atrybut postaci wpływa ta broń?",
                "options": [
                    {"label": "STR", "description": "Siła — dla broni do walki wręcz"},
                    {"label": "DEX", "description": "Zręczność — dla broni zwinnych i ranged"},
                    {"label": "INT", "description": "Inteligencja — dla broni magicznych"},
                ],
            },
            "two_handed": {
                "type": "boolean",
                "question": "Czy broń wymaga obu rąk? (Deprecated — użyj weapon_slot=two_handed)",
            },
            "weapon_slot": {
                "type": "single_choice",
                "question": "Który slot zajmuje ta broń?",
                "options": [
                    {"label": "main_hand", "description": "Główna ręka (miecz, topór, młot — jednoręczne)"},
                    {"label": "two_handed", "description": "Oburęczna — zajmuje główną i pomocniczą rękę (łuk, kostur, miecz dwuręczny)"},
                    {"label": "off_hand_only", "description": "Tylko pomocnicza ręka (tarcza, parująca broń)"},
                    {"label": "either", "description": "Może być w obu rękach jednocześnie (sztylety — dwa sztylety jednocześnie)"},
                ],
            },
            "value_gp": {
                "type": "number",
                "question": "Ile kosztuje ta broń (w złotych monetach, 1-500)?",
                "min": 0,
                "max": 500,
            },
            "allowed_classes": {
                "type": "multi_choice",
                "question": "Które klasy mogą używać tej broni?",
                "options": [
                    {"label": "warrior", "description": "Wojownik"},
                    {"label": "scholar", "description": "Uczony"},
                    {"label": "ranger", "description": "Łucznik/Strzelec"},
                ],
            },
            "description": {
                "type": "textarea",
                "question": "Opis broni dla GM (wygląd, materiał, historia, klimat).",
            },
            "note": {
                "type": "textarea",
                "question": "Specjalne zdolności / reguły (np. 'Zadaje 1k4 trucizny przy trafieniu, DC 12 odporność').",
            },
            "targeting": {
                "type": "single_choice",
                "question": "Rodzaj celowania?",
                "options": [
                    {"label": "single", "description": "Jeden cel"},
                    {"label": "aoe", "description": "Obszar (AOE)"},
                    {"label": "line", "description": "Linia"},
                ],
            },
            "weight_kg": {
                "type": "number",
                "question": "Waga w kilogramach (np. 0.5, 2.0)?",
                "min": 0,
            },
            "effect_json": {
                "type": "effect_builder",
                "question": (
                    "Efekty bojowe przy trafieniu (JSON). Schemat:\n"
                    '{"effects":[{"type":"extra_damage","dice":"1d6","damage_type":"fire"}]}\n'
                    "lub: on_hit_save z on_fail: extra_damage albo apply_condition.\n"
                    "damage_type: fire|cold|poison|lightning|magic|physical\n"
                    "apply_condition keys: poisoned|burning|bleeding|stunned|blinded|frightened|cursed\n"
                    "Zostaw null jeśli brak efektów specjalnych."
                ),
            },
        },
    },
    "game_config_items": {
        "required": ["key", "label", "item_type", "value_gp"],
        "optional": ["ac_bonus", "armor_coverage", "effect_json", "is_component", "component_type"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tego przedmiotu, np. 'iron_shield'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ten przedmiot (wyświetlana nazwa)?",
            },
            "item_type": {
                "type": "single_choice",
                "question": "Jaki to rodzaj przedmiotu?",
                "options": [
                    {"label": "relic", "description": "Relikt / artefakt — zakładany w slot reliktu, daje pasywne bonusy (staty/AC/umiejętności) z effect_json"},
                    {"label": "armor", "description": "Zbroja / ochrona"},
                    {"label": "accessory", "description": "Akcesoria (pierścień, amulet)"},
                    {"label": "misc", "description": "Różne przedmioty"},
                    {"label": "material", "description": "Surowiec / komponent rzemieślniczy (skóry, kły, rudy, esencje) — ustaw is_component=1 + component_type"},
                    {"label": "key_item", "description": "Przedmiot fabularny / klucz"},
                    {"label": "map", "description": "Mapa — użycie odkrywa fragment mgły wojny (effect_json: mode radius/region/hexes)"},
                ],
            },
            "value_gp": {
                "type": "number",
                "question": "Ile kosztuje ten przedmiot (w złotych monetach)?",
                "min": 0,
            },
            "ac_bonus": {
                "type": "number",
                "question": "O ile punktów zwiększa Klasę Pancerza (AC)? (0-8)",
                "min": 0,
                "max": 8,
            },
            "armor_coverage": {
                "type": "single_choice",
                "question": "Jaki obszar ciała chroni ta zbroja? (tylko dla item_type='armor')",
                "options": [
                    {"label": "head", "description": "Głowa (hełm, kaptur, czepiec)"},
                    {"label": "torso", "description": "Tors (kirys, kolczuga, kaftan)"},
                    {"label": "limb_arm", "description": "Ramię (rękawica, naramiennik) — gracz wybiera lewe lub prawe"},
                    {"label": "limb_leg", "description": "Noga (nagolennik) — gracz wybiera lewą lub prawą"},
                    {"label": "hands", "description": "Dłonie (rękawice)"},
                    {"label": "feet", "description": "Stopy (buty, sandały)"},
                    {"label": "back", "description": "Plecy (płaszcz, peleryna, kołczan)"},
                    {"label": "full", "description": "Pełne pokrycie (zbroja płytowa) — zajmuje tors + 4 kończyny jednocześnie"},
                ],
            },
            "effect_json": {
                "type": "text",
                "question": "Opisz efekt przedmiotu w formacie JSON (opcjonalnie), np. {\"type\": \"heal\", \"amount\": 5}.",
            },
            "is_component": {
                "type": "single_choice",
                "question": "Czy to komponent rzemieślniczy (surowiec do wytwarzania)?",
                "options": [
                    {"label": "0", "description": "Nie — zwykły przedmiot"},
                    {"label": "1", "description": "Tak — komponent (pokaż z badge 🧩 w osobnej sekcji ekwipunku)"},
                ],
            },
            "component_type": {
                "type": "single_choice",
                "question": "Rodzaj komponentu (tylko gdy is_component=1).",
                "options": [
                    {"label": "pelt", "description": "Skóra / futro (skóra wilcza, łuska jaszczura)"},
                    {"label": "fang", "description": "Kieł / ząb / pazur"},
                    {"label": "herb", "description": "Zioło / grzyb / korzeń"},
                    {"label": "ore", "description": "Ruda / minerał / kruszec"},
                    {"label": "essence", "description": "Esencja / posoka / gruczoł magiczny"},
                    {"label": "part", "description": "Część / szczątek (pył kostny, sadło, jedwab)"},
                ],
            },
        },
    },
    "game_config_consumables": {
        "required": ["key", "label", "effect_type", "base_price"],
        "optional": ["effect_dice", "effect_bonus"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tego konsumabla, np. 'healing_potion'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ten konsumable (wyświetlana nazwa)?",
            },
            "effect_type": {
                "type": "single_choice",
                "question": "Jaki efekt ma ten konsumable?",
                "options": [
                    {"label": "heal_hp", "description": "Leczy punkty życia"},
                    {"label": "restore_mana", "description": "Przywraca manę"},
                    {"label": "cure_condition", "description": "Usuwa negatywny stan"},
                    {"label": "buff", "description": "Daje tymczasowe wzmocnienie"},
                ],
            },
            "base_price": {
                "type": "number",
                "question": "Ile kosztuje ten konsumable (w złotych monetach)?",
                "min": 1,
            },
            "effect_dice": {
                "type": "text",
                "question": "Ile kości efektu? Podaj notację np. '1d8', '2d6' (opcjonalnie).",
            },
            "effect_bonus": {
                "type": "number",
                "question": "Stały bonus do efektu (np. +2 do leczenia, opcjonalnie).",
            },
        },
    },
    "game_config_enemies": {
        "required": ["key", "label", "tier", "hp_base", "ac_base", "attack_bonus", "damage_dice"],
        "optional": ["drop_chance", "loot_table_key"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tego przeciwnika, np. 'goblin_raider'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ten przeciwnik (wyświetlana nazwa)?",
            },
            "tier": {
                "type": "single_choice",
                "question": "Jaka jest siła tego przeciwnika?",
                "options": [
                    {"label": "weak", "description": "Słaby — łatwy do pokonania"},
                    {"label": "standard", "description": "Standardowy — normalny wróg"},
                    {"label": "elite", "description": "Elitarny — silniejszy niż przeciętny"},
                    {"label": "boss", "description": "Boss — bardzo potężny"},
                ],
            },
            "hp_base": {
                "type": "number",
                "question": "Ile podstawowych punktów życia ma ten przeciwnik?",
                "min": 1,
            },
            "ac_base": {
                "type": "number",
                "question": "Jaka jest podstawowa Klasa Pancerza (AC) tego przeciwnika? (zwykle 8-18)",
                "min": 1,
            },
            "attack_bonus": {
                "type": "number",
                "question": "Jaki bonus do ataku ma ten przeciwnik?",
            },
            "damage_dice": {
                "type": "text",
                "question": "Ile obrażeń zadaje w jednym ataku? Podaj notację np. '1d6', '2d8+2'.",
            },
            "drop_chance": {
                "type": "number",
                "question": "Szansa na upuszczenie łupu (0.0-1.0, opcjonalnie)?",
                "min": 0,
                "max": 1,
            },
            "loot_table_key": {
                "type": "text",
                "question": "Klucz tabeli łupów (opcjonalnie, np. 'goblin_loot').",
            },
        },
    },
    "game_config_spells": {
        "required": ["key", "label", "tier", "mana_cost", "spell_type"],
        "optional": ["damage_die", "heal_die", "effect_stat", "effect_type", "effect_duration", "target_zone", "aoe", "description", "rank2_json", "rank3_json"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla zaklęcia, np. 'frost_bolt'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać to zaklęcie (wyświetlana nazwa)?",
            },
            "tier": {
                "type": "number",
                "question": "Jaki poziom mocy ma zaklęcie? (1=podstawowe, 2=solidne, 3=silne, 4=potężne, 5=legendarne)",
                "min": 1,
                "max": 5,
            },
            "mana_cost": {
                "type": "number",
                "question": "Ile many kosztuje rzucenie (1–10)?",
                "min": 1,
                "max": 10,
            },
            "spell_type": {
                "type": "single_choice",
                "question": "Jaki rodzaj zaklęcia?",
                "options": [
                    {"label": "attack", "description": "Atak — zadaje obrażenia jednemu wrogowi"},
                    {"label": "attack_aoe", "description": "Atak AoE — uderza wszystkich wrogów"},
                    {"label": "heal", "description": "Leczenie — przywraca HP"},
                    {"label": "defense", "description": "Obrona — tarcza, buffy"},
                    {"label": "effect", "description": "Efekt — nakłada stan na cel"},
                ],
            },
            "damage_die": {
                "type": "text",
                "question": "Kość obrażeń (np. '2d6', '1d8'). Zostaw puste jeśli nie atakuje.",
            },
            "heal_die": {
                "type": "text",
                "question": "Kość leczenia (np. '2d6'). Zostaw puste jeśli nie leczy.",
            },
            "effect_stat": {
                "type": "single_choice",
                "question": "Na jaki atrybut rzuca się rzut obronny celu (jeśli zaklęcie nakłada stan)?",
                "options": [
                    {"label": "STR", "description": "Siła"},
                    {"label": "DEX", "description": "Zręczność"},
                    {"label": "CON", "description": "Kondycja"},
                    {"label": "INT", "description": "Inteligencja"},
                    {"label": "WIS", "description": "Mądrość"},
                    {"label": "CHA", "description": "Charyzma"},
                ],
            },
            "effect_type": {
                "type": "text",
                "question": "Klucz nakładanego stanu (np. 'sleeping', 'stunned', 'poisoned', 'blinded'). Zostaw puste jeśli brak.",
            },
            "effect_duration": {
                "type": "number",
                "question": "Ile rund trwa efekt (domyślnie 1)?",
                "min": 1,
                "max": 10,
            },
            "target_zone": {
                "type": "single_choice",
                "question": "Zasięg zaklęcia — w jakiej strefie może być cel?",
                "options": [
                    {"label": "any", "description": "Dowolna strefa"},
                    {"label": "self", "description": "Tylko siebie"},
                    {"label": "engaged", "description": "Tylko cel w zasięgu walki wręcz"},
                    {"label": "ranged", "description": "Tylko cel w zasięgu dystansowym"},
                ],
            },
            "aoe": {
                "type": "boolean",
                "question": "Czy zaklęcie trafia wszystkich wrogów naraz (AoE)?",
            },
            "description": {
                "type": "textarea",
                "question": "Opis zaklęcia dla GM (wygląd efektu, klimat, atmosfera, 2-3 zdania).",
            },
            "rank2_json": {
                "type": "textarea",
                "question": "Ulepszenie na Rangę 2 (JSON, np. '{\"mana_cost\":2,\"damage_die\":\"2d8\"}'). Zostaw puste jeśli brak.",
            },
            "rank3_json": {
                "type": "textarea",
                "question": "Ulepszenie na Rangę 3 (JSON, np. '{\"mana_cost\":1,\"damage_die\":\"3d6\"}'). Zostaw puste jeśli brak.",
            },
        },
    },
    "game_locations": {
        "required": ["key", "label", "location_type", "location_subtype", "biome", "tier", "description"],
        "optional": ["parent_key", "safe_for_rest", "rules"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) lokacji, np. 'karczma_pod_zlotym_krukiem'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ta lokacja (wyświetlana nazwa)?",
            },
            "location_type": {
                "type": "single_choice",
                "question": "Typ lokacji?",
                "options": [
                    {"label": "macro", "description": "Makro — duża, samodzielna lokacja (miasto, las, góry)"},
                    {"label": "sub",   "description": "Pod-lokacja — wewnątrz makra (karczma w mieście)"},
                ],
            },
            "location_subtype": {
                "type": "single_choice",
                "question": "Podtyp lokacji (z curated listy)?",
                "options": [
                    {"label": "tavern",          "description": "Karczma / Tawerna"},
                    {"label": "inn",             "description": "Zajazd"},
                    {"label": "shop",            "description": "Sklep"},
                    {"label": "temple",          "description": "Świątynia"},
                    {"label": "guild",           "description": "Cech / Gildia"},
                    {"label": "village",         "description": "Wioska"},
                    {"label": "town",            "description": "Miasteczko"},
                    {"label": "city",            "description": "Miasto"},
                    {"label": "castle",          "description": "Zamek / Twierdza"},
                    {"label": "ruin",            "description": "Ruiny"},
                    {"label": "cave",            "description": "Jaskinia"},
                    {"label": "dungeon",         "description": "Loch"},
                    {"label": "tower",           "description": "Wieża"},
                    {"label": "watchtower",      "description": "Strażnica"},
                    {"label": "forest_clearing", "description": "Polana leśna"},
                    {"label": "camp",            "description": "Obóz"},
                    {"label": "road",            "description": "Droga / Trakt"},
                    {"label": "bridge",          "description": "Most"},
                    {"label": "crossroads",      "description": "Rozdroże"},
                    {"label": "graveyard",       "description": "Cmentarz"},
                    {"label": "swamp_hut",       "description": "Chata na mokradłach"},
                    {"label": "mine",            "description": "Kopalnia"},
                    {"label": "harbor",          "description": "Port"},
                    {"label": "other",           "description": "Inne"},
                ],
            },
            "biome": {
                "type": "single_choice",
                "question": "Biom / klimat geograficzny?",
                "options": [
                    {"label": "forest",      "description": "Las"},
                    {"label": "mountain",    "description": "Góry"},
                    {"label": "swamp",       "description": "Bagna"},
                    {"label": "plains",      "description": "Równiny"},
                    {"label": "coast",       "description": "Wybrzeże"},
                    {"label": "desert",      "description": "Pustynia"},
                    {"label": "tundra",      "description": "Tundra"},
                    {"label": "urban",       "description": "Tereny miejskie"},
                    {"label": "underground", "description": "Podziemia"},
                ],
            },
            "tier": {
                "type": "number",
                "question": "Poziom trudności / siły (1=lvl 1-2, 2=lvl 3-4, 3=lvl 5-6, 4=lvl 7-8, 5=lvl 9+).",
                "min": 1,
                "max": 5,
            },
            "description": {
                "type": "textarea",
                "question": "Klimatyczny opis lokacji dla GM (wygląd, atmosfera, dźwięki, zapachy, 2-4 zdania).",
            },
            "parent_key": {
                "type": "text",
                "question": "Klucz lokacji nadrzędnej (tylko dla 'sub'). Zostaw puste dla 'macro'.",
            },
            "safe_for_rest": {
                "type": "boolean",
                "question": "Czy bohaterowie mogą tu bezpiecznie odpocząć (karczmy, świątynie, obozy = TAK)?",
            },
            "rules": {
                "type": "textarea",
                "question": "Reguły specjalne w formacie JSON (opcjonalnie), np. '{\"no_combat\": true, \"rest_bonus\": 2}'.",
            },
        },
    },
    # #1338 BL-C3 — przepisy rzemiosła (game_config_recipes). Bohater dostarcza
    # komponenty, rzemieślnik NPC (kowal/zielarz) wytwarza za opłatą.
    "game_config_recipes": {
        "required": ["key", "label", "output_type", "crafter_type"],
        "optional": ["inputs_json", "output_key", "output_qty", "service_cost_gold", "is_hidden", "is_active"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Unikalny klucz (slug) przepisu, np. 'herbal_potion_minor'.",
            },
            "label": {
                "type": "text",
                "question": "Nazwa przepisu wyświetlana graczowi.",
            },
            "output_type": {
                "type": "single_choice",
                "question": "Co wytwarza ten przepis?",
                "options": [
                    {"label": "consumable", "description": "Mikstura / przedmiot do ekwipunku"},
                    {"label": "weapon_upgrade", "description": "Ulepszenie broni (+1 obrażeń, afiks craft_hone)"},
                    {"label": "armor_repair", "description": "Naprawa założonego pancerza"},
                ],
            },
            "crafter_type": {
                "type": "single_choice",
                "question": "Jaki rzemieślnik wykonuje ten przepis?",
                "options": [
                    {"label": "smith", "description": "Kowal — broń, pancerz"},
                    {"label": "herbalist", "description": "Zielarz — mikstury, zioła"},
                ],
            },
            "inputs_json": {
                "type": "textarea",
                "question": "Składniki jako tablica JSON, np. '[{\"item_key\": \"healing_herb\", \"qty\": 2}]'.",
            },
            "output_key": {
                "type": "text",
                "question": "Klucz wyniku dla typu 'consumable' (klucz konsumabli), np. 'potion_healing_minor'. Puste dla ulepszenia/naprawy.",
            },
            "output_qty": {
                "type": "number",
                "question": "Ile sztuk wyniku (dla consumable)?",
                "min": 1,
                "max": 20,
            },
            "service_cost_gold": {
                "type": "number",
                "question": "Opłata rzemieślnika w złocie (0-500).",
                "min": 0,
                "max": 500,
            },
            "is_hidden": {
                "type": "boolean",
                "question": "Ukryty przepis (legendarny, niedostępny w tej fazie)? Zwykle NIE.",
            },
            "is_active": {
                "type": "boolean",
                "question": "Przepis aktywny (dostępny w grze)?",
            },
        },
    },
}


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _db_get(table: str, key: str) -> Optional[dict]:
    """SELECT WHERE key = ?"""
    conn = _get_db()
    try:
        row = conn.execute(f"SELECT * FROM {table} WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _db_insert(table: str, record: dict) -> str:
    """INSERT into table, returns key."""
    conn = _get_db()
    try:
        cols = ", ".join(record.keys())
        placeholders = ", ".join(["?" for _ in record])
        conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(record.values()),
        )
        # U11c dual-write: re-read legacy row → upsert game_items (item-kind tables only)
        try:
            from app.services.game_items_service import sync_from_legacy
            sync_from_legacy(conn, table, record.get("key", ""))
        except Exception:
            pass
        conn.commit()
        return record["key"]
    finally:
        conn.close()


def _db_update_field(table: str, key: str, field: str, value: Any) -> None:
    """UPDATE single field WHERE key = ?"""
    conn = _get_db()
    try:
        conn.execute(
            f"UPDATE {table} SET {field} = ? WHERE key = ?",
            (value, key),
        )
        # U11c dual-write: re-read legacy row → upsert game_items (item-kind tables only)
        try:
            from app.services.game_items_service import sync_from_legacy
            sync_from_legacy(conn, table, key)
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


# ── LLM prompt (v2 — JSON output) ─────────────────────────────────────────────

SMART_ENTRY_SYSTEM_PROMPT_V2 = """Jesteś asystentem WYPEŁNIANIA FORMULARZA rekordów gry RPG (mroczna fantasy, WFRP-inspired).
Admin opisuje rekord. Ty WYPEŁNIASZ POLA — nie zapisujesz, nie tworzysz rekordu (to robi admin przyciskiem).

ZAWSZE odpowiadaj WYŁĄCZNIE prawidłowym JSON-em w formacie:
{"reply": "krótki komentarz co wypełniłem (po polsku, max 2 zdania)", "draft": {"pole": wartość, ...}}

ZASADY:
- Pola i dozwolone wartości są podane w kontekście (SCHEMAT). NIE wymyślaj innych nazw pól.
- single_choice: użyj DOKŁADNIE jednej z podanych wartości (np. "d6", "melee", "STR")
- multi_choice: lista wartości oddzielona przecinkami, np. "warrior,scholar,ranger"
- boolean: 1 lub 0
- number: liczba (nie string)
- 'key' (slug): generuj z 'label': małe litery, polskie znaki → ascii, spacje → _, bez specjalnych
- 'description': ZAWSZE generuj klimatyczny opis dla GM (wygląd, historia, atmosfera, 2-3 zdania)
- 'note': ZAWSZE generuj krótki opis efektów dla GM (co czuje bohater, jak GM powinien to opisać)
- Nie pisz "zapisałem" ani "utworzyłem rekord" — tylko wypełniasz formularz
- Jeśli admin zmienia konkretne pole, zaktualizuj tylko to pole i wróć cały current_draft

POLE effect_json (MECHANIKA BOJOWA — bronie i przedmioty):
Generuj jako JSON string używając formatu Effect Object (F1 schema). OBOWIĄZKOWO schema_version:1.
Format: {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"TYP","value":N}]}

Dostępne typy efektów (effect_category="gear_bonus"):
  damage_bonus  — stały bonus do obrażeń po mnożniku (np. +3 na każdy atak)
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":3}]}
  heal_on_hit   — leczenie atakującego przy trafieniu (kradzież życia, life-steal)
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"heal_on_hit","value":2}]}
  ac_bonus      — bonus do Klasy Pancerza z broni/przedmiotu (np. parująca broni, tarcza-miecz)
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":1}]}
  static_stat_modifier — modyfikator statystyki; wymaga pola "stat". DZIAŁA W WALCE I POZA WALKĄ (testy).
                  Dozwolone "stat": 7 statystyk STR|DEX|CON|INT|WIS|CHA|LCK ORAZ cele pochodne ac|attack_bonus|damage_bonus|initiative
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"STR","value":2}]}
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"CHA","value":2}]}
  static_skill_modifier — bonus do UMIEJĘTNOŚCI; wymaga pola "skill". Działa OD ZERA — nadaje umiejętność
                  nawet gdy bohater jej NIE wykupił (np. magiczny wytrych pozwala otwierać zamki bez wprawy).
                  Dozwolone "skill" (klucz z game_config_skills): lockpick (otwieranie zamków), stealth (skradanie),
                  persuasion, deception, intimidation, awareness, investigation, medicine, survival, tracking,
                  pickpocket, athletics, acrobatics, lore, arcana, haggling, climb, swim i in.
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_skill_modifier","skill":"lockpick","value":2}]}
  narrative_only — efekt narracyjny bez mechaniki (opis dla GM). Używaj TYLKO gdy naprawdę brak twardego efektu.
                  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"narrative_only"}]}

Można łączyć wiele typów w jednej tablicy effects[].
Przykład miecza kradnącego życie i zadającego bonus obrażeń:
  {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":2},{"type":"heal_on_hit","value":1}]}
Zostaw null jeśli broń nie ma efektów specjalnych.

RELIKTY / ARTEFAKTY (item_type="relic"):
Gdy admin opisuje PASYWNY przedmiot zakładany przez gracza (daje statystykę, pancerz LUB umiejętność —
np. "amulet dający +2 CHA", "magiczny wytrych do otwierania zamków", "pierścień skradania"):
  - USTAW item_type="relic" (NIE "accessory", NIE "misc"),
  - WYGENERUJ effect_json z realnym efektem (static_stat_modifier / static_skill_modifier / ac_bonus),
    a NIE narrative_only — relikt ma działać mechanicznie.
Przykład magicznego wytrycha (otwiera zamki bez umiejętności):
  item_type="relic", effect_json = {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_skill_modifier","skill":"lockpick","value":2}]}
Przykład amuletu charyzmy:
  item_type="relic", effect_json = {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"CHA","value":2}]}

TABELA game_config_spells — zaklęcia Uczonego (NIE mają effect_json):
- 'key': slug z label (polskie znaki→ascii, spacje→_)
- 'tier': liczba 1–5
- 'mana_cost': liczba 1–10
- 'spell_type': attack|attack_aoe|heal|defense|effect
- 'damage_die': tylko dla attack/attack_aoe, np. "2d6". Dla innych null.
- 'heal_die': tylko dla heal, np. "2d6". Dla innych null.
- 'effect_stat': atrybut rzutu obronnego (dla type=effect), np. "WIS". Dla innych null.
- 'effect_type': klucz stanu np. "silence", "sleeping", "stunned", "poisoned". Dla innych null.
- 'effect_duration': ile rund trwa efekt (liczba, domyślnie 1–3)
- 'aoe': 1 jeśli trafia wszystkich wrogów, 0 jeśli jeden cel
- 'rank2_json' i 'rank3_json': JSON string z ulepszeniami wyższej rangi. ZAWSZE generuj jeśli zaklęcie ma sens na wyższym poziomie:
  Dla ataku: '{"mana_cost":2,"damage_die":"2d8"}' (lepsza kość lub tańszy koszt)
  Dla leczenia: '{"mana_cost":2,"heal_die":"2d8"}'
  Dla efektu/debuffu: '{"mana_cost":3,"effect_duration":4}' (dłuższy efekt lub tańszy)
  Dla obrony: '{"mana_cost":2,"ac_bonus":5,"duration":2}'
  Jeśli naprawdę brak sensu dla wyższej rangi — wstaw null (nie placeholder tekst).

TABELA game_locations — lokacje świata gry (mroczne, klimatyczne, polskie nazewnictwo):
- 'key': slug z label (polskie znaki→ascii, spacje→_, np. "Karczma Pod Złotym Krukiem" → "karczma_pod_zlotym_krukiem")
- 'label': polska nazwa lokacji, najlepiej z przedimkiem ("Karczma Pod...", "Ruiny Zapomnianego...", "Las Zgniłych Kości")
- 'location_type': "macro" dla dużych lokacji (miasto, las, góry, ruiny), "sub" dla wewnętrznych (karczma w mieście, sala tronowa w zamku)
- 'location_subtype': DOKŁADNIE jedna wartość z listy (tavern, inn, shop, temple, guild, village, town, city, castle, ruin, cave, dungeon, tower, watchtower, forest_clearing, camp, road, bridge, crossroads, graveyard, swamp_hut, mine, harbor, other)
- 'biome': DOKŁADNIE jedna z listy (forest, mountain, swamp, plains, coast, desert, tundra, urban, underground)
  - tawerny/sklepy/świątynie/kamienice → "urban"
  - jaskinie/lochy/kopalnie → "underground"
  - polany leśne → "forest"
- 'tier': liczba 1-5 (1=peryferia/wioski, 2=miasteczka, 3=miasta, 4=elitarne lokacje, 5=legendarne ruiny i siedziby bossów)
- 'description': 2-4 zdania, mroczna klimatyczna proza — wygląd, atmosfera, dźwięki, zapachy, sugerowane wydarzenia dla GM
- 'parent_key': klucz lokacji-rodzica (tylko jeśli location_type=sub). Dla macro zostaw null/pusty.
- 'safe_for_rest': 1 dla karczm, świątyń, obozów, dobrze strzeżonych miejsc; 0 dla podziemi, ruin, bagien, dzikich obszarów
- 'rules': JSON string lub null. Przykłady:
  - świątynia: '{"no_combat": true, "rest_bonus": 2, "reason": "Sacred ground"}'
  - tajemna jaskinia: '{"stealth_check": true, "required_item": "torch"}'
  - dziki teren: null (brak reguł specjalnych)
"""


def _build_schema_constraint_text(table: str) -> str:
    """Build a human-readable schema description for the LLM."""
    schema = SCHEMA_DESCRIPTORS.get(table, {})
    if not schema:
        return ""
    lines = [f"SCHEMAT {table}:", "Wymagane:"]
    for fk in schema.get("required", []):
        fd = schema["fields"].get(fk, {})
        line = f"  {fk} (typ={fd.get('type', 'text')})"
        if fd.get("options"):
            opts = [str(o.get("label", o) if isinstance(o, dict) else o) for o in fd["options"]]
            line += f" → dozwolone: [{', '.join(opts)}]"
        if "min" in fd:
            line += f" min={fd['min']}"
        if "max" in fd:
            line += f" max={fd['max']}"
        lines.append(line)
    if schema.get("optional"):
        lines.append("Opcjonalne:")
        for fk in schema.get("optional", []):
            fd = schema["fields"].get(fk, {})
            line = f"  {fk} (typ={fd.get('type', 'text')})"
            if fd.get("options"):
                opts = [str(o.get("label", o) if isinstance(o, dict) else o) for o in fd["options"]]
                line += f" → dozwolone: [{', '.join(opts)}]"
            lines.append(line)
    return "\n".join(lines)


def _parse_llm_draft_response(reply: str) -> tuple[str, dict]:
    """Parse LLM reply that should contain JSON {reply, draft}. Returns (text, draft)."""
    text = reply.strip()
    # Remove markdown code fences
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = text.replace('```', '').strip()
    # Try whole thing as JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return str(data.get("reply", "")), dict(data.get("draft", {}))
    except json.JSONDecodeError:
        pass
    # Find first { ... } block
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict):
                            return str(data.get("reply", reply)), dict(data.get("draft", {}))
                    except json.JSONDecodeError:
                        break
    return reply, {}


# ── Request/response models ───────────────────────────────────────────────────

class SmartEntryMessageReq(BaseModel):
    session_id: str
    table: Optional[str] = None
    message: str = ""
    current_draft: Optional[dict] = None  # full form state from frontend
    target_key: Optional[str] = None      # if editing an existing record


class SmartEntrySaveReq(BaseModel):
    session_id: str
    draft: dict = {}        # form values from frontend
    table: Optional[str] = None
    target_key: Optional[str] = None  # if editing existing


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/schema")
def smart_entry_schema(table: str, _: None = Depends(_require_admin)):
    """Return field schema for frontend form rendering."""
    schema = SCHEMA_DESCRIPTORS.get(table)
    if not schema:
        raise HTTPException(status_code=404, detail=f"No schema for table '{table}'")

    FIELD_LABELS = {
        "key": "Klucz (slug)", "label": "Nazwa", "damage_die": "Kość obrażeń",
        "weapon_type": "Typ broni", "linked_stat": "Stat. powiązana", "two_handed": "Dwuręczna",
        "value_gp": "Cena (gp)", "allowed_classes": "Klasy", "item_type": "Typ przedmiotu",
        "ac_bonus": "Bonus AC", "effect_json": "Efekt (JSON)", "effect_type": "Typ efektu",
        "base_price": "Cena bazowa", "effect_dice": "Kości efektu", "effect_bonus": "Bonus efektu",
        "tier": "Poziom", "hp_base": "HP bazowe", "ac_base": "AC bazowe",
        "attack_bonus": "Bonus do ataku", "damage_dice": "Kości obrażeń",
        "drop_chance": "Szansa łupu", "loot_table_key": "Tabela łupów",
        "description": "Opis (dla GM)", "note": "Zdolności specjalne",
        "targeting": "Rodzaj celowania", "weight_kg": "Waga (kg)",
        "effect_json": "Efekty bojowe (JSON)",
        # Locations
        "location_type": "Typ lokacji", "location_subtype": "Podtyp",
        "biome": "Biom", "parent_key": "Lokacja nadrzędna",
        "safe_for_rest": "Bezpieczna do odpoczynku", "rules": "Reguły (JSON)",
        # Recipes (#1338 BL-C3)
        "output_type": "Typ wyniku", "crafter_type": "Rzemieślnik",
        "inputs_json": "Składniki (JSON)", "output_key": "Klucz wyniku",
        "output_qty": "Ilość wyniku", "service_cost_gold": "Opłata (gp)",
        "is_hidden": "Ukryty", "is_active": "Aktywny",
    }

    fields = []
    for field_key in schema["required"] + schema.get("optional", []):
        field_def = schema["fields"].get(field_key, {})
        f: dict[str, Any] = {
            "key": field_key,
            "label": FIELD_LABELS.get(field_key, field_key.replace("_", " ").title()),
            "type": field_def.get("type", "text"),
            "required": field_key in schema["required"],
        }
        if field_def.get("options"):
            f["options"] = field_def["options"]
        if "min" in field_def:
            f["min"] = field_def["min"]
        if "max" in field_def:
            f["max"] = field_def["max"]
        if field_def.get("question"):
            f["placeholder"] = field_def["question"]
        fields.append(f)

    return {"table": table, "fields": fields}


@router.get("/list")
def smart_entry_list(table: str, _: None = Depends(_require_admin)):
    """Return list of existing records for the dropdown."""
    if table not in WRITABLE_TABLES:
        raise HTTPException(status_code=400, detail=f"Unknown table '{table}'")
    conn = _get_db()
    try:
        rows = conn.execute(f"SELECT key, label FROM {table} ORDER BY label LIMIT 300").fetchall()
        return {"items": [{"key": r["key"], "label": r["label"]} for r in rows]}
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/record")
def smart_entry_record(table: str, key: str, _: None = Depends(_require_admin)):
    """Return a single record by key for editing."""
    _assert_writable(table)
    record = _db_get(table, key)
    if not record:
        raise HTTPException(status_code=404, detail=f"Record '{key}' not found in {table}")
    return record


@router.post("/message")
def smart_entry_message(
    req: SmartEntryMessageReq,
    _: None = Depends(_require_admin),
):
    session = _get_or_create_session(req.session_id)

    # Sync table
    if req.table:
        _assert_writable(req.table)
        session["table"] = req.table
    if req.target_key is not None:
        session["target_key"] = req.target_key or None

    # Merge frontend draft into session draft
    if req.current_draft:
        session["draft"].update({k: v for k, v in req.current_draft.items() if v not in (None, "")})

    table = session.get("table")

    # Build system prompt with schema constraints
    schema_text = _build_schema_constraint_text(table) if table else "Tabela nieznana — zapytaj o typ rekordu."

    # Build user message context
    context_parts = []
    if table:
        context_parts.append(schema_text)
    if session["draft"]:
        context_parts.append(f"Bieżący draft: {json.dumps(session['draft'], ensure_ascii=False)}")
    if session.get("target_key"):
        context_parts.append(f"TRYB EDYCJI rekordu: {session['target_key']}")

    user_content = req.message
    if context_parts:
        user_content = "\n".join(context_parts) + f"\n\nAdmin: {req.message}"

    session["history"].append({"role": "user", "content": user_content})
    messages = [{"role": "system", "content": SMART_ENTRY_SYSTEM_PROMPT_V2}] + session["history"][-10:]

    try:
        # #818 (H4): content generation runs on the offline/local profile (.170),
        # separate from the live-gameplay preset. Falls back to the global preset
        # when CONTENT_LLM_ENABLED=0.
        _content_cfg = resolve_content_llm_config() if content_llm_enabled() else None
        raw_reply = generate_chat(
            messages=messages, llm_config=_content_cfg, call_type="smart_entry"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": raw_reply})

    # Parse JSON response
    reply_text, new_draft = _parse_llm_draft_response(raw_reply)

    # Validate and merge new_draft into session draft
    if new_draft and table:
        schema = SCHEMA_DESCRIPTORS.get(table, {})
        valid_fields = set(schema.get("required", [])) | set(schema.get("optional", []))
        for k, v in new_draft.items():
            if k in valid_fields:
                session["draft"][k] = v

    return {
        "session_id": req.session_id,
        "reply": reply_text or "Wypełniłem co mogłem.",
        "draft": session["draft"],
    }


@router.post("/save")
def smart_entry_save(
    req: SmartEntrySaveReq,
    _: None = Depends(_require_admin),
):
    # Use request values, fall back to session
    session = _sessions.get(req.session_id, {})
    table = req.table or session.get("table")
    draft = req.draft or session.get("draft", {})
    target_key = req.target_key or session.get("target_key")

    if not table:
        raise HTTPException(status_code=400, detail="No table specified.")
    _assert_writable(table)
    if not draft:
        raise HTTPException(status_code=400, detail="No draft data to save.")

    schema = SCHEMA_DESCRIPTORS.get(table, {})
    required = schema.get("required", [])
    missing = [f for f in required if not draft.get(f)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {missing}")

    # Coerce types
    record = dict(draft)
    fields_def = schema.get("fields", {})
    for k, v in list(record.items()):
        field_type = fields_def.get(k, {}).get("type")
        if field_type == "boolean":
            record[k] = 1 if v else 0
        elif field_type == "number":
            try:
                record[k] = float(v) if "." in str(v) else int(v)
            except (ValueError, TypeError):
                pass
        elif field_type == "multi_choice":
            # Store as JSON array e.g. '["warrior","scholar"]'
            if isinstance(v, list):
                record[k] = json.dumps(v, ensure_ascii=False)
            elif isinstance(v, str) and v and not v.startswith("["):
                vals = [s.strip() for s in v.split(",") if s.strip()]
                record[k] = json.dumps(vals, ensure_ascii=False)
        elif isinstance(v, (dict, list)):
            # Fallback: serialize any other nested object to JSON string
            record[k] = json.dumps(v, ensure_ascii=False)

    # game_locations: inject provenance + resolve parent_key → parent_id
    if table == "game_locations":
        if not target_key:
            record.setdefault("created_by", "admin_kreator")
            record.setdefault("canonical", 1)
        # Resolve parent_key → parent_id (FK still required by app)
        pk = record.get("parent_key")
        if pk:
            conn = _get_db()
            try:
                row = conn.execute(
                    "SELECT id FROM game_locations WHERE key = ?", (pk,)
                ).fetchone()
                if row:
                    record["parent_id"] = row["id"]
                else:
                    raise HTTPException(
                        status_code=422,
                        detail=f"parent_key '{pk}' nie istnieje w bazie.",
                    )
            finally:
                conn.close()
        elif record.get("location_type") == "sub":
            raise HTTPException(
                status_code=422,
                detail="Pod-lokacja wymaga parent_key (klucza lokacji nadrzędnej).",
            )

    # S2 (#582): new enemy via Kreator AI gets archetype-derived 7 stats when the
    # admin didn't supply stats_json — mirrors admin_config.create_enemy. NULL would
    # otherwise default to 10; this gives the enemy a meaningful stat profile up front.
    if table == "game_config_enemies" and not target_key:
        if not record.get("stats_json"):
            from app.services.actor_stats import stats_for_actor

            record["stats_json"] = json.dumps(
                stats_for_actor(record.get("key", ""), record.get("label")),
                ensure_ascii=False,
            )

    if target_key:
        # UPDATE existing record (skip immutable provenance fields)
        immutable = {"created_by"} if table == "game_locations" else set()
        for field, value in record.items():
            if field == "key" or field in immutable:
                continue
            _db_update_field(table, target_key, field, value)
        return {"ok": True, "key": target_key, "table": table, "mode": "update"}
    else:
        # INSERT new record
        try:
            key = _db_insert(table, record)
            return {"ok": True, "key": key, "table": table, "mode": "create"}
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409, detail=f"Record already exists: {e}")
