"""E24 + E27 (#442) — Onboarding card triggers.

check_onboarding_triggers(user_id, triggered_keys, conn) → list of card dicts
for mechanic keys NOT yet seen by this user.
Does NOT mark them as seen — frontend calls POST /api/users/{id}/seen-mechanics after showing.

E27 (#442): adds "affixes" and "crafting" card definitions + trigger heuristics.
"""
from __future__ import annotations
import json
import sqlite3
from typing import List

MECHANIC_CARDS: dict[str, dict] = {
    "dice_roll": {
        "title": "Rzut kością",
        "content": (
            "Twoje akcje rozstrzygane są rzutem: k20 + Mod. statystyki + Ranga umiejętności + Biegłość "
            "(te same składniki widzisz na karcie rzutu). Wynik porównywany jest z trudnością (DC): "
            "8 łatwe, 12 średnie, 16 trudne, 20 ekstremalne. "
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
            "Za pokonanych wrogów i ukończone zadania zdobywasz punkty doświadczenia (XP/PD). "
            "Aby je wydać: w bezpiecznej lokacji otwórz panel „Odpoczynek”, kliknij „★ Długi”, "
            "a potem „📖 Ucz się” — tam podnosisz umiejętności i statystyki (możesz też użyć „⬆ Awansuj”). "
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
        "title": "Na krawędzi śmierci",
        "content": (
            "Twoje HP spadły poniżej 25% — jesteś o krok od upadku. Gdy HP dojdą do 0, bohater pada "
            "i rzuca test śmierci (CON DC 10): sukces — wstajesz z 1 HP, porażka przybliża śmierć "
            "(drabina nieudanych rzutów). Niektóre zdolności i mikstury ratują przed śmiercią, ale "
            "wskrzeszenie kosztuje złoto. Lecz się teraz — miksturą, czarem albo wycofaniem z walki. "
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
    # U20 (#572) — new mechanic cards
    "durability": {
        "title": "Zużycie ekwipunku",
        "content": (
            "Twoja broń i zbroja zużywają się z użyciem — broń przy własnym trafionym ataku, "
            "zbroja przy otrzymanym ciosie. Pasek trwałości w ekwipunku spadł poniżej połowy. "
            "Gdy trwałość dojdzie do zera, przedmiot pęka i działa o połowę słabiej (−50%). "
            "Naprawisz go w karcie przedmiotu („🔧 Naprawa”) za złoto — zrób to, zanim pęknie."
        ),
    },
    "raids": {
        "title": "Napady na szlaku",
        "content": (
            "Wszedłeś na dziki teren z sakiewką pełną złota (>100 gp). Z dala od bezpiecznych osad "
            "bandyci mogą cię napaść i ukraść część złota, zanim zdążysz zareagować. "
            "Im więcej nosisz, tym większa pokusa. Wydaj lub zdeponuj złoto w mieście, "
            "albo trzymaj się bezpieczniejszych dróg, by zmniejszyć ryzyko."
        ),
    },
    "crafter": {
        "title": "Rzemieślnik",
        "content": (
            "Spotkałeś rzemieślnika (kowala/płatnerza). To on potrafi ulepszać twój sprzęt: "
            "nakłada magiczne afiksy, przelosowuje je i awansuje do wyższego tieru, a także naprawia "
            "zużyte przedmioty — wszystko za złoto. Ulepszenia obsłużysz z karty przedmiotu w ekwipunku "
            "(„⚒ Kuźnia afiksów”, „🔧 Naprawa”). Zajrzyj do niego, gdy chcesz wzmocnić ekwipunek."
        ),
    },
}


# U20 (#572) trigger thresholds (starting values — Numbers Policy)
DEATH_SAVE_HP_RATIO = 0.25      # teach the death ladder once HP drops below 25%
LOW_DURABILITY_RATIO = 0.50     # warn about equipment wear below 50%
RAID_GOLD_THRESHOLD = 100       # raids risk card when carrying more than 100 gp on a wild hex


def _cget(character, key, default=None):
    """Read a field from a character that may be a dict or a sqlite3.Row."""
    try:
        val = character[key]
    except Exception:
        return default
    return default if val is None else val


def _player_hp_ratio(conn, character) -> float | None:
    """current_hp / max_hp, or None if unknown.

    Reads the FRESH sheet from the DB (the `character` row is loaded at turn start,
    so its HP predates this turn's damage). Falls back to the passed sheet_json.
    """
    raw = None
    char_id = _cget(character, "id")
    if char_id is not None:
        try:
            row = conn.execute(
                "SELECT sheet_json FROM characters WHERE id = ?", (char_id,)
            ).fetchone()
            if row and row["sheet_json"]:
                raw = row["sheet_json"]
        except Exception:
            raw = None
    if raw is None:
        raw = _cget(character, "sheet_json")
    sheet = {}
    if isinstance(raw, str) and raw:
        try:
            sheet = json.loads(raw)
        except Exception:
            sheet = {}
    elif isinstance(raw, dict):
        sheet = raw
    try:
        mx = int(sheet.get("max_hp") or 0)
        cur = int(sheet.get("current_hp"))
    except (TypeError, ValueError):
        return None
    if mx <= 0:
        return None
    return cur / mx


def _has_low_durability(conn, character) -> bool:
    """True if any equipped weapon/armor has durability below LOW_DURABILITY_RATIO."""
    char_id = _cget(character, "id")
    if char_id is None:
        return False
    try:
        rows = conn.execute(
            "SELECT durability_current, durability_max FROM character_inventory "
            "WHERE character_id = ? AND equipped = 1 "
            "AND durability_max IS NOT NULL AND durability_max > 0",
            (char_id,),
        ).fetchall()
    except Exception:
        return False
    for r in rows:
        mx = int(r["durability_max"] or 0)
        cur = int(r["durability_current"] or 0)
        if mx > 0 and cur / mx < LOW_DURABILITY_RATIO:
            return True
    return False


def _is_on_wild_hex(conn, character) -> bool:
    """True if the character's current location is NOT safe for rest (wild territory)."""
    char_id = _cget(character, "id")
    campaign_id = _cget(character, "campaign_id")
    if char_id is None or campaign_id is None:
        return False
    try:
        from app.services.rest_service import _is_safe_for_character
        return not _is_safe_for_character(int(char_id), int(campaign_id), conn)
    except Exception:
        # No session / unknown location → treat as wild
        return True


def _scene_has_crafter(conn, character) -> bool:
    """True if a scene NPC in the current campaign is flagged is_crafter."""
    campaign_id = _cget(character, "campaign_id")
    if campaign_id is None:
        return False
    try:
        row = conn.execute(
            "SELECT scene_npcs FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row or not row["scene_npcs"]:
            return False
        scene = json.loads(row["scene_npcs"] or "[]")
        keys = [str(n.get("key")) for n in scene if isinstance(n, dict) and n.get("key")]
        if not keys:
            return False
        placeholders = ",".join("?" for _ in keys)
        crow = conn.execute(
            f"SELECT 1 FROM npcs WHERE is_crafter = 1 AND key IN ({placeholders}) LIMIT 1",
            keys,
        ).fetchone()
        return crow is not None
    except Exception:
        return False


def inject_onboarding_to_out(out: dict, user_id: int, conn, character=None) -> dict:
    """Detect triggered mechanics from a turn out-dict and inject onboarding_cards in-place.

    Trigger heuristics:
    - dice_roll    → out has skill_test_pending
    - combat_start → out has combat_state
    - world_map    → out has current_hex (campaign uses the hex world)
    - xp_gained    → result has xp_granted or xp_earned > 0
    - gold_gained  → result has gold_drop or gold_earned > 0
    - damage_taken → result has damage > 0
    - affixes      → result.loot has item with non-empty affixes list (E27 #442)

    U20 (#572) — character-aware triggers (only when `character` is provided):
    - death_save   → player HP ratio < DEATH_SAVE_HP_RATIO (first drop below 25%, not first roll)
    - durability   → any equipped weapon/armor below LOW_DURABILITY_RATIO
    - raids        → on a wild hex carrying more than RAID_GOLD_THRESHOLD gold
    - crafter      → NPC dialogue this turn with an is_crafter scene NPC
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
        # E27 (#442): trigger affixes card when loot contains items with affixes
        loot = result.get("loot")
        if isinstance(loot, list):
            for item in loot:
                if isinstance(item, dict) and item.get("affixes"):
                    triggered.append("affixes")
                    break

    # U20 (#572): character-aware just-in-time triggers
    if character is not None:
        ratio = _player_hp_ratio(conn, character)
        if ratio is not None and ratio < DEATH_SAVE_HP_RATIO:
            triggered.append("death_save")
        if _has_low_durability(conn, character):
            triggered.append("durability")
        if (
            out.get("current_hex") is not None
            and int(_cget(character, "gold_gp", 0) or 0) > RAID_GOLD_THRESHOLD
            and _is_on_wild_hex(conn, character)
        ):
            triggered.append("raids")
        if out.get("npc_dialogue") and _scene_has_crafter(conn, character):
            triggered.append("crafter")

    cards = check_onboarding_triggers(user_id=user_id, triggered_keys=triggered, conn=conn)
    out["onboarding_cards"] = cards
    return out


def _card_content(key: str, conn: sqlite3.Connection | None = None) -> dict | None:
    """#594: card {title, content} from knowledge_book (kind='onboarding_card'),
    falling back to the hardcoded MECHANIC_CARDS when the DB row is missing or the
    `kind` column hasn't been migrated yet. Keeps onboarding working pre-migration.
    """
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT title, body FROM knowledge_book "
                "WHERE kind = 'onboarding_card' AND tip_key = ? AND is_active = 1",
                (key,),
            ).fetchone()
            if row:
                return {"title": row["title"], "content": row["body"]}
        except Exception:
            pass
    return MECHANIC_CARDS.get(key)


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
        if key in already_seen:
            continue
        content = _card_content(key, conn)
        if content:
            cards.append({"mechanic_key": key, **content})
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
        if key in already_seen:
            continue
        content = _card_content(key, conn)
        if content:
            cards.append({"mechanic_key": key, **content})
    return cards
