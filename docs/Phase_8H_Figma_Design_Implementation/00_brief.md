<!-- STATUS: ACTIVE -->
<!-- PHASE: 8H | DATE_START: 2026-04-30 | DATE_END: - -->

# Phase 8H — Figma-First Design-to-Implementation · Brief

---

## 1. Cel fazy

Przygotowanie procesu i artefaktów do przyszłego wdrożenia redesignu z Figma 1:1, bez natychmiastowego przepisywania frontendu.  
Ta faza ma zebrać wymagania, kontrakty i techniczną specyfikację migracji UI tak, żeby kolejne etapy implementacji były przewidywalne.

**Definicja ukończenia (DoD):**
- [ ] Istnieje komplet dokumentów procesu Figma -> kod (brief + prompty + spec techniczna)
- [ ] Mamy listę ekranów/flow i priorytetów migracji (mobile-first)
- [ ] Mamy zestaw zasad design systemu i mapowanie komponentów Figma -> kod
- [ ] Mamy checklistę jakości dla wdrożeń 1:1 (visual + funkcjonalna)
- [ ] Mamy plan rolloutu etapowego bez zatrzymania produktu

---

## 2. Zakres

| # | Komponent | Opis | Priorytet |
|---|---|---|---|
| 1 | Proces współpracy Figma+Cursor | Stały workflow REV1/REV2 pod design i implementację | 🔴 Must |
| 2 | Specyfikacja techniczna Figma-to-Code | Kontrakty, tokeny, mapowanie komponentów, QA | 🔴 Must |
| 3 | Plan etapowego rolloutu UI | Kolejność ekranów i kryteria gotowości | 🔴 Must |
| 4 | Rejestr decyzji (living document) | Miejsce do dopisywania ustaleń przy kolejnych iteracjach | 🟡 Should |

**Out of scope:**
- bezpośrednia implementacja kodu frontendu w tej fazie
- migracja backendu lub API
- wdrożenie redesignu na PROD

---

## 3. Zależności

| Zależność | Status | Gdzie |
|---|---|---|
| Obecny workflow dokumentacyjny | ✅ DONE | `docs/_WORKFLOW_PERPLEXITY_CURSOR.md` |
| Szablon briefów faz | ✅ DONE | `docs/_PHASE_BRIEF_TEMPLATE.md` |
| Szablon promptów | ✅ DONE | `docs/_UNIVERSAL_CURSOR_PROMPT_TEMPLATE.md` |
| Istniejące fazy frontend/combat/economy | ✅ DONE | `docs/Phase_ DONE/*` oraz aktywne `docs/Phase_*` |
| Projekt Figma (Make) | ⏳ PENDING do pełnego rozpisania | URL użytkownika + przyszłe iteracje |

---

## 4. Reguły biznesowe / design decisions

- **Model odpowiedzialności (dla tej fazy 8H):**
  - **Cursor** = manager nadrzędny procesu (plan, decyzje techniczne, priorytety, kryteria jakości, raporty).
  - **Figma** = wykonawca designu/spec po stronie projektowej (rewizje layoutu, aktualizacje artefaktów designu).
- Figma jest źródłem docelowego wyglądu UI, ale implementacja zachowuje istniejące kontrakty API i logikę gry.
- Najpierw stabilizacja procesu, dopiero potem przepisywanie widoków.
- Każdy etap migracji UI musi mieć kryteria:
  - zgodność wizualna,
  - zgodność interakcji,
  - brak regresji funkcjonalnej.
- Wdrożenia mają być etapowe (screen-by-screen), bez big-bang rewrite.

---

## 5. Architektura dokumentacyjna fazy

### Nowe pliki
```
docs/Phase_8H_Figma_Design_Implementation/00_brief.md
docs/Phase_8H_Figma_Design_Implementation/01_prompt_figma_readiness_audit.md
docs/Phase_8H_Figma_Design_Implementation/02_prompt_design_contract.md
docs/Phase_8H_Figma_Design_Implementation/03_prompt_rollout_plan.md
docs/Phase_8H_Figma_Design_Implementation/04_technical_spec_figma_to_code.md
```

### Modyfikowane pliki
```
brak (ta faza tworzy nowy pakiet dokumentacji)
```

### NIE ruszamy
```
backend/*
frontend/*
docker-compose*.yml
data/ai_gm.db
```

---

## 6. Kontrakty i artefakty wejściowe

```
Artefakt A: Figma source of truth (frames/components/tokens)
Artefakt B: Screen inventory + flow map (must-have / should-have)
Artefakt C: Component mapping table (Figma -> code)
Artefakt D: Quality gates (visual regression, functional checks, accessibility baseline)
Artefakt E: Rollout schedule (phases/waves, fallback plan)
```

---

## 7. UI/UX (kierunek docelowy)

- Mobile-first redesign jako główny kierunek.
- Ujednolicenie layoutu gry (chat, akcje, panele, sklep, combat UI).
- Zachowanie czytelności i niskiego tarcia dla flow gracza:
  - input narracyjny,
  - informacje o stanie postaci,
  - widoki kontekstowe (loot/shop/combat).

---

## 8. Testy i walidacja procesu (dla kolejnych faz implementacyjnych)

```python
def test_visual_baseline_screen_matches_figma_tolerance()
def test_core_game_flow_not_broken_after_ui_update()
def test_shop_modal_flow_after_redesign()
def test_combat_overlay_flow_after_redesign()
def test_mobile_breakpoints_core_views()
```

---

## 9. Weryfikacja manualna (dokumentacyjna)

```bash
# 1) Zweryfikuj komplet dokumentów fazy 8H
ls -la docs/Phase_8H_Figma_Design_Implementation

# 2) Zweryfikuj spójność workflow
cat docs/_WORKFLOW_PERPLEXITY_CURSOR.md
cat docs/_PHASE_BRIEF_TEMPLATE.md
cat docs/_UNIVERSAL_CURSOR_PROMPT_TEMPLATE.md
```

---

## 10. Podsumowanie wdrożenia (Cursor)

- Co zrobiono:
- Co nie weszło:
- Odchylenia:
- Kolejne kroki:

## 11. Analiza po fazie (Figma)

- Zgodność z briefem:
- Ryzyka:
- Proponowany start implementacji:

