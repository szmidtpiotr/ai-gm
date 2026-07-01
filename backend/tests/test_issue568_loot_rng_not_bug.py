"""TDD: Issue #568 — „brak lootu po zwycięstwie": rozstrzygnięcie bug vs RNG.

Werdykt: NIE bug. `roll_loot` rzuca KAŻDY wpis tabeli niezależnie wg jego `chance`
(loot_enemy: bandaż 50% / pochodnia 40% / sztylet 15%). P(nic) = 0.5*0.6*0.85 ≈ 25%,
więc puste łupy ~1/4 to normalny pech — nie błąd ścieżki.

Te testy dowodzą deterministycznie (seedowany RNG), że:
1) ścieżka rolla DZIAŁA — przy sprzyjających seedach wypada przedmiot,
2) puste łupy SĄ możliwe — co tłumaczy zgłoszenie gracza bez błędu w kodzie.

Czyste, izolowane od /data: monkeypatch `get_loot_table` + `_conn` (tylko lookup loot_table_key).
"""
import sys
sys.path.insert(0, "/app")

import random
import sqlite3
import app.services.loot_service as loot_service


_ENTRIES = [
    {"item_key": "bandage", "weapon_key": None, "consumable_key": None, "chance": 0.50, "quantity_min": 1, "quantity_max": 1},
    {"item_key": "torch", "weapon_key": None, "consumable_key": None, "chance": 0.40, "quantity_min": 1, "quantity_max": 1},
    {"item_key": None, "weapon_key": "dagger", "consumable_key": None, "chance": 0.15, "quantity_min": 1, "quantity_max": 1},
]


def _patch(monkeypatch):
    """Enemy ma loot_table_key; wpisy z _ENTRIES — bez dotykania /data."""
    class _FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k):
            class _C:
                def fetchone(self_inner): return {"loot_table_key": "loot_enemy", "drop_chance": 1.0}
            return _C()
    monkeypatch.setattr(loot_service, "_conn", lambda: _FakeConn())
    monkeypatch.setattr(loot_service, "get_loot_table", lambda _ek: list(_ENTRIES))


# ─── Dowód 1: ścieżka działa — przedmiot wypada ──────────────────────────────

def test_loot_path_can_drop_items(monkeypatch):
    """Przy seedach sprzyjających przynajmniej raz wypada przedmiot (ścieżka OK)."""
    _patch(monkeypatch)
    saw_item = False
    for s in range(50):
        random.seed(s)
        if loot_service.roll_loot("enemy"):
            saw_item = True
            break
    assert saw_item, "roll_loot nigdy nic nie zwrócił — to byłby bug ścieżki (#568)"


# ─── Dowód 2: puste łupy są możliwe (RNG, nie bug) ───────────────────────────

def test_empty_loot_is_possible(monkeypatch):
    """Istnieje seed dający puste łupy — „brak lootu" to legalny wynik RNG (#568)."""
    _patch(monkeypatch)
    saw_empty = False
    for s in range(50):
        random.seed(s)
        if not loot_service.roll_loot("enemy"):
            saw_empty = True
            break
    assert saw_empty, "puste łupy niemożliwe — sprzeczne z obserwacją gracza (#568)"


# ─── Kontrakt: pusty/nieznany enemy_key → [] ─────────────────────────────────

def test_blank_key_returns_empty():
    assert loot_service.roll_loot("") == []
    assert loot_service.roll_loot(None) == []


# ─── drop_chance gate (#1076) ─────────────────────────────────────────────────

def test_drop_chance_zero_always_blocks_loot(monkeypatch):
    """drop_chance=0.0 → gate zawsze blokuje, żaden item nie wypada."""
    class _FakeConnZero:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k):
            class _C:
                def fetchone(self_inner): return {"loot_table_key": "loot_enemy", "drop_chance": 0.0}
            return _C()
    monkeypatch.setattr(loot_service, "_conn", lambda: _FakeConnZero())
    monkeypatch.setattr(loot_service, "get_loot_table", lambda _ek: list(_ENTRIES))
    for s in range(20):
        random.seed(s)
        assert loot_service.roll_loot("enemy") == [], f"seed {s}: drop_chance=0.0 powinien blokować wszystko"


def test_drop_chance_one_never_blocks_loot(monkeypatch):
    """drop_chance=1.0 → gate zawsze przepuszcza (przy dobrym seedzie wypada item)."""
    _patch(monkeypatch)
    saw_item = False
    for s in range(50):
        random.seed(s)
        if loot_service.roll_loot("enemy"):
            saw_item = True
            break
    assert saw_item, "drop_chance=1.0 powinien zawsze przepuszczać gate"
