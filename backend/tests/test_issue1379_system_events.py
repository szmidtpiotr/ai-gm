"""TDD: Issue #1379 — ujednolicony strumień komunikatów systemowych (system_events).

Rdzeń: bus akumulujący zdarzenia w obrębie tury + rejestr domyślnych ikon/tonów
per `kind` + konwerter istniejących pól legacy (granted_items / gold_events /
completed_beats / completed_quests) na jednolity kształt, + emisja przez
contextvar (serwis emituje bez przewlekania parametru przez sygnatury)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services import system_events as se


# ─── Test główny: bus emituje i drenuje jednolite zdarzenia ──────────────────

def test_bus_emit_and_drain_shape():
    """emit() dokłada zdarzenie o kształcie {kind, icon, tone, text}; drain() zwraca listę i czyści."""
    bus = se.SystemEventBus()
    bus.emit("xp", "+25 XP — zwycięska walka")
    out = bus.drain()
    assert isinstance(out, list) and len(out) == 1
    ev = out[0]
    assert ev["kind"] == "xp"
    assert ev["text"] == "+25 XP — zwycięska walka"
    assert ev["tone"] in ("success", "info", "warning", "danger")
    assert isinstance(ev["icon"], str) and ev["icon"]
    # drain czyści bufor — drugie wywołanie puste
    assert bus.drain() == []


def test_kind_defaults_icon_and_tone():
    """Rejestr KIND_DEFAULTS nadaje domyślną ikonę + ton per kategoria."""
    bus = se.SystemEventBus()
    bus.emit("xp", "a")
    bus.emit("gold_loss", "b")
    bus.emit("condition_applied", "c")
    bus.emit("durability", "d")
    bus.emit("night", "e")
    bus.emit("quest_new", "f")
    evs = {e["kind"]: e for e in bus.drain()}
    # XP = sukces, strata złota = danger, kondycja/durability = warning/danger
    assert evs["xp"]["tone"] == "success"
    assert evs["gold_loss"]["tone"] == "danger"
    assert evs["durability"]["tone"] == "warning"
    assert evs["quest_new"]["tone"] == "info"
    # każda kategoria ma niepustą ikonę
    assert all(e["icon"] for e in evs.values())


def test_explicit_icon_and_tone_override_defaults():
    """Jawne icon/tone nadpisują domyślne z rejestru."""
    bus = se.SystemEventBus()
    bus.emit("xp", "x", icon="🔥", tone="danger")
    ev = bus.drain()[0]
    assert ev["icon"] == "🔥"
    assert ev["tone"] == "danger"


def test_unknown_kind_falls_back_to_info():
    """Nieznany kind nie wywala się — dostaje neutralny ton info + domyślną ikonę."""
    bus = se.SystemEventBus()
    bus.emit("czegos_takiego_nie_ma", "hej")
    ev = bus.drain()[0]
    assert ev["tone"] == "info"
    assert ev["icon"]


def test_dedupe_by_key_collapses_duplicates():
    """Zdarzenia z tym samym dedupe_key w jednej turze łączą się w jedno (ostatnie wygrywa tekstem)."""
    bus = se.SystemEventBus()
    bus.emit("condition_applied", "Zatrucie (1)", dedupe_key="poison")
    bus.emit("condition_applied", "Zatrucie (2)", dedupe_key="poison")
    bus.emit("xp", "+5 XP")  # inny — zostaje
    out = bus.drain()
    poison = [e for e in out if e["kind"] == "condition_applied"]
    assert len(poison) == 1
    assert poison[0]["text"] == "Zatrucie (2)"
    assert len(out) == 2


def test_empty_text_is_ignored():
    """Pusty/whitespace tekst nie tworzy dymka (ochrona przed śmieciem)."""
    bus = se.SystemEventBus()
    bus.emit("xp", "   ")
    bus.emit("xp", "")
    assert bus.drain() == []


# ─── Emisja przez contextvar (serwis bez przewlekania parametru) ─────────────

def test_module_emit_noop_without_active_bus():
    """se.emit() bez aktywnego busa jest no-opem (serwis wywołany poza turą nie wywala się)."""
    # brak aktywnego busa
    se.emit("xp", "nikt nie słucha")  # nie może rzucić


def test_module_emit_routes_to_active_bus():
    """W obrębie use_turn_bus() moduł-level emit trafia do aktywnego busa."""
    with se.use_turn_bus() as bus:
        se.emit("gold_loss", "−14 zł — okradziono cię!")
        # serwis zagnieżdżony też trafia do tego samego busa
        _fake_service_deep_emit()
    out = bus.drain()
    kinds = {e["kind"] for e in out}
    assert "gold_loss" in kinds
    assert "durability" in kinds


def _fake_service_deep_emit():
    """Symuluje serwis emitujący bez wiedzy o busie (import modułu, wywołanie emit)."""
    se.emit("durability", "Miecz uszkodzony (12/20)")


def test_new_turn_bus_sets_active_without_context_manager():
    """new_turn_bus() — dla generatorów SSE, które nie mogą użyć `with`.

    Ustawia świeży bus jako aktywny (nadpisując poprzedni) i zwraca go;
    kolejne se.emit() trafiają do niego."""
    bus = se.new_turn_bus()
    se.emit("xp", "+5 XP")
    assert [e["text"] for e in bus.drain()] == ["+5 XP"]
    # kolejny new_turn_bus nadpisuje — poprzedni już nie łapie
    bus2 = se.new_turn_bus()
    se.emit("xp", "+7 XP")
    assert [e["text"] for e in bus2.drain()] == ["+7 XP"]


def test_use_turn_bus_isolates_between_turns():
    """Dwa kolejne konteksty tury nie przeciekają zdarzeniami."""
    with se.use_turn_bus() as bus1:
        se.emit("xp", "tura 1")
    with se.use_turn_bus() as bus2:
        se.emit("xp", "tura 2")
    assert [e["text"] for e in bus1.drain()] == ["tura 1"]
    assert [e["text"] for e in bus2.drain()] == ["tura 2"]


# ─── Konwerter legacy → system_events (back-compat, unifikacja dymków) ────────

def test_events_from_legacy_granted_items():
    """granted_items → dymek 🎒 sukces."""
    payload = {"granted_items": [{"label": "Mikstura leczenia"}]}
    evs = se.events_from_legacy(payload)
    assert len(evs) == 1
    assert evs[0]["kind"] == "item_granted"
    assert "Mikstura leczenia" in evs[0]["text"]
    assert evs[0]["tone"] == "success"


def test_events_from_legacy_gold_events_sign_drives_tone():
    """gold_events: delta<0 → danger, delta>0 → success."""
    payload = {"gold_events": [
        {"delta": -14, "label": "Okradziono cię"},
        {"delta": 30, "label": "Nagroda"},
    ]}
    evs = se.events_from_legacy(payload)
    tones = [e["tone"] for e in evs]
    assert tones == ["danger", "success"]


def test_events_from_legacy_beats_and_quests():
    """completed_beats + completed_quests → dymki sukcesu z zachowaniem tekstu."""
    payload = {
        "completed_beats": [{"key": "b1", "label": "Znajdź młyn"}],
        "completed_quests": [{"title": "Eskorta", "xp": 40}],
    }
    evs = se.events_from_legacy(payload)
    texts = " ".join(e["text"] for e in evs)
    assert "Znajdź młyn" in texts
    assert "Eskorta" in texts
    assert "40" in texts  # XP questa widoczne
    assert all(e["tone"] == "success" for e in evs)


def test_events_from_legacy_empty_payload():
    """Brak pól legacy → pusta lista (żaden dymek)."""
    assert se.events_from_legacy({}) == []


# ─── Backward compatibility: istniejące pola pozostają nietknięte ────────────

# ─── Integracja: dekorator z turns.py łączy legacy + emit w system_events ─────

def test_turns_decorator_attaches_system_events():
    """_with_system_events: emit w trakcie handlera + pola legacy → result['system_events']."""
    from app.api.turns import _with_system_events

    @_with_system_events
    def fake_handler():
        # serwis zagnieżdżony emituje przez contextvar (bez znajomości busa)
        se.emit("xp", "+25 XP — walka")
        # handler zwraca dict z polem legacy (jak realna tura)
        return {"prose": "...", "granted_items": [{"label": "Miecz"}]}

    result = fake_handler()
    assert "system_events" in result
    kinds = {e["kind"] for e in result["system_events"]}
    assert "xp" in kinds          # z emit()
    assert "item_granted" in kinds  # z konwersji legacy
    # pole legacy nietknięte (back-compat)
    assert result["granted_items"] == [{"label": "Miecz"}]


def test_turns_decorator_no_events_no_field():
    """Brak emitów i brak legacy → pole system_events nie pojawia się (czysto)."""
    from app.api.turns import _with_system_events

    @_with_system_events
    def fake_handler():
        return {"prose": "nic się nie stało"}

    result = fake_handler()
    assert "system_events" not in result


def test_legacy_converter_does_not_mutate_payload():
    """Konwerter tylko czyta — oryginalne pola payloadu zostają (okres przejściowy)."""
    payload = {"granted_items": [{"label": "X"}], "gold_events": [{"delta": 5, "label": "Y"}]}
    before = {k: list(v) for k, v in payload.items()}
    se.events_from_legacy(payload)
    assert payload["granted_items"] == before["granted_items"]
    assert payload["gold_events"] == before["gold_events"]
