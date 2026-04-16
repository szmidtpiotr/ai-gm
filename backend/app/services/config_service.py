import json
import os
import sqlite3
import time
from typing import Any

DB_PATH = "/data/ai_gm.db"
_CACHE_TTL_SECONDS = 60
_CACHE: dict[str, Any] = {"expires_at": 0.0, "value": None}


def _use_db_config() -> bool:
    raw = (os.getenv("USE_DB_CONFIG", "false") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _default_config() -> dict[str, Any]:
    return {
        "stats": [
            {"key": "STR", "label": "Strength", "description": "Physical power and melee force"},
            {"key": "DEX", "label": "Dexterity", "description": "Agility, stealth, initiative"},
            {"key": "CON", "label": "Constitution", "description": "Endurance and physical resilience"},
            {"key": "INT", "label": "Intelligence", "description": "Arcane aptitude and knowledge"},
            {"key": "WIS", "label": "Wisdom", "description": "Awareness, survival, intuition"},
            {"key": "CHA", "label": "Charisma", "description": "Persuasion and intimidation presence"},
            {"key": "LCK", "label": "Luck", "description": "Fortune and chance"},
        ],
        "skills": [
            {
                "key": "athletics",
                "label": "Athletics",
                "linked_stat": "STR",
                "rank_ceiling": 5,
                "description": "Wysiłek fizyczny: bieganie, skoki, wspinaczka i dźwiganie.",
            },
            {
                "key": "stealth",
                "label": "Stealth",
                "linked_stat": "DEX",
                "rank_ceiling": 5,
                "description": "Ciche poruszanie się i unikanie wykrycia. Odpowiada za wymykanie się, skradanie i działanie w cieniu.",
            },
            {
                "key": "initiative",
                "label": "Initiative",
                "linked_stat": "DEX",
                "rank_ceiling": 5,
                "description": "Szybka reakcja i gotowość do działania. Odpowiada za tempo i pierwszeństwo w niebezpiecznych chwilach.",
            },
            {
                "key": "attack",
                "label": "Attack",
                "linked_stat": "STR",
                "rank_ceiling": 5,
                "description": "Zdolność do skutecznego uderzenia: celowanie, siła i timing ataku.",
            },
            {
                "key": "awareness",
                "label": "Awareness",
                "linked_stat": "WIS",
                "rank_ceiling": 5,
                "description": "Wnikliwa obserwacja i czujność. Pomaga dostrzec zagrożenia, śledzić tropy i wyłapywać drobne sygnały.",
            },
            {
                "key": "persuasion",
                "label": "Persuasion",
                "linked_stat": "CHA",
                "rank_ceiling": 5,
                "description": "Urok, argumenty i przekonywanie innych. Odpowiada za perswazję i rozmowę prowadzącą do zgody.",
            },
            {
                "key": "intimidation",
                "label": "Intimidation",
                "linked_stat": "CHA",
                "rank_ceiling": 5,
                "description": "Straszenie, stanowczość i presja psychiczna. Odpowiada za zastraszanie i wymuszanie reakcji.",
            },
            {
                "key": "survival",
                "label": "Survival",
                "linked_stat": "WIS",
                "rank_ceiling": 5,
                "description": "Przetrwanie w trudnych warunkach. Odpowiada za orientację, instynkt i decyzje w terenie.",
            },
            {
                "key": "lore",
                "label": "Lore",
                "linked_stat": "INT",
                "rank_ceiling": 5,
                "description": "Wiedza z opowieści i dawnych ksiąg. Odpowiada za rozpoznanie kultury, historii, symboli i opowieści świata.",
            },
            {
                "key": "arcana",
                "label": "Arcana",
                "linked_stat": "INT",
                "rank_ceiling": 5,
                "description": "Rozumienie magii i zjawisk magicznych. Odpowiada za rozpoznawanie zaklęć, rytuałów i sekretów arkanów.",
            },
            {
                "key": "medicine",
                "label": "Medicine",
                "linked_stat": "WIS",
                "rank_ceiling": 5,
                "description": "Udzielanie pomocy i leczenie. Odpowiada za ocenę ran, dobór środków i stabilizację w walce.",
            },
            {
                "key": "investigation",
                "label": "Investigation",
                "linked_stat": "INT",
                "rank_ceiling": 5,
                "description": "Dociekliwość i analizowanie szczegółów. Odpowiada za szukanie tropów, wyciąganie wniosków i składanie faktów.",
            },
        ],
        "dc_tiers": [
            {"key": "easy", "label": "Łatwe", "value": 8, "description": "Proste, oczywiste działania."},
            {"key": "medium", "label": "Średnie", "value": 12, "description": "Wymaga skupienia i biegłości."},
            {"key": "hard", "label": "Trudne", "value": 16, "description": "Niepewne i wymagające."},
            {"key": "extreme", "label": "Ekstremalne", "value": 20, "description": "Granica możliwości."},
            {"key": "legendary", "label": "Legendarne", "value": 24, "description": "Działanie na poziomie legend."},
        ],
        "source": "constants",
    }


def _load_from_db() -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        stats = conn.execute(
            "SELECT key, label, description FROM game_config_stats ORDER BY sort_order ASC, key ASC"
        ).fetchall()
        skills = conn.execute(
            """
            SELECT key, label, linked_stat, rank_ceiling, description
            FROM game_config_skills
            ORDER BY sort_order ASC, key ASC
            """
        ).fetchall()
        dc_rows = conn.execute(
            "SELECT key, label, value, description FROM game_config_dc ORDER BY sort_order ASC, key ASC"
        ).fetchall()
        return {
            "stats": [
                {
                    "key": r["key"],
                    "label": r["label"] if "label" in r.keys() else None,
                    "description": (r["description"] if "description" in r.keys() and r["description"] else None)
                    or (r["label"] if "label" in r.keys() and r["label"] else None),
                }
                for r in stats
            ],
            "skills": [
                {
                    "key": r["key"],
                    "label": r["label"] if "label" in r.keys() else None,
                    "linked_stat": r["linked_stat"] if "linked_stat" in r.keys() else None,
                    "rank_ceiling": int(r["rank_ceiling"] or 5) if "rank_ceiling" in r.keys() else 5,
                    "description": (r["description"] if "description" in r.keys() and r["description"] else None)
                    or (r["label"] if "label" in r.keys() and r["label"] else None),
                }
                for r in skills
            ],
            "dc_tiers": [
                {
                    "key": r["key"],
                    "label": r["label"] if "label" in r.keys() else None,
                    "value": int(r["value"]),
                    "description": (r["description"] if "description" in r.keys() and r["description"] else None)
                    or (r["label"] if "label" in r.keys() and r["label"] else None),
                }
                for r in dc_rows
            ],
            "source": "db",
        }
    finally:
        conn.close()


def get_runtime_config() -> dict[str, Any]:
    if not _use_db_config():
        return _default_config()

    now = time.time()
    cached_value = _CACHE.get("value")
    if cached_value is not None and now < float(_CACHE.get("expires_at") or 0.0):
        return cached_value

    try:
        value = _load_from_db()
    except Exception:
        value = _default_config()
    _CACHE["value"] = value
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return value


def build_runtime_config_block() -> str:
    cfg = get_runtime_config()
    return (
        "Konfiguracja mechanik (runtime):\n"
        f"{json.dumps(cfg, ensure_ascii=False)}\n"
        "Używaj opisów z tej konfiguracji do mapowania niejednoznacznych akcji gracza na odpowiedni test/umiejętność.\n"
        "Jeśli nazwa testu nie pasuje 1:1, dopasuj na podstawie 'description' (szczególnie dla słów kluczowych i celu działania)."
    )
