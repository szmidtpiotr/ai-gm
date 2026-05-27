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
from app.services.llm_service import generate_chat

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
    "npcs",
    "game_config_armor",       # virtual → saves to game_config_items with item_type='armor'
    "game_config_loot_tables",
    "game_config_riddles",
    "game_dungeons",
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
        "optional": ["ac_bonus", "armor_coverage", "effect_json"],
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
                    {"label": "armor", "description": "Zbroja / ochrona"},
                    {"label": "accessory", "description": "Akcesoria (pierścień, amulet)"},
                    {"label": "misc", "description": "Różne przedmioty"},
                    {"label": "key_item", "description": "Przedmiot fabularny / klucz"},
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
                    {"label": "limb_leg", "description": "Noga (nagolennik, but) — gracz wybiera lewą lub prawą"},
                    {"label": "full", "description": "Pełne pokrycie (zbroja płytowa) — zajmuje tors + 4 kończyny jednocześnie"},
                ],
            },
            "effect_json": {
                "type": "text",
                "question": "Opisz efekt przedmiotu w formacie JSON (opcjonalnie), np. {\"type\": \"heal\", \"amount\": 5}.",
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
    "npcs": {
        "required": ["key", "label"],
        "optional": ["npc_type", "description", "personality_prompt", "is_ally", "is_shop", "is_quest_giver"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla NPC, np. 'stary_bartek' lub 'wiedźma_z_bagna'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ta postać NPC (imię lub tytuł)?",
            },
            "npc_type": {
                "type": "single_choice",
                "question": "Jaki to typ NPC?",
                "options": [
                    {"label": "neutral",     "description": "Neutralna postać tła (wieśniak, strażnik, mnich)"},
                    {"label": "merchant",    "description": "Kupiec — handluje z graczem"},
                    {"label": "quest_giver", "description": "Dawca zadań — daje misje"},
                    {"label": "ally",        "description": "Sojusznik — pomaga graczowi w walce lub fabule"},
                    {"label": "hostile",     "description": "Wrogi — zagrożenie lub antagonista"},
                ],
            },
            "description": {
                "type": "textarea",
                "question": "Opis wyglądu i historii NPC dla GM (2-3 zdania, klimatyczny — wygląd, zachowanie, tło fabularne).",
            },
            "personality_prompt": {
                "type": "textarea",
                "question": "Osobowość i styl mowy NPC (dla GM/AI — np. 'Mówi ostrożnie, ważąc każde słowo. Zna mroczny sekret i podpowiada go pośrednio. Nie ufa obcym.').",
            },
            "is_ally": {
                "type": "boolean",
                "question": "Czy NPC jest sojusznikiem gracza?",
            },
            "is_shop": {
                "type": "boolean",
                "question": "Czy NPC prowadzi sklep i handluje z graczem?",
            },
            "is_quest_giver": {
                "type": "boolean",
                "question": "Czy NPC daje zadania (questy) graczowi?",
            },
        },
    },
    "game_config_armor": {
        "required": ["key", "label", "ac_bonus", "armor_coverage", "value_gp"],
        "optional": ["description", "note", "allowed_classes", "weight_kg"],
        "fields": {
            "key": {"type": "text", "question": "Podaj unikalny klucz (slug) dla zbroi, np. 'zelazna_kolczuga'."},
            "label": {"type": "text", "question": "Jak ma się nazywać ta zbroja (wyświetlana nazwa)?"},
            "ac_bonus": {
                "type": "number", "question": "O ile punktów zwiększa Klasę Pancerza (AC)? Lekka=1-2, Średnia=3-4, Ciężka=5-7.",
                "min": 1, "max": 8,
            },
            "armor_coverage": {
                "type": "single_choice", "question": "Który obszar ciała chroni ta zbroja?",
                "options": [
                    {"label": "torso",    "description": "Tors (kirys, kolczuga, kaftan) — najpopularniejsza"},
                    {"label": "head",     "description": "Głowa (hełm, kaptur, czepiec)"},
                    {"label": "limb_arm", "description": "Ramię (rękawica, naramiennik)"},
                    {"label": "limb_leg", "description": "Noga (nagolennik, but)"},
                    {"label": "full",     "description": "Pełne pokrycie (zbroja płytowa) — zajmuje tors + kończyny"},
                ],
            },
            "value_gp": {"type": "number", "question": "Ile kosztuje ta zbroja (w złotych monetach)?", "min": 0},
            "description": {"type": "textarea", "question": "Opis zbroi dla GM (wygląd, materiał, historia, 2-3 zdania)."},
            "note": {"type": "textarea", "question": "Zdolności specjalne (np. 'Odporna na ogień', 'Spowalnia o 1m')."},
            "allowed_classes": {
                "type": "multi_choice", "question": "Które klasy mogą nosić tę zbroję?",
                "options": [
                    {"label": "warrior", "description": "Wojownik"},
                    {"label": "scholar", "description": "Uczony"},
                    {"label": "ranger",  "description": "Łucznik/Strzelec"},
                ],
            },
            "weight_kg": {"type": "number", "question": "Waga w kilogramach (np. 2.5, 8.0)?", "min": 0},
        },
    },
    "game_config_loot_tables": {
        "required": ["key", "label"],
        "optional": ["description", "gold_min", "gold_max"],
        "fields": {
            "key": {"type": "text", "question": "Podaj unikalny klucz tabeli łupów, np. 'loot_bandits' lub 'loot_dungeon_chest'."},
            "label": {"type": "text", "question": "Nazwa wyświetlana tabeli łupów (np. 'Łupy Bandytów', 'Skrzynka Lochowa')."},
            "description": {"type": "textarea", "question": "Krótki opis skąd pochodzi ta tabela łupów (opcjonalnie)."},
            "gold_min": {"type": "number", "question": "Minimalna ilość złota w łupach (0 = brak złota).", "min": 0},
            "gold_max": {"type": "number", "question": "Maksymalna ilość złota w łupach.", "min": 0},
        },
    },
    "game_config_riddles": {
        "required": ["key", "text", "answer"],
        "optional": ["answer_alts", "hints", "difficulty", "theme"],
        "fields": {
            "key": {"type": "text", "question": "Podaj unikalny klucz zagadki, np. 'riddle_smok_001'."},
            "text": {"type": "textarea", "question": "Treść zagadki (pytanie, które usłyszy gracz). Napisz klimatycznie, w duchu mrocznej fantasy."},
            "answer": {"type": "text", "question": "Główna poprawna odpowiedź (jedno słowo lub krótka fraza)."},
            "answer_alts": {
                "type": "textarea",
                "question": "Alternatywne poprawne odpowiedzi w formacie JSON, np. [\"ogień\",\"płomień\"]. Zostaw puste jeśli jedna odpowiedź.",
            },
            "hints": {
                "type": "textarea",
                "question": "Podpowiedzi w formacie JSON, np. [\"Szuka tlenu\",\"Niszczy drewno\"]. Napisz 2-3 klimatyczne wskazówki.",
            },
            "difficulty": {
                "type": "single_choice", "question": "Poziom trudności zagadki?",
                "options": [
                    {"label": "1", "description": "Łatwa — dla początkujących"},
                    {"label": "2", "description": "Średnia — wymaga zastanowienia"},
                    {"label": "3", "description": "Trudna — tylko dla mistrzów"},
                ],
            },
            "theme": {
                "type": "single_choice", "question": "Motyw tematyczny zagadki?",
                "options": [
                    {"label": "general",  "description": "Ogólna — pasuje wszędzie"},
                    {"label": "dungeon",  "description": "Lochowa — zamki, podziemia, pułapki"},
                    {"label": "magic",    "description": "Magiczna — zaklęcia, artefakty, runy"},
                    {"label": "death",    "description": "Śmierć — kości, cienie, zaświaty"},
                    {"label": "nature",   "description": "Przyroda — zwierzęta, las, żywioły"},
                ],
            },
        },
    },
    "game_dungeons": {
        "required": ["key", "label", "location_key", "rooms"],
        "optional": ["atmosphere", "loot_tier", "min_level", "cooldown_hours", "boss_enemy"],
        "fields": {
            "key": {"type": "text", "question": "Podaj unikalny klucz lochu, np. 'dungeon_krypty_przeklety'."},
            "label": {"type": "text", "question": "Nazwa lochu (wyświetlana dla gracza), np. 'Przeklęte Krypty'."},
            "location_key": {"type": "text", "question": "Klucz lokacji, w której leży loch (musi istnieć w game_locations), np. 'ruiny_zapomniane'."},
            "rooms": {"type": "number", "question": "Ile pokoi ma loch? (3-10, rekomendowane 5)", "min": 2, "max": 15},
            "atmosphere": {"type": "textarea", "question": "Klimatyczny opis atmosfery lochu dla GM (mroczna proza, 2-3 zdania: wygląd, zapachy, dźwięki)."},
            "loot_tier": {
                "type": "single_choice", "question": "Poziom łupów w tym lochu?",
                "options": [
                    {"label": "poor",     "description": "Skromne — słabe łupy, graty"},
                    {"label": "standard", "description": "Standardowe — przeciętne łupy"},
                    {"label": "rich",     "description": "Bogate — wartościowe łupy"},
                    {"label": "epic",     "description": "Epickie — rzadkie artefakty"},
                ],
            },
            "min_level": {"type": "number", "question": "Minimalny poziom bohatera (1-10)?", "min": 1, "max": 10},
            "cooldown_hours": {"type": "number", "question": "Czas odnowienia lochu w godzinach (np. 72 = 3 doby)?", "min": 1},
            "boss_enemy": {"type": "text", "question": "Klucz przeciwnika-bossa (z game_config_enemies), np. 'lich_lord'. Zostaw puste jeśli brak bossa."},
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
        conn.commit()
    finally:
        conn.close()


# ── LLM prompt (v2 — JSON output) ─────────────────────────────────────────────

SMART_ENTRY_SYSTEM_PROMPT_V2 = """Jesteś asystentem WYPEŁNIANIA FORMULARZA rekordów gry RPG (mroczna fantasy, WFRP-inspired).
Admin opisuje rekord. Ty WYPEŁNIASZ POLA — nie zapisujesz, nie tworzysz rekordu (to robi admin przyciskiem).

ZAWSZE odpowiadaj WYŁĄCZNIE prawidłowym JSON-em w formacie:
{"reply": "krótki komentarz co wypełniłem (po polsku, max 2 zdania)", "draft": {"pole": wartość, ...}}

TRYBY PRACY:
- TRYB TWORZENIA (brak current_draft lub pusty): Wypełnij WSZYSTKIE pola od zera na podstawie opisu admina. Generuj key, label, description, note i wszystkie wymagane pola.
- TRYB UZUPEŁNIANIA (current_draft niepusty): Admin edytuje istniejący szkic. Zwróć w "draft" WYŁĄCZNIE pola które admin wprost prosi zmienić. NIE powtarzaj pól których admin nie wymienił — backend zachowa istniejące wartości. Wyjątek: jeśli zmiana jednego pola logicznie wymaga aktualizacji innego (np. zmiana label → nowy key), uwzględnij oba.

ZASADY:
- Pola i dozwolone wartości są podane w kontekście (SCHEMAT). NIE wymyślaj innych nazw pól.
- single_choice: użyj DOKŁADNIE jednej z podanych wartości (np. "d6", "melee", "STR")
- multi_choice: lista wartości oddzielona przecinkami, np. "warrior,scholar,ranger"
- boolean: 1 lub 0
- number: liczba (nie string)
- 'key' (slug): generuj z 'label': małe litery, polskie znaki → ascii, spacje → _, bez specjalnych
- 'description': W trybie tworzenia ZAWSZE generuj klimatyczny opis dla GM (wygląd, historia, atmosfera, 2-3 zdania)
- 'note': W trybie tworzenia ZAWSZE generuj krótki opis efektów dla GM
- Nie pisz "zapisałem" ani "utworzyłem rekord" — tylko wypełniasz formularz

POLE effect_json (MECHANIKA BOJOWA — tylko dla broni):
Generuj jako JSON string gdy broń ma specjalne efekty. Dozwolone typy:
  extra_damage: {"type":"extra_damage","dice":"1d6","damage_type":"fire|cold|poison|lightning|magic|physical"}
  on_hit_save:  {"type":"on_hit_save","stat":"CON|STR|DEX|INT|WIS|CHA","dc":12,
                  "on_fail":{"type":"extra_damage","dice":"1d4","damage_type":"poison"}
                             lub {"type":"apply_condition","condition_key":"poisoned|burning|bleeding|stunned|blinded|frightened|cursed","duration_rounds":2}}
Przykład ognistego miecza: {"effects":[{"type":"extra_damage","dice":"1d6","damage_type":"fire"}]}
Przykład zatrutego sztyletu: {"effects":[{"type":"on_hit_save","stat":"CON","dc":12,"on_fail":{"type":"apply_condition","condition_key":"poisoned","duration_rounds":3}}]}
Zostaw null jeśli broń nie ma efektów specjalnych.

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

TABELA game_config_armor — zbroje i elementy ochronne (mroczna fantasy, klimatyczne nazwy):
- 'key': slug z label (polskie znaki→ascii, spacje→_)
- 'label': polska nazwa zbroi ("Żelazna Kolczuga", "Skórzana Napiersnica", "Hełm Kościany")
- 'ac_bonus': 1-2=lekka, 3-4=średnia, 5-6=ciężka, 7-8=pełna płyta
- 'armor_coverage': torso (najczęstsza), head, limb_arm, limb_leg, full (płytowa — daje bonus do torso+kończyn)
- 'value_gp': wycena realistyczna: kolczuga=50-120gp, płyta=300-800gp, skóra=15-40gp
- 'description': 2-3 zdania, mroczny klimat — wygląd, materiał, znaki użycia
- 'note': specjalne właściwości (ognioodporność, błogosławieństwo/klątwa, waga) — krótko
- 'allowed_classes': warrior może wszystko; scholar=lekkie (skóra, ac_bonus≤2); ranger=lekkie/średnie (ac_bonus≤4)
- Nowa zbroja dostaje item_type='armor' automatycznie — NIE podawaj tego pola.

TABELA game_config_loot_tables — tabele łupów (definiują co wpada z wrogów i skrzynek):
- 'key': slug, np. 'loot_goblin_camp', 'loot_dungeon_chest_rare'. Zacznij od 'loot_'.
- 'label': czytelna nazwa ("Łupy z Obozu Goblinów", "Skrzynka Rzadka")
- 'description': jedno zdanie — skąd pochodzi ta tabela
- 'gold_min'/'gold_max': zakres złota. 0/0 = bez złota. Realistyczne: weak=0-5, standard=5-25, elite=10-50, boss=20-100.
- Wpisy (items/weapons/consumables) są dodawane ręcznie po stworzeniu tabeli — nie podawaj ich.

TABELA game_config_riddles — zagadki do lochów (mroczne, klimatyczne, po polsku):
- 'key': slug, np. 'riddle_ogien_001'. Dodaj numer jeśli podobne zagadki istnieją.
- 'text': treść zagadki, którą słyszy gracz. Nie pytanie wprost — klimatyczna zagadka (np. "Jestem zimny jak śmierć, lecz parzę jak ogień...")
- 'answer': główna odpowiedź — jedno słowo (np. "lód", "ogień", "czas")
- 'answer_alts': JSON array synonimów (np. ["lód","mróz","lodowiec"]) — zawsze generuj 2-4 alternatyw
- 'hints': JSON array 2-3 klimatycznych podpowiedzi (od ogólnej do konkretnej)
- 'difficulty': 1=prosta, 2=średnia, 3=trudna
- 'theme': general/dungeon/magic/death/nature — dobierz do klimatu zagadki

TABELA game_dungeons — lochy do eksploracji:
- 'key': slug z label (np. "Przeklęte Krypty" → "przekleta_krypta")
- 'label': polska pełna nazwa ("Przeklęte Krypty Varathnula", "Kopalnia Zgniłej Miedzi")
- 'location_key': musi być istniejącym kluczem z game_locations — zapytaj admina jeśli nie podał
- 'rooms': 3-5 dla krótkich lochów, 6-10 dla standardowych. Domyślnie 5.
- 'atmosphere': 2-4 zdania mrocznej prozy: wilgoć, zapachy, dźwięki, klimat fabularny
- 'loot_tier': poor/standard/rich/epic — zależnie od min_level (1-3=standard, 4-6=rich, 7+=epic)
- 'min_level': 1-3=łatwy, 4-6=średni, 7-9=trudny, 10=heroiczny
- 'cooldown_hours': 24=szybko, 72=normalne, 168=tygodniowe
- 'boss_enemy': klucz z game_config_enemies — pomiń jeśli admin nie podał

TABELA npcs — postacie niezależne (NPCe) w świecie gry (mroczna fantasy, klimatyczne, polskie imiona):
- 'key': slug z label (polskie znaki→ascii, spacje→_, np. "Stary Bartek" → "stary_bartek")
- 'label': polska nazwa/imię NPC (może być z tytułem: "Wiedźma z Bagna", "Kapitan Straży", "Stary Bartek")
- 'npc_type': DOKŁADNIE jedna wartość: neutral | merchant | quest_giver | ally | hostile
  - karczmarze, strażnicy, wieśniacy, mnisi → "neutral"
  - kupcy, handlarze, alchemicy ze sklepem → "merchant"
  - starcy z misją, rycerze zakonni, tajemnicze postacie → "quest_giver"
  - towarzysze, magowie-pomocnicy, wierny giermek → "ally"
  - bandyci, rycerze wroga, antagoniści → "hostile"
- 'description': 2-3 zdania, mroczna klimatyczna proza — wygląd fizyczny, charakterystyczny szczegół, atmosfera
- 'personality_prompt': styl mowy i osobowość dla AI GM (1-3 zdania technicznego opisu: "Mówi ostrożnie...", "Używa archaicznego języka...", "Zawsze kłamie w trzech słowach...")
- 'is_ally': 1 dla sojuszników, towarzyszy, opiekunów; 0 dla reszty
- 'is_shop': 1 dla kupców, karczmarzy sprzedających zasoby; 0 dla reszty
- 'is_quest_giver': 1 gdy NPC może dawać zadania; 0 dla reszty
- Nowe NPCe trafiają do "Oczekujących" w Bestiariuszu — admin może je zatwierdzić lub odrzucić.

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
        # NPCs
        "npc_type": "Typ NPC", "personality_prompt": "Osobowość (prompt GM)",
        "is_ally": "Sojusznik", "is_shop": "Kupiec", "is_quest_giver": "Dawca zadań",
        # Armor
        "ac_bonus": "Bonus AC", "armor_coverage": "Obszar ochrony",
        # Loot tables
        "gold_min": "Złoto min", "gold_max": "Złoto max",
        # Riddles
        "text": "Treść zagadki", "answer": "Odpowiedź", "answer_alts": "Alternatywne odpowiedzi (JSON)", "hints": "Podpowiedzi (JSON)",
        "difficulty": "Trudność", "theme": "Motyw",
        # Dungeons
        "location_key": "Klucz lokacji", "rooms": "Liczba pokoi", "atmosphere": "Atmosfera",
        "loot_tier": "Poziom łupów", "min_level": "Min. poziom", "cooldown_hours": "Odnowienie (h)",
        "boss_enemy": "Boss (klucz wroga)",
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
        if table == "game_config_armor":
            rows = conn.execute(
                "SELECT key, label FROM game_config_items WHERE item_type='armor' ORDER BY label LIMIT 300"
            ).fetchall()
        elif table == "game_config_riddles":
            rows = conn.execute(
                "SELECT key, SUBSTR(text,1,60) as label FROM game_config_riddles ORDER BY key LIMIT 300"
            ).fetchall()
        else:
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
    real_table = "game_config_items" if table == "game_config_armor" else table
    record = _db_get(real_table, key)
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

    # Build user message context — explicit mode distinction
    context_parts = []
    if table:
        context_parts.append(schema_text)

    is_refinement = bool(session["draft"])
    if is_refinement:
        draft_str = json.dumps(session["draft"], ensure_ascii=False)
        context_parts.append(
            f"TRYB UZUPEŁNIANIA — bieżący stan formularza (zachowaj wszystko czego admin nie zmienia):\n{draft_str}\n"
            f"Zwróć w 'draft' TYLKO pola które admin teraz zmienia."
        )
        if session.get("target_key"):
            context_parts.append(f"Edytowany rekord: {session['target_key']}")
    else:
        context_parts.append("TRYB TWORZENIA: Wypełnij wszystkie pola od zera.")
        if session.get("target_key"):
            context_parts.append(f"EDYCJA ISTNIEJĄCEGO REKORDU: {session['target_key']}")

    user_content = "\n\n".join(context_parts) + f"\n\nAdmin: {req.message}"

    session["history"].append({"role": "user", "content": user_content})
    messages = [{"role": "system", "content": SMART_ENTRY_SYSTEM_PROMPT_V2}] + session["history"][-10:]

    try:
        raw_reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": raw_reply})

    # Parse JSON response
    reply_text, new_draft = _parse_llm_draft_response(raw_reply)

    # Validate and merge new_draft into session draft; track what changed + build delta
    changed_fields: list[str] = []
    delta_parts: list[str] = []
    if new_draft and table:
        schema = SCHEMA_DESCRIPTORS.get(table, {})
        valid_fields = set(schema.get("required", [])) | set(schema.get("optional", []))
        for k, v in new_draft.items():
            if k in valid_fields:
                old_v = session["draft"].get(k)
                if old_v != v:
                    changed_fields.append(k)
                    # Build delta string only when there was a prior value (refinement)
                    if old_v is not None and old_v != "" and old_v != {}:
                        old_str = str(old_v) if not isinstance(old_v, (dict, list)) else "…"
                        new_str = str(v) if not isinstance(v, (dict, list)) else "…"
                        if len(old_str) > 30:
                            old_str = old_str[:27] + "…"
                        if len(new_str) > 30:
                            new_str = new_str[:27] + "…"
                        delta_parts.append(f"{k}: {old_str} → {new_str}")
                session["draft"][k] = v

    delta = f"Zmieniłem: {', '.join(delta_parts)}" if delta_parts else None

    return {
        "session_id": req.session_id,
        "reply": reply_text or "Wypełniłem co mogłem.",
        "draft": session["draft"],
        "changed_fields": changed_fields,
        "delta": delta,
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

    # game_config_armor: virtual → redirect to game_config_items with item_type='armor'
    if table == "game_config_armor":
        record["item_type"] = "armor"
        table = "game_config_items"

    # npcs: inject defaults + mark as pending for review
    if table == "npcs":
        if not target_key:
            record.setdefault("review_status", "pending")
            record.setdefault("is_active", 1)
            record.setdefault("npc_type", "neutral")
            record.setdefault("is_ally", 0)
            record.setdefault("is_shop", 0)
            record.setdefault("is_quest_giver", 0)

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
