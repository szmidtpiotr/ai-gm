# ADR: T14 — W2 (`campaign_story_beats`) odroczone (W1 wystarcza na MVP)

**Status:** zaakceptowane (2026-05-04)  
**Kontekst:** [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) §15 (**T14**); **[S11b]** w [`04_decisions_log.md`](04_decisions_log.md) — warianty **W1** (jeden JSON na kampanii) vs **W2** (osobna tabela beatów).

---

## Problem

T14 przewiduje **ADR + migrację SQL** dla **`campaign_story_beats`** wyłącznie wtedy, gdy **W1** (`campaigns.gm_plan_json`) jest **niewystarczający** (rozmiar, złożoność, locking). W masterze jest **blokada:** nie wdrażać W2 bez **pisemnej** decyzji „W1 insufficient because …”.

---

## Decyzja

**Na dzień 2026-05-04 W1 jest uznane za wystarczające** dla zakresu MVP i istniejącej implementacji (**T06**):

- Plan MG żyje w **`gm_plan_json`** z normalizacją / merge (**`gm_plan_schema`**), PATCH planu, **`advance-scene`**, pola typu roadmap / cele sceny / log odcinków — zgodnie ze specyfikacją ([`07_extended_design_spec.md`](07_extended_design_spec.md) §7).
- **Kolejne łuki „z wyprzedzeniem”** można utrzymywać w strukturze JSON (np. szkice przyszłych etapów niewidoczne dla API gracza) bez osobnej tabeli — zgodnie z opcją **W1** w uchwale **[S11b]**.
- **Nie zidentyfikowano** w produkcie deweloperskiej twardego wymogu **row-level locking** beatów ani rozmiaru JSON wykraczającego poza sensowne użycie SQLite `TEXT` w MVP.

**Tabela `campaign_story_beats` (W2) nie jest wprowadzana** w ramach domykania T14.

---

## Kiedy ponownie rozważyć W2

Nowy ADR + implementacja W2, jeśli pojawi się **co najmniej jeden** z uzasadnień, np.:

1. **Rozmiar / utrzymanie:** `gm_plan_json` rutynowo przekracza praktyczny limit edycji lub powoduje regresje merge.
2. **Produkt / workflow:** potrzeba jawnych statusów beatów (`planned` | `active` | `resolved`) z osobnymi uprawnieniami lub UI bez dotykania całego JSON-a.
3. **Silnik fabularny:** strukturalne questy wymagają relacji FK beat → nagrody XP / NPC — a JSON przestaje być wygodnym źródłem prawdy.

---

## Konsekwencje

- Brak nowej migracji SQLite dla **`campaign_story_beats`** w tej iteracji.
- Dokumentacja i [`06_schema_gaps.md`](06_schema_gaps.md): jawna notka „W2 świadomie odłożone”.
- **T14** zamykany jako **decyzja zapisana**, nie jako migracja.

---

## Powiązania

- **[S11b]** — opcje W1 / W2 / W3: [`04_decisions_log.md`](04_decisions_log.md).
- Implementacja W1: **T06** (master §6).
