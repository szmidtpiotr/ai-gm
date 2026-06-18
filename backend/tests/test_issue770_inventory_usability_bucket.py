"""TDD: Issue #770 — inventory bucketing by usability (can_use) not item_type."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Helpers — simulate frontend bucketing predicates ────────────────────────

def _old_is_lore(item: dict) -> bool:
    """OLD (buggy) predicate from app.js:7299 — checks item_type only."""
    t = str(item.get("item_type") or "").lower()
    return t in ("misc", "quest", "narrative")


def _new_is_usable(item: dict) -> bool:
    """NEW predicate (post-fix) — uses can_use + item_type for weapon/armor."""
    t = str(item.get("item_type") or "").lower()
    if t in ("weapon", "armor"):
        return True
    return item.get("can_use") is True


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_narrative_item_with_item_type_item_wrongly_goes_to_backpack_with_old_predicate():
    """Dowód buga #770: narracyjny przedmiot z item_type='item' (#757 pattern) trafia
    do backpack zamiast do sekcji lore, bo _invIsLore nie rozpoznaje item_type='item'."""
    # Item from #757: created via game_config_items, has item_type='item', can_use=False
    pergamin = {"item_type": "item", "can_use": False, "label": "Pergamin z mapą"}

    # OLD predicate: returns False for item_type='item' → item goes to BACKPACK (bug)
    assert _old_is_lore(pergamin) is False, "Stary predykat błędnie klasyfikuje pergamin jako backpack"

    # NEW predicate: can_use=False → not usable → should go to LORE (correct)
    assert _new_is_usable(pergamin) is False, "Nowy predykat powinien dać False → sekcja lore"


def test_consumable_is_usable():
    """Mikstura/consumable (can_use=True) trafia do górnej sekcji (plecak)."""
    mikstura = {"item_type": "consumable", "can_use": True, "label": "Mikstura leczenia"}
    assert _new_is_usable(mikstura) is True


def test_ammo_as_consumable_is_usable():
    """Strzały (#764) są consumable → can_use=True → górna sekcja."""
    strzaly = {"item_type": "consumable", "can_use": True, "label": "Strzały"}
    assert _new_is_usable(strzaly) is True


def test_weapon_is_usable():
    """Broń (weapon) idzie do górnej sekcji."""
    miecz = {"item_type": "weapon", "can_use": False, "label": "Miecz krótki"}
    assert _new_is_usable(miecz) is True


def test_armor_is_usable():
    """Zbroja (armor) idzie do górnej sekcji."""
    zbroja = {"item_type": "armor", "can_use": False, "label": "Kolczuga"}
    assert _new_is_usable(zbroja) is True


def test_misc_item_is_not_usable():
    """Przedmioty misc (lina, kaganek) → dolna sekcja."""
    lina = {"item_type": "misc", "can_use": False, "label": "Lina 10m"}
    assert _new_is_usable(lina) is False


def test_quest_item_is_not_usable():
    """Przedmioty questowe → dolna sekcja."""
    klucz = {"item_type": "quest", "can_use": False, "label": "Klucz do lochu"}
    assert _new_is_usable(klucz) is False


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_explicitly_narrative_item_type_still_goes_to_lore():
    """item_type='narrative' (stary format) nadal → lore przy nowym predykacie."""
    stary = {"item_type": "narrative", "can_use": False, "label": "Stary pergamin"}
    # Old predicate: caught it correctly
    assert _old_is_lore(stary) is True
    # New predicate: still goes to lore (can_use=False)
    assert _new_is_usable(stary) is False


def test_explicit_misc_still_lore_with_new_predicate():
    """item_type='misc' nadal ląduje w lore po zmianie."""
    misc = {"item_type": "misc", "can_use": False, "label": "Świeczka"}
    assert _new_is_usable(misc) is False
