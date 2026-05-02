# Phase 8D — Location Integrity

> **Branch:** `phase-8d-location-integrity`  
> **Status:** 🔴 Następna do implementacji  
> **Poprzedza:** Phase 8C (Inventory System)  
> **Notion:** https://www.notion.so/34d8842467a880479914c074f7a66281

---

## Problem

GM LLM widzi tylko ostatnie 8 tur wolnego tekstu — nie ma żadnej struktury lokalizacji
w session state. Gracz może napisać dowolny tekst zmieniający lokalizację bez
uzasadnienia, a GM kontynuuje nowy wątek bez weryfikacji spójności narracji.

**Przykład:** Gracz jest w karczmie → w następnej turze pisze że jest w lesie →
GM opisuje las bez pytania jak tam dotarł.

---

## Cel Phase 8D

1. Wprowadzić tabelę `game_locations` — dynamicznie budowaną podczas gry
2. Wstrzykiwać kontekst lokalizacji do każdego promptu GM
3. Blokować narracyjną "teleportację" — niespójne zmiany lokalizacji
4. Dać adminowi pełną kontrolę przez flagi per sesja i globalnie

---

## Kolejność faz

| Faza | Nazwa | Status |
|------|-------|--------|
| **8D** | **Location Integrity** | 🔴 Następna |
| 8C | Inventory System | 🔴 Po 8D |
| 9 | NPC System + Dialogue | 🔴 Planowane |

> Phase 8D musi być przed 8C, bo `pending_loot.location_id` (Inventory)
> i NPC sell_ratio wymagają działającego systemu lokalizacji.

---

## Decyzje designowe (wszystkie zamknięte)

### D-LOC-01 ✅ — Dynamiczna tabela `game_locations`

Tabela istnieje w DB, ale GM LLM może dynamicznie dopisywać nowe lokalizacje
podczas gry. Mapa świata rośnie organicznie.

**Flow:**
1. GM sprawdza czy lokalizacja już istnieje (fuzzy match po `label`)
2. Jeśli pasuje istniejąca — używa jej
3. Jeśli nowa — tworzy wpis przez `action: "create"` w JSON response
4. Backend zapisuje do `game_locations` i ustawia jako aktualną

**Schema:**
```sql
CREATE TABLE game_locations (
  id            INTEGER PRIMARY KEY,
  key           TEXT UNIQUE NOT NULL,
  label         TEXT NOT NULL,
  description   TEXT,
  parent_id     INTEGER,                    -- FK → game_locations (makro → sub)
  location_type TEXT DEFAULT 'macro',       -- 'macro' | 'sub'
  rules         TEXT,                       -- JSON lub free text: zasady specjalne
  enemy_keys    TEXT,                       -- JSON: lista kluczy z game_config_enemies
  npc_keys      TEXT,                       -- JSON: lista kluczy z game_config_npcs
  is_active     INTEGER DEFAULT 1,
  created_at    TEXT DEFAULT (datetime('now')),
  updated_at    TEXT DEFAULT (datetime('now'))
);
```

**Zasady specjalne (`rules`) — przykłady:**
```json
{"no_combat": true, "reason": "Teren sakralny — walka zakazana przez prawo miasta"}
```
```
"Teren skąpany w ciemności. Awareness DC +3. Postacie bez latarni mają disadvantage."
```

---

### D-LOC-02 ✅ — Detekcja zmiany lokalizacji: LLM ekstrahuje intencję

GM LLM ekstrahuje intencję ruchu z narracji gracza i zwraca ją w polu
`location_intent` w JSON. Backend weryfikuje i zatwierdza lub blokuje.

**Format odpowiedzi GM (Opcja A — JSON wrapper):**
```json
{
  "narrative": "Wychodzisz z karczmy. Chłodne powietrze...",
  "location_intent": {
    "action": "move",
    "target_label": "Rynek Główny",
    "target_key": "market_square"
  }
}
```

**Brak zmiany lokalizacji:**
```json
{
  "narrative": "Siadasz przy stole i zamawiasz piwo...",
  "location_intent": null
}
```

**Fallback komenda:** `/move [lokalizacja]` — explicite intent gdy narracja niejednoznaczna.

---

### D-LOC-03 ✅ — Blokada niespójnej zmiany: trójwarstwowa

| Warstwa | Działanie |
|---------|----------|
| **GM narracja** | GM tłumaczy dlaczego ruch jest niemożliwy |
| **Backend** | `current_location_id` NIE jest aktualizowane |
| **Admin log** | Zapis próby w logu widocznym w Grafana/admin panelu |

---

### D-LOC-04 ✅ — Granulacja: Makro + Sub

Makro jako domyślna granulacja. Sub-lokalizacje podpinane przez `parent_id`.

**Przykładowe drzewo:**
```
Miasto Varen (makro)
├── Karczma Pod Wisielcem (sub)
├── Rynek Główny (sub)
├── Stajnia (sub)
└── Brama Południowa (sub)

Las Czarny (makro)
├── Rozświetlona Polana (sub)
└── Obozówisko Bandytów (sub)
```

**Zasady przechodzenia:**
- Sub → Sub (ten sam makro): swobodne
- Makro → Makro: wymaga uzasadnienia narracyjnego
- Sub → Sub (różne makro): traktowane jak Makro → Makro

---

### D-LOC-05 ✅ — Admin flag `location_integrity_enabled`

Flaga globalna i per sesja. Tylko konta admin mogą toggleować.

- `PATCH /admin/session/{id}/flags` body: `{"location_integrity_enabled": 0}`
- Admin panel: toggle switch w panelu sesji
- Gdy wyłączone: backend pomija całą weryfikację lokalizacji

---

### D-LOC-06 ✅ — Parser: JSON wrapper (A) + fallback parser (B), obie toggleowalne

**Flow:**
```
GM generuje odpowiedź
        │
        ▼
[flaga A włączona?]
   TAK ──► Czy poprawny JSON?
                  TAK ──► Użyj location_intent z JSON ✅
                  NIE ──► [flaga B włączona?]
   NIE ─────────────────► [flaga B włączona?]
                                   TAK ──► Uruchom fallback parser prompt
                                               │
                                               ▼
                                         zwraca location lub "brak"
                                   NIE ──► Brak akcji — lokalizacja bez zmian
```

**Scenariusze użycia:**
| Konfiguracja | Kiedy używać |
|---|---|
| A+B (domyślnie) | Najbezpieczniejsze — JSON + sieć bezpieczeństwa |
| Tylko A | JSON działa stabilnie, zero dodatkowych tokenów |
| Tylko B | Model sypie JSON — parser jako jedyna metoda |
| Żadne | Detekcja globalnie wyłączona |

> ⚠️ Opcja B uruchamia się TYLKO gdy JSON parse się nie uda — nie przy każdej turze.

---

### D-LOC-07 ✅ — Matching lokalizacji: fuzzy match (`rapidfuzz`) + LLM fallback

- Score ≥ 80%: użyj istniejącej lokalizacji
- Score < 80%: krótki prompt do LLM — "Czy 'X' to ta sama lokalizacja co 'Y'?"
- LLM mówi NIE → utwórz nową lokalizację w DB
- Embedding similarity: możliwy upgrade w późniejszej iteracji, pomijamy na start

---

### D-LOC-08 ✅ — Tworzenie nowej lokalizacji: tylko przez Opcję A (`action: "create"`)

Opcja B (fallback parser) może TYLKO matchować istniejące lokalizacje.
Nigdy nie tworzy nowych — zbyt duże ryzyko duplikatów.

**JSON dla nowej lokalizacji:**
```json
{
  "narrative": "Odkrywasz ukrytą grotę za wodospadem...",
  "location_intent": {
    "action": "create",
    "target_label": "Grota za Wodospadem",
    "parent_key": "forest_black",
    "description": "Wilgotna, ciemna grota ukryta za kaskadą wody."
  }
}
```

---

### D-LOC-09 ✅ — Zasięg flag: dwa poziomy (global + per sesja)

Backend merge logic: `session_flag ?? global_flag`

```
game_config_meta:  location_parser_json_enabled = 1      ← default dla wszystkich
game_config_meta:  location_parser_fallback_enabled = 1
                            ↓ można nadpisać per sesja
session_flags:     location_parser_json_enabled = 0      ← tylko ta sesja
```

**Pełna lista flag (wszystkie działają na obu poziomach):**

| Flaga | Domyślnie | Opis |
|-------|-----------|------|
| `location_integrity_enabled` | `1` | Cały system Location Integrity |
| `location_parser_json_enabled` | `1` | Opcja A — JSON wrapper |
| `location_parser_fallback_enabled` | `1` | Opcja B — fallback parser |

---

## Zasady pracy

- Branch: `phase-8d-location-integrity`
- `system_prompt.txt` — zmieniamy tylko po decyzji o formacie `location_intent`
- Po każdym zadaniu: `python3 -m pytest` → wszystkie testy passed
- `location_integrity_enabled = 0` jako domyślne podczas development
- Włączamy weryfikację tylko do testów (8D-20 do 8D-24)
