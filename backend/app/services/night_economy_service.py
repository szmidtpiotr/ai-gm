"""#1127 (PT14) — Night economy for settlements.

The campaign clock (session_flags.ingame_hours) already tells time. This module
turns that into shop behaviour:

  * normal shops/services close during the 21:00–05:00 window ("zamknięte, wróć rano"),
  * the tavern (karczma) stays open around the clock,
  * the black-market fence (paser) trades ONLY at night, with worse prices
    (buy ×1.3, sell ×0.6).

Shop kind is inferred from the NPC's key/label/type keywords — no schema change,
same pattern as shop_service._HEALER_KEYWORDS. All numbers are STARTING values,
Sandbox-tunable (Numbers Policy).
"""

from __future__ import annotations

# ── Numbers Policy (STARTING values, Sandbox-tunable) ────────────────────────
NIGHT_CLOSE_START = 21   # shops close at 21:00
NIGHT_CLOSE_END = 5      # shops reopen at 05:00
BLACK_MARKET_BUY_MULT = 1.3   # fence charges more
BLACK_MARKET_SELL_MULT = 0.6  # fence pays less

# Player-facing refusal messages (also serve as the narrator fact).
SHOP_CLOSED_MSG = "Zamknięte na noc — wróć rano (otwarte 5:00–21:00)."
BLACK_MARKET_DAY_MSG = "Paser handluje tylko po zmroku. Wróć nocą."

_TAVERN_KEYWORDS = (
    "karczma", "karczmarz", "gospoda", "oberża", "oberza", "zajazd",
    "szynk", "tawerna", "tavern", "innkeeper",
)
_BLACK_MARKET_KEYWORDS = (
    "paser", "czarny rynek", "czarnorynk", "przemytnik", "szmugler",
    "fence", "smuggler", "black market", "blackmarket",
)


def is_night_closed_hour(hour: int) -> bool:
    """True when the hour falls in the 21:00–05:00 closing window."""
    h = int(hour) % 24
    return h >= NIGHT_CLOSE_START or h < NIGHT_CLOSE_END


def classify_shop(key: str = "", label: str = "", npc_type: str = "") -> str:
    """Return 'black_market' | 'tavern' | 'normal' from NPC keyword hints."""
    hay = " ".join(str(x or "").lower() for x in (key, label, npc_type))
    if any(w in hay for w in _BLACK_MARKET_KEYWORDS):
        return "black_market"
    if any(w in hay for w in _TAVERN_KEYWORDS):
        return "tavern"
    return "normal"


def shop_open_state(shop_kind: str, hour: int | None) -> dict:
    """Whether a shop of the given kind trades at the given hour.

    `hour is None` (clock unknown, e.g. hero with no campaign) never blocks —
    keeps non-campaign callers working exactly as before.

    Returns: {open: bool, is_black_market: bool, reason: str|None, message: str|None}
    """
    is_bm = shop_kind == "black_market"
    if hour is None:
        return {"open": True, "is_black_market": is_bm, "reason": None, "message": None}

    closed_hour = is_night_closed_hour(hour)

    if shop_kind == "tavern":
        return {"open": True, "is_black_market": False, "reason": None, "message": None}

    if shop_kind == "black_market":
        if closed_hour:
            return {"open": True, "is_black_market": True, "reason": None, "message": None}
        return {
            "open": False, "is_black_market": True,
            "reason": "black_market_day", "message": BLACK_MARKET_DAY_MSG,
        }

    # normal shop / service
    if closed_hour:
        return {
            "open": False, "is_black_market": False,
            "reason": "shop_closed_night", "message": SHOP_CLOSED_MSG,
        }
    return {"open": True, "is_black_market": False, "reason": None, "message": None}
