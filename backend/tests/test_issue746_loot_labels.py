"""TDD: Issue #746 — Nazwy łupów w preview walki muszą być polskimi etykietami z DB,
nie surowymi kluczami (`key.replace("_", " ")`)."""
import sqlite3
import pytest

from app.services.combat_service import _preview_loot_from_roll_items, _conn


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_preview_loot_uses_db_label_for_consumable():
    """Consumable o znanym kluczu dostaje polską etykietę z game_config_consumables,
    a nie 'potion healing standard' z key.replace."""
    conn = _conn()
    try:
        # upewnij się że rekord referencyjny istnieje w DB DEV
        row = conn.execute(
            "SELECT label FROM game_config_consumables WHERE key = 'potion_healing_standard'"
        ).fetchone()
        if not row:
            pytest.skip("brak potion_healing_standard w DB testowej")
        expected = str(row["label"])

        out = _preview_loot_from_roll_items(
            [{"consumable_key": "potion_healing_standard", "quantity": 1}],
            conn=conn,
        )
        assert len(out) == 1
        assert out[0]["label"] == expected, (
            f"label={out[0]['label']!r} — powinno być z DB {expected!r}, "
            "nie surowy klucz"
        )
        assert out[0]["label"] != "potion healing standard"
    finally:
        conn.close()


def test_preview_loot_label_has_no_underscores_when_in_db():
    """Etykieta z DB nie jest surowym kluczem z podkreśleniami."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT key FROM game_config_consumables WHERE label IS NOT NULL "
            "AND label != '' LIMIT 1"
        ).fetchone()
        if not row:
            pytest.skip("brak consumable z etykietą w DB testowej")
        key = str(row["key"])
        out = _preview_loot_from_roll_items(
            [{"consumable_key": key, "quantity": 2}], conn=conn
        )
        assert out[0]["quantity"] == 2
        assert out[0]["label"] != key.replace("_", " ")
    finally:
        conn.close()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_preview_loot_fallback_for_unknown_key():
    """Nieznany klucz (brak w DB) nadal degraduje do key.replace('_',' ')."""
    out = _preview_loot_from_roll_items(
        [{"item_key": "totally_fake_thing_xyz", "quantity": 1}]
    )
    assert len(out) == 1
    assert out[0]["label"] == "totally fake thing xyz"


def test_preview_loot_callable_without_conn():
    """Stara sygnatura (bez conn) nadal działa — nie wymaga przekazania połączenia."""
    out = _preview_loot_from_roll_items(
        [{"consumable_key": "potion_healing_standard", "quantity": 1}],
        loot_tier="standard",
    )
    assert len(out) == 1
    # bez podanego conn funkcja sama otwiera połączenie → też polska etykieta
    assert out[0]["label"] != "potion healing standard"
