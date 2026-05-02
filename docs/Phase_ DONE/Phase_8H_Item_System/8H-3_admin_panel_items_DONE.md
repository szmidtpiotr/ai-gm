<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-05-01 -->

# PROMPT 8H-3 — Admin Panel — Zakładka Items (Phase 8H)

> Wymaga ukończonych 8H-1 i 8H-2. REV 2 — pełna implementacja na podstawie skanu kodu.

---

## Cel

Dodanie zakładki **Items** do `frontend/admin.html` i obsługi JS w `frontend/js/admin.js` zgodnie ze wzorcem istniejących zakładek (Weapons, Enemies). Panel obsługuje nową zunifikowaną tabelę `game_config_items` z filtrem `item_type`, warunkowymi polami dla armor (`ac_bonus`) i consumable (pola efektów) oraz flagą zatwierdzania.

### Stan wyjściowy
- W `admin.html` NIE ma zakładki Items — do dodania od zera
- Wzorzec istniejący: `data-tab="weapons"` + `data-panel="weapons"` + `renderWeapons()` + `loadWeapons()` w JS
- Endpointy backendu po 8H-2: `GET/POST /admin/config/items`, `PUT /admin/config/items/{key}`, `DELETE /admin/config/items/{key}`

---

## Kontekst techniczny

- **Pliki do zmiany:** `frontend/admin.html`, `frontend/js/admin.js`
- **NIE ruszać:** inne zakładki, `docker-compose.yml` prod, `data/ai_gm.db`
- **Zależność:** 8H-2 zmerge'owane lub na tym samym branchu
- **Branch:** `phase-8h-2-backend-services` (lub nowy `phase-8h-3-admin-panel`)

---

## Odpowiedzi do REV 1 (na podstawie skanu kodu)

| Pytanie | Odpowiedź |
|---|---|
| Struktura frontendu panelu | `frontend/admin.html` — jeden plik HTML z sekcjami `data-panel`, JS w `frontend/js/admin.js` |
| Osobny plik JS dla Items? | Nie — całość w jednym `admin.js` (73 kb) |
| Panel HTML dynamiczny czy strony? | Jeden HTML, sekcje pokazywane/ukrywane przez CSS na podstawie `data-tab`/`data-panel` |
| Endpointy consumables w admin.py? | Istnieją jako proxy na items po 8H-2 (deprecated, nie usuwając) |
| Aktualne endpointy items URL? | `GET /admin/config/items`, `POST /admin/config/items`, `PUT /admin/config/items/{key}` |

---

## Implementacja (REV 2)

### Krok 1 — `frontend/admin.html` — zakładka Items

#### 1a. Dodaj przycisk zakładki (w `<div class="admin-tabs">`)

Wstaw **za** przyciskiem `Weapons`, **przed** `Enemies`:

```html
<button class="secondary admin-tab" data-tab="items">Items</button>
```

#### 1b. Dodaj panel sekcji (w `<main class="admin-main">`)

Wstaw po sekcji `data-panel="weapons"`, przed `data-panel="enemies"`:

```html
<section class="admin-card admin-tab-panel" data-panel="items">
  <h2>Items</h2>
  <p class="muted">
    Katalog przedmiotów (armor, misc, quest, consumable, narrative).
    <code>allowed_classes</code>: lista klas oddz. przecinkami lub puste = wszystkie.
    Pola efektów aktywne tylko dla <code>item_type=consumable</code>.
    <code>ac_bonus</code> aktywne tylko dla <code>item_type=armor</code>.
  </p>

  <!-- Filtr item_type -->
  <div class="inline-form" style="margin-bottom: 0.5rem;">
    <label for="items-filter-type">Filtr type:</label>
    <select id="items-filter-type">
      <option value="">wszystkie</option>
      <option value="armor">armor</option>
      <option value="misc">misc</option>
      <option value="quest">quest</option>
      <option value="consumable">consumable</option>
      <option value="narrative">narrative</option>
    </select>
    <button id="items-filter-btn" class="secondary" type="button" disabled>Filtruj</button>
  </div>

  <!-- Formularz dodawania -->
  <div class="inline-form" id="new-item-form" style="grid-template-columns: repeat(4, 1fr);">
    <input id="new-item-key" placeholder="key (snake_case)">
    <input id="new-item-label" placeholder="label">
    <select id="new-item-type">
      <option value="misc">misc</option>
      <option value="armor">armor</option>
      <option value="consumable">consumable</option>
      <option value="quest">quest</option>
      <option value="narrative">narrative</option>
    </select>
    <input id="new-item-value-gp" placeholder="value_gp" type="number" min="0" value="0">
    <input id="new-item-weight-kg" placeholder="weight_kg" type="number" min="0" step="0.1" value="0">
    <input id="new-item-allowed-classes" placeholder="allowed_classes" style="grid-column: span 2;">
    <label class="inline-check"><input id="new-item-active" type="checkbox" checked> active</label>
    <input id="new-item-description" placeholder="description" style="grid-column: 1 / -1;">
    <div id="new-item-armor-fields" style="grid-column: 1 / -1; display: none;">
      <input id="new-item-ac-bonus" placeholder="ac_bonus" type="number" min="0" value="0">
    </div>
    <div id="new-item-consumable-fields" style="grid-column: 1 / -1; display: none;">
      <select id="new-item-effect-type">
        <option value="misc">misc</option>
        <option value="heal_hp">heal_hp</option>
        <option value="restore_mana">restore_mana</option>
        <option value="remove_condition">remove_condition</option>
      </select>
      <input id="new-item-effect-dice" placeholder="effect_dice (np. 2d6)">
      <input id="new-item-effect-bonus" placeholder="effect_bonus" type="number" value="0">
      <select id="new-item-effect-target">
        <option value="self">self</option>
        <option value="ally">ally</option>
        <option value="any">any</option>
      </select>
      <input id="new-item-charges" placeholder="charges" type="number" min="1" value="1">
    </div>
    <button id="new-item-btn" class="secondary" type="button" disabled>Add item</button>
  </div>

  <div id="items-list" class="table-wrap"></div>
</section>
```

---

### Krok 2 — `frontend/js/admin.js`

(Szczegółowy kod w REV 2 — patrz commit `266c9ed`)

- `bindEls` / `setConnected` / `updateItemFormFields` / `renderItems`
- `loadItems` — GET `/admin/items`, filtr po stronie klienta
- `handleCreateItem` — POST `/admin/items` z `key` w body
- Lazy load przy `data-tab="items"`

---

## Co zostało zrobione *(uzupełnia Cursor)*

- **`frontend/admin.html`**: zakładka **Items** (przycisk + panel) między Weapons a Enemies — filtr `item_type`, formularz dodawania, pola warunkowe armor (`ac_bonus`) / consumable (efekty, `charges`).
- **`frontend/js/admin.js`**: `bindEls` / `setConnected` / `logout` / `refreshAll`, `updateItemFormFields`, `renderItems` (tabela, Zatwierdź / toggle `is_active` / Usuń przez **`PATCH`/`DELETE` `/admin/items/...`**), `loadItems` (GET **`/admin/items`**, filtr po stronie klienta — backend nie ma `?item_type=`), `handleCreateItem` (POST **`/admin/items`** z polem `key` w body), lazy load przy przełączeniu na zakładkę Items.

**Różnica względem REV 2 w dokumencie:** endpointy to **`/admin/items`** (nie `/admin/config/items`); aktualizacje przez **`PATCH`** (nie `PUT`); POST tworzenia na **`/admin/items`** z `key` w JSON (nie `POST .../items/{key}`).

**Commit:** `266c9ed` — `8H-3: panel admin — zakładka Items (lista, filtr, CRUD)`  
**Branch:** `phase-8h-2-backend-services` → `origin`

---

## Notatki po implementacji *(Perplexity)*

**Cel osiągnięty.** Zakładka Items działa jako pełny CRUD dla `game_config_items`.

**Korekta URL i metody** względem REV 2 to ważna informacja do propagacji — zaktualizowałem 8H-4 i 8H-5 z poprawnymi ścieżkami (`/admin/items`, PATCH).

**Zakładka `Consumables` nadal widoczna w panelu** (potwierdzone screenshotem, 2026-05-01). Jest to oczekiwane na tym etapie — 8H-2 zdeprecjonowało endpoint jako proxy, ale nie ukryło przycisku w HTML. Należy usunąć lub oznaczyć jako `⚠ deprecated` w osobnym drobnym tasku — NIE blokuje działania Items. Zakładka `Przedmioty` (widoczna na screenshocie) to właśnie ta zakładka — nazwa polska jest poprawna.

**Tech debt do zamknięcia przed Phase 9:** ukrycie przycisku `Consumables` z `admin.html` + drop tabeli `game_config_consumables` po weryfikacji brak referencji na prod.
