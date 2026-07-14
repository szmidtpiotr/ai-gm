"""Issue #1379 — ujednolicony strumień komunikatów systemowych (`system_events`).

Jedno pole w odpowiedzi tury niesie WSZYSTKIE zdarzenia poza narracją (XP,
utrata złota, kondycje, durability, noc/pogoda, nowy quest…), renderowane tym
samym środkowym dymkiem co dotąd `granted_items` / `gold_events`.

Trzy elementy:
  1. `SystemEventBus` — akumuluje zdarzenia w obrębie jednej tury; `drain()`
     dedupe'uje po `dedupe_key` i czyści bufor.
  2. contextvar `_current_bus` + `emit()` / `use_turn_bus()` — pozwala dowolnie
     zagnieżdżonemu serwisowi emitować bez przewlekania busa przez sygnatury.
     Poza aktywną turą `emit()` jest no-opem (serwis wywołany w teście/skrypcie
     się nie wywala).
  3. `events_from_legacy()` — konwertuje istniejące pola odpowiedzi tury na
     jednolity kształt, żeby stare dymki weszły do tego samego strumienia
     (back-compat na okres przejściowy; nie mutuje payloadu).

Kształt zdarzenia (dict, bo odpowiedź tury to luźny dict — patrz turns.py):
    {"kind": str, "icon": str, "tone": str, "text": str, "dedupe_key": str|None}

`tone` ∈ {"success", "info", "warning", "danger"} — front mapuje na kolor
obramowania dymka (paleta z toast.tsx). `kind` jest maszynowy (front używa do
filtrowania/grupowania, NIE do stylu).
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Iterator

# Dozwolone tony (kolor obramowania dymka na froncie).
VALID_TONES = ("success", "info", "warning", "danger")

# Domyślna ikona + ton per kategoria. Serwis podaje sam `kind` + `text`;
# ikonę/ton bierzemy stąd (można nadpisać jawnie w emit()).
KIND_DEFAULTS: dict[str, tuple[str, str]] = {
    # postęp bohatera
    "xp": ("✨", "success"),
    "level_up": ("⬆️", "success"),
    "arcane_point": ("🔮", "success"),
    "spell_learned": ("🔮", "success"),
    # ekwipunek / złoto
    "item_granted": ("🎒", "success"),
    "item_consumed": ("🎒", "info"),
    "gold_gain": ("💰", "success"),
    "gold_loss": ("💰", "danger"),
    "durability": ("⚒️", "warning"),
    "item_broken": ("💔", "danger"),
    "ammo": ("🏹", "warning"),
    "set_bonus": ("🛡️", "success"),
    "recipe_learned": ("📜", "success"),
    # stan bohatera
    "condition_applied": ("☠️", "danger"),
    "condition_removed": ("✨", "success"),
    "fatigue": ("😮‍💨", "warning"),
    "hp_loss": ("🩸", "danger"),
    "rest": ("🏕️", "success"),
    "death_save": ("💀", "danger"),
    # świat / czas
    "night": ("🌙", "info"),
    "dawn": ("☀️", "info"),
    "weather": ("🌧️", "info"),
    "hex_discovered": ("🗺️", "info"),
    "rumor": ("💬", "info"),
    # fabuła / questy
    "beat_complete": ("✓", "success"),
    "quest_complete": ("✓", "success"),
    "quest_new": ("📖", "info"),
    "quest_failed": ("📖", "warning"),
    "chapter": ("📜", "info"),
    "bestiary": ("📗", "info"),
    # blokady / ograniczenia
    "cooldown": ("⏳", "warning"),
    "reputation": ("⚖️", "info"),
    # multiplayer
    "party": ("👥", "info"),
    "absence": ("⚠️", "warning"),
}

# Fallback dla nieznanego kind — neutralny, nie wywala się.
_FALLBACK = ("ℹ️", "info")


def _build_event(
    kind: str,
    text: str,
    *,
    icon: str | None = None,
    tone: str | None = None,
    dedupe_key: str | None = None,
) -> dict[str, Any] | None:
    """Buduje jedno zdarzenie; None gdy tekst pusty (odfiltrowywane wyżej)."""
    text = (text or "").strip()
    if not text:
        return None
    d_icon, d_tone = KIND_DEFAULTS.get(kind, _FALLBACK)
    ev_tone = tone if tone in VALID_TONES else d_tone
    return {
        "kind": kind,
        "icon": icon or d_icon,
        "tone": ev_tone,
        "text": text,
        "dedupe_key": dedupe_key,
    }


class SystemEventBus:
    """Akumuluje zdarzenia w obrębie jednej tury."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def emit(
        self,
        kind: str,
        text: str,
        *,
        icon: str | None = None,
        tone: str | None = None,
        dedupe_key: str | None = None,
    ) -> None:
        ev = _build_event(kind, text, icon=icon, tone=tone, dedupe_key=dedupe_key)
        if ev is not None:
            self._events.append(ev)

    def drain(self) -> list[dict[str, Any]]:
        """Zwraca zdedupe'owaną listę zdarzeń i czyści bufor.

        Dedupe: zdarzenia z tym samym (nie-None) `dedupe_key` łączą się w jedno —
        ostatnie wygrywa tekstem, zachowując pierwotną pozycję.
        """
        out: list[dict[str, Any]] = []
        pos_by_key: dict[str, int] = {}
        for ev in self._events:
            key = ev.get("dedupe_key")
            if key is not None and key in pos_by_key:
                out[pos_by_key[key]] = ev  # ostatni wygrywa, pozycja pierwszego
            else:
                if key is not None:
                    pos_by_key[key] = len(out)
                out.append(ev)
        self._events = []
        return out


# ── Emisja przez contextvar — serwis emituje bez znajomości busa ─────────────

_current_bus: contextvars.ContextVar[SystemEventBus | None] = contextvars.ContextVar(
    "system_events_current_bus", default=None
)


def emit(
    kind: str,
    text: str,
    *,
    icon: str | None = None,
    tone: str | None = None,
    dedupe_key: str | None = None,
) -> None:
    """Moduł-level emit: dokłada zdarzenie do aktywnego busa tury.

    No-op gdy brak aktywnego busa (serwis wywołany poza turą — test/skrypt/CLI).
    """
    bus = _current_bus.get()
    if bus is not None:
        bus.emit(kind, text, icon=icon, tone=tone, dedupe_key=dedupe_key)


@contextlib.contextmanager
def use_turn_bus() -> Iterator[SystemEventBus]:
    """Ustawia bus jako aktywny dla contextvar na czas trwania tury.

    Użycie w turns.py:
        with use_turn_bus() as bus:
            ... cały handler tury (serwisy wołają se.emit(...)) ...
            payload["system_events"] = events_from_legacy(payload) + bus.drain()
    """
    bus = SystemEventBus()
    token = _current_bus.set(bus)
    try:
        yield bus
    finally:
        _current_bus.reset(token)


def new_turn_bus() -> SystemEventBus:
    """Ustawia świeży bus jako aktywny i zwraca go — bez `with`.

    Dla streamowych generatorów SSE (turns.py `token_generator`), które nie mogą
    owinąć całego ciała w context manager. Nie wymaga jawnego resetu: każdy request
    działa we własnym kontekście, a kolejny `new_turn_bus()` nadpisuje poprzedni.
    """
    bus = SystemEventBus()
    _current_bus.set(bus)
    return bus


def current_bus() -> SystemEventBus | None:
    """Aktywny bus tury (lub None poza turą)."""
    return _current_bus.get()


# ── Konwerter legacy → jednolity strumień (back-compat) ──────────────────────

def events_from_legacy(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Czyta istniejące pola odpowiedzi tury i zwraca je jako system_events.

    Nie mutuje payloadu (pola legacy zostają — front czyta oba w okresie
    przejściowym). Odtwarza teksty/ikony/tony obecnych zielonych dymków:
      - completed_beats   → "✓ Cel wykonany: …"
      - completed_quests  → "✓ Quest: … [— +N XP]"
      - granted_items     → "🎒 Otrzymano: …"
      - gold_events       → "±N zł — …" (znak delty steruje tonem)
    """
    out: list[dict[str, Any]] = []

    for b in payload.get("completed_beats") or []:
        label = b.get("label") or b.get("key") or ""
        ev = _build_event("beat_complete", f"Cel wykonany: {label}")
        if ev:
            out.append(ev)

    for q in payload.get("completed_quests") or []:
        title = q.get("title") or ""
        xp = q.get("xp")
        text = f"Quest: {title} — +{xp} XP" if xp else f"Quest: {title}"
        ev = _build_event("quest_complete", text)
        if ev:
            out.append(ev)

    for it in payload.get("granted_items") or []:
        label = it.get("label") or ""
        ev = _build_event("item_granted", f"Otrzymano: {label}")
        if ev:
            out.append(ev)

    for g in payload.get("gold_events") or []:
        delta = int(g.get("delta") or 0)
        label = g.get("label") or ""
        sign = "+" if delta >= 0 else "−"
        text = f"{sign}{abs(delta)} zł — {label}" if label else f"{sign}{abs(delta)} zł"
        kind = "gold_gain" if delta >= 0 else "gold_loss"
        ev = _build_event(kind, text)
        if ev:
            out.append(ev)

    return out
