"""#1420 — normalizacja tekstu GRACZA do dopasowań intencji.

Polacy na mobilnych CZĘSTO piszą bez polskich znaków ("przeplywam" zamiast
"przepływam", "ide" zamiast "idę"). Każdy DETERMINISTYCZNY matcher tekstu gracza
(intent-regex, keyword-skan) musi normalizować diakrytyki, inaczej pudłuje na wejściu
ASCII i funkcja „nie działa".

Kanonicznie używamy `str.maketrans` — obsługuje `ł`/`Ł`, których `unicodedata.NFD`
NIE rozkłada (ł to osobny codepoint, nie litera + znak łączący).

Wzorce pisz w ASCII i porównuj z `strip_pl_diacritics(user_text)`; wtedy łapiesz
OBA warianty (z ogonkami i bez).
"""

# ł/Ł nie mają rozkładu NFD — mapujemy jawnie razem z resztą polskich diakrytyków.
_PL_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def strip_pl_diacritics(s: str | None) -> str:
    """Zamień polskie diakrytyki na ASCII (ł→l, ę→e, ą→a, …), resztę zostaw bez zmian.

    Zachowuje spacje, wielkość liter i interpunkcję — nadaje się pod regexy z ``\\s+``.
    """
    return (s or "").translate(_PL_MAP)


def fold(s: str | None) -> str:
    """Normalizacja pod porównania keyword-owe: bez diakrytyków + lowercase."""
    return strip_pl_diacritics(s).lower()
