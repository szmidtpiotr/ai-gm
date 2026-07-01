"""Lore item category classification — mirrors the client-side JS heuristic in game.js."""
import re

_SCROLL_RE = re.compile(r"pergamin|zwój|zwoj|list|pismo|manuskrypt", re.IGNORECASE)
_BOOK_RE   = re.compile(r"księga|ksiega|książka|ksiazka|kodeks|kronika|traktat|tome", re.IGNORECASE)
_KEY_RE    = re.compile(r"klucz", re.IGNORECASE)


def lore_category_key(label: str, item_type: str) -> str:
    """Return category slug for a lore/misc inventory item.

    Categories (in priority order):
      scrolls — pergaminy, zwoje, listy, pisma
      books   — księgi, książki, kodeksy, kroniki, traktaty
      keys    — klucze
      quest   — item_type='quest' with no keyword match
      misc    — everything else
    """
    t = str(item_type or "").strip().lower()
    lab = str(label or "")

    if _SCROLL_RE.search(lab):
        return "scrolls"
    if _BOOK_RE.search(lab):
        return "books"
    if _KEY_RE.search(lab):
        return "keys"
    if t == "quest":
        return "quest"
    return "misc"
