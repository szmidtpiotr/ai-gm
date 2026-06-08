# 10 — Przebudowa Admin Panelu (strangler-fig) — Brief Agenta

> **Sesja założycielska:** 2026-06-08
> **Epic:** [#401](https://github.com/szmidtpiotr/ai-gm/issues/401)
> **Dla kogo ten dokument:** agent który przejmuje przebudowę panelu admina. Czytasz to przed pierwszą linią kodu.

---

## Problem który rozwiązuje

Panel admina to dziś **jeden plik** `frontend/admin_panel_v3/index.html` — **19 447 linii, 1 MB, 967 funkcji, 358 wywołań API, 14 sekcji**. Wszystko inline: HTML, CSS, JS, logika każdej sekcji w jednym worku.

Każdy nowy feature (D5 item view, D6 narrative state, D7 encountery) dorzucamy do tego monolitu. Plik puchnie, sekcje się przeplatają, nic nie da się testować w izolacji. To ten sam antywzorzec ("grób"), który już raz sprzątaliśmy przy admin2.

> **Zasada projektowa (zatwierdzona 2026-06-08):**
> Budujemy `frontend/admin/` jako cienką modularną skorupę. Portujemy sekcje **jedna po drugiej** z monolitu. admin3 **zostaje jako fallback** dla nieprzeniesionych sekcji — nie usuwamy go teraz. Po porcie i akceptacji sekcji jej kopia w monolicie jest kasowana **natychmiast**. Migracja kończy się, gdy admin3 ma zero sekcji.

> **Dlaczego strangler-fig, a nie rewrite albo łatanie?**
> - **Pełny rewrite naraz** — najczystszy wynik, ale blokuje obsługę admina na cały czas przebudowy, brak testu przyrostowego, najwyższe ryzyko. Odrzucone.
> - **Naprawa monolitu w miejscu** — mniej ruchu na starcie, ale modularność niemożliwa, smrody zostają. Odrzucone.
> - **Strangler-fig** — admin3 żyje i obsługuje, my przenosimy sekcję po sekcji, każdą testujemy osobno, ryzyko rozłożone. Wybrane.

> **Co odrzucono i dlaczego (anty-grób):**
> Sekcja istnieje w **DOKŁADNIE JEDNYM** miejscu naraz. Zakaz "zostawię kopię w admin3 na wszelki wypadek" — to tworzy czwarty grób: nowy panel obok admin3 obok admin2, wszystkie półfunkcjonalne. Po porcie + akceptacji kopia w monolicie znika w tym samym commicie.

---

## Strategia: delete-as-you-go (zatwierdzona 2026-06-08)

> **Decyzja:** Wariant **delete-as-you-go** — sekcję usuwamy z monolitu od razu po jej porcie i akceptacji. Rozważano alternatywę "pełny parallel + cutover na końcu" (admin3 nietknięty aż nowy panel kompletny). **Odrzucono.**

> **Dlaczego delete-as-you-go, nie pełny parallel?**
> - **Pełny parallel** trzyma każdą portowaną sekcję w dwóch miejscach naraz aż do końca migracji. To dokładnie antywzorzec "grobu": dwie wersje tej samej sekcji żyją równolegle, rozjeżdżają się (ktoś poprawi bug w jednej, zapomni w drugiej), nie wiadomo która jest prawdą. Im dłużej trwa, tym gorzej.
> - **Delete-as-you-go** ma w każdej chwili jedno źródło prawdy na sekcję. Zero rozjazdu, zero "która wersja obowiązuje".

> **Co to znaczy w praktyce — i dlaczego to NIE jest "wyłączenie starego":**
> `/admin3/` jako **route żyje przez całą migrację** (HTTP 200, fallback). Nie wyłączamy go. Usuwamy tylko **pojedynczą sekcję** z jego `index.html` po tym, jak jej odpowiednik w `/admin/` przeszedł parity i akceptację. admin3 kurczy się sekcja po sekcji, ale serwuje wszystkie jeszcze-nieprzeniesione.
>
> ```
> Po porcie np. content:
>   /admin/#content   ← działa (nowe, jedyne miejsce)
>   /admin3/#content  ← usunięte z monolitu (anty-grób)
>   /admin3/          ← dalej serwuje resztę sekcji (overview, world, ...)
> ```
>
> Pełne `rm -rf admin_panel_v3/` = **FADM-DONE**, dopiero gdy admin3 ma zero sekcji (po Fazie 4). Do tego momentu oba panele działają równolegle.

> **Twardy warunek bezpieczeństwa:** sekcji NIE wolno usunąć ze starego, dopóki `/admin/#<key>` nie robi **wszystkiego** co `/admin3/#<key>` (parity zweryfikowana ręcznie + Playwright GREEN). Parity jest bramką usunięcia — nie odwrotnie.

---

## Co budujemy — układ plików

```
frontend/admin/
  index.html              ← cienka skorupa: CSS (wygląd dziedziczony z admin3),
                            sidebar nav (14 sekcji), <main id="panel">, hash-router
  shared/
    api.js                ← apiFetch + APIError (wyciągnięte z monolitu, sygnatura bez zmian)
    table.js              ← _ROW_REGISTRY
    toast.js
    modal.js
    form.js
  sections/
    overview.js           ← export async function init(panel)
    mechanics.js
    content.js
    ...                    ← po jednym pliku na sekcję, montowany dynamicznie
```

**Hash-router:** `#<key>` → `import('./sections/<key>.js')` → `await mod.init(panel)`. localStorage zapamiętuje ostatnią sekcję.

**Fallback (symetryczny redirect):** każda sekcja działa w **dokładnie jednym** miejscu. Klik sekcji jeszcze nieportowanej w `/admin/` → `window.location.replace('/admin3/#<key>')` (bounce do admin3, jej aktualny dom). Symetrycznie: klik sekcji już sportowanej w `/admin3/` → redirect do `/admin/#<key>`. Lista sportowanych: `const PORTED` w `admin/index.html` (rośnie z każdym FADM-Px). Placeholder zostaje tylko jako sygnał błędu importu modułu (ported, ale padł) — nie cichy redirect, by nie maskować buga. Zero martwych klików.

**Trasy:** `/admin/` serwowane równolegle z `/admin3/`. Oba żyją przez całą migrację. `/admin3/` znika dopiero w FADM-DONE (osobny task, po Fazie 4).

---

## Recepta portu jednej sekcji (powtarzasz dla każdej)

Każdy port idzie wg **/tdd** (RED → GREEN → REFACTOR → GitHub → /document) i **/document**.

```
1. RED   — napisz Playwright spec: /admin/#<key> renderuje sekcję + 1 kluczowa akcja.
           Spec faili (modułu jeszcze nie ma). Lista w admin3 → Narzędzia → Playwright.
2. GREEN  — wytnij logikę sekcji z monolitu, przenieś do sections/<key>.js jako
           export async function init(panel). Wywołania API przez shared/api.js
           BEZ przepisywania. Backend bez zmian.
3. REFACTOR — posprzątaj: nazwy, duplikaty, toasty zamiast alert(), kontrakty
           przypięte (nie ?? ?? na ślepo).
4. AKCEPTACJA — ręczny checklist parity: /admin/#<key> == /admin3/#<key>.
5. ANTY-GRÓB — przepnij trasę sekcji + USUŃ sekcję z monolitu index.html w TYM
           SAMYM commicie. Sekcja w jednym miejscu.
6. /document — log w tym pliku (sekcja ✅ + data), CZĘŚĆ AE w game_mechanics.md
           (❌ → ✅), notes.md (FADM-Px [ ] → [x]).
7. GitHub — issue → review + needs-testing, komentarz "jak przetestować ręcznie".
```

> **Dlaczego port mechaniczny, nie przepisywanie?**
> Endpointy backendu już istnieją i działają (~163 trasy, sprawdzone). Sekcja ma działać **identycznie** po porcie. Przepisywanie logiki = nowe bugi + brak parity. Przenosimy kod 1:1, zmienia się tylko opakowanie (osobny plik + init). Smrody naprawiamy przy okazji (REFACTOR), nie przepisujemy od zera.

---

## Kolejność (zależności)

```
FADM-P0 (bootstrap)  ← BLOKUJE WSZYSTKO. Skorupa + shared utils. Zacznij tutaj.
   │
   ├─ FADM-P1  overview    ← proste, waliduje wzorzec
   ├─ FADM-P2  mechanics   ← proste
   ├─ FADM-P3  content     ← ciężkie (+ D5 item VIEW)
   ├─ FADM-P4  world       ← ciężkie (+ D7 encountery)
   ├─ FADM-P6  campaigns   ← ciężkie (5 zakładek + B6 World State + B7 Inspector + D6 narrative)
   ├─ FADM-P5  map
   ├─ FADM-P7  dungeons
   ├─ FADM-P8  forge       (+ D7 hook_type)
   ├─ FADM-P9  players
   ├─ FADM-P10 tools       (sandbox + Playwright + Inspector)
   ├─ FADM-P11 system      (LLM presety + config)
   └─ FADM-P12 misc        (invites + push + bugreports)
```

> **Dlaczego proste sekcje najpierw?**
> overview/mechanics są małe i mało ryzykowne. Portując je pierwsze, walidujesz że skorupa, router i shared utils działają, ZANIM wejdziesz w content/world/campaigns (największe sekcje, najwięcej do stracenia). Jeśli wzorzec jest zły, dowiadujesz się na taniej sekcji.

---

## Mapowanie tasków D do sekcji (pokrycie do D7)

Modularny `admin/` musi pokryć wszystkie zdolności admina aż do D7:

| Task | Sekcja docelowa | Co musi się znaleźć |
|---|---|---|
| D5 — item VIEW | content (P3) | modal podglądu przedmiotu (nazwa, opis, statystyki) |
| D6 — narrative state | campaigns (P6) | blok Stan Świata + Inspector pokazują narrative_state |
| D7 — encountery | world (P4) / forge (P8) | UI encounterów generycznych + hook_type w Forge |

> **Praca nad sekcją D wstrzymana** do końca tej fazy. Najpierw wyrównujemy architekturę, potem wracamy do D8+.

---

## Reguły żelazne

1. **Backend bez zmian** — to czysty port frontendu. Jeśli kusi cię zmiana endpointu, to znak że robisz coś innego niż port. Zatrzymaj się.
2. **Anty-grób** — sekcja w jednym miejscu. Usunięcie z monolitu w tym samym commicie co przepięcie trasy.
3. **admin3 żyje** — nie ruszaj `/admin3/` jako całości. Usuwasz tylko portowaną sekcję z jego index.html. `rm -rf admin_panel_v3/` to FADM-DONE, osobny task po Fazie 4.
4. **Parity przed usunięciem** — jeśli `/admin/#<key>` nie robi wszystkiego co `/admin3/#<key>`, NIE usuwaj sekcji z monolitu. Najpierw pełne pokrycie.
5. **/tdd + /document na każdej sekcji** — RED przed kodem, log po akceptacji.

---

## Status implementacji

| Etap | Issue | Status |
|---|---|---|
| FADM-P0 bootstrap (skorupa + shared utils) | [#402](https://github.com/szmidtpiotr/ai-gm/issues/402) | ✅ 2026-06-08 |
| FADM-P1 overview | [#403](https://github.com/szmidtpiotr/ai-gm/issues/403) | ✅ 2026-06-08 |
| FADM-P2 mechanics | [#404](https://github.com/szmidtpiotr/ai-gm/issues/404) | ✅ 2026-06-08 |
| FADM-P3 content (+D5) | [#405](https://github.com/szmidtpiotr/ai-gm/issues/405) | ✅ 2026-06-08 |
| FADM-P4 world (+D7) | [#406](https://github.com/szmidtpiotr/ai-gm/issues/406) | ✅ 2026-06-08 |
| FADM-P5 map | [#407](https://github.com/szmidtpiotr/ai-gm/issues/407) | ✅ 2026-06-08 |
| FADM-P6 campaigns (+B6/B7/D6) | [#408](https://github.com/szmidtpiotr/ai-gm/issues/408) | ✅ 2026-06-08 |
| FADM-P7 dungeons | [#409](https://github.com/szmidtpiotr/ai-gm/issues/409) | ❌ |
| FADM-P8 forge (+D7) | [#410](https://github.com/szmidtpiotr/ai-gm/issues/410) | ❌ |
| FADM-P9 players | [#411](https://github.com/szmidtpiotr/ai-gm/issues/411) | ❌ |
| FADM-P10 tools | [#412](https://github.com/szmidtpiotr/ai-gm/issues/412) | ❌ |
| FADM-P11 system | [#413](https://github.com/szmidtpiotr/ai-gm/issues/413) | ❌ |
| FADM-P12 misc (invites/push/bugreports) | [#414](https://github.com/szmidtpiotr/ai-gm/issues/414) | ❌ |
| FADM-DONE `rm -rf admin_panel_v3/` | — | ❌ (po Fazie 4) |

---

## Dziennik portu

### FADM-P0 — bootstrap skorupy ✅ 2026-06-08

Skorupa `frontend/admin/` żyje: `index.html` (router hash + sidebar 14 sekcji montowanych z listy `SECTIONS`), `shared/` (`api.js`, `toast.js`, `modal.js`, `table.js`, `form.js`). Trasa `/admin/` przepięta z martwego legacy v1 (alias do nieistniejącego `admin_panel/` → 404) na nową skorupę. `/admin3/` nietknięte (200). Sekcje nieportowane → placeholder „w trakcie migracji → /admin3/#key". Spec: `playwright/ux/regression/issue_402_admin_shell.spec.js` (RED: /admin/ 404 → GREEN: skorupa + router + admin3 żyje). Anty-grób: brak — P0 nie portuje żadnej sekcji, monolit nietknięty.

> **⚠️ Gotcha (zapamiętać na każdą zmianę `nginx.conf`):** frontend to `nginx:alpine` z **bind-mountami** (`./frontend:/usr/share/nginx/html` + `./frontend/nginx.conf:/etc/nginx/conf.d/default.conf`). Pliki w `admin/` (mount katalogu) widać od razu — wystarczy odświeżyć przeglądarkę. Ale `nginx.conf` to **mount pojedynczego pliku**: edytor na sshfs zapisuje atomowo (nowy inode), więc kontener dalej trzyma stary inode — `nginx -s reload` NIE wystarczy. Trzeba **zrestartować kontener** (`docker compose -f docker-compose.dev.yml restart frontend`), żeby bind-mount przeładował inode. Zmiana treści sekcji (HTML/JS w `admin/`) = bez restartu; zmiana `nginx.conf` = restart frontendu.

### FADM-P1 — port sekcji overview ✅ 2026-06-08

`sections/overview.js` (`init(panel)`) — port 1:1 z monolitu: 4 karty statystyk + 2 feedy (tury/audyt, `/api/admin/overview`) + 6 zakładek analityki (overview/dice/combat/economy/events/llm, `/api/admin/analytics/*`, filtr 7/30/Wszystko). Backend nietknięty.

**Odkrycie wzorca (walidacja na prostej sekcji — po to były pierwsze):** admin3 to **light theme** (`--canvas` biały, `--t1` ciemny, `--accent` niebieski). Skorupa P0 miała własny dark theme → brak parzystości wizualnej. Rozwiązanie: wyciągnięto cały blok `<style>` admin3 do **`admin/shared/components.css`** (1956 linii, dziedziczony przez WSZYSTKIE przyszłe sekcje), a skorupę przepisano na prawdziwą ramkę admin3 (`.shell`/`.sidebar`/`.topbar`/`.main`, klasy `.nav-item[data-section]`). To jednorazowy koszt na P1 — kolejne sekcje już mają wygląd.

**Smell-fixy przy porcie (FADM-P2):** brak mock-liczb w HTML (start `—`, dane z API), usunięte zmyślone delty/subtitle, ciche `console.warn` → widoczny toast błędu, kontrakty 1:1.

**Anty-grób:** overview usunięte z monolitu (−364 linie: sekcja HTML + wszystkie loadery analityki + handler zakładek + wpisy dispatch/hash). admin3 `/admin3/#overview` → **redirect do `/admin/#overview`**, domyślna sekcja admin3 = `players`, 13 pozostałych sekcji nietknięte (smoke 16/16). Incydentalnie utwardzono współdzielony dispatch `_load` (`Promise.resolve(fn())` — pre-existing crash mechanics przy void-arrow loaderze).

**Testy:** `issue_403_overview.spec.js` (struktura + przełączanie sub-tabów + dane z API + zero błędów JS), `admin3_smoke.spec.js` zaktualizowany (overview→redirect, default players). Wszystko GREEN.

### FADM-P2 — port sekcji mechanics ✅ 2026-06-08

`sections/mechanics.js` (`init(panel)`) — port 1:1 z monolitu: encounter config (interwał/dwell, `/api/admin/world/encounter-config`) + 5 zakładek stab: Statystyki (`/api/admin/stats`), Umiejętności (`/api/admin/skills`, CRUD modal), Poziomy DC (`/api/admin/dc`, inline PATCH), Kondycje (`/api/admin/conditions`, CRUD modal), Archetypy (`/api/admin/archetypes`, inline PATCH). Backend netknięty.

**Gotcha:** `mechPatchEdit` jest SHARED — używana też przez Enemies (world) i Hex Terrain (map) → funkcja POZOSTAŁA w monolicie. Przy portowaniu world/map — przenieść do `shared/` lub zduplikować w modułach.

**Anty-grób:** mechanics usunięte z monolitu (−384 linie: sekcja HTML + _mechLoaded + _loadStats/Skills/DC/Conditions/Archetypes + loadEncounterConfig/saveEncounterConfig + _loadMechanicsTab + event handler + openAddSkillModal/EditSkillModal + _openSkillForm + openAddConditionModal/EditConditionModal + _openConditionForm + deleteSkill/deleteCondition + wpis dispatch + subtab hash). `mechPatchEdit` POZOSTAJE. admin3 `/admin3/#mechanics` → **redirect do `/admin/#mechanics`**. Smoke spec: mechanics usunięte z SECTIONS, dodany test redirect.

**Testy:** `issue_404_mechanics.spec.js` (struktura 5 tabów + encounter config + stats 8s load + skills tab przełączenie + admin3 alive). `admin3_smoke.spec.js` zaktualizowany. 8/8 GREEN.

### FADM-P3 — port sekcji content (+D5) ✅ 2026-06-08

`sections/content.js` (`init(panel)`) — port 1:1 z monolitu: 6 zakładek stab — Broń (`/api/admin/weapons`), Zbroje (`/api/admin/items?item_type=armor`), Przedmioty (`/api/admin/items`), Materiały eksploatacyjne (`/api/admin/consumables`), Tabele łupów (`/api/admin/loot-tables`), Czary (`/api/admin/spells`). Tabela łupów była ukryta w monolicie (brak przycisku tab) — wyeksponowana jako 6. tab w module. Backend netknięty.

**D5 item VIEW:** klik na nazwę przedmiotu w tabeli → modal read-only (nazwa, opis, statystyki, miniatura obrazu). Zaimplementowane przez `_openItemViewModal(rec)`. Triggery via `window._contentViewRec`.

**Smart Entry (Kreator AI):** pełny port overlay SE — lazy init, schema fetch, LLM chat, form fill. Tabele: weapons/items/consumables/enemies. Funkcje eksponowane na `window._contentImgModal`, `window._contentViewRec`, `window._contentEditSpell`, itp. (JS modules nie wystawiają globalnych funkcji automatycznie — `window._contentXxx` pattern).

**_ROW_REGISTRY:** dodano entry dla `weapons-table` (monolitu brakowało — edycja broni była zepsuta). Broń teraz ma pełny CRUD przez `_wireRowActions`.

**Gotcha:** `_ROW_REGISTRY`, `_wireRowActions`, `_openGenericEditModal`, `_genericDelete` są SHARED — używane też przez world (enemies). Pozostają w monolicie. `_loadEnemiesContent` i `openEnemyImageModal` — też shared — pozostają. `openLootEntriesModal` wywoływana w world section (linia ~6359 monolitu) — pozostaje w monolicie.

**Anty-grób:** content usunięte z monolitu (−1068 linii fazy 1: sekcja HTML 2297-2929 + `_contentLoaded` Set + ROW_REGISTRY entries armor/items/consumables + `_loadContentTab` + `_loadWeapons`/`_loadArmor`/`_loadItems` + `_loadConsumables` przez `deleteSpell` z pominięciem `_loadEnemiesContent`; −33 linie fazy 2: content-tabs event handler + weapons-table event handler + weapon save reload + smart-entry-saved weapons/items/consumables handlers + wpis content w `_load dispatch` + bulk delete reload + `openItemImageModal` reloadMap). admin3 `/admin3/#content` → **redirect do `/admin/#content`**. Smoke spec: content usunięte z SECTIONS, dodany test redirect.

**Testy:** `issue_405_content.spec.js` (6 tabów + weapons load >0 rows + spells tab switch + admin3 alive). `admin3_smoke.spec.js` zaktualizowany. 4/4 GREEN.

### FADM-P4 — port sekcji world ✅ 2026-06-08

`sections/world.js` (`init(panel)`) — port 1:1 z monolitu: 4 zakładki `data-wtab` — NPC (`/api/admin/npcs`), Wrogowie (`/api/admin/enemies`), Tabele Łupów (`/api/admin/loot-tables`), Oczekujące (`/api/admin/world/pending/*`).

**Przeniesione dodatkowo:** `openLootEntriesModal` — w monolicie nie istniała po P3 (content usunął ją jako `_openLootEntriesModal`). W world.js zaimplementowana ponownie z content.js source. Obrazy enemy (`openEnemyImageModal`, `eiOpenGallery`, `eiPickGallery`, `_buildEnemyImagePrompt`) i NPC (`openNpcImageModal`, `niOpenGallery`, `niPickGallery`, `_buildNpcImagePrompt`) portowane w całości.

**Poprawka:** `openEnemyImageModal`/`eiPickGallery` — użyto `_loadEnemies()` zamiast `_loadEnemiesContent()` (dead function po P3). ROW_REGISTRY dla NPC z pełnym CRUD.

**Anty-grób:** world usunięte z monolitu (−1206 linii: section-world HTML + world-tabs handler + ROW_REGISTRY npcs-table + `_loadWorldTab` + `_loadNPCs` + `openShopInventoryModal` + `_loadBestiaryLoot` + `_openAddLootTableModal` + `_submitAddLootTable` + `_deleteBestiaryLootTable` + `_loadBestiaryPending` + `reviewEntityBestiary` + `openPending*/savePending*` (NPC/Enemy/Item) + `_loadEnemies` + `deleteEnemy` + `openEnemyFormModal` + `saveEnemyForm` + `_worldAddAction` + wszystkie image modals enemy/NPC). admin3 `/admin3/#world` → **redirect do `/admin/#world`**. Smoke spec: world usunięte z SECTIONS, dodany test redirect.

**Testy:** `issue_406_world.spec.js` (4 taby + NPC load >0 rows + enemies tab switch + admin3 alive). `admin3_smoke.spec.js` zaktualizowany. 4/4 GREEN, 16/16 smoke GREEN.

### FADM-P5 — port sekcji map ✅ 2026-06-08

`sections/map.js` (`init(panel)`) — port 1:1: 5 zakładek `data-mtap` — budowniczy świata (SVG hex grid), generuj świat (proceduralnie), lokacje (drzewo parent/child), teren (`/api/admin/hex-terrain-config`), oczekujące (lokacje + heksy submappable).

**Największa sekcja dotąd (+2009 linii w map.js).** Złożone podsystemy: `_wb*` world builder (paint/select, teleporty, location markers, zoom/pan, ResizeObserver), `openSubmapModal` (edytor podmapy z paintem + przypisaniem lokacji), `_renderLocTree` (akordeon parent/child), `openLocImageModal` (generowanie/galeria obrazów lokacji), `openLocNpcModal`, terrain CRUD z `mechPatchEdit` inline.

**Cache na re-mount:** `_worldLoaded.clear()` na starcie `init()` — DOM jest czyszczony przy każdym mount, więc cache zakładek resetowany aby budowniczy odrysował SVG od nowa (różnica wobec world.js — strictly safer).

**Inline globals:** ekspozycja nazw bare przez `Object.assign(window, {...})` (port zachowuje oryginalne nazwy onclick — zero przepisywania handlerów). `mechPatchEdit` skopiowany lokalnie (shared helper). Generic edit/delete (`_openGenericEditModal`/`_genericDelete`/`_wireRowActions`) + wpis `locations-table` (noDelete).

**Anty-grób:** map usunięte z monolitu (−1758 linii): section-map HTML + map-tabs handler + `locations-table` ROW_REGISTRY + `_loadMapTab` + `hexmap*` + drzewo lokacji + `openLocNpcModal` + `_loadPendingLocations` + `pendingGenSubmap` + `openSubmapModal` + `approveKanon` + `reviewEntity` + terrain + cały world builder + `openLocImageModal`. **Martwy `_loadPendingReview` (zero callerów) usunięty.** Dispatcher `_load` — wpis `map:` sprzątnięty. admin3 `/admin3/#map` → **redirect do `/admin/#map`**. CSS `.wb-*` już w `components.css`; `.smod-*`/`.whx`/`.wloc-marker` to selektory bez stylów (inline w JS).

**Testy:** `issue_407_map.spec.js` (5 tabów + SVG heksy `wb-svg polygon.whx` >0 + paleta terenu + lokacje load + teren load + admin3 alive). `admin3_smoke.spec.js` zaktualizowany (map redirect + usunięte z SECTIONS). 5/5 GREEN, 16/16 smoke GREEN, 4/4 world (#406) bez regresji.

### FADM-P6 — port sekcji campaigns ✅ 2026-06-08

`sections/campaigns.js` (`init(panel)`) — port 1:1: tabela kampanii (widok tabela/karty toggle), 8-tabowy modal kampanii (overview/plan/turns/map/npcs/workshop/world/inspector), admin komendy `/debug set-hp`, Warsztat kampanii (LLM), wstrzykiwanie spotkań.

**Adapatacje wobec monolitu:**
- `deleteCampaign` / `_bulkDeleteCampaigns`: usunięto `_sectionLoaded.delete('campaigns')` (nie istnieje w module) → bezpośrednie `_loadCampaigns()` po operacji
- Inspector tab: raw `fetch()` z `_ADMIN_TOKEN_KEY` zastąpiony przez `apiFetch()` (auth obsługiwany przez shared/api.js)
- Moduł definiuje lokalne `_timeAgo`, `_hp`, `_showToast`, `filterTableGeneric` (te z monolitu globalnych, niezdostępne w module)

**Anty-grób:** campaigns usunięte z monolitu (−958 linii): section-campaigns HTML + `filterCampaigns` + `_campsData`/`_loadCampaigns`/`_renderCampCards`/`_setCampView` + `deleteCampaign`/`_bulkDeleteCampaigns` + `_CAMP_CMDS` + cmd helpers + `_campModalResurrect` + `_renderAdminHexMap` + `_HEX_TYPES` + `_showHexEditModal` + `openCampaignModal` + `_loadCampTab` (8 tabów) + `advanceCampScene` + `_loadWorkshopEncounters` + `_injectEncounterFromWorkshop` + `sendWorkshopMsg`. Dispatcher `_load` — wpis `campaigns:_loadCampaigns` sprzątnięty. admin3 `/admin3/#campaigns` → **redirect do `/admin/#campaigns`**. `_loadPdrawerCamps` (players drawer) — NIE portowana, zostaje w monolicie (należy do players sekcji).

**Testy:** `issue_408_campaigns.spec.js` (tabela renderuje + dane z API + modal 8 tabów + admin3 alive + redirect). `admin3_smoke.spec.js` zaktualizowany (campaigns redirect + usunięte z SECTIONS). 5/5 GREEN, 16/16 smoke GREEN.

---

## Referencje

- Plan źródłowy: `game_mechanics.md` → **CZĘŚĆ AE — Audyt Panelu Admina (admin_panel_v3)**
- Monolit do portowania: `frontend/admin_panel_v3/index.html` (sekcje `data-section="<key>"`)
- Skill TDD: `/tdd` (RED-GREEN-REFACTOR + Playwright spec + aktualizacja notes/game_mechanics)
- Skill dokumentacji: `/document` (język nietechniczny, bloki Dlaczego, tabele statusu)
- Serwer DEV: `claude@192.168.1.61`, rebuild `docker compose -f docker-compose.dev.yml up -d --build frontend`, weryfikacja `https://aigm-dev.studio-colorbox.com/admin/`
