# Figma-to-Code Technical Specification (living)

**Status:** ACTIVE  
**Owner:** Product + Design + Engineering  
**Scope:** przygotowanie do przyszłej implementacji redesignu z Figma

---

## 1) Cel dokumentu

Ten dokument zbiera wszystkie techniczne decyzje i ustalenia potrzebne do wdrażania designu z Figma możliwie 1:1 w kolejnych iteracjach.

---

## 2) Źródła i workflow

- Workflow pracy: `docs/_WORKFLOW_PERPLEXITY_CURSOR.md`
- W tej fazie rola iteracyjna po stronie design/spec pełniona jest przez **Figma** (zamiast Perplexity): Figma przygotowuje kolejne rewizje REV i notatki po odpowiedziach Cursora.
- Model governance: **Cursor = manager nadrzędny**, **Figma = wykonawca designu**. Ostateczne decyzje techniczne i kolejność wdrożeń zatwierdza Cursor.
- Brief fazy: `docs/Phase_8H_Figma_Design_Implementation/00_brief.md`
- Prompty fazy:
  - `01_prompt_figma_readiness_audit.md`
  - `02_prompt_design_contract.md`
  - `03_prompt_rollout_plan.md`

---

## 3) Inventory (uzupełniać sukcesywnie)

### 3.1 Ekrany i flow

| Area | Screen / Flow | Priority | Notes |
|------|----------------|----------|-------|
| Game | Main gameplay loop | MUST | [TODO] |
| Combat | Combat HUD + overlays | MUST | [TODO] |
| Inventory | Inventory + equipment | SHOULD | [TODO] |
| Shop | NPC shop modal / panel | SHOULD | [TODO] |
| Admin | Admin critical panels | LATER | [TODO] |

### 3.2 Komponenty

| Figma component | Code component target | Variant strategy | Status |
|-----------------|-----------------------|------------------|--------|
| [TODO] | [TODO] | [TODO] | pending |

---

## 4) Design Tokens Contract

### 4.1 Minimum token sets

- Colors (semantic + raw scale)
- Typography (font family, size scale, line height, weight)
- Spacing scale
- Radius scale
- Shadow/elevation scale
- Breakpoints (mobile-first)

### 4.2 Rules

- Każdy token musi mieć stabilny identyfikator i changelog.
- Brak hardcoded kolorów/spacings w nowych ekranach.
- Token rename = breaking change, wymaga wpisu w changelogu.

---

## 5) Design Contract (1:1 vs adaptacja)

### 5.1 Pixel strict (docelowo 1:1)

- layout grid i spacing na kluczowych ekranach
- typografia nagłówków i CTA
- stany krytycznych komponentów (normal/hover/active/disabled/error)

### 5.2 Functional equivalent (adaptowalne)

- mikroanimacje nieskrytyczne biznesowo
- drugorzędne dekoracje bez wpływu na flow

---

## 6) Engineering Constraints (uzupełniać)

- Nie naruszać kontraktów backend API.
- Nie zmieniać semantyki eventów gameplay bez osobnej fazy.
- Zachować kompatybilność mobile-first.
- Etapowe wdrożenia i rollback na poziomie fal.

---

## 7) Quality Gates

### 7.1 Przed merge każdej fali

- Visual regression pass (ustalona tolerancja)
- Core flow regression pass (manual + automaty)
- Accessibility smoke (focus order, contrast, keyboard na krytycznych akcjach)
- Performance smoke (czas interakcji krytycznych)

### 7.2 Exit criteria fali

- 0 blocker regressions
- zaakceptowane różnice wizualne udokumentowane
- komplet release notes dla zespołu

---

## 8) Rollout waves (draft)

| Wave | Scope | Goal | Risk | Rollback |
|------|-------|------|------|----------|
| 1 | Core shell + navigation | stabilna rama UI | medium | feature flag / branch rollback |
| 2 | Gameplay + combat | kluczowy flow gracza | high | szybki rollback widoków |
| 3 | Inventory/shop/admin polish | domknięcie UX | medium | selektywny rollback modułów |

---

## 9) Open Decisions

- [ ] Czy docelowy frontend stack pozostaje obecny czy planujemy migrację komponentową?
- [ ] Jakie narzędzie visual regression wybieramy?
- [ ] Czy update Figma wymaga formalnego version tag (v1, v1.1, v2)?
- [ ] Czy tworzymy dedykowany changelog designu?

---

## 10) Change Log

### 2026-04-30
- Utworzono specyfikację bazową pod Figma-first workflow.
- Dodano sekcje inventory, contract, quality gates i rollout waves.

