# Kolejka następcza — Phase 9B (po T01–T21)

<!-- QUEUE_STATUS: ACTIVE -->
<!-- LAST_UPDATE: 2026-05-04 -->
<!-- MASTER_DONE: T01–T21 → patrz [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) -->

**Cel:** Jedna lista **ustaleń z audytu** ([`04_decisions_log.md`](04_decisions_log.md), [`06_schema_gaps.md`](06_schema_gaps.md), [`07_extended_design_spec.md`](07_extended_design_spec.md), [`08_open_decisions_checklist.md`](08_open_decisions_checklist.md)), które **nie są** jeszcze domknięte w kodzie — z wyłączeniem rzeczy świadomie odłożonych (np. mapa taktyczna **[S19]**).

**Zasady (2026-05-04):**

1. **Nowy frontend gry (React / Figma / [S16]) — poza zakresem tej kolejki.** Pracujemy na **istniejącym** kliencie HTML/JS i panelu admin (`frontend/`).
2. **[S20] asystent LLM** wdrażamy na **legacy adminie** (zakładki Game design / katalog), zgodnie z dopiskiem w [`07_extended_design_spec.md`](07_extended_design_spec.md) §10–11 (*„chyba że zespół zdecyduje się podpiąć asystenta wcześniej pod legacy admin”*).
3. Po każdym ukończonym ID: odhacz `[x]` w tabeli poniżej, zaktualizuj [`06_schema_gaps.md`](06_schema_gaps.md) oraz **Notatki po implementacji** w [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) §17 (albo osobna podsekcja przy tym pliku).

**Zależności:** kolumna *Zależność* = minimalny numer ID gotowy wcześniej (lub `—`).

---

## 1. Kolejka realizacji (T22+)

| Lp | ID | Gotowe | Zadanie (skrót) | Zależność | Uchwały / ślad w dokach |
|----|-----|:------:|-----------------|-----------|-------------------------|
| 22 | **T22** | [ ] | **[S12]** Migracja `game_config_weapons`: `targeting`, `aoe_radius_m`, `magic_school`; seed; admin CRUD; `import_catalog_snapshot`; walidacja aplikacyjna ([`07` §1](07_extended_design_spec.md)) | — | [S12], `06` broń/czary |
| 23 | **T23** | [ ] | **[S14]** Kolumna `game_config_enemies.skills_json` + zapis/odczyt; użycie w konfrontacjach / przygotowanie pod **[S1b]** ([`07` §5](07_extended_design_spec.md)) | — | [S14], `06` wrogowie |
| 24 | **T24** | [ ] | **[S6]** Runtime turowy: obsługa wybranych typów z `effect_json` — min. `periodic_save`, `block_action` w pętli walki / stanie postaci (obecnie częściowo tylko przy consumables) | T17† | `06` warunki |
| 25 | **T25** | [ ] | **[S13] cleanup:** migracja treści z płaskich `effect_*` wyłącznie do `effect_json`; potem migracja schematu usuwająca legacy kolumny (etapami, z dry-run) | T17, T18 | `06` przedmioty |
| 26 | **T26** | [ ] | **[S7a]** Backup bazy / artefaktu przed `import_catalog_snapshot` / `import_config` + polityka retencji kopii ([`04`](04_decisions_log.md), [`00_brief.md`](00_brief.md)) | T19 | import |
| 27 | **T27** | [ ] | **[S18]** Centralny resolver LLM: jedna ścieżka wyboru providera/modelu/klucza dla narracji, panelu admina i testów; hierarchia Default vs Custom; dokumentacja `env` | — | [S18], `07` §12 |
| 28 | **T28** | [ ] | **[S20]** Asystent konwersacyjny **na legacy adminie**: API (draft rekordu / JSON z opisu) → walidacja → podgląd → zapis; integracja z `game_design.js` i kolejnymi zakładkami katalogu **[S15]** | T27, T17 | [S20], `07` §10 |
| 29 | **T29** | [ ] | **Frontend gracza (legacy):** UI do **wydawania XP na cechy** (endpointy **T21**) + wyświetlanie kosztów z `GET …/xp` | T21 | — |
| 30 | **T30** | [ ] | **[S1b]** Konfrontacje / taktyka NPC: konkretne formuły w kodzie + testy; korzystanie z `skills_json` wroga po **T23** (lub częściowy zakres wcześniej) | T23† | `08` §2, `06` |
| 31 | **T31** | [ ] | **AC / pancerze (MVP):** jawna reguła sumowania `ac_bonus` przy wielu źródłach ([`07` §4](07_extended_design_spec.md)) — implementacja + test | — | [S2] |
| 32 | **T32** | [ ] | **W2** Tabela `campaign_story_beats` + migracja — **tylko jeśli** W1 (`gm_plan_json`) przestaje wystarczać; najpierw ADR / kryterium wejścia ([`ADR_T14_W2_story_beats_deferred.md`](ADR_T14_W2_story_beats_deferred.md)) | T06, T07 | [S11b] |

† *Zależność miękka:* można rozpocząć prototyp równolegle, ale „DONE” dopiero po domknięciu wskazanego ID.

---

## 2. Świadomie poza tą kolejką (nie „do domknięcia teraz”)

| Temat | Powód |
|-------|--------|
| **[S19]** Mapa bitwy / solver AOE / tokeny | MVP bez mapy — [`07` §1.1](07_extended_design_spec.md); osobna przyszła uchwała. |
| **Nowy klient gry React + Figma [S16]** | Odłożony — praca na starym froncie do domknięcia backendu i legacy admina. |
| **Profil konta gracza + własny endpoint LLM w prod [S17]** | Backlog produktowy po epiku konta — nie blokuje powyższej kolejki backendowej. |

---

## 3. Backlog pomocniczy (po żądaniu — poza T22–T32)

| ID | Opis |
|----|------|
| **B03** | Dalsza konsolidacja **`game_config_consumables`** / FK `consumable_key` vs wyłącznie `game_config_items` — jeśli macie jeszcze stare środowiska z legacy danymi. |
| **B04** | Grant XP / mechanika MG dla użytkownika **nie będącego ownerem** kampanii (`campaign_members` / rola `gm`) — [`07` §8]. |
| **B05** | Widok „wszystkie rekordy bez filtra” w adminie — z **[S15]** wynika, że **nie** jest potrzebny; tylko jeśli zmienicie decyzję. |

---

## 4. Mapowanie: ID → glówny dokument źródłowy

| ID | Gdzie dyskusja / uzasadnienie |
|----|-------------------------------|
| T22 | `06` wiersz broń/czary; `07` §1; `08` [S12] accepted |
| T23 | `06` wrogowie; `07` §5; `08` [S14] |
| T24 | `06` warunki — typy efektów; `04` [S6] |
| T25 | `06` przedmioty dual JSON; `04` [S13] |
| T26 | `00_brief`, `04` [S7a] |
| T27 | `07` §12; `08` [S18] |
| T28 | `07` §10–11; `08` [S20]; **legacy UI** |
| T29 | Konsekwencja **T21** dla gracza (API już jest) |
| T30 | `08` §2 [S1b]; `06` |
| T31 | `07` §4 |
| T32 | `ADR_T14`; `06` W2 |

---

## 5. Sugerowana kolejność pracy (orientacyjna)

1. **T22** — odblokowuje spójny katalog czarów/AOE w DB i imporcie (reszta mechaniki nadal bez mapy — **[S19]**).
2. **T23** + **T30** — silnik konfrontacji zależy od skilli wroga.
3. **T24** — najbardziej „systemowe”; często po stablinym effekcie JSON.
4. **T25** — porządek danych przed długim utrzymaniem.
5. **T26** — bezpieczeństwo operacyjne przy importach na prod.
6. **T27** → **T28** — resolver przed asystentem admina wołającym LLM.
7. **T29** — UX gracza na istniejącym froncie.
8. **T31** — jeśli walka już liczy AC z kilku źródeł — wtedy pilne; inaczej można wcześniej.
9. **T32** — tylko po decyzji produktowej vs ADR.

---

## 6. Historia zmian tego pliku

| Data | Zmiana |
|------|--------|
| 2026-05-04 | Utworzenie kolejki T22–T32 + backlog B03–B05; zakres bez nowego frontu gry; [S20] na legacy adminie. |
