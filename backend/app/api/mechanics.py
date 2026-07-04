import sqlite3
from fastapi import APIRouter

from app.services.admin_config import list_dc, list_skills, list_stats


router = APIRouter()
DB_PATH = "/data/ai_gm.db"


def _build_test_descriptions() -> dict[str, str]:
    stats = list_stats()
    skills = list_skills()
    dcs = list_dc()

    stats_by_key = {s.get("key"): (s.get("description") or s.get("label") or "") for s in stats}
    skills_by_key = {s.get("key"): (s.get("description") or s.get("label") or "") for s in skills}

    # Canonical save tests used in roll cues parsing.
    fortitude = stats_by_key.get("CON") or stats_by_key.get("STR") or ""
    reflex = stats_by_key.get("DEX") or ""
    willpower = stats_by_key.get("WIS") or stats_by_key.get("CHA") or ""
    arcane = stats_by_key.get("INT") or ""

    return {
        # Skill tests
        **skills_by_key,
        # Save tests (used by cues: Dex/Con/Wis/Int/Cha Save aliases)
        "fortitude_save": fortitude,
        "reflex_save": reflex,
        "willpower_save": willpower,
        "arcane_save": arcane,
    }


@router.get("/mechanics/metadata")
def get_mechanics_metadata():
    return {
        "test_descriptions": _build_test_descriptions(),
        "dc_tiers": {d.get("key"): (d.get("description") or d.get("label") or "") for d in list_dc()},
    }


# E2 (#417) — Creator help content: archetypes / stats / skills, each with a
# plain-language description AND a concrete mechanical example so the character
# creator tooltips can explain what the player is choosing.
_CREATOR_ARCHETYPES = [
    {
        "key": "warrior",
        "label": "Wojownik",
        "icon": "⚔️",
        "description": "Frontowy wojownik w ciężkiej zbroi. Wysoki HP, silne ciosy, mistrz broni wręcz.",
        "bonus": "+2 SIŁ · +1 KON · HP: 12",
        "example": "Atak mieczem: d20 + SIŁ + ranga Atak Wręcz ≥ DC. Najwięcej HP — wytrzyma najwięcej ciosów w zwarciu.",
    },
    {
        "key": "rogue",
        "label": "Łotrzyk",
        "icon": "🏹",
        "description": "Zwinny cień: snajper z ukrycia lub złodziej w ciemnościach. Skradanie, łuk, inteligentna walka.",
        "bonus": "+2 ZRĘ · +1 SZCZ · HP: 8",
        "example": "Skradanie: d20 + ZRĘ + ranga ≥ DC 12. Atak z ukrycia dodaje obrażenia; wysoki SZCZ poprawia łupy i ucieczki.",
    },
    {
        "key": "scholar",
        "label": "Uczony",
        "icon": "📜",
        "description": "Tkacz arkanów: kruchy, ale niszczycielski dzięki zaklęciom. Zarządza maną i ryzykiem Omylenia.",
        "bonus": "+2 INT · +1 MĄD · HP: 6 · Mana",
        "example": "Zaklęcie: d20 + INT ≥ DC, koszt many. Nat 1 = Omylenie (ogłuszenie/obrażenia własne). Najmniej HP — unikaj zwarcia.",
    },
]

# Canonical 7 stats (locked per game mechanics). Config may lack LCK, so we
# define key→(label, description, example) here and merge config descriptions on top.
_CREATOR_STATS = [
    ("STR", "Siła", "Obrażenia wręcz, atletyka, dźwiganie, forsowanie drzwi.",
     "Forsowanie drzwi: d20 + SIŁ ≥ DC 12. Modyfikuje obrażenia w walce wręcz."),
    ("DEX", "Zręczność", "Inicjatywa, skradanie, uniki, ataki finezyjne i dystansowe.",
     "Unik strzału: d20 + ZRĘ ≥ DC. Decyduje o inicjatywie i atakach dystansowych."),
    ("CON", "Kondycja", "Punkty życia, odporność na trucizny i ból, wytrzymałość.",
     "Odporność na truciznę: d20 + KON ≥ DC. Zwiększa HP o modyfikator na każdy poziom."),
    ("INT", "Inteligencja", "Magia arkanów, wiedza, badanie, alchemia.",
     "Identyfikacja artefaktu: d20 + INT ≥ DC 16. Zasila zaklęcia i pulę many."),
    ("WIS", "Mądrość", "Percepcja, przetrwanie, medycyna, odporność na strach.",
     "Zauważ pułapkę: d20 + MĄD ≥ DC 14. Percepcja, medycyna, odporność na strach."),
    ("CHA", "Charyzma", "Perswazja, zastraszanie, negocjacje, przywództwo.",
     "Przekonaj strażnika: d20 + CHA ≥ DC 12. Perswazja, zastraszanie, handel."),
    ("LCK", "Szczęście", "Rzuty losowe, jakość łupów, szanse ucieczki i zdarzenia losowe.",
     "Rzut losowy zdarzenia: wysoki SZCZ przechyla wynik na twoją korzyść (łupy, ucieczki)."),
]

_CREATOR_SKILL_EXAMPLES = {
    "athletics": "Wspinaczka po murze: d20 + SIŁ + ranga ≥ DC 12 (Średni).",
    "endurance": "Marsz w śnieżycy: d20 + KON + ranga ≥ DC 14.",
    "stealth": "Przemknij obok straży: d20 + ZRĘ + ranga ≥ DC 12.",
    "sleight_of_hand": "Kradzież sakiewki: d20 + ZRĘ + ranga ≥ DC 16 (Trudny).",
    "arcana": "Rozpoznaj zaklęcie: d20 + INT + ranga ≥ DC 16.",
    "investigation": "Znajdź ukryty przełącznik: d20 + INT + ranga ≥ DC 14.",
    "lore": "Przypomnij sobie legendę: d20 + INT + ranga ≥ DC 12.",
    "awareness": "Wykryj zasadzkę: d20 + MĄD + ranga ≥ DC 14.",
    "survival": "Wytrop zwierzynę: d20 + MĄD + ranga ≥ DC 12.",
    "medicine": "Zatamuj krwawienie: d20 + MĄD + ranga ≥ DC 12.",
    "persuasion": "Wynegocjuj cenę: d20 + CHA + ranga ≥ DC 12.",
    "intimidation": "Zmuś do ucieczki: d20 + CHA + ranga ≥ DC 14.",
    "melee_attack": "Cios mieczem: d20 + SIŁ + ranga ≥ obrona celu.",
    "ranged_attack": "Strzał z łuku: d20 + ZRĘ + ranga ≥ obrona celu.",
}


@router.get("/mechanics/creator-help")
def get_creator_help():
    """E2 (#417) — Tooltip content for the character creator.

    Returns archetypes, stats and skills, each with a description and a
    concrete mechanical example (roll formula / DC). Stat and skill labels
    come from admin config so they stay in sync; examples are curated here.
    """
    skills = list_skills()

    # Config descriptions keyed by stat — merged over the canonical defaults.
    cfg_stats = {s.get("key"): s for s in list_stats() if s.get("key")}
    stat_out = []
    for key, label, desc, example in _CREATOR_STATS:
        cfg = cfg_stats.get(key, {})
        stat_out.append({
            "key": key,
            "label": cfg.get("label") or label,
            "description": cfg.get("description") or desc,
            "example": example,
        })

    skill_out = []
    for s in skills:
        key = s.get("key")
        if not key:
            continue
        skill_out.append({
            "key": key,
            "label": s.get("label") or key,
            "stat": s.get("linked_stat") or "",
            "description": s.get("description") or s.get("label") or key,
            "example": _CREATOR_SKILL_EXAMPLES.get(key, f"Test: d20 + cecha + ranga ≥ DC."),
        })

    return {
        "archetypes": _CREATOR_ARCHETYPES,
        "stats": stat_out,
        "skills": skill_out,
    }


@router.get("/mechanics/skills")
def get_public_skills():
    """Skill catalog for autocomplete (key, label, linked_stat). No auth required."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT key, label, linked_stat FROM game_config_skills ORDER BY label"
        ).fetchall()
        return {"skills": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/mechanics/conditions")
def get_public_conditions():
    """Player-facing condition catalog: key/label/description only. Powers
    tooltip on condition chips in the character sheet (Stage 4 S5).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT key, label, description FROM game_config_conditions WHERE is_active = 1 ORDER BY key"
        ).fetchall()
        return {"conditions": [dict(r) for r in rows]}
    finally:
        conn.close()

