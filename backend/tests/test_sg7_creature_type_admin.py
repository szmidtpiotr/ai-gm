"""SG-7 (#1481) — przełącznik „istota Rdzenia" w panelu admina.

Kolumna `creature_type` powstała razem z solą, ale admin nie miał jak jej ustawić —
modal wroga nie miał pola, a modele żądań (extra="forbid") odrzucały to pole.

Przy okazji dwa defekty modala wychodzą tu na jaw i są testowane jako regresja:
POST z modala niósł `min_level` (nieznane polu Create), a PATCH niósł `key`
(nieznane polu Patch) — oba kończyły się 422 zamiast zapisu.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers.admin import EnemyCreateReq, EnemyPatchReq
from app.services import admin_config

KEY = "test_sg7_creature_type"


@pytest.fixture
def enemy_key():
    try:
        admin_config.delete_enemy(KEY, force=True)
    except Exception:
        pass
    yield KEY
    try:
        admin_config.delete_enemy(KEY, force=True)
    except Exception:
        pass


# ─── kontrakt API (modele żądań) ─────────────────────────────────────────────

def test_create_request_accepts_the_modal_payload():
    """Payload, który realnie wysyła modal wroga — z min_level i klasą istoty."""
    req = EnemyCreateReq(
        key=KEY, label="Test", hp_base=10, ac_base=10, attack_bonus=1,
        damage_die="1d6", min_level=3, creature_type="undead",
    )
    assert req.min_level == 3
    assert req.creature_type == "undead"


def test_patch_request_accepts_creature_type():
    assert EnemyPatchReq(creature_type="rdzen").creature_type == "rdzen"
    assert EnemyPatchReq(creature_type="").creature_type == ""


def test_patch_request_still_rejects_the_key_field():
    """Klucz jedzie w URL — modal nie może go wkładać do ciała (to był powód 422)."""
    with pytest.raises(Exception):
        EnemyPatchReq(key="x", label="y")


# ─── zapis do bazy ───────────────────────────────────────────────────────────

def test_create_enemy_stores_creature_type(enemy_key):
    row = admin_config.create_enemy(
        key=enemy_key, label="Widmo Testowe", hp_base=12, ac_base=11,
        attack_bonus=2, damage_die="d6", creature_type="undead", min_level=4,
    )
    assert row.get("creature_type") == "undead"
    assert row.get("min_level") == 4


def test_create_enemy_without_class_is_a_living_creature(enemy_key):
    """Domyślny stan: puste = żywe stworzenie, sól nie działa."""
    row = admin_config.create_enemy(
        key=enemy_key, label="Troll Testowy", hp_base=12, ac_base=11,
        attack_bonus=2, damage_die="d6",
    )
    assert not row.get("creature_type")


def test_update_enemy_sets_and_clears_creature_type(enemy_key):
    admin_config.create_enemy(
        key=enemy_key, label="Test", hp_base=12, ac_base=11,
        attack_bonus=2, damage_die="d6",
    )
    common = dict(
        label=None, hp_base=None, ac_base=None, attack_bonus=None, damage_die=None,
        description=None, is_active=None, force=False,
    )
    row = admin_config.update_enemy(enemy_key, creature_type="demon", **common)
    assert row.get("creature_type") == "demon"

    # pusty string = świadome wyzerowanie (wróg znów jest żywy)
    row = admin_config.update_enemy(enemy_key, creature_type="", **common)
    assert not row.get("creature_type")

    # None = pole nietknięte
    row = admin_config.update_enemy(enemy_key, creature_type="rdzen", **common)
    row = admin_config.update_enemy(enemy_key, creature_type=None, **common)
    assert row.get("creature_type") == "rdzen"


def test_invalid_creature_type_is_rejected(enemy_key):
    with pytest.raises(ValueError, match="invalid_creature_type"):
        admin_config.create_enemy(
            key=enemy_key, label="Test", hp_base=12, ac_base=11,
            attack_bonus=2, damage_die="d6", creature_type="wampirek",
        )


def test_list_enemies_exposes_creature_type(enemy_key):
    """Lista musi nieść pole — inaczej modal edycji nie ma czym wypełnić selecta."""
    admin_config.create_enemy(
        key=enemy_key, label="Test", hp_base=12, ac_base=11,
        attack_bonus=2, damage_die="d6", creature_type="undead",
    )
    row = next(e for e in admin_config.list_enemies() if e["key"] == enemy_key)
    assert row.get("creature_type") == "undead"
