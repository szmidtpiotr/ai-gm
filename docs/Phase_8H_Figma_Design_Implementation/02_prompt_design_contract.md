<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-30 -->

# PROMPT 2 — Design contract (Figma -> Code)

> Workflow: REV 1 pytania -> odpowiedzi Cursora -> REV 2 dokumentowanie kontraktów implementacyjnych.

---

## Cel

Zdefiniować kontrakt między designem Figma a implementacją:
- co ma być 1:1,
- co może być adaptowane,
- jakie są twarde reguły mapowania komponentów i tokenów.

---

## Kontekst

Ten prompt buduje „umowę” między design i engineering, aby kolejne update'y z Figma były przewidywalne.
W tej fazie Cursor jest właścicielem decyzji końcowych, a Figma przygotowuje wykonawcze rewizje design/spec.

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

1. Które elementy UI są „pixel strict” (muszą być 1:1), a które „functional equivalent”?
2. Jak mapujemy komponenty Figma na komponenty kodowe (nazwa, props, variants)?
3. Jakie tokeny są wymagane minimum: color/typography/spacing/radius/shadow?
4. Jakie breakpointy i zasady mobile-first przyjmujemy jako obowiązkowe?
5. Jaki próg akceptacji visual diff ustalamy (np. tolerance)?
6. Jak dokumentujemy breaking changes po stronie designu?

---

## Implementacja (REV 1 — do zatwierdzenia)

Po odpowiedziach Cursora Figma przygotowuje REV 2:
- tabelę kontraktów Figma->Code,
- listę Design Invariants,
- listę Engineering Constraints,
- szablon changelogu designu pod kolejne update'y.

---

## Odpowiedzi Cursora (REV 1)

*(Cursor uzupełnia)*

---

## Co zostało zrobione *(uzupełnia Cursor)*

*(Cursor uzupełnia po REV 2)*

---

## Notatki po implementacji *(uzupełnia Figma)*

*(Figma uzupełnia po raporcie Cursora)*

