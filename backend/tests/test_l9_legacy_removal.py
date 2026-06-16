"""TDD L9 — Usunięcie trybu proceduralnego lochu (#678).

Weryfikuje stan PO czystce: legacy funkcje nie istnieją,
endpointy zwracają 410, seedy legacy nieaktywne.
"""
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"


# ── 1. generate_dungeon_instance usunięte ─────────────────────────────────────

def test_generate_dungeon_instance_removed():
    """generate_dungeon_instance nie może być importowalne po L9."""
    import app.services.dungeon_service as ds
    assert not hasattr(ds, "generate_dungeon_instance"), (
        "generate_dungeon_instance nadal istnieje w dungeon_service — nie usunięto legacy generatora"
    )


# ── 2. scale_enemy_stats usunięte ────────────────────────────────────────────

def test_scale_enemy_stats_removed():
    """scale_enemy_stats (skalowanie po poziomie bohatera) nie może istnieć po L9."""
    import app.services.dungeon_service as ds
    assert not hasattr(ds, "scale_enemy_stats"), (
        "scale_enemy_stats nadal istnieje — legacy skalowanie nie zostało usunięte"
    )


# ── 3. advance_room usunięte z dungeon_service ───────────────────────────────

def test_advance_room_removed_from_service():
    """advance_room (legacy) nie może istnieć w dungeon_service po L9."""
    import app.services.dungeon_service as ds
    assert not hasattr(ds, "advance_room"), (
        "advance_room nadal istnieje w dungeon_service — funkcja legacy nie usunięta"
    )


# ── 4. resolve_room usunięte z dungeon_service ───────────────────────────────

def test_resolve_room_removed_from_service():
    """resolve_room (legacy) nie może istnieć w dungeon_service po L9."""
    import app.services.dungeon_service as ds
    assert not hasattr(ds, "resolve_room"), (
        "resolve_room nadal istnieje w dungeon_service — funkcja legacy nie usunięta"
    )


# ── 5. POST /dungeons/advance-room → 410 ─────────────────────────────────────

def test_advance_room_endpoint_returns_410():
    """POST /dungeons/advance-room musi zwracać 410 Gone (stary endpoint usunięty)."""
    r = client.post("/api/dungeons/advance-room", json={"campaign_id": 1, "character_id": 1})
    assert r.status_code == 410, (
        f"Oczekiwano 410 Gone, dostano {r.status_code}. "
        "Endpoint /dungeons/advance-room nie zwraca 410 — legacy endpoint nie zablokowany."
    )


# ── 6. POST /dungeons/resolve-room → 410 ─────────────────────────────────────

def test_resolve_room_endpoint_returns_410():
    """POST /dungeons/resolve-room musi zwracać 410 Gone (stary endpoint usunięty)."""
    r = client.post("/api/dungeons/resolve-room", json={"campaign_id": 1, "character_id": 1})
    assert r.status_code == 410, (
        f"Oczekiwano 410 Gone, dostano {r.status_code}. "
        "Endpoint /dungeons/resolve-room nie zwraca 410 — legacy endpoint nie zablokowany."
    )


# ── 7. Żaden aktywny loch bez tile_category_key ──────────────────────────────

def test_no_active_dungeon_without_tile_category():
    """Po L9 żaden aktywny loch nie może mieć NULL tile_category_key."""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT key FROM game_dungeons WHERE is_active = 1 AND (tile_category_key IS NULL OR tile_category_key = '')"
        ).fetchall()
        assert len(rows) == 0, (
            f"Aktywne lochy bez tile_category_key: {[r[0] for r in rows]}. "
            "Seedy legacy muszą być dezaktywowane (is_active=0)."
        )
    finally:
        conn.close()


# ── 8. dungeon_tiles_enabled nie w _GAME_MODE_DEFAULTS ──────────────────────

def test_dungeon_tiles_enabled_not_in_defaults():
    """dungeon_tiles_enabled nie może być w _GAME_MODE_DEFAULTS po L9 (jeden tryb)."""
    from app.routers.admin import _GAME_MODE_DEFAULTS
    assert "dungeon_tiles_enabled" not in _GAME_MODE_DEFAULTS, (
        "dungeon_tiles_enabled nadal jest w _GAME_MODE_DEFAULTS — flag bezprzedmiotowa po L9"
    )


# ── 9. dungeon_tile_service importuje bez błędu po usunięciu scale_enemy_stats ─

def test_dungeon_tile_service_import_clean():
    """dungeon_tile_service musi importować się bez błędów po usunięciu scale_enemy_stats z importu."""
    try:
        import importlib
        import app.services.dungeon_tile_service as dts
        importlib.reload(dts)
    except ImportError as e:
        pytest.fail(f"dungeon_tile_service rzuca ImportError po L9: {e}")
    except Exception as e:
        pytest.fail(f"dungeon_tile_service rzuca wyjątek po L9: {e}")


# ── 10. _build_dungeon_instance usunięte ─────────────────────────────────────

def test_build_dungeon_instance_removed():
    """_build_dungeon_instance (legacy generator) nie może istnieć po L9."""
    import app.services.dungeon_service as ds
    assert not hasattr(ds, "_build_dungeon_instance"), (
        "_build_dungeon_instance nadal istnieje — legacy generator nie usunięty"
    )


# ── 11. Zachowane funkcje nadal działają ─────────────────────────────────────

def test_critical_functions_still_exist():
    """Funkcje używane przez nowy system MUSZĄ pozostać po L9."""
    import app.services.dungeon_service as ds
    must_exist = [
        "_answer_matches",       # dungeon_tile_service używa
        "check_cooldown",
        "complete_dungeon",
        "get_dungeon",
        "list_dungeons",
        "get_active_dungeon_run",
        "get_current_room",
        "clear_dungeon_run",
        "grant_dungeon_loot",
        "roll_boss_loot",
        "RARITY_TIERS",
        "get_loot_rarity_for_difficulty",
        "restore_dungeon_checkpoint",
        "handle_dungeon_death",
        "handle_dungeon_abandon",
        "start_dungeon_cooldown",
    ]
    missing = [fn for fn in must_exist if not hasattr(ds, fn)]
    assert not missing, (
        f"Usunięto za dużo! Brakuje: {missing}. "
        "Te funkcje są wymagane przez nowy system kafelkowy."
    )
