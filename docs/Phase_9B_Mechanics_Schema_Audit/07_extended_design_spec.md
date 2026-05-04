# Rozszerzona specyfikacja projektowa (draft pod uchwały)

**Status:** draft roboczy **2026-05-03** — nie zastępuje `04_decisions_log.md` dopóki wpisy nie przejdą na **accepted**.  
**Cel:** Zaprojektować wcześniej pola, ścieżki importu i JSON, żeby **nie dokładać** migracji „na kolanie” i nie rozjeżdżać katalogów.

**Powiązania:** [`06_schema_gaps.md`](06_schema_gaps.md), [`04_decisions_log.md`](04_decisions_log.md), **[IMPL]** (kolejność fal).

---

## 1. Magia, czary, AOE vs cel pojedynczy (**[S1]**, luka w `06`)

### Problem

`weapon_type` + `range_m` nie mówią wprost: **jeden cel** vs **obszar**.

### Propozycja (jedna ścieżka katalogową)

Traktujemy **czar** jak wpis w **`game_config_weapons`** z `weapon_type = 'spell'` (już zgodne z kierunkiem **[S1]**). Rozszerzenia kolumn (migracja jednorazowa):

| Kolumna | Typ | Opis |
|---------|-----|------|
| `targeting` | `TEXT` (walidacja w aplikacji) | **MVP [S12]:** tylko `single` \| `aoe_radius` (kula). W przyszłości możliwe rozszerzenie (`cone`, `line`, `self`…) bez zmiany tabeli. Domyślnie `single` dla istniejących wierszy. |
| `aoe_radius_m` | `REAL` nullable | Promień kuli w metrach; **NULL** gdy `targeting = single`. |
| `magic_school` | `TEXT` nullable | **Etykieta** (np. ogień, iluzja) — filtry admina + LLM; **bez** wpływu na liczenie na MVP (**[S12]**). |

**Zasady:**

- Atak magiczny w silniku **nadal** wiąże się z tym samym pipe’m co bronie (klucz broni / czaru z katalogu).
- **AOE (MVP):** `aoe_radius` + `aoe_radius_m` — **prosta** spójność katalogu z narracją; **mapa / automatyczne „kto w promieniu”** — po MVP (**[S12]**).
- **Osobna tabela `game_config_spells`:** **nie** na MVP — duplikacja kluczy i konflikt z **[S1]** (typ broni / magia). Jeśli kiedyś powstanie widok „tylko czary”, to **VIEW** lub filtr `weapon_type = spell`.

**Ryzyko techniczne:** każda nowa kolumna musi trafić do **`import_catalog_snapshot`** (nie do wąskiego `import_config`).

### 1.1 Mapa bitwy i taktyka (**[S19]**)

| Faza | Co obowiązuje |
|------|----------------|
| **MVP** | **Brak mapy taktycznej w silniku** — bez siatki, bez tokenów na planszy w DB, bez automatycznego „kto jest w promieniu” z geometrii. `range_m` / `aoe_radius_m` kotwiczą **opis i zasady** (**[S12]**). Kto trafiony / w zasięgu — **narracja i uzgodnienie z MG (AI)**, nie solver mapy. |
| **Później** | Osobna uchwała: możliwa mapa (strefy, hex, VTT, automatyczne AOE). Nie część MVP. |

---

## 2. Broń / atak — mapowanie kod ↔ konfiguracja

### Kontrakt

- `weapon_type`: `melee` \| `ranged` \| `spell` — **wymagana** zgodność z rodzajem akcji w `combat_service` / `dice` (np. `melee_attack` vs klucz broni).
- **`linked_stat`** przy broni już jest — obrażenia i testy muszą **zawsze** brać mapowanie z rekordu broni + **[S4b]** dla umiejętności.
- **Dwuręczność:** jeden **`game_config_skills.key`** zarezerwowany (np. `two_handed` lub `great_weapon`) — wpis w katalogu + opis w `draft_formulas`; combat aplikuje kary wg **[S1]** dopiero gdy implementacja będzie gotowa.

---

## 3. `effect_json` — szkielet **wersji 0** (**[S2]**, **[S6]**, **[S13]** accepted)

Wspólny podzbiór dla **`game_config_items`** i **`game_config_conditions`** — jeden „język” efektów.

**Zasady produktowe ([S13]):** walidacja **przed zapisem i przy imporcie**; lista typów `type` **krótka na start**, **rozszerzalna**; LLM może **proponować** JSON z opisu — po walidacji i akceptacji admina; **bez** utrzymania migracji ze starych płaskich `effect_*` — możliwy reset katalogu + rekordy wzorcowe.

### Top-level (wszystkie rekordy z efektem JSON)

```json
{
  "schema_version": 1,
  "effect_category": "character_condition | gear_bonus | consumable_immediate | aura",
  "effects": [ … ]
}
```

### Element tablicy `effects` (jeden lub wiele na rekord)

| Pole | Znaczenie |
|------|-----------|
| `type` | Enum aplikacji (lista **startowa**, **rozszerzalna** — **[S13]**): m.in. `periodic_save`, `static_stat_modifier`, `heal_hp`, `apply_condition`, `remove_condition`, `block_action`, `narrative_only` |
| `condition_key` | Opcjonalnie odwołanie do `game_config_conditions.key` |
| `dc_key` | Opcjonalnie klucz z `game_config_dc` (**[S5]**) zamiast liczby |
| `stat` | STR, DEX, … przy modyfikatorach |
| `value` | Liczba lub dice string (`1d4`) — interpretacja wg `type` |
| `tick` | `start_turn` \| `each_round` \| `on_use` — dla stanów cyklicznych |
| `expires` | `save_success` \| `duration_rounds:N` \| `manual` |

**Rozróżnienie [S6]:** `effect_category = gear_bonus` vs `character_condition` — walidator **nie** pozwala mylić „buff z pierścienia” ze „strachem” przy tym samym `type`, jeśli reguły tego wymagają (reguły walidacji w kodzie).

**Migracja treści:** Zgodnie z **[S13]** — **nie** wymagamy konwersji starej treści; dopuszczalny reset katalogu i **rekordy wzorcowe**; kolumny `effect_*` do usunięcia w migracji schematu razem z kodem (bez długiego dual-read).

---

## 4. Obrona i AC (**[S2]**)

### MVP (jedna liczba „na postać”)

- **`ac_bonus`** z założonego pancerza (suma lub jeden przedmiot typu armor — **do decyzji implementacyjnej**: „najwyższy” vs suma lekkich bonusów).
- Wzór projektowy: `AC = 10 + DEX_mod (ograniczony zasadami zbroi jeśli dodacie cap) + suma(ac_bonus z założonych)` — szczegół balansu poza tym dokumentem.
- **Hit locations:** poza MVP — nie dodawać kolumn dopóki nie ma uchwały.

---

## 5. Wrogowie vs karta gracza (**[S14]** accepted; **[S5b]** superseded)

### Jedna tabela, ta sama logika co PC — pola **opcjonalnie** wypełnione

**`game_config_enemies`** — pojedynczy katalog; znaczenia liczb **jak przy karcie gracza**, rekord może mieć **tylko podzbiór** pól wypełniony (**sparse**). Nie druga osobna „postać” w DB sesji.

| Obszar | Stan / kierunek |
|--------|------------------|
| Walka | Istniejące kolumny pokrywają **`combat_service`** na MVP. |
| Umiejętności / konfrontacje **[S1b]** | **`skills_json` TEXT** nullable — mapa `{ "skill_key": ranga_lub_bonus }`, klucze jak **`game_config_skills`** (**[S4b]**). Migracja + kod rzutów. |
| Asystent **[S20]** | Opis („bandzita z kuszą”) → propozycja parametrów + sensowne umiejętności → walidacja → zapis. |

**Pełna kopia arkusza PC:** nie jest celem — **wspólna struktura znaczeń**, część pól pusta lub domyślna.

---

## 6. Import i środowiska (**[S7]**)

### Reguła operacyjna (żeby nie „ucinać” broni)

| Cel | Ścieżka |
|-----|---------|
| Pełny katalog (bronie ze **wszystkimi** kolumnami, items, loot) | **`import_catalog_snapshot`** |
| Szybki dev (stats/skills/dc rdzeń) | **`import_config`** — **świadomie ryzykowne** dla broni |

### Checklist przed importem produkcyjnym

1. Snapshot bazy (**[S7a]**).
2. Porównanie listy kolumn z `PRAGMA table_info(game_config_weapons)` vs pole w JSON.
3. Dry-run jeśli endpoint to wspiera.

---

## 7. Kampania — uzupełnienie projektowe (**[S11]**, **[S11a]**, **[S11b]**)

| Temat | Projekt |
|-------|---------|
| **Wizja ([S11b])** | Haki z opisu postaci + „drugi hook” (LLM: wygląd, mocne/słabe strony) → MG **generuje** konspekt kampanii → zapis w DB; MG prowadzi grę narracyjnie; **PATCH planu** — **admin/debug**, docelowo zbędny (**[S11b]** doprecyzowanie). |
| **Timing pierwszego planu** | Po zapisaniu postaci, **przed** pierwszym promptem MG; generacja planu **do skutku** (bez startu narracji z pustym planem) — **[S11b]** runda 2. |
| **Nowy akt po głównym queście** | **Ten sam** `campaign_id`: warunek zakończenia questa → LLM jak przy starcie (**merge** planu) + narracja spinająca; **ciągłe** `campaign_turns` i numeracja tur — **[S11b]** runda 2. |
| **Notatnik gracza** | Tylko to, co wynika z **dotychczasowej narracji MG** (rolling recap); **nie** podgląd ukrytego planu (**[S11b]**). |
| **Kanoniczna treść vs rollup** | **SoT:** `campaign_turns` (tury `narrative`); podsumowanie = **pochodna** LLM z transkryptu — bez zmiany filozofii (**[S11b]**). |
| **Jawne / MG-only** | **Dwa rekordy** (np. `audience` w `campaign_ai_summaries` lub osobna tabela); plan strukturalny w **`gm_plan_json`** / tabela prywatna — **nie** w odpowiedziach API dla gracza (**[S11b]**). |
| **Multiplayer / odświeżenie** | Każdy gracz może wymusić rollup; opcjonalny **cooldown** (np. co 20 rund) (**[S11b]**). |
| **Błąd LLM przy rollupie** | Stan **„wymaga odświeżenia”** w UI (**[S11b]**). |
| **Kolejne łuki „z wyprzedzeniem”** | **W1** merge w `gm_plan_json` vs **W2** tabela beatów — decyzja przy kodzie; **W3** nowy `campaigns` tylko jawny sequel (**[S11b]**). |
| Podsumowanie (cadence) | **N** tur / ręcznie — bez zmiany modelu rollupu; strojenie kosztów (**[S11b]**). |
| Dywergencja | MG realizuje plan; przy silnym odejściu — **rework planu** + dotychczasowe opcje techniczne **(a)–(d)** w **[S11b]** §6. |
| Kontynuacja po „końcu” fabuły | Preferencja: **ta sama kampania** + W1/W2; **W3** — świadomy wariant produktowy. |
| UI planu | **Generowanie LLM**; PATCH operatora — wyłącznie narzędzie awaryjne. |
| Questy / XP | Dla systemu preferowana **struktura w DB** (cele, statusy) — ułatwia XP i audyt (**[S11b]**). |

---

## 8. XP — reszta projektowa

| Temat | Projekt |
|-------|---------|
| Staty za XP | Meta `xp_stat_raise_costs`: `{ "STR": [50,100,...], ... }` lub jedna krzywa dla wszystkich statów — **jedna** tabela prawdy w **`game_config_meta`**. |
| Grant MG nie-owner | Osobna rola `gm` w `campaign_members` lub flaga admin — **ten sam** endpoint z dodatkowym sprawdzeniem. |

---

## 9. Kolejność „projekt → uchwała → kod”

1. Przejść ten dokument na sesji i zmienić wybrane sekcje na **[S12]…[S20]** w `04_decisions_log.md` ze statusem **accepted**.
2. Zaktualizować **`01_schema_inventory.md`** po akceptacji nowych kolumn.
3. Implementować zgodnie z **[IMPL]** — bez wyprzedzania migracji przed uchwałą.

---

## 10. Panel administratora — **zakładki (UX)** vs **tabele SQL (model)**

**To są dwie niezależne decyzje** — często mylone.

### Ludzka logika (to Wy + narzędzia UI)

- **Osobna zakładka** „Czary”, „Pancerze”, „Broń wręcz”, „Mikstury” itd. ma sens **zawsze**, niezależnie od liczby tabel SQL: admin widzi **filtrowany widok** na jednym katalogu (`WHERE weapon_type = 'spell'`, `WHERE item_type = 'armor'`, …).
- Formularz pod zakładką pokazuje **tylko pola istotne** dla tej kategorii (ukrywa np. `damage_die` przy czystym przedmiocie fabularnym) — walidacja po stronie API / JSON Schema.
- **([S15] accepted):** zestaw zakładek może być **raczej stały** w danym etapie, ale **łatwo dokładamy kolejne** zakładki bez zmiany filozofii; na wszystkich zakładkach ta sama mechanika **edycji, sortowania, wyszukiwania**. Osobnego widoku „wszystkie rekordy naraz bez filtra” **nie** planujemy.

### Model relacyjny (kiedy **druga tabela** ma rację bytu)

Osobną tabelę SQL warto rozważyć **nie** dlatego, że „wygodniej w menu”, tylko gdy:

- inny **cykl życia** lub **import** (rzadko),
- **inne powiązania FK** (np. tylko czary podpinane pod szkołę magii z osobnej księgi),
- **inne uprawnienia** edytorskie per rola,
- **konflikt kluczy** rozwiązany inaczej niż prefiks `key`.

W przeciwnym razie **jedna tabela + typ/kolumna dyskryminująca** + zakładki w panelu = mniej migracji i jeden import (**[S7]**).

### Powiązanie z §1 (czary)

Propozycja **[S12]**: czary w **`game_config_weapons`** — **nie** oznacza „jedna zakładka Broń dla wszystkiego”. Oznacza: **jeden rekord w jednym miejscu prawdy**, a w UI — **osobna zakładka „Czary”** z presetem filtrów i pól.

### Asystent LLM — Game design i katalogi (**[S20]**)

| Zasada | Opis |
|--------|------|
| **Zakres** | **Konwersacja** z adminem → **propozycja** poprawnego JSON / pól rekordu dla **całego modułu Game design** (obecnie `game_design` w panelu) oraz **tym samym wzorcem** dla pozostałych zakładek katalogu **[S15]**, gdy jest zdefiniowany schemat zapisu. |
| **Przepływ** | Cel opisany słowami → LLM generuje **draft** zgodny ze schematem → **walidacja** backend (**[S13]**, **[S7]**) → admin **akceptuje / edytuje**. |
| **Centralny LLM** | Resolver **[S18]**; treść i polityka kosztów — osobno od narracji gracza (do rozdzielenia w implementacji). |
| **UI** | Jedna rodzina komponentów przy **[S16]** — unikamy osobnego prototypu na każdą zakładkę. |

---

## 11. Figma, design system i przebudowa klienta (**[S16]** accepted)

| Temat | Kierunek |
|-------|-----------|
| **Cel** | Wierność **1:1** projektowi z Figmy; **Figma = źródło komponentów**; handoff tokenów + komponentów do kodu (np. Code Connect / równoważnie). **Figma Make** — nie jest obowiązującą ścieżką (eksperymenty bez sukcesu OK). |
| **Framework** | **Świadomy skok** z obecnego HTML/JS na stack zgodny z mapowaniem z Figmy — typowo **React** w ekosystemie Code Connect; **ostateczny wybór** przy starcie repo. Figma (produkt) **nie narzuca** frameworku gry — wybór = integracja design-to-code. |
| **Kolejność** | **Najpierw UI gracza** (czat, sesja, walka…); **admin może zostać legacy** do osobnej fazy. |
| **API** | Możliwe **zamrożenie** kontraktu pod front; rozszerzenia bez łamania klienta. |
| **Kiedy start frontu** | Merytorycznie: nie trzeba czekać na pełne **[IMPL]** (rdzeń API). **Operacyjnie (2026-05-01):** zespół **odkłada** start nowego frontu **na koniec** planu — po nauce Figmy / workflow; patrz dopisek w **[S16]**. |
| **Tokeny** | Kolory, typografia, spacing zsynchronizowane między Figmą a kodem. |
| **Admin (później)** | Makietę admina **[S15]** zintegrować przy **fali admin v2**; pierwsza fala = gra. |

**Powiązanie z Azure:** dostawca LLM (**[S17]**) nie zmienia UI katalogów — tylko ustawienia połączenia i ewentualnie ekran „Model / Endpoint” w ustawieniach.

**Powiązanie z [S20]:** Asystent konwersacyjny w **Game design** wdrażany przy **fali admina** po nowym froncie gry (**[S16]** pkt 4–5), chyba że zespół zdecyduje się podpiąć asystenta wcześniej pod legacy admin — do backlogu.

---

## 12. Centralna konfiguracja LLM (**[S18]**)

| Zasada | Opis |
|--------|------|
| **Jeden resolver** | Backend wyznacza efektywną konfigurację (provider, URL, model, klucz) w **jednym** miejscu kodu; konsumenci tylko wołają API lub serwis. |
| **UI — Default vs Custom** | **Default** = konfiguracja serwera / admina (np. `LLM_*`). **Custom** = użytkownik ustawia własny endpoint — wtedy **wygrywa** nad domyślnym. |
| **Dev vs prod [S17]** | Dev: **wspólny** endpoint dla zespołu (bez zmuszania do klikania przy każdej sesji). Prod docelowo: własny endpoint gracza — **po** epiku „profil konta”; do tego backlog. |
| **Klucz API — UX** | Raz zapisany po stronie serwera; maska w UI; „zmień klucz” przy rotacji — bez ponownego wpisywania przy każdym logowaniu (szczegół tech przy wdrożeniu). |
| **Testy / CI** | Domyślnie **mock / fałszywy URL** z env testowego; brak wymogu prawdziwego Azure w CI; ewent. test „prawdziwy” opcjonalny i oznaczony. |
| **Azure [S17]** | Ten sam magazyn i resolver; nie osobna ścieżka równoległa. |
| **Kampania** | Per-campaign model — tylko jeśli kiedyś wrócimy; jawny wpis w DB, nie hack w froncie. |

---

## Odnośniki

- Luki: [`06_schema_gaps.md`](06_schema_gaps.md)
- Uchwały: [`04_decisions_log.md`](04_decisions_log.md)
- Kolejka: **[IMPL]**
