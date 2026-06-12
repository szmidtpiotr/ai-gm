"""E24 + E27 (#442) — Onboarding card triggers.

check_onboarding_triggers(user_id, triggered_keys, conn) → list of card dicts
for mechanic keys NOT yet seen by this user.
Does NOT mark them as seen — frontend calls POST /api/users/{id}/seen-mechanics after showing.

E27 (#442): adds "affixes" and "crafting" card definitions + trigger heuristics.
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
    "world_map": {
        "title": "Podróż po świecie",
        "content": (
            "Świat to mapa pól (heksów). Aby się przemieścić, masz dwie drogi: "
            "1) otwórz mapę ikoną 🗺 (prawy górny róg) i kliknij sąsiednie pole, potem „Wyrusz”; "
            "2) napisz w polu akcji, dokąd idziesz — np. „idę na północ”, „idę na wschód” "
            "lub „idę do karczmy”. Kierunki: północ / południe / wschód / zachód. "
            "Podróż zużywa czas gry i może wywołać spotkanie po drodze."
        ),
    },
    "affixes": {
        "title": "Magiczne afiksy",
        "content": (
            "Ten przedmiot ma magiczne właściwości zwane afiksami! Afiksy to specjalne bonusy — "
            "np. +3 do obrażeń, leczenie przy trafieniu, bonus do pancerza. "
            "Możesz dodać lub przelosować afiksy u Rzemieślnika w mieście za złoto. "
            "Im wyższy tier afiksu (T1→T3), tym potężniejszy efekt."
        ),
    },
    "crafting": {
        "title": "Rzemiosło i ulepszanie",
        "content": (
            "Możesz ulepszać swoje przedmioty u Rzemieślnika! Wybierz broń lub zbroję z ekwipunku, "
            "a Rzemieślnik doda magiczny afiks za złoto. Możesz też przelosować afiks (ten sam tier, "
            "nowy efekt) lub awansować afiks do wyższego tiera (T1→T2→T3) za wyższą cenę. "
            "Crafting to najszybszy sposób na mocniejszy ekwipunek bez czekania na losy."
        ),
    },
}


def inject_onboarding_to_out(out: dict, user_id: int, conn) -> dict:
    """Detect triggered mechanics from a turn out-dict and inject onboarding_cards in-place.

    Trigger heuristics:
    - dice_roll    → out has skill_test_pending
    - combat_start → out has combat_state
    - world_map    → out has current_hex (campaign uses the hex world)
    - xp_gained    → result has xp_granted or xp_earned > 0
    - gold_gained  → result has gold_drop or gold_earned > 0
    - damage_taken → result has damage > 0
    - death_save   → result.test == "death_save"
    - affixes      → result.loot has item with non-empty affixes list (E27 #442)
    """
    triggered: List[str] = []
    if out.get("skill_test_pending"):
        triggered.append("dice_roll")
    if out.get("combat_state") is not None:
        triggered.append("combat_start")
    # world_map: campaign has a hex world → teach movement once, early
    if out.get("current_hex") is not None:
        triggered.append("world_map")
    result = out.get("result") or {}
    if isinstance(result, dict):
        if int(result.get("xp_granted") or result.get("xp_earned") or 0) > 0:
            triggered.append("xp_gained")
        if int(result.get("gold_drop") or result.get("gold_earned") or 0) > 0:
            triggered.append("gold_gained")
        if int(result.get("damage") or 0) > 0:
            triggered.append("damage_taken")
        if result.get("test") == "death_save":
            triggered.append("death_save")
        # E27 (#442): trigger affixes card when loot contains items with affixes
        loot = result.get("loot")
        if isinstance(loot, list):
            for item in loot:
                if isinstance(item, dict) and item.get("affixes"):
                    triggered.append("affixes")
                    break
    cards = check_onboarding_triggers(user_id=user_id, triggered_keys=triggered, conn=conn)
    out["onboarding_cards"] = cards
    return out


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


def get_unseen_cards_for_mechanics(
    conn: sqlite3.Connection,
    user_id: int,
    mechanic_keys: List[str],
) -> List[dict]:
    """Return card dicts for mechanic_keys that user hasn't seen yet.

    Used by craft endpoints to inject "crafting" onboarding on first use.
    Does not modify DB — caller handles mark-seen.
    """
    if not mechanic_keys:
        return []
    try:
        rows = conn.execute(
            "SELECT mechanic_key FROM seen_mechanics WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        already_seen = {r["mechanic_key"] for r in rows}
    except Exception:
        already_seen = set()

    cards = []
    for key in mechanic_keys:
        if key not in already_seen and key in MECHANIC_CARDS:
            cards.append({"mechanic_key": key, **MECHANIC_CARDS[key]})
    return cards
