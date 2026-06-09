"""E24 — Onboarding card triggers.

check_onboarding_triggers(user_id, triggered_keys, conn) → list of card dicts
for mechanic keys NOT yet seen by this user.
Does NOT mark them as seen — frontend calls POST /api/users/{id}/seen-mechanics after showing.
"""
from __future__ import annotations
import sqlite3
from typing import List

MECHANIC_CARDS: dict[str, dict] = {
    "dice_roll": {
        "title": "Rzut kością",
        "content": (
            "Twoje akcje rozstrzygane są rzutem k20 + modyfikator statystyki + ranga umiejętności. "
            "Wynik porównywany jest z trudnością (DC): 8 łatwe, 12 średnie, 16 trudne, 20 ekstremalne. "
            "Naturalna 20 = automatyczny sukces z podwójnymi obrażeniami. Naturalna 1 = porażka z komplikacją."
        ),
    },
    "combat_start": {
        "title": "Walka",
        "content": (
            "Wchodzisz do walki turowej. Każda tura to jedna akcja: atak, czar, ucieczka lub inna. "
            "Twój bohater i wrogowie działają naprzemiennie według inicjatywy. "
            "Strefa walki (zwarcie/dystans) decyduje, które bronie możesz użyć."
        ),
    },
    "damage_taken": {
        "title": "Obrażenia i HP",
        "content": (
            "Twoje Punkty Życia (HP) to miara wytrzymałości. Gdy HP spadną do 0, bohater traci "
            "przytomność. Leczenie (mikstura, czar, odpoczynek) przywraca HP. "
            "Pancerz i CON zmniejszają przyjmowane obrażenia."
        ),
    },
    "xp_gained": {
        "title": "Doświadczenie (XP)",
        "content": (
            "Za pokonanych wrogów i ukończone zadania zdobywasz punkty doświadczenia (XP). "
            "Zebranie odpowiedniej liczby XP awansuje bohatera na wyższy poziom. "
            "Awans zwiększa HP, modyfikatory statystyk i odblokowuje nowe zdolności."
        ),
    },
    "gold_gained": {
        "title": "Złoto i ekwipunek",
        "content": (
            "Złoto (GP) to waluta świata. Kupujesz za nie bronie, pancerze i mikstury u kupca. "
            "Łupy ze skrzynek i pokonanych wrogów trafiają prosto do ekwipunku. "
            "Sprawdzaj ekwipunek — dobra broń zmienia wynik walki."
        ),
    },
    "death_save": {
        "title": "Test śmierci",
        "content": (
            "Gdy HP spadną do 0, rzucasz test śmierci (CON DC 10). Sukces — przeżywasz z 1 HP. "
            "Porażka — bohater umiera. Niektóre zdolności i mikstury ratują przed śmiercią. "
            "Uważaj: w lochach śmierć jest permanentna."
        ),
    },
}


def check_onboarding_triggers(
    user_id: int,
    triggered_keys: List[str],
    conn: sqlite3.Connection,
) -> List[dict]:
    """Return onboarding card dicts for mechanic_keys triggered but not yet seen by user.

    Does not modify DB — caller handles mark-seen.
    """
    if not triggered_keys:
        return []

    rows = conn.execute(
        "SELECT mechanic_key FROM seen_mechanics WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    already_seen = {r["mechanic_key"] for r in rows}

    cards = []
    for key in triggered_keys:
        if key not in already_seen and key in MECHANIC_CARDS:
            cards.append({"mechanic_key": key, **MECHANIC_CARDS[key]})
    return cards
