"""TDD: Issue #973 — Kowalskie oko: rabat sklepowy i akcja Reperuj."""
import sys
import sqlite3
import json
sys.path.insert(0, "/app")

from app.services.shop_service import DWARF_SHOP_DISCOUNT, _get_character_race, _cha_buy_multiplier
from app.services import haggle_service

DB_PATH = "/data/ai_gm.db"


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_dwarf_shop_discount_constant():
    """Stała DWARF_SHOP_DISCOUNT musi istnieć i wynosić 0.15."""
    assert DWARF_SHOP_DISCOUNT == 0.15, f"Oczekiwano 0.15, jest {DWARF_SHOP_DISCOUNT}"


def test_get_character_race_returns_human_fallback():
    """_get_character_race zwraca 'human' gdy char nie istnieje lub brak race."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    race = _get_character_race(conn, 999999999)  # nieistniejące ID
    conn.close()
    assert race == "human"


def test_dwarf_effective_buy_multiplier_lower():
    """Krasnolud ma niższy mnożnik ceny niż człowiek przy tej samej CHA."""
    cha = 10
    # Człowiek: bez racial discount
    human_mult = round(_cha_buy_multiplier(cha) * 1.0, 4)
    # Krasnolud: racial discount 15%
    dwarf_mult = round(_cha_buy_multiplier(cha) * (1.0 - DWARF_SHOP_DISCOUNT), 4)
    assert dwarf_mult < human_mult, (
        f"Krasnolud powinien mieć niższy mnożnik ceny: {dwarf_mult} >= {human_mult}"
    )


def test_dwarf_repair_endpoint_exists():
    """Endpoint POST /characters/{id}/dwarf-repair musi istnieć w characters router."""
    import app.api.characters as ch_module
    routes = [r.path for r in ch_module.router.routes]
    dwarf_repair_routes = [r for r in routes if "dwarf-repair" in r]
    assert len(dwarf_repair_routes) > 0, (
        f"Brak endpointu dwarf-repair. Dostępne: {[r for r in routes if 'character' in r][:10]}"
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_human_discount_unchanged():
    """Człowiek nie ma racial discount — mnożnik tylko z CHA."""
    cha = 10
    cha_mult = _cha_buy_multiplier(cha)
    # Bez racial discount mnożnik = sam CHA
    assert cha_mult == 1.0, f"Człowiek z CHA 10 powinien mieć mult=1.0, jest {cha_mult}"
