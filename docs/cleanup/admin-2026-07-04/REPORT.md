# Cleanup admin — #1177 martwy frontend admin (2026-07-04)

Scope: `frontend/admin/`, `frontend/admin_panel_v2/`, `frontend/nginx.conf`. Zero backendu, zero DB, zero PROD.
Baseline pytest: **N/A** — same zmiany frontendowe (HTML/JS/CSS/nginx), nie dotykają Pythona. Weryfikacja = smoke w przeglądarce.

---

### F-01 — usuń `frontend/admin/sections/knowledge.js` (137 l.)
- Kategoria: nieużywany-komponent
- Dowody:
  - `SECTIONS`/`KEYS`/`PORTED` w `admin/index.html` NIE zawierają klucza `knowledge` → `route()` importuje tylko `./sections/${key}.js` dla kluczy z KEYS → nigdy nie załadowany.
  - grep całego repo: brak `import ... knowledge.js` wskazującego na ten plik.
  - Funkcja żyje jako zakładka „📖 Wiedza" w `tools.js` (`toolstab-knowledge`, endpointy `/api/admin/knowledge-book`).
  - UWAGA: `admin_panel_v2/sections/knowledge.js` to INNY, ŻYWY plik (moduleMap:379) — NIE ruszamy.
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: `/admin/#tools` → zakładka „📖 Wiedza" ładuje listę wpisów; brak błędu w konsoli (F12).

### F-02 — usuń `frontend/admin/shared/form.js`
- Kategoria: dead-code
- Dowody: `renderForm`/`readForm` zdefiniowane tylko tu; grep repo = 0 importerów. `_renderForm*` w `smart_entry.js` to osobne, prywatne funkcje (inna nazwa, nie import).
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: `/admin/` ładuje się, sekcje działają (żaden moduł nie importował form.js).

### F-03 — usuń `admin_panel_v2/sections/{designer,dungeons,campaigns_settings}.js`
- Kategoria: nieużywany-komponent
- Dowody: `admin_panel_v2/index.html` ładuje sekcje wyłącznie przez `moduleMap` (linie 370-383). Te 3 klucze NIE występują w moduleMap → nigdy `import()`-owane. Odwołania „designer" w `world.js` to endpoint API `/api/admin/campaign-designer/...` (żywy, inny byt); `.designer-*` w `layout.css` to osierocony CSS (zostawiamy, nieszkodliwy, poza zakresem).
- Ryzyko: LOW (v2 = legacy-ale-żywy, ale te 3 pliki są martwe wewnątrz v2)
- JAK PRZETESTOWAĆ: `/admin2/` → klik po sekcjach z moduleMap (Świat/Kampanie/Mechanika) działa; brak błędu.

### F-04 — usuń martwe bloki nginx `/panel/` + `/admin_panel/` (+ redirect `/panel`)
- Kategoria: dead-code
- Dowody: `nginx.conf:138-142` alias → `/usr/share/nginx/html/admin_panel/` — katalog NIE ISTNIEJE (brak `frontend/admin_panel`). `:144-147` root ten sam nieistniejący katalog. `:114` redirect `/panel`→`/panel/`. Wszystkie → zawsze 404. Zero odwołań w kodzie frontu.
- Ryzyko: LOW (usuwamy trasy które i tak zwracają 404)
- JAK PRZETESTOWAĆ: po restarcie kontenera frontendu — `/admin/`, `/admin2/`, `/showcase/` działają; `curl /panel/` = 404 (jak wcześniej).
- UWAGA: zmiana nginx.conf wymaga **restartu** kontenera frontendu (nie reload — bind-mount inode).

### F-05 — bump `components.css?v=4` → `?v=5` (`admin/index.html:9`)
- Kategoria: niespójność-wersji
- Dowody: nie bumpnięty mimo 11+ commitów; łamie konwencję `?v=N` (CLAUDE.md). Obecnie ratuje tylko `Cache-Control: no-store`.
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: `/admin/` — style OK, DevTools→Network pokazuje `components.css?v=5`.

### F-06 — wersjonuj import `table.js` w `overview.js:5` → `?v=7`
- Kategoria: niespójność-wersji (podwójna instancja modułu)
- Dowody: `index.html:128` importuje `./shared/table.js?v=7`, `overview.js:5` importuje `../shared/table.js` (bez wersji) → przeglądarka ładuje moduł 2× (dwie instancje `esc`/`enhanceTable`). Jedyny importer table.js w `admin/sections/` to overview.js → ujednolicenie do `?v=7` daje 1 instancję.
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: `/admin/#overview` — statystyki + tabele renderują, sort/resize działa; Network pokazuje table.js raz.

### F-07 — usuń nieużywaną `badgeId` (`admin/index.html:160`)
- Kategoria: dead-code
- Dowody: `const badgeId = ...` policzone, ale linia 161 wstawia id inline (`id="world-nav-badge"`), `badgeId` nigdzie nie użyty.
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: `/admin/` — badge „Świat" (licznik oczekujących) pokazuje się normalnie.

### F-08 — usuń martwy `PORTED` + nieosiągalną gałąź (`admin/index.html:204,219`)
- Kategoria: dead-code / złożoność
- Dowody: `PORTED` (18 kluczy) == `KEYS` (18 kluczy) — identyczny zbiór. W `route()` `key` jest już gwarantowane w KEYS (linie 216-217), więc `!PORTED.has(key)` zawsze fałsz → gałąź placeholder-return (219) nieosiągalna. `placeholder()` zostaje (używany w catch).
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: `/admin/` — nawigacja po wszystkich 18 sekcjach ładuje moduły; zły hash `#xyz` → placeholder „Nie udało się załadować".

### F-09 — popraw komentarze „15 sekcji" → 18 (`admin/index.html:130,202`)
- Kategoria: komentarz-nieaktualny
- Dowody: SECTIONS ma 18 wpisów, komentarze mówią „15 sekcji".
- Ryzyko: LOW (tylko komentarz)

### F-10 — `route()` catch: dodaj `console.error` (`admin/index.html:237`)
- Kategoria: bug (cichy błąd) — z opisu #1177
- Dowody: catch połyka błąd importu bez logu, a placeholder mówi „sprawdź konsolę" → nic tam nie ma. Dodaj `console.error('[admin route] import failed', key, e)`.
- Ryzyko: LOW
- JAK PRZETESTOWAĆ: wymuś błąd sekcji → placeholder + błąd widoczny w konsoli.

---

## Zostawiamy (KEEP)
- `.designer-*` CSS w `admin_panel_v2/layout.css` — osierocony po F-03, ale nieszkodliwy; czyszczenie CSS poza zakresem #1177.
- `admin_panel_v2/sections/knowledge.js` — ŻYWY (moduleMap).
- Propozycja z #1177 (port workshops+debug → wycofanie `/admin2/`) — osobne, większe zadanie, NIE w tym batchu.
