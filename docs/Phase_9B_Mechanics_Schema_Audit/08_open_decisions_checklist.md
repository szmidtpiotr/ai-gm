# Niedomknięte ustalenia — lista robocza do domknięcia

**Cel:** jeden widok na to, co w [`04_decisions_log.md`](04_decisions_log.md) jest nadal **proposed**, **częściowo** zamknięte lub **open** jako proces — żeby kolejne spotkania nie szukały luk „po pamięci”.

**Zasada:** po zamknięciu pozycji zaktualizuj status w `04_decisions_log.md` i skreśl lub przenieś wiersz tutaj (albo dopisz datę „domknięto YYYY-MM-DD”).

**Odłożone na koniec (2026-05-01):** Nowy front + Figma — nauka wg [`09_figma_to_code_workflow.md`](09_figma_to_code_workflow.md); start kodu **po** zrozumieniu workflow; uchwała **[S16]** bez zmian merytorycznych — dopisek operacyjny w `04`.

### Domknięte w tej rundzie

| ID | Skrót | Ustalenie |
|----|--------|-----------|
| **[S15]** | Zakładki vs SQL | **accepted** 2026-05-01 — jedna tabela jeśli wystarcza; bez osobnej tabeli czarów; zakładki raczej stałe, łatwo dodawać kolejne w UI; **spójna** edycja / sort / szukanie na zakładkach; brak widoku „cała tabela bez filtra”. |
| **[S12]** | Magia / AOE | **accepted** 2026-05-01 — jedna tabela `game_config_weapons`, zakładka „Czary” osobno w UI; MVP: `single` + `aoe_radius` (kula); szkoła = etykieta; taktyka/mapą później. |
| **[S19]** | Mapa / taktyka | **accepted** 2026-05-01 — MVP: **brak** mapy w silniku; zasięgi = kotwica narracji; trafienia obszarowe narracyjnie; mapa/siatka = osobna późniejsza uchwała. |
| **[S13]** | `effect_json` v0 | **accepted** 2026-05-01 — jeden format items+conditions; walidacja przy zapisie i imporcie; LLM → propozycja JSON z opisu; krótka lista typów, rozszerzalna; bez migracji starych `effect_*`, czysty start + wzorce. |
| **[S20]** | Asystent LLM w adminie | **accepted** 2026-05-01 — **generator konwersacyjny** dla całego **Game design** + ten sam wzorzec dla zakładek katalogu **[S15]**; rozmowa → draft JSON/rekord → walidacja → akceptacja; **[S18]** resolver; **[S16]** wspólne komponenty. |
| **[S14]** | Wrogowie | **accepted** 2026-05-01 — jedna `game_config_enemies`; struktura jak PC, pola sparse; MVP walki OK; **`skills_json`** pod konfrontacje; generator **[S20]**; **[S5b]** superseded. |
| **[S17]** | Azure / OpenAI-compatible | **accepted** 2026-05-01 — dev: wspólny endpoint; prod: własny endpoint gracza **po** profilu konta (backlog); klucz: zapis po stronie serwera, maska, zmiana przy rotacji — bez ciągłego przepisywania. |
| **[S18]** | Centralny LLM | **accepted** 2026-05-01 — **Default** (serwer/admin) vs **Custom** (wygrywa nad defaultem); testy/CI na mocku / env testowym; hierarchia bez per-kampania na ten moment. |
| **[S16]** | Front / Figma | **accepted** 2026-05-01 — 1:1 z Figmą; **React** (typowo) przy starcie; admin legacy OK; **pierwsza gra**; API zamrażalne; **nie** czekać na całe **[IMPL]**; repo TBD. |

---

## 1. Uchwały ze statusem **proposed** (wiążące dla projektu rozszerzonego)

*(Brak pozycji z Phase 9B extended — patrz `04_decisions_log.md` dla ewentualnych nowych draftów.)*

---

## 2. Uchwały **częściowo** zamknięte (kierunek OK — brak procedury / liczb)

| ID | Co jest ustalone | Co zostało |
|----|------------------|------------|
| **[S1b]** | Jedna czytelna procedura + **[S1e]** warianty; konfrontacje; **[S1c]** + **[S1d]** (remis pojedynczy → przerzut) | Dokładne formuły per wariant w kodzie i instrukcji; NPC — **`skills_json`** **[S14]** |
| ~~**[S5b]**~~ | — | **Superseded** przez **[S14]** |

---

## 3. Proces **open**

| ID | Opis | Domknięcie |
|----|------|------------|
| **[AUDIT]** | Lista luk / nadmiarów w [`06_schema_gaps.md`](06_schema_gaps.md) | **T11** w [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) §12; wpis w `04` po domknięciu |

---

## 4. Bloki z agendy (kierunek uchwalony — szczegóły operacyjne nadal otwarte)

Źródło: sekcja *„Następny etap planowania”* w [`03_discussion_agenda.md`](03_discussion_agenda.md).

| Blok | Temat | Status (2026-05) | Pytania do domknięcia |
|------|--------|-------------------|------------------------|
| **A** | Kampania / pamięć LLM (**[S11]** / **[S11a]** / **[S11b]**) | MVP w kodzie + **wizja [S11b]** + doprecyzowanie runda 2 | **Kolejka + prompty:** [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) (**T01–T15**); m.in. plan do skutku, rollup, cooldown, nowy akt |
| **B** | XP / grant MG (**[S10d]** / **[S10e]**) | MVP grant + log + **katalog XP w DB** | Fabularnie tylko MG; technicznie owner; LLM nie zapisuje XP; implementacja **T12** w [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) |
| **C** | **[IMPL]** | Kolejka zapisana | Aktualizować przy zmianie ryzyk — nie jest „niedomknięty”, tylko żywy dokument |
| **D** | Player rulebook — rozdział XP | Do napisania po A–B | **T13** w [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md); zgodnie z **[S10b]/[S10c]** |

---

## 5. Opcjonalne tematy poza główną listą uchwał

| Temat | Plik agendy |
|--------|-------------|
| Widok „wszystkie rekordy” (debug) vs same zakładki **[S15]** | [Sesja 9d](03_discussion_agenda.md#sesja-9d-opcjonalnie--widok-wszystkie-rekordy-w-adminie) — **odpowiedź:** nie potrzeba (**[S15]**). |
| Następna runda mechaniki po Sesjach 9c–11 | Tabela *„Następna runda tematów”* w [`03_discussion_agenda.md`](03_discussion_agenda.md) |

---

## 6. Sugerowana kolejność domykania (nie jest uchwałą — orientacja dla facylitacji)

1. ~~**Sesja 9c** → **[S15]**~~ — **zrobione** (2026-05-01).
2. ~~**Sesja 11** → **[S17]** + **[S18]**~~ — **uzgodnione** (2026-05-01); implementacja w kodzie = osobne ticket’y.
3. **Projekt treści:** ~~**[S12]**~~, ~~**[S13]**~~, ~~**[S14]**~~ **zrobione**.
4. ~~**Sesja 10** → **[S16]**~~ — **zrobione** (2026-05-01); implementacja frontu gry po **MVP kontraktu** API, równolegle backend.
5. **Mechanika walki:** doprecyzowanie **[S1b]** gdy wchodzi implementacja taktyki / trafienia.

---

## Odnośniki

- Log uchwał: [`04_decisions_log.md`](04_decisions_log.md)
- Agenda: [`03_discussion_agenda.md`](03_discussion_agenda.md)
- Luki schematu: [`06_schema_gaps.md`](06_schema_gaps.md)
- Draft specyfikacji rozszerzonej: [`07_extended_design_spec.md`](07_extended_design_spec.md)
