# Admin Panel Mobile — design spec

**Data:** 2026-06-19
**Milestone GitHub:** `Admin Panel Mobile`
**Status:** zatwierdzony do wdrożenia (fazami)

## Problem

Modularny panel admina (`frontend/admin/`) jest desktop-first. Na telefonie renderuje się jako **pomniejszony desktop** — pełny sidebar (17 sekcji), mikroskopijny tekst, wszystko wciśnięte. Patrz screenshot z 2026-06-19 (@~390px).

Kluczowe odkrycie: scaffolding responsywny **istnieje w kodzie, ale jest martwy**. `@media (max-width:768px)` (który chowa sidebar → bottom-nav/hamburger) nigdy się nie odpala, bo jakiś element rozpycha layout viewport powyżej 768px (kandydat: tabele `min-width:560px` + sidebar 228px = >788px). Przeglądarka widzi „szeroki" ekran, nie wchodzi w tryb mobile, skaluje cały desktop do szerokości ekranu.

## Cel

Etap 1 (teraz): admin **używalny w biegu** z telefonu — szybkie sprawdzenia, lekka edycja.
Cel docelowy: **pełny admin** działa na mobile, fazami.

## Stan zastany (fakty)

- Viewport meta: **jest** (`index.html:5`).
- Shell: CSS Grid `grid-template-columns: var(--sidebar-w) 1fr` (`components.css:77`), sidebar 228px.
- Istnieje 7 `@media` w `components.css` (768px, 480px) — m.in. chowanie sidebara (`:889`), bottom-nav, hamburger. **Martwe przez overflow.**
- 18 sekcji JS (`frontend/admin/sections/`), 19 832 linii. Najcięższe: forge.js (194K), map.js (121K), system.js, campaigns.js, world.js, content.js, tools.js, dungeons.js.
- 8 realnych `<table class="data-table">` z `min-width:560px` (content.js).
- ~2328 inline `style=` z hardcoded px rozsianych po sekcjach.
- Mapa świata: SVG hex (map.js `:2183`, campaigns.js viewBox), brak zoom/pan dotykowego.
- Modale (`shared/modal.js`): `max-width` + `width:100%` — już ~ok na mobile.
- CSS scentralizowany w `shared/components.css` (1956 linii) — jeden punkt kontroli.

## Decyzje projektowe

1. **Strategia tabel = C (hybryda).** Card-view (wiersz → karta etykieta:wartość) dla list (campaigns, bugreports, players). Poziomy scroll + sticky pierwsza kolumna dla gęstych tabel danych gdzie liczy się porównanie kolumn (weapons/items/loot w content.js).
2. **Nawigacja:** 18 sekcji nie zmieści się w bottom-nav. Mobile dostaje pełną listę sekcji w szufladzie/hamburgerze.
3. **Hex mapa:** do M5 tylko skaluje się do podglądu (viewBox) + blokada edycji z notką „edytuj na desktopie". Pełna obsługa dotykowa (pinch-zoom/pan/tap edycja) = osobna faza końcowa M5.
4. **Breakpointy docelowe:** 390px (telefon), 768px (tablet). Test na realnym urządzeniu: Moto G32 (Appium).
5. **Bez przepisywania architektury.** Retrofit responsywny: globalny CSS + per-sekcja klasy zamiast inline-px. Root-cause overflow to tani fix, nie rewrite.

## Fazy (każda = osobne issues pod milestone)

### M0 — Fundament responsywny (blokuje resztę)
Globalne reguły w `components.css`, raz a dobrze.
- **M0-1 (blocker):** Mobile breakpoint nie odpala — strona renderuje jako pomniejszony desktop. Znaleźć element rozpychający viewport, `overflow-x:hidden` + `max-width:100vw`, ograniczyć winowajców `min-width`. Weryfikacja: screenshot @390px = tryb mobile, nie shrunk desktop.
- **M0-2:** Nawigacja mobilna — 18 sekcji w szufladzie/hamburgerze (nie bottom-nav z 18 ikonami).
- **M0-3:** Tabele — strategia hybryda C: utility classy `.data-table--cards` (card-view) i `.data-table--scroll` (scroll+sticky) w `@media`.
- **M0-4:** Formularze i gridy 2-col → 1-col `<768px`; touch-targety min 44px (przyciski, ikony 🗑/✓).
- **M0-5:** Hex mapa — skalowanie do podglądu + blokada edycji z notką na mobile (quick-win, pełna obsługa w M5).

### M1 — Sekcje „w biegu" (opcja 1: read + lekka edycja)
overview, campaigns (lista+przegląd), bugreports, players (LLM toggle), invites, push, system (toggle ustawień). Osobny issue per sekcja lub zgrupowane lekkie.

### M2 — Sekcje contentowe (ciężkie tabele)
content.js (8 tabel), world.js, mechanics, dungeons. Card-view/scroll wg C, edycja inline mobilna.

### M3 — Forge
forge.js (194K, największy). Osobna faza ze względu na rozmiar/ryzyko.

### M4 — Polish + test urządzenie
Moto G32 (Appium) regresja wszystkich sekcji @390/@768, fix-up znalezionych usterek.

### M5 — Hex mapa: pełna obsługa dotykowa
pinch-zoom/pan/tap edycja, map.js + campaigns hex. Faza końcowa, najtrudniejsza.

## Weryfikacja (definicja „done" per faza)

- Screenshot @390px każdej dotkniętej sekcji — brak poziomego scrolla strony, czytelny tekst, klikalne targety.
- Brak regresji desktop (≥1024px wygląda jak wcześniej).
- M4: przejście realnym urządzeniem przez kluczowe flow.

## Poza zakresem

- Player UI (`frontend/front/`) — osobny temat.
- Legacy admin `admin_panel_v2/` — nie ruszamy.
- Przepisanie architektury sekcji / usuwanie inline-styli „przy okazji" poza tym co konieczne dla responsywności.
