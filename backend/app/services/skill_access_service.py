"""#1522 — kto może mieć jaką umiejętność: bramka archetyp + rasa.

Problem: do tej pory pula umiejętności była JEDNA dla wszystkich. Rzut startowy
losował z 18 kluczy (archetyp wpływał tylko na wagę 3:1), a zamiana w kreatorze
dopuszczała **cały** katalog `game_config_skills` — więc Zwiadowca bez kropli many
mógł wziąć Tarczę Many, a Wojownik Arkanową Barierę.

Reguła (Księga Zasad, rozdz. Umiejętności):
  • trzy grupy zamknięte klasowo — magiczne (Uczony), ciężka walka (Wojownik),
    złodziejskie (Łotrzyk/Zwiadowca),
  • rasa potrafi otworzyć drzwi zamknięte klasą: elf czyta pęknięcia Rdzenia
    (Wyczucie Magii) niezależnie od archetypu, krasnolud wychowany przy tarczy
    i kowadle (Blok Tarczą, Broń dwuręczna) też,
  • wszystko poza tymi grupami (~33 klucze) jest wspólne — bramkujemy tożsamość,
    nie odbieramy graczowi wyborów.

To jedyne źródło prawdy: używa go rzut startowy, zamiana w kreatorze, awans za XP
i publiczny katalog. Lustro w kliencie: `frontend/front-v2/src/lib/creation.ts`.
Istniejące postacie NIE są ruszane — bramka działa na przyszłe nabycia (#1522).
"""

from __future__ import annotations

from typing import Final

#: Umiejętność → archetypy, które mogą ją mieć. Klucz spoza mapy = wspólny.
SKILL_ARCHETYPE_LOCK: Final[dict[str, frozenset[str]]] = {
    # ── Magiczne: wymagają many albo znajomości zaklęć ───────────────────────
    # #1475 — Wojownik-Mag (gish) też włada arkanami (krew oswojona z Rdzeniem).
    "arcana": frozenset({"scholar", "wojownik_mag"}),
    "arcane_ward": frozenset({"scholar", "wojownik_mag"}),
    "mana_shield": frozenset({"scholar", "wojownik_mag"}),
    "magic_sense": frozenset({"scholar", "wojownik_mag"}),
    # ── Ciężka walka: ściana tarcz i broń, której uczony nie udźwignie ───────
    # two_handed zostaje wojownikowi — gish włada tylko bronią jednoręczną.
    "shield_block": frozenset({"warrior"}),
    "two_handed": frozenset({"warrior"}),
    "wrestling": frozenset({"warrior", "wojownik_mag"}),
    # ── Złodziejskie: rzemiosło dzielnicy złodziei ──────────────────────────
    "lockpick": frozenset({"rogue"}),
    "pickpocket": frozenset({"rogue"}),
    "disguise": frozenset({"rogue"}),
}

#: Rasa → umiejętności odblokowane MIMO bramki klasowej.
#: Elf zna mapę pęknięć Rdzenia lepiej niż ktokolwiek (LORE_v1_KANON §Rdzeń),
#: krasnolud wyrasta przy tarczy i kowadle (Siwe Granie, rody kowali).
RACE_SKILL_UNLOCK: Final[dict[str, frozenset[str]]] = {
    "elf": frozenset({"magic_sense"}),
    "dwarf": frozenset({"shield_block", "two_handed"}),
    "human": frozenset(),
}

#: Bias rasowy w rzucie startowym — nie blokuje niczego, tylko podbija szansę.
#: Wagi mnożą się z biasem archetypu (`ARCHETYPE_SKILL_WEIGHTS`).
RACE_SKILL_WEIGHTS: Final[dict[str, tuple[str, ...]]] = {
    "elf": ("survival", "stealth", "awareness", "acrobatics"),
    "dwarf": ("endurance", "athletics", "intimidation", "alchemy"),
    # #1475 — Piętnowani: krew oswojona z Rdzeniem, uczą się od pokoleń.
    "pietnowani": ("arcana", "lore", "magic_sense", "survival"),
    "human": (),
}

_ARCHETYPES: Final = frozenset({"warrior", "scholar", "rogue", "wojownik_mag"})


def _norm_archetype(archetype: str | None) -> str:
    a = str(archetype or "warrior").strip().lower()
    return a if a in _ARCHETYPES else "warrior"


def _norm_race(race: str | None) -> str:
    return str(race or "human").strip().lower()


def skill_allowed(skill_key: str, archetype: str | None, race: str | None = "human") -> bool:
    """Czy postać o tym archetypie i rasie może mieć tę umiejętność."""
    key = str(skill_key or "").strip()
    lock = SKILL_ARCHETYPE_LOCK.get(key)
    if lock is None:
        return True  # klucz wspólny
    if _norm_archetype(archetype) in lock:
        return True
    return key in RACE_SKILL_UNLOCK.get(_norm_race(race), frozenset())


def filter_allowed_skills(keys, archetype: str | None, race: str | None = "human") -> list[str]:
    """Odsiej klucze niedostępne dla tej pary archetyp+rasa (kolejność zachowana)."""
    return [k for k in keys if skill_allowed(k, archetype, race)]


def blocked_skills_for(archetype: str | None, race: str | None = "human") -> frozenset[str]:
    """Zbiór kluczy zamkniętych dla tej pary — do UI i komunikatów błędów."""
    return frozenset(
        k for k in SKILL_ARCHETYPE_LOCK if not skill_allowed(k, archetype, race)
    )


def skill_block_reason(skill_key: str, archetype: str | None, race: str | None = "human") -> str | None:
    """Powód po polsku, gdy umiejętność jest zamknięta; None gdy wolno."""
    if skill_allowed(skill_key, archetype, race):
        return None
    lock = SKILL_ARCHETYPE_LOCK.get(str(skill_key or "").strip(), frozenset())
    pretty = {
        "warrior": "Wojownik", "scholar": "Uczony", "rogue": "Łotrzyk / Zwiadowca",
    }
    who = " lub ".join(pretty.get(a, a) for a in sorted(lock))
    return (
        f"Umiejętność '{skill_key}' jest zastrzeżona dla klas: {who}. "
        f"Twoja klasa ({_norm_archetype(archetype)}) jej nie używa."
    )
