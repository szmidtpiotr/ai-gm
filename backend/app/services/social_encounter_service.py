"""PT-D2 #1125 — Encountery społeczne w sub-lokacjach.

Wyrasta z PT10 (#1120): jeden rzut ryzyka 0.20 na ryzykownym local hexie
(`_check_local_encounter`). Przy TRAFIENIU dzielimy pulę 50/50:
  - dolna połowa → walka (dotychczasowa ścieżka combat encounter),
  - górna połowa → zdarzenie SPOŁECZNE (kieszonkowiec, pijak, oszust, plotka,
    naganiacz, kontrola straży) — konsekwencje miękkie (złoto/reputacja/hook).

Rozstrzyganie w locie: standardowa formuła d20 + stat + skill + proficiency vs DC
w tej samej turze; ruch dochodzi do skutku. Eskalacja do walki TYLKO przy
krytycznej porażce (Nat 1).

Kieszonkowiec: strata 10% złota (cap 50 szt.). Gracz NIE dowiaduje się od razu —
opóźniony dymek 💰 po 1-3 turach (mechanizm licznika `pending_gold_notices`
w session_flags; docelowo współdzielony kanał gold_events #1101).

Numbers Policy (startowe, Sandbox-tunable):
  ENCOUNTER_SOCIAL_SPLIT = 0.5   — udział zdarzeń społecznych w puli PT10
  PICKPOCKET_LOSS_PCT    = 0.10  — 10% złota
  PICKPOCKET_LOSS_CAP    = 50    — górny limit straty
  NOTICE_DELAY_MIN/MAX   = 1..3  — opóźnienie dymka (tury)

Rdzeń jest CZYSTY — bez DB, bez I/O. Konsumenci (local_map.local_travel,
turn pipeline) wołają czyste funkcje i mapują wynik na zapis session_flags /
narrację / odjęcie złota.
"""
from __future__ import annotations

import random
from typing import Optional

# ── Numbers Policy (startowe, Sandbox-tunable) ────────────────────────────────
ENCOUNTER_SOCIAL_SPLIT = 0.5
PICKPOCKET_LOSS_PCT = 0.10
PICKPOCKET_LOSS_CAP = 50
NOTICE_DELAY_MIN = 1
NOTICE_DELAY_MAX = 3
PROFICIENCY_RANK_THRESHOLD = 3
PROFICIENCY_BONUS = 2


# ── Pule zdarzeń per subtyp sub-lokacji ───────────────────────────────────────
# Każde zdarzenie: stat/skill do rozstrzygnięcia + DC (locked DC scale) + kind.
#   kind='pickpocket' → strata złota + opóźniony dymek
#   kind='soft'       → miękka konsekwencja (hook/reputacja), bez złota
_EVENT_DEFS: dict[str, dict] = {
    # zaułek / ulica
    "pickpocket": {"stat": "WIS", "skill": "awareness", "dc": 12, "kind": "pickpocket"},
    "drunk_harassment": {"stat": "CHA", "skill": "persuasion", "dc": 12, "kind": "soft"},
    # karczma
    "card_cheat": {"stat": "WIS", "skill": "insight", "dc": 14, "kind": "soft"},
    "quest_rumor": {"stat": "CHA", "skill": "gossip", "dc": 8, "kind": "soft"},
    # targ
    "tout": {"stat": "WIS", "skill": "insight", "dc": 10, "kind": "soft"},
    "guard_check": {"stat": "CHA", "skill": "persuasion", "dc": 12, "kind": "soft"},
}

_SUBTYPE_EVENTS: dict[str, list[str]] = {
    "alley": ["pickpocket", "drunk_harassment"],
    "tavern": ["card_cheat", "quest_rumor"],
    "market": ["tout", "guard_check"],
}

# Słowa-klucze mapujące dowolny opis location_subtype na kanoniczny subtyp.
_SUBTYPE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("karczm", "gospod", "tavern", "zajazd", "oberż"), "tavern"),
    (("targ", "rynek", "market", "bazar", "kram"), "market"),
    (("zauł", "ulic", "alley", "street", "zakątek", "brama"), "alley"),
]


# ── Split 50/50 (wspólna pula z PT10) ─────────────────────────────────────────

def classify_encounter_kind(roll: float) -> str:
    """Podziel trafienie puli PT10 na walkę vs zdarzenie społeczne.

    roll < ENCOUNTER_SOCIAL_SPLIT → 'combat', wpp. → 'social'.
    """
    return "combat" if roll < ENCOUNTER_SOCIAL_SPLIT else "social"


# ── Subtypy ───────────────────────────────────────────────────────────────────

def resolve_subtype(location_subtype: Optional[str]) -> str:
    """Zmapuj game_locations.location_subtype na kanoniczny subtyp zdarzeń.

    Nieznany/None → 'alley' (generyczna ulica — zawsze ma pełną pulę).
    """
    if not location_subtype:
        return "alley"
    text = str(location_subtype).lower()
    for keywords, subtype in _SUBTYPE_KEYWORDS:
        if any(k in text for k in keywords):
            return subtype
    return "alley"


def subtype_event_keys(subtype: str) -> list[str]:
    """Klucze zdarzeń dostępne w danym subtypie (fallback: alley)."""
    return list(_SUBTYPE_EVENTS.get(subtype, _SUBTYPE_EVENTS["alley"]))


def _event_from_catalog_row(row: dict) -> dict:
    """Zmapuj rekord katalogu social (#1130) na strukturę zdarzenia silnika.

    payload katalogu: {stat, skill, dc, resolution_kind, ...} → {key, stat, skill,
    dc, kind}. resolution_kind='pickpocket' → kind='pickpocket', wpp. 'soft'.
    """
    payload = row.get("payload") or {}
    kind = "pickpocket" if payload.get("resolution_kind") == "pickpocket" else "soft"
    return {
        "key": row.get("key"),
        "stat": payload.get("stat"),
        "skill": payload.get("skill"),
        "dc": payload.get("dc"),
        "kind": kind,
        "from_catalog": True,
    }


def pick_social_event(
    subtype: str,
    roll: Optional[float] = None,
    conn=None,
    rng=random,
) -> dict:
    """Wybierz zdarzenie z puli subtypu. Zwraca kopię definicji + 'key'.

    PT-D4d (#1133): gdy podano `conn`, dobór idzie z katalogu `game_config_encounters`
    (`draw_social`) i podbija `times_used`. Pusty katalog / brak conn → fallback do
    hardcode `_EVENT_DEFS` (dotychczasowe zachowanie). roll (0..1) deterministycznie
    wskazuje element w trybie hardcode; None → losowo.
    """
    if conn is not None:
        try:
            from app.services import encounter_catalog_service as cat
            row = cat.draw_social(conn, subtype, rng=rng)
        except Exception:
            row = None
        if row:
            cat.increment_times_used(conn, row.get("key"))
            return _event_from_catalog_row(row)

    keys = subtype_event_keys(subtype)
    if roll is None:
        key = rng.choice(keys)
    else:
        idx = min(int(roll * len(keys)), len(keys) - 1)
        key = keys[idx]
    ev = dict(_EVENT_DEFS[key])
    ev["key"] = key
    return ev


# ── Kieszonkowiec ─────────────────────────────────────────────────────────────

def pickpocket_loss(gold: int) -> int:
    """Strata złota kieszonkowca: 10% zaokrąglone w dół, cap 50, nieujemne."""
    g = max(0, int(gold or 0))
    loss = int(g * PICKPOCKET_LOSS_PCT)
    return min(loss, PICKPOCKET_LOSS_CAP)


# ── Rozstrzyganie w locie (locked formula) ────────────────────────────────────

def resolve_skill_check(
    d20: int, stat_mod: int, skill_rank: int, dc: int
) -> dict:
    """d20 + stat_mod + skill_rank + proficiency vs DC (locked mechanic).

    Nat 20 → auto-sukces; Nat 1 → auto-porażka + JEDYNY przypadek eskalacji
    do walki. Proficiency +2 gdy skill_rank >= 3.
    """
    d20 = int(d20)
    nat20 = d20 == 20
    nat1 = d20 == 1
    prof = PROFICIENCY_BONUS if int(skill_rank) >= PROFICIENCY_RANK_THRESHOLD else 0
    total = d20 + int(stat_mod) + int(skill_rank) + prof

    if nat1:
        success = False
    elif nat20:
        success = True
    else:
        success = total >= int(dc)

    return {
        "success": success,
        "nat1": nat1,
        "nat20": nat20,
        "total": total,
        "escalate_combat": nat1,  # eskalacja WYŁĄCZNIE przy krytycznej porażce
    }


# ── Opóźniony dymek 💰 (gold_events delayed) ─────────────────────────────────

def schedule_gold_notice(
    flags: dict, amount: int, delay_turns: int, label: str = "sakiewka lżejsza"
) -> None:
    """Dopisz opóźnione powiadomienie o stracie złota do session_flags.

    reveal_in = licznik tur do ujawnienia; maleje w pop_due_gold_notices.
    """
    notices = flags.setdefault("pending_gold_notices", [])
    notices.append(
        {
            "amount": int(amount),
            "reveal_in": max(1, int(delay_turns)),
            "label": label,
        }
    )


def pop_due_gold_notices(flags: dict) -> list[dict]:
    """Zmniejsz liczniki i zwróć powiadomienia, które właśnie dojrzały.

    Wywoływane raz na turę. Dojrzałe (reveal_in -> 0) są usuwane z kolejki
    i zwracane do wyrenderowania jako dymek 💰.
    """
    notices = flags.get("pending_gold_notices")
    if not notices:
        return []
    due: list[dict] = []
    remaining: list[dict] = []
    for n in notices:
        n["reveal_in"] = int(n.get("reveal_in", 1)) - 1
        if n["reveal_in"] <= 0:
            due.append({"amount": n["amount"], "label": n.get("label", "sakiewka lżejsza")})
        else:
            remaining.append(n)
    flags["pending_gold_notices"] = remaining
    return due


def random_notice_delay() -> int:
    """Losowe opóźnienie dymka (1-3 tury, startowe)."""
    return random.randint(NOTICE_DELAY_MIN, NOTICE_DELAY_MAX)


# ── Koordynator zdarzenia społecznego ─────────────────────────────────────────

def build_social_outcome(
    event_key: str,
    subtype: str,
    gold: int,
    skill_check: dict,
    flags: dict,
    delay_turns: Optional[int] = None,
    kind: Optional[str] = None,
) -> dict:
    """Złóż konsekwencję zdarzenia społecznego (miękkie, walka to wyjątek).

    Dla kieszonkowca (kind='pickpocket') przy PORAŻCE testu percepcji: policz
    stratę złota i zaplanuj opóźniony dymek. Przy SUKCESIE — brak straty
    (gracz łapie złodzieja za rękę). Zwraca payload dla konsumenta:
      {event_key, kind, gold_loss, escalate_combat, delay_turns}

    PT-D4d (#1133): `kind` można podać jawnie (rekord z katalogu z nowym kluczem
    spoza `_EVENT_DEFS`). None → wyprowadzenie z `_EVENT_DEFS` (stare zachowanie).
    """
    if kind is None:
        kind = _EVENT_DEFS.get(event_key, {}).get("kind", "soft")
    success = bool(skill_check.get("success"))
    escalate = bool(skill_check.get("escalate_combat"))

    gold_loss = 0
    used_delay: Optional[int] = None
    if kind == "pickpocket" and not success:
        gold_loss = pickpocket_loss(gold)
        if gold_loss > 0:
            used_delay = int(delay_turns) if delay_turns is not None else random_notice_delay()
            schedule_gold_notice(flags, gold_loss, used_delay)

    return {
        "event_key": event_key,
        "kind": kind,
        "subtype": subtype,
        "gold_loss": gold_loss,
        "escalate_combat": escalate,
        "delay_turns": used_delay,
    }
