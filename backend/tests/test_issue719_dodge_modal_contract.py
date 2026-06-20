"""TDD: Issue #719 — modal kości pokazuje rzut wroga na unik (test OPOZYCYJNY).

Trafienie w walce to pojedynek: Twój atak (d20 + bonusy) vs rzut wroga na unik
(d20 + ZRC). Modal kości na froncie tylko NAZYWA te dane — całą logikę liczy silnik
(`compute_player_attack_dodge_outcome`). Ten test blokuje KONTRAKT, na którym opiera
się modal: defender wygrywa remisy, nat1 = auto-pudło, nat20 = auto-trafienie (wróg
nie rzuca uniku). Jeśli ktoś zmieni regułę uniku, front pokaże nieprawdę → test złapie.

Feature wdrożona wcześniej (commit cefb46d, tuning 3d5d7ba). Ten plik = strażnik regresji.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.combat_service import compute_player_attack_dodge_outcome

# ─── Test główny — opozycyjny unik, defender wygrywa remisy ───────────────────

def test_high_attack_beats_low_dodge_is_hit():
    """Atak > unik wroga → trafienie (modal: '✔ Trafienie!')."""
    dodged, hit, dodge_total = compute_player_attack_dodge_outcome(
        attack_total=18, dodge_roll_raw=5, dex_modifier=2, player_raw_d20=15
    )
    assert dodge_total == 7
    assert hit is True
    assert dodged is False


def test_dodge_ge_attack_is_dodged():
    """Unik wroga ≥ atak → pudło (modal: '🛡 Wróg uniknął ciosu')."""
    dodged, hit, _ = compute_player_attack_dodge_outcome(
        attack_total=12, dodge_roll_raw=14, dex_modifier=3, player_raw_d20=10
    )
    assert dodged is True
    assert hit is False


def test_defender_wins_ties():
    """Remis (unik == atak) → wróg unika. To clue dla gracza, czemu 'równy' rzut chybia."""
    dodged, hit, dodge_total = compute_player_attack_dodge_outcome(
        attack_total=15, dodge_roll_raw=12, dex_modifier=3, player_raw_d20=11
    )
    assert dodge_total == 15
    assert dodged is True
    assert hit is False


def test_nat20_auto_hit_no_dodge():
    """Nat 20 → auto-trafienie, wróg nie rzuca uniku (modal: '✦ Krytyczny sukces!')."""
    dodged, hit, _ = compute_player_attack_dodge_outcome(
        attack_total=99, dodge_roll_raw=20, dex_modifier=10, player_raw_d20=20
    )
    # mimo bardzo wysokiego rzutu uniku — nat20 wygrywa
    assert hit is True
    assert dodged is False


def test_nat1_auto_miss():
    """Nat 1 → auto-pudło niezależnie od uniku (modal: '✧ Krytyczna porażka')."""
    dodged, hit, _ = compute_player_attack_dodge_outcome(
        attack_total=50, dodge_roll_raw=1, dex_modifier=0, player_raw_d20=1
    )
    assert hit is False
    assert dodged is True


# ─── Backward compatibility — wywołanie bez raw d20 (np. spell path bez nat) ───

def test_no_raw_d20_falls_back_to_totals():
    """player_raw_d20=None → czysty test opozycyjny bez reguł nat (stary interfejs)."""
    dodged, hit, dodge_total = compute_player_attack_dodge_outcome(
        attack_total=16, dodge_roll_raw=10, dex_modifier=2, player_raw_d20=None
    )
    assert dodge_total == 12
    assert hit is True
    assert dodged is False
