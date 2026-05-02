<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-30 -->

# PROMPT 1 — Figma readiness audit (bez implementacji)

> Workflow (8H): Cursor prowadzi proces jako manager nadrzędny. Figma pełni rolę wykonawczą po stronie designu.
> Przepływ: Cursor odpowiada na pytania blokujące (NIE implementuje) -> Figma przygotowuje rewizję design/spec (REV 2) -> Cursor zatwierdza i realizuje kolejne kroki dokumentacyjne.

---

## Cel

Sprawdzić gotowość projektu do przyszłego wdrażania layoutu z Figma 1:1:
- jakie mamy ograniczenia obecnego stacka,
- co jest już gotowe,
- czego brakuje w warstwie design system / komponenty / QA.

---

## Kontekst techniczny

- Źródła workflow:
  - `docs/_WORKFLOW_PERPLEXITY_CURSOR.md`
  - `docs/_PHASE_BRIEF_TEMPLATE.md`
  - `docs/_UNIVERSAL_CURSOR_PROMPT_TEMPLATE.md`
- Obszar docelowy: frontend gry (chat/gameplay/admin).
- Obecny cel: tylko dokumentacja i analiza, bez modyfikacji kodu produktu.

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

1. Jaki jest aktualny stack frontendowy i ograniczenia (moduły, style, bundling)?
2. Jakie widoki są krytyczne funkcjonalnie i nie mogą stracić zgodności przy redesignie?
3. Czy istnieją już tokeny designu lub centralna warstwa stylów?
4. Jakie są najczęstsze regresje po zmianach UI w tym repo?
5. Czy mamy istniejącą infrastrukturę screenshot/visual testów?
6. Które ekrany mają najwyższy priorytet migracji w kolejności business value?

---

## Implementacja (REV 1 — do zatwierdzenia)

Po odpowiedzi Cursora Figma przygotowuje REV 2 zawierające:
- checklistę gotowości Figma-to-code,
- listę braków i ryzyk,
- pierwszą wersję „Definition of Ready” dla ekranu przed wdrożeniem.

---

## Odpowiedzi Cursora (REV 1)

*(Cursor uzupełnia)*

---

## Co zostało zrobione *(uzupełnia Cursor)*

*(Cursor uzupełnia po REV 2)*

---

## Notatki po implementacji *(uzupełnia Figma)*

*(Figma uzupełnia po raporcie Cursora)*

