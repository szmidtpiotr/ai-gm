# frontend_design.md — System projektowania nowego frontendu gracza (AI-GM)

> **Status:** żywy dokument. Powstał 2026-06-17.
> **Zakres:** TYLKO frontend gracza (`frontend/front/`). Admin panel = osobna sprawa, NIE dotyczy tego pliku.
> **Cel:** przygotować kompletny, dwufazowy prompt dla **Claude Design** tak, aby zbudować nowy UI w React, który odwzorowuje **1:1** każdą funkcjonalność obecnego frontendu — i żeby migracja gotowego projektu z chmury była przyjemna i prosta.

---

## 1. Cel i jak używać tego pliku

Ten plik ma **dwie role naraz**:

1. **Master prompt dla Claude Design** (sekcje 3 i 4) — gotowe do wklejenia bloki. Faza 0 = eksploracja wizualna, Faza 1 = build pełnego systemu.
2. **Living ledger / rejestr 1:1** (sekcje 5–8) — źródło prawdy: co MUSI istnieć w nowym UI. Każdy nowy feature dopisywany tutaj (sekcja 9 mówi jak). Dzięki temu po skończeniu implementacji wszystkich funkcji mamy listę do odhaczenia 1:1 w nowym UI.

**Procedura użycia:**
1. Dziś: wklej **PROMPT FAZA 0** (sekcja 3) do Claude Design → dostajesz 3–4 kierunki wizualne (mobile + desktop) na 3 kluczowych ekranach.
2. Wybierasz kierunek (lub mix). Uzupełniasz **sekcję 6 (Design Tokens)** wybranymi wartościami.
3. Później: wklej **PROMPT FAZA 1** (sekcja 4) → build całego Design Systemu + wszystkich ekranów z Feature Ledger.
4. Każda nowa funkcja w grze → aktualizujesz Feature Ledger (sekcja 7) wg konwencji z sekcji 9.

> **Czy można odpalić Fazę 0 teraz, zanim ledger jest kompletny?** TAK. Faza 0 jest samodzielna — generuje tylko kierunek wizualny + tokeny na 3 ekranach. Pełny ledger jest potrzebny dopiero w Fazie 1. Dopisywanie sekcji później nie psuje Fazy 0.

---

## 2. Stack technologiczny (cel migracji)

Deployment: **opcja B** — dozwolony build step. Multi-stage Dockerfile buduje bundle, Nginx serwuje `dist/` (runtime bez zmian względem dziś).

| Warstwa | Wybór | Uzasadnienie |
|---|---|---|
| Framework | **React 18 + Vite** | Claude Design generuje React natywnie → migracja 1:1, najmniej ręcznego tłumaczenia |
| Style | **Tailwind CSS** | Generowane natywnie przez Claude; design tokens jako konfiguracja theme |
| Komponenty | **shadcn/ui** (na Radix) | gotowe, accessible modale / sheety / dropdowny / dialogi — mamy ~30 modali |
| Server-state / auto-refresh | **TanStack Query** | polling, invalidacja, cache tur/combat/inventory bez ręcznych pętli |
| Realtime (multiplayer, combat) | cienka warstwa **WebSocket/SSE → Zustand store** | rundy MP, enemy-turn, reaction window |
| Client-state | **Zustand** | lekki global store (currentHero, activeCombat, dungeonRunState) |
| Routing | **React Router** | ekrany = trasy, lazy-load per trasa |
| 3D dice | **three.js + cannon ZOSTAJE**, opakowane w React wrapper | nie przepisujemy fizyki kości, tylko komponent-most |
| Build / deploy | multi-stage Dockerfile → Nginx serwuje `dist/` | runtime identyczny jak dziś |

---

## 3. >>> PROMPT FAZA 0 — Eksploracja kierunków wizualnych (WKLEJ DO CLAUDE DESIGN)

> Ten blok jest samodzielny. Można go wkleić od razu. Output = 3–4 kierunki wizualne do wyboru, NIE pełna aplikacja.

```
Jesteś senior product designerem. Buduję nowy frontend dla narracyjnej gry RPG z mistrzem gry sterowanym przez AI ("AI Game Master"). Narracja w grze jest po polsku, ciemne fantasy. Gra jest grana w przeglądarce.

WAŻNE: NIE buduj jeszcze całej aplikacji. W tej fazie chcę 3–4 RÓŻNE KIERUNKI WIZUALNE (design directions) do wyboru. Każdy kierunek ma być wyraźnie inny w nastroju, typografii, kolorze i gęstości.

Stack docelowy: React 18 + Vite + Tailwind CSS + shadcn/ui. Generuj kod w tym stacku.

PRIORYTET URZĄDZEŃ: 70% użytkowników to mobile, 30% desktop. Projektuj MOBILE-FIRST. Desktop = progresywne wzbogacenie (NIE odwrotnie).

Dla KAŻDEGO z 3–4 kierunków pokaż te 3 kluczowe ekrany (niosą 90% charakteru UI):
  1. EKRAN GRY (narracja) — strumień wiadomości czatu: dymki gracza, dymki Mistrza Gry (GM), dymki systemowe; nagłówek z paskiem HP (i many dla maga); pole wpisywania akcji u dołu (composer) z przyciskiem mikrofonu (voice) i wysyłania.
  2. EKRAN WALKI (combat) — kompaktowy baner walki (#967, Wariant D): każdy uczestnik to jedna linia z inline paskiem HP, w strefach ZWARCIE (melee) / DYSTANS (ranged); licznik rundy; wskaźnik czyja tura; przyciski akcji (Atak / Akcja / Zbliż się).
  3. KARTA POSTACI (character sheet) — staty (STR/DEX/CON/INT/WIS/CHA/LCK), paski HP/Mana/XP, poziom, warunki/statusy, ekwipunek (8 slotów na ciele + plecak), złoto.

Dla każdego ekranu pokaż 2 widoki: MOBILE (priorytet) i DESKTOP.

Każdy kierunek ma dostarczyć DESIGN TOKENS:
  - paleta kolorów (bg, surface, primary/accent, success, danger, tekst) jako zmienne
  - typografia (font nagłówków + font treści, skala rozmiarów)
  - spacing scale, border-radius, cienie
  - styl dymków GM vs gracza vs system

Sugerowane (ale nie wymagane) różne nastroje kierunków, by były naprawdę odmienne:
  - A: "Dark Grimoire" — ciemny, pergamin/złoto, serif fantasy (Cinzel/Playfair), atmosferyczny
  - B: "Clean Minimal-Fantasy" — czysty, dużo oddechu, nowoczesna typografia, subtelne akcenty fantasy
  - C: "Tactical HUD" — gęsty, taktyczny, jak interfejs gry strategicznej, mocny nacisk na combat
  - D: "Cozy Parchment" — ciepły, przytulny, jasny pergamin, zaokrąglenia, przyjazny

Zasady mobile, których trzymaj się w każdym kierunku:
  - bottom tab bar na mobile do szybkiej nawigacji (czat / postać / ekwipunek)
  - panele jako sheety wysuwane z dołu (bottom sheet)
  - obsługa safe-area insets (notch / home indicator)
  - duże cele dotykowe
  - na desktopie te same panele mogą stać się stałymi side-panelami (np. karta postaci jako prawy panel)

Dostarcz: dla każdego kierunku zestaw ekranów (mobile+desktop) + blok design tokens + 1-zdaniowy opis nastroju. Na końcu krótka rekomendacja, który kierunek najlepiej pasuje do mobilnej, narracyjnej gry RPG.
```

---

## 4. >>> PROMPT FAZA 1 — Build pełnego Design Systemu (WKLEJ PO WYBORZE KIERUNKU)

> Uzupełnij `[WYBRANY KIERUNEK]` i wklej tokeny z sekcji 6 przed wysłaniem. Faza 1 odwołuje się do pełnego Feature Ledger (sekcja 7) — wklej go też lub jego istotną część.

```
Kontynuujemy projekt frontendu gry RPG z AI Game Masterem. Wybrałem kierunek wizualny: [WYBRANY KIERUNEK / opis miksu]. Oto design tokens do użycia: [WKLEJ TOKENY Z SEKCJI 6].

Stack: React 18 + Vite + Tailwind CSS + shadcn/ui + TanStack Query (server-state) + Zustand (client-state) + React Router. MOBILE-FIRST (70% mobile / 30% desktop).

Zadanie: zbuduj kompletny Design System + wszystkie ekrany i komponenty z poniższej listy (Feature Ledger). Zachowaj 1:1 funkcjonalność.

Najpierw zbuduj fundament Design Systemu:
  - konfigurację Tailwind theme z tokenami
  - bazowe komponenty: Button, Input, Sheet (bottom sheet mobile / side panel desktop), Dialog/Modal, Card, Badge/Chip, ProgressBar (HP/Mana/XP), Avatar, Toast
  - layout aplikacji: nagłówek, obszar treści, bottom tab bar (mobile), routing
  - wzorce responsywne: jak sheet → side panel na desktop

Następnie zbuduj ekrany i modale z Feature Ledger [WKLEJ SEKCJĘ 7].

Dla stanu i danych użyj kontraktu z [WKLEJ SEKCJĘ 8] — endpointy API, polling/WS, kształt store.

Zasady:
  - mobile-first, desktop jako wzbogacenie
  - każdy ekran = osobna trasa (lazy-loaded)
  - każdy modal = komponent shadcn Dialog/Sheet
  - server-state przez TanStack Query (polling tam gdzie dziś jest polling — patrz tabela realtime)
  - 3D dice: zostaw miejsce na wrapper opakowujący istniejący three.js/cannon (nie przepisuj fizyki)
  - kod gotowy do wklejenia do repo, modularny, jeden komponent = jeden plik
```

---

## 5. Notatki z Fazy 0 — WYBRANY KIERUNEK: „ŻAR"

> Zdecydowano 2026-07-05 (Piotr). Makiety: `temp-img/design-concepts/` (koncepty 1-4 + iteracje zar2…zar9, HTML + PNG mobile/desktop).

- **Kierunek wybrany: ŻAR** — ciepły mrok, narracja jak książka (serif), akcent = tlący się żar. Odrzucone: RAPORT (za zimny), KARTA (jasny, tylko dzień), MGŁA (pierścienie/glass = za cyberpunkowe do fantasy).
- **Zasada kontrastu (rdzeń kierunku): kod typu treści temperaturą.** Świat/narracja GM = ciepły dymek z tłem. Akcja gracza = karta ember, wyrównana **do prawej** (czat). Mechanika (rzuty/systemowe) = ciepła konwencja (nie zimna stal — poprawka z v2), mono, tabela, mniejsza. Rzut **gracza** = prawo/ember; rzut **wroga** = lewo/krwawy (konwencja GM). Nat 20 = złoty flash karty, Nat 1 = krwawy.
- **Zaakceptowane ekrany (komplet trzonu):** login · bohaterowie (hub) · kampanie (breadcrumb + Historia) · kreator (5-krokowy stepper) · profil · ekran gry · karta postaci (staty/umiej./czary) · ekwipunek (sylwetka Diablo-overlap + toggle sylwetka/lista) · mapa (hex + panel podróży) · WALKA (baner kompakt jednokolumnowy — strefy=lekkie nagłówki, uczestnicy jedno pod drugim, zwijanie) · reakcja SF10 · sheet akcji/czarów · kość 3D (three.js ZOSTAJE, tylko reskin karty) · koniec+łup · śmierć · zwycięstwo-loch · level-up · dziennik · sklep · lobby MP · podróż-cinematic · drop-celebration · paleta komend · bug-report.
- **Reguły mobilne (zamrożone):** topbar bez imienia bohatera (zegar+pora stack + tylko główny quest; dzień+miejsce → zakładka Mapa); HP/Mana = 2 cienkie paski nad dolnym paskiem tabów; dolny pasek tabów przewijany poziomo z **przypiętą** „Opowieścią"; panele = zakładki w obrębie gry (nie osobny ekran); combat oszczędza pionową przestrzeń (baner kompakt + zwijanie). Desktop: przełączanie zakładek karty postaci = lewy pionowy rail; panele mogą być stałym prawym railem.
- **Ikony:** jeden zestaw — **Phosphor** (web font; `ph` / `ph-fill`). Zastępuje emoji (spójność + brak braków glifów). Portret postaci = art/sylwetka (nie emoji, nie w topbarze).

---

## 6. Design Tokens — ŻAR (ŹRÓDŁO PRAWDY dla Fazy 1)

> Finalne po iteracjach zar2→zar9. Do Tailwind theme (`tailwind.config` → `theme.extend.colors` + CSS vars w `:root`).

```css
:root{
  /* Powierzchnie — hue stały (ciepły), zmienia się tylko jasność */
  --bg:            #14100c;   /* kanwa / najgłębsze tło */
  --surface:       #1e1811;   /* topbar, paski, tabbar */
  --gm-bubble:     #221a12;   /* tło dymka narracji GM */
  --player-card:   #2a1f14;   /* karta akcji gracza + karta rzutu gracza (ember) */
  --mech-card:     #20180f;   /* karta mechaniki/rzutu (ciepła, NIE zimna stal) */
  --inset:         #0d0a07;   /* wnętrza pasków HP/Mana (inset) */

  /* Tekst — 3 poziomy */
  --text:          #f2e8d8;   /* primary */
  --text-2:        #c9b99f;   /* secondary */
  --text-3:        #8f8069;   /* muted / metadane */

  /* Akcent i semantyka */
  --ember:         #ff7a3d;   /* akcent główny (żar) — CTA, aktywny aktor, gracz */
  --ember-glow:    #ffb07a;   /* jaśniejszy żar — hover, highlight, em w prozie */
  --gold:          #e8c15a;   /* inicjatywa, nagłówki mechaniki, krytyk, złoto */
  --gold-glow:     #ffdd88;   /* zwycięstwo / krytyk hero */
  --success:       #a8c983;   /* zieleń (leczenie, gotowy) */
  --mech-ok:       #c8a24a;   /* „sukces" w karcie rzutu (ciepłe złoto, nie zielone) */
  --danger:        #e8604f;   /* krew / wróg / porażka */
  --danger-glow:   #ff8a7a;
  --mana:          #82a7c7;   /* mana / dystans / chłodny akcent info */
  --rare:          #b58cf0;   /* item rzadki */
  --epic:          #e8963c;   /* item epicki */

  /* Obrysy — progresja przez opacity, nie solidny hex */
  --line:          rgba(242,232,216,.12);
  --line-soft:     rgba(242,232,216,.06);
  --line-ember:    rgba(255,122,61,.45);
  --line-mech:     rgba(232,193,90,.26);
  --line-danger:   rgba(232,96,79,.40);

  /* Typografia */
  --font-serif:  'Literata', Georgia, serif;    /* proza GM, tytuły, nazwy */
  --font-ui:     'Inter', system-ui, sans-serif; /* UI, przyciski, etykiety */
  --font-mono:   'JetBrains Mono', monospace;    /* liczby, rzuty, kody, HP */
  /* skala: 11 (mikro) · 13 (label) · 15 (body UI) · 16-17 (proza) · 18-27 (tytuły) */

  /* Promienie */
  --r-sm: 8px;   /* input, mała ikona */
  --r-md: 12px;  /* przycisk, karta rzutu */
  --r-lg: 16px;  /* karta, panel */
  --r-xl: 20px;  /* modal, arkusz */
  --r-pill: 999px;

  /* Spacing: baza 4px (4/6/8/12/16/20/24) */
  /* Depth: głównie obrysy + subtelne tło; cienie tylko dla warstw pływających */
  --shadow-float: 0 8px 32px rgba(0,0,0,.35);
  --shadow-modal: 0 24px 70px rgba(0,0,0,.6);
}
```

**Ikony:** Phosphor (`@phosphor-icons/web`), warianty `ph` (regular) + `ph-fill`. Jeden zestaw w całym UI.

**Konwencja dymków / kart (rdzeń kontrastu):**

| Typ treści | Wyrównanie | Tło | Font | Znak |
|---|---|---|---|---|
| Narracja GM | lewo, max 94% | `--gm-bubble` + lewy border ember | serif | nagłówek „MISTRZ GRY · tura N" (ember) |
| Akcja gracza | **prawo**, max 82% | gradient ember na `--player-card`, prawy border | serif italic | „TWOJA AKCJA ◀" (ember-glow) |
| Rzut gracza | **prawo** | `--player-card`, obrys ember, mono | mono | Nat 20 → złoty flash |
| Rzut wroga | **lewo** | `--gm-bubble`, lewy border krwawy, mono | mono | trafienie → `--danger` |
| Systemowe | pełna szer., wyśrodk. | kreskowany obrys `--line-mech` | mono | złoto, dyskretne |

---

## 7. FEATURE LEDGER — pełny inwentarz frontendu gracza (1:1)

> Źródło prawdy: co musi istnieć w nowym UI. Format wpisu w sekcji 9.
> Prefill z inwentaryzacji obecnego `frontend/front/` (2026-06-17). Kolumna "React" wypełniana podczas migracji.

### 7.1 Ekrany (13)

| ID | Ekran | DOM (stary) | Opis | React |
|---|---|---|---|---|
| F-01 | Login | `#login-screen` | Email/hasło, linki rejestracja/reset | — |
| F-02 | Rejestracja | `#register-screen` | Tworzenie konta, karta zapraszającego | — |
| F-03 | Weryfikacja email | `#verify-email-screen` | Potwierdzenie + resend | — |
| F-04 | Zapomniane hasło | `#forgot-password-screen` | Wysłanie linku reset | — |
| F-05 | Reset hasła | `#reset-password-screen` | Nowe hasło z linku | — |
| F-06 | Onboarding | `#onboarding-screen` | Cinematic powitalny + wybór theme (dark_fantasy/classic) | — |
| F-07 | Profil | `#profile-screen` | Avatar, nazwa, email, statystyki kroniki, znajomi, zaproszenia, konfiguracja LLM, wygląd, bezpieczeństwo | — |
| F-08 | Lista bohaterów | `#heroes-screen` | Karuzela postaci + "Nowy bohater" | — |
| F-09 | Lista kampanii | `#campaigns-screen` | Wybór kampanii, typ przygody (Nowa/Gotowa/Loch), aktywne, empty state; completed/archived → sekcja Historia (read-only), klik → viewer, nie enterGame (#1095) | ✅ front-v2 `Campaigns.tsx` (KROK 3 #1231): breadcrumb Bohaterowie › hero, 3 typy, aktywne z paskiem+Graj+usuń, Historia→`CampaignHistory.tsx` viewer (#1095) |
| F-10 | Nowa kampania | `#new-campaign-screen` | Kreator nazwy kampanii | ✅ front-v2 (KROK 3 #1231): dialog nazwy w `Campaigns.tsx` → POST /campaigns (solo/pre_built/dungeon) + assign-campaign → /gra |
| F-11 | Kreator postaci | `#character-wizard-screen` | 5 kroków: Krok 0 wybór rasy (Człowiek/Krasnolud) → tożsamość → staty → umiejętności → finalizacja (#976 R7) | ✅ front-v2 `CreateCharacter.tsx` (KROK 3 #1232): Rasa→Tożsamość→Cechy(+/- z modami+HP/Mana/Init)→Umiej.→Finał; POST /characters→finalize-sheet; pula skilli z serwera |
| F-12 | Ekran gry | `#game-screen` | Główny gameplay: kompaktowy "pasek przygody" (1 rząd ~50px: avatar · imię+HP hairline · chip czasu ☀/🌙 · 🗺 · ☰ menu; auto-hide przy scrollu; w lochu klaster krypty inline zamiast 2. piętra — #952) + log narracji + composer; hostuje panele combat/inventory/settings | ✅ front-v2 `Game.tsx` (KROK 4 #1233): topbar zegar+pora(stack)+tylko główny quest+mapa/menu BEZ imienia; log narracji (`NarrationLog`) + composer (`Composer`); HP/Mana hairline nad tabbarem (`Vitals`/`TabBar`), desktop prawy rail; TanStack polling `useTurnStream`/`useCampaignClock` (auto-refresh bez F5); bootstrap `__AI_GM_OPEN` gdy 0 tur |
| F-13 | Lobby (MP) | `#lobby-screen` | Multiplayer pre-game: team builder, zaproszenia, timer | — |

### 7.2 Modale i overlaye (~30)

| ID | Modal | Trigger | Kluczowe elementy | React |
|---|---|---|---|---|
| F-20 | Rzut kośćmi (3D) | rzut na test / combat / `/roll` | canvas 3D, d4–d100, karta wyniku | ✅ front-v2 (FE9 #1236): `components/game/combat/Dice3DOverlay.tsx` — pełnoekranowy overlay owijający silnik dice-box-threejs (`lib/dice3d.ts`), po zatrzymaniu odsłania kartę rzutu (F-52) i zwija się do feedu; fallback 2D |
| F-21 | Karta postaci (panel) | nagłówek / swipe | zakładki Staty / Ekwipunek / Czary (mag) / Wygląd; swipe-down zamyka tylko gdy lista na szczycie (scrollTop guard #1091); overscroll-behavior:contain blokuje pull-to-refresh | ✅ front-v2 (KROK 5 #1234): panele = zakładki w grze (nie osobny ekran). 5 paneli — Postać/Umiejętności/Czary/Ekwipunek/Reputacja&opis. Przełącznik: desktop lewy pionowy rail (`components/game/GameRail.tsx`), mobile górny poziomy scroll (`components/sheet/CharacterSheet.tsx`) + dolny tabbar (`shell/TabBar.tsx`) — wszystkie sterują `appStore.gameTab`. Wspólna definicja zakładek `components/sheet/tabs.ts` |
| F-22 | Ustawienia (panel) | ikona koła zębatego / swipe | push, wygląd tekstu (font/rozmiar/preview), metadane dymków, voice (TTS/STT), theme, sekcja admin | — |
| F-23 | Dziennik (panel) | ikona dziennika | Zadania / Wątki / Kronika, recap "Poprzednio…", regen | — |
| F-24 | Akcja walki (sheet) | "Akcja" w walce | Czar / Ruch / Unik-Blok / Zapasy; ikona+nazwa+koszt+opis | ✅ front-v2 (FE9 #1236): `components/game/combat/ActionSheet.tsx` — wysuwany arkusz z trybami (Atak/Czar/Ruch/Obrona) + pasek akcji `CombatActionBar.tsx` (Atak/Czar/Zbliż↔Cofnij/Unik/Uciekaj); reakcja SF10 `ReactionModal.tsx` (timer-ring + Przyjmij/Unik/Blok). Makieta zar6-akcja/zar6-reakcja |
| F-25 | Atak (sheet) | "Atak" w walce | warianty ataku (melee/ranged/spell) | ✅ front-v2 (FE9 #1236): tryb „Atak" w `ActionSheet.tsx` + przycisk Atak w `CombatActionBar.tsx` → `POST /combat/resolve-attack` z pre-rollem d20 (kość 3D ląduje na tej samej wartości); bramkowanie zasięgu przez backend (blocked out_of_range → toast) |
| F-26 | Wybór czaru | mag rzuca czar | pula many + lista czarów; heal/efekt OOC z animacją kości NdX (#653) | ✅ front-v2 (FE9 #1236): tryb „Czar" w `ActionSheet.tsx` — banner many + lista czarów (znane × katalog, koszt/ranga/afford), klik → resolve-attack ze `spell_key`; przycisk Czar tylko dla klas z pulą many |
| F-27 | Level-up | próg XP | alokacja statystyk | — |
| F-28 | Ekran śmierci | HP ≤ 0 | czaszka, epitafium, akcje (nowa przygoda/świat/bohater/wskrzeszenie) | — |
| F-29 | Ekran zwycięstwa | boss pokonany (loch) | laur, tytuł zakończenia, statystyki, akcje | — |
| F-30 | Koniec walki | walka wygrana (poza lochem) | ikona zwycięstwa, podsumowanie łupu, "Kontynuuj" | — |
| F-31 | Popup łupu | zwycięstwo w walce | siatka itemów, "Weź łup" / "Pomiń" | — |
| F-32 | Drop celebration | rzadki/affixed drop (U17) | karta rzadkiego itemu, diff vs założony | — |
| F-33 | Recap overlay | przycisk w dzienniku | opis przerwy, treść, "Kontynuuj" | — |
| F-34 | Picker lochów | tryb lochu | lista lochów, loading | — |
| F-35 | Zagadka lochu | wejście do pokoju-zagadki | treść, podpowiedź, input, submit | — |
| F-36 | Modal kafelka lochu | pierwsze wejście / klik mapy (L12b) | obraz kafelka + nazwa | — |
| F-37 | Mapa lochu (overlay) | przycisk mapy w lochu | SVG: nieznane/aktualne/oczyszczone kafelki. #869: klik w odkryty kafel = pathfinding (BFS `dungeonBfsPath` po otwartych drzwiach, tylko visited) → auto-marsz sekwencyjny (`_dungeonAutoWalk`), narracja pośrednich tłumiona, stop na walce/zagadce/bossie/blokadzie; cel może być PIERWSZYM kaflem mgły (granicznym) — ostatni hop odkrywający, nawet za kilkoma znanymi kaflami; głęboka mgła (trasa przez nieznany kafel) = no-op | — |
| F-38 | Ukończenie lochu | loch oczyszczony | łup, cooldown, "Wyjdź" | — |
| F-39 | Śmierć w lochu (L13) | śmierć w lochu | checkpoint restore, kara XP, cooldown | — |
| F-40 | Porzucenie lochu (L13) | próba porzucenia | potwierdzenie + info restore/cooldown | — |
| F-41 | Wznowienie lochu (L13) | niedokończony loch | "Kontynuuj" / "Porzuć" | — |
| F-42 | Boss lochu (L13) | boss pokonany | "Wyjdź z łupem" / "Idź głębiej" | — |
| F-43 | Mapa świata (panel) | ikona mapy / podróż | SVG hex mapa + potwierdzenie podróży. #1106: nagłówek panelu pokazuje pełną nazwę aktualnego hexa (`_wmUpdateTitle`, aktualizacja przy open/travel); etykieta aktualnego hexa renderowana zawsze (bez progu zoomu, bez slice(0,14)), większy font + halo dla kontrastu; pozostałe hexy: slice 14→20+"…". #1258: dotyk na mobile — jeden palec przesuwa, dwa palce zoomują (pinch); wspólny helper `_attachMapTouch(_wmap, _wmRender)` (parytet z myszą/kółkiem); `stopPropagation` na geście, by nie odpalać swipe-to-close panelu. Ten sam helper podpięty do mapy lokalnej (F-ML). #1258b: `touch-action:none` na `.wmap-svg` (przeglądarka nie kradła połowy gestu → pan 1:1 z palcem); min zoom obniżony do `_wmap.minZoom=0.12` (widać całą krainę), mapa lokalna `_lmap.minZoom=0.5` | ✅ front-v2 (KROK 4 FE8 #1235): zakładka gry `map` (`components/game/WorldMap.tsx`) — otwierana z 🗺 w pasku przygody + dolnego tabbara/desktop railu (`tabs.ts` MAP_TAB). Własny nagłówek zegar+pora+lokacja+X (Topbar chowany gdy `gameTab==='map'`). SVG hex flat-top (`lib/worldmap.ts`: `hexToPixel`/`hexPoints`/`hexDistance`), mgła wojny (discovered/known/outline/unexplored), aktualny heks glow (`#hexglow`), flaga celu tylko na NAZWANYCH known-heksach, ikony terenu **Phosphor przez foreignObject** (nie emoji), zoom/pan (wskaźnik+kółko) + centruj; dane z `useWorldMap` (GET /world-map, polling 20s). Panel podróży: dystans/czas/teren/spotkanie (SZACUNKI wg terenu — `estimateTravel`; prawda z backendu po dotarciu) + ostrzeżenie nocy + Podróżuj → `useTravel` (POST /travel) |
| F-44 | Paleta komend | Ctrl+/ / ikona | search, lista komend, nawigacja | — |
| F-45 | Zaproszenie | przycisk invite | email + wiadomość, submit | — |
| F-46 | Zgłoszenie buga | FAB (tylko tester) | typ, obserwacja/reprodukcja, submit | — |
| F-47 | Cinematic podróży | aktywacja podróży | full-screen: ikona, tytuł, atmosfera, progress | ✅ front-v2 `components/game/TravelCinematic.tsx` (KROK 4 FE8 #1235): pełnoekranowy overlay podczas podróży (makieta zar9-podroz) — ikona ścieżki, „Podróż w toku" · „Ku {cel}", proza atmosfery (z odpowiedzi /travel), pasek postępu 0→100%, zegar+pora; klik=pomiń, auto-domknięcie po zakończeniu podróży (min. czas na pasek) → invalidacja mapy/zegara/strumienia tur (advance) |

### 7.3 Komponenty gameplay

| ID | Komponent | Opis | React |
|---|---|---|---|
| F-50 | Composer | pole akcji + licznik znaków + mic STT + paleta + wyślij + overlay "czytanie TTS" | ✅ front-v2 `components/game/Composer.tsx` (KROK 4 #1233): mic (STT placeholder), pole auto-grow + licznik `n/500`, ikona palety komend (placeholder F-44), wyślij (ember), quick-action chips z `suggested_actions` (Enter=wyślij, Shift+Enter=nowa linia) |
| F-51 | Log narracji | dymki gracza/GM/system, metadane (nazwa/tura/data — toggle), fade-in, auto-scroll, slash-popup; karty combat_turn (⚔️ atak gracza / 🗡️ atak wroga / 💀 śmierć / 🛡 reakcja). **#861 (dual-wield):** off-hand drugi cios → karta „🗡️🗡️ DRUGI CIOS" (klasa `cturn--offhand`); atak wroga sparowany → badge „🛡 Parujesz (+N obrona)" (`cturn--parried`) — flagi `offhand`/`parry_bonus` z meta combat_turn (silnik #598) | ✅ front-v2 `components/game/NarrationLog.tsx` (KROK 4 #1233): dymek GM (serif, tło, „MISTRZ GRY · tura N") · akcja gracza prawo/ember/italic · systemowe=kreskowany pasek · „GM pisze…" (submit pending) · fade-in + auto-scroll; proza escapowana z *kursywą*/«cytatami»→em (bez XSS); parser `buildLog` |
| F-52 | Karta rzutu | nazwa testu, modyfikator, suma, werdykt (sukces/porażka/krytyk) | ✅ front-v2 `components/game/RollCard.tsx` (KROK 4 #1233): rzut gracza=prawo/ember, wróg=lewo/krwawy; Nat20=złoty flash, Nat1=krwawy; siatka komórek (d20/mod/Suma/DC/Wynik); stare rzuty zwijane do 1 linii (zar3); dane z `rollFromResult(result)` |
| F-53 | Baner walki | **#967 — kompaktowy layout (Wariant D):** każdy uczestnik = JEDNA linia (`.cline`) z inline HP barem (kolor wg %): TY/imię · ❤HP · pasek · DEF · INI · strefa(🗡/🏹) · warunki · 🎯cel; (gracz dodatkowo 🛡absorb + ostrzeżenie trwałości broni). Strefy ZWARCIE/DYSTANS = lekkie nagłówki (`.czone__head`), pusta strefa = inline „— pusto —" (nie pełna sekcja). Aktywny aktor = amber glow (`.cline--active`). Banner ≥40% niższy niż stary (karty + oś + sekcje usunięte). Render: `combatLineHtml()` w `combat_ui.js`. | ✅ front-v2 (FE9 #1236): `components/game/combat/CombatBanner.tsx` — kompakt jednokolumnowy, strefy ZWARCIE/DYSTANS = lekkie nagłówki, gracz + wrogowie jeden pod drugim, inline HP (tier hi/mid/lo), piny DEF/🛡absorb/warunek, aktywny = amber glow, zwijanie (mobile), klik wroga = wybór celu; orkiestrator `CombatView.tsx` (poll `useCombatState` tylko gdy aktywna, auto-driver tury wroga, karty rzutów w feedzie). Makieta zar7-walka |
| F-54 | Paski HP/Mana/XP | nagłówek (HP, Mana-mag) + karty w sheecie + XP bar z meta | ✅ front-v2 (KROK 5 #1234): sekcja Żywotność w panelu Postać (`PanelSkills`/`PanelCharacter.tsx`) — HP+Mana(mag)+XP; osobny panel Umiejętności = pipsy rang (sufit 3) + bonus (mod+ranga+biegłość ★+2), 2-kol; dane z `sheet.skills`+`stat_modifiers` |
| F-55 | Warunki/statusy | sekcja buffów/debuffów/ran; pasek statusu gracza w walce (SF4) | ✅ front-v2 (KROK 5 #1234): sekcja Stan w panelu Postać (`PanelCharacter.tsx`) — `sheet.conditions` z poziomem (np. Zmęczony · poz. 3) + opis; pusto → „w pełni sił" |
| F-56 | Ekwipunek | złoto, diagram anatomii (8 slotów), plecak (stackable), itemy fabularne (lore), equip przez klik/drag | ✅ front-v2 (KROK 5 #1234): `PanelInventory.tsx` — sylwetka Diablo-overlap (itemy NACHODZĄ na figurę, 8 slotów, pasek trwałości, broń dwuręczna lustrzana na 2. rękę), toggle Sylwetka/Lista, sakiewka złoto+udźwig, plecak grupowany (zużywalne/sprzęt), podsumowanie obrony; equip/zdejmij przez klik → `POST /inventory/{id}/equip` (`useSheetData.useEquipItem`) |
| F-57 | Sklep / NPC | interakcja przez narrację; siatka itemów z cenami; kup/sprzedaj | — |
| F-58 | Quest/cele | pasek questa w nagłówku + sekcja questów w sheecie + sekcje dziennika (Zadania/Wątki/Kronika) | — |
| F-59 | Crit flash | wiązki na Nat 20 / Nat 1 przez ekran | — |

### 7.4 Systemy (podsystemy do opakowania)

| ID | System | Opis | React |
|---|---|---|---|
| F-70 | 3D Dice | `dice.js` + three.js + cannon: scena, fizyka, geometrie d4–d100, parser notacji "1d20+5", detekcja ściany, SFX. **Zostawić silnik, dać React wrapper.** | ✅ front-v2 (FE9 #1236): silnik ZACHOWANY — vendorowany `dice-box-threejs.umd.js` (THREE r143 + Cannon, z front/) do `public/vendor/`, owinięty w `lib/dice3d.ts` (recreate-per-roll, predeterminacja `1d20@N`, backstop 9s, fallback 2D — wierny combat_ui.js:1684-1783). Fizyka NIE przepisana. Overlay `Dice3DOverlay.tsx` |
| F-71 | Multiplayer | `multiplayer_ui.js`: lobby, status bar (timer + licznik zgłoszeń), rundy, dymki akcji innych graczy, whispery, party chat, join przez token `?join=`, polling 2s/5s | — |
| F-72 | Voice | `voice.js`: TTS (GET `/voice/tts`), STT (WS `/voice/stt` + MediaRecorder, auto-stop na ciszy), toggles w localStorage, health/config check | — |
| F-73 | PWA | meta tagi, theme-color, apple-mobile-web-app, push (`#enable-push-btn`), service worker (poza scope `front/`), `sendBeacon` na unload | — |
| F-74 | Client logging | `clog.js`: RUM — page load, click `[data-clog]`, errory, unload beacon, session ID, batch flush 2.5s → POST `/api/client-logs` | — |
| F-75 | D-pad lochu | `#dungeon-nav` (L12): krzyżak kierunków N/W/E/S + akcje (skrzynia/zagadka/odpoczynek). #741: przeciągany palcem (pointer events, próg 6px tap-vs-drag), pozycja zapamiętana w `localStorage.dungeonNavPos`; środek ⊕ otwiera mapę lochu (`openDungeonMap`, jak ikona 🗺 — F-37) | — |
| F-76 | Grupowanie ekwipunku lore | `#sheet-lore` (#1088): lore items grupowane w zwijalne `<details>` sekcje — zwoje/księgi/klucze/fabularne/inne. Klasyfikacja client-side (`_loreCategoryKey()`) regex na labelu. Stan zwinięcia zapamiętany w `sessionStorage`. | ✅ front-v2 (KROK 5 #1234): sekcja „Przedmioty fabularne" w `PanelInventory.tsx` — itemy typu quest/map/book/note/key/scroll w zwijalnym `<details>` (natywny), reszta w plecaku |
| F-77 | Bramka finału (soft victory gate) | `#finish-campaign-btn` (menu ☰) + `#finale-confirm-modal` (#1097): karta na czacie „📜 Osiągnąłeś cel przygody…" przy pierwszym otwarciu bramki (`finale_available` transition w odpowiedzi tury) + trwały przycisk „Zakończ przygodę" w menu ☰ dopóki bramka otwarta (stan przywracany z `GET /campaigns/{id}.finale_available` przy wejściu). Klik → modal potwierdzenia „Osiągnąłeś cel przygody" ([Zakończ przygodę]/[Jeszcze zostań]) → `POST /campaigns/{id}/finish` → `showVictoryScreen()`. MP: przycisk ukryty dla nie-gospodarza (`multiplayerUI.isHost()`). | #1097 |
| F-78 | Pasek reputacji (karta postaci) | `#sheet-reputation-section` (#1107): sekcja „REPUTACJA" pod stat+skill listem w zakładce Staty. Dane z `GET /api/characters/{id}/reputation`; per-wpis: nazwa regionu (PL mapowanie) + wartość ±N + tier PL (Czczony/Przyjazny/Neutralny/Nielubiany/Znienawidzony) w kolorze (green/gray/red). Pusta lista → „Świat jeszcze nie zna bohatera.". Ukryta gdy endpoint niedostępny. Render: `renderReputationSection(character)` w `game.js`. | ✅ front-v2 (KROK 5 #1234): panel „Reputacja & opis" (scalony) — `PanelReputation.tsx`: standing per region (`GET /characters/{id}/reputation`), wartość ±N + tier PL w kolorze (Czczony/Przyjazny/Neutralny/Nielubiany/Znienawidzony); pod nim opis postaci (wygląd/osobowość/więzi/skaza/sekret z `sheet.identity`); pusto → „czyny nie odbiły się echem". #1107 |

---

## 8. Stan i dane (kontrakt dla Fazy 1)

### Global store (Zustand) — kandydaci

| Zmienna | Cel |
|---|---|
| `currentUser` | zalogowany user (id, username, email) |
| `currentCampaignId` | aktywna kampania |
| `currentHero` / `currentHeroId` | wybrana postać |
| `characterData` | pełny stan postaci (staty, eq, czary, warunki) |
| `activeCombat` | snapshot walki (tura, wrogowie, strefy) |
| `turnHistory` | historia tur (narracja + logi rzutów) |
| `dungeonRunState` | postęp lochu (pokój, mapa, łup) |

### Endpointy API (z inwentaryzacji)

- **Auth:** `POST /auth/login`, `/auth/register`, `/auth/verify-email`, `/auth/forgot-password`, `/auth/reset-password`
- **Bohaterowie:** `GET /heroes`, `POST /characters`, `GET /characters/{id}`, `DELETE /characters/{id}`
- **Kampanie:** `GET /campaigns`, `POST /campaigns`, `GET/POST /campaigns/{id}/turns`, `GET /campaigns/{id}/clock`
- **Walka:** `GET /campaigns/{id}/combat`, `POST .../combat/resolve-attack`, `.../enemy-turn`, `.../zone-change`, `.../declare-reaction`, `.../resolve-reaction`
- **Ekwipunek:** `GET /inventory/{id}`, `POST /inventory/{id}/equip`
- **Loch:** `POST /campaigns/{id}/dungeon-run`, `.../dungeon-run/action`
- **Multiplayer:** `POST /multiplayer/campaigns`, `GET .../lobby`, `POST .../start`, `GET /campaigns/{id}/round/status`, `POST .../round/submit`, `GET .../round/narration`, `.../invite-link`
- **Voice:** `GET /voice/healthz`, `/voice/config`, `/voice/tts`, WS `/voice/stt`
- **Logi:** `POST /api/client-logs`

### Realtime / auto-refresh (mapowanie na TanStack Query / WS)

| Cel | Interwał dziś | Nowy mechanizm |
|---|---|---|
| Strumień tur | ~3–5s lub SSE | TanStack Query polling / SSE |
| Stan walki | 1.5s podczas walki | Query refetchInterval (tylko gdy combat aktywny) |
| Status rundy (MP) | 2s | Query polling |
| Narracja (MP) | 2s | Query polling |
| Party chat | 5s | Query polling |
| Lobby | 5s | Query polling |
| STT | WebSocket | WS → store |

### localStorage keys

- token auth, `voice_tts_enabled`, `voice_stt_enabled`, `voice_stt_autosend`, preferencje fontu/rozmiaru, theme, toggles metadanych dymków

---

## 9. Konwencja aktualizacji (reguła living-doc)

**Reguła:** każda zmiana w `frontend/front/` (nowy ekran / modal / komponent / system) → dopisz lub zaktualizuj wpis w **Feature Ledger** (sekcja 7).

**Format wpisu:**

```
### [F-NN] Nazwa ekranu/komponentu
- Status:   ISTNIEJE w starym UI  |  NOWY (po 2026-06-17)
- Typ:      ekran | modal | komponent | overlay | system
- Trigger:  co go otwiera/uruchamia
- Stan/dane: jakie API, jaki store
- Realtime: polling Xs | WS | none
- React:    <NazwaKomponentu>   (wypełniane po migracji)
- UX:       animacje, dźwięki, zachowanie mobile vs desktop
```

**Numeracja:** nowe ID nadawaj rosnąco w odpowiednim bloku (ekrany 7.1, modale 7.2, gameplay 7.3, systemy 7.4). Nie nadpisuj zwolnionych numerów.

**Zalecenie do dopisania w `CLAUDE.md`:** *"Każda zmiana w `frontend/front/` → zaktualizuj odpowiedni wpis F-NN w `frontend_design.md`."*

---

## 10. Zasady responsywności (mobile-first, 70/30)

- **70% mobile / 30% desktop** → projektuj mobile-first; desktop = progresywne wzbogacenie.
- Breakpoint bazowy = mobile; `md:` / `lg:` dla desktopu.
- Wzorce mobilne zachowane: **bottom tab bar**, sheety wysuwane z dołu, swipe gesty, safe-area insets (notch/home indicator), duże cele dotykowe.
- Desktop: sheety mogą stać się stałymi side-panelami (np. karta postaci jako prawy panel zamiast wysuwanego).
- Combat: mobile = 2 kolumny stref kompaktowo; desktop = szersza arena.

---

---

## 11. Mapa nawigacji (flow ekranów) — DO WDROŻENIA w osobnym milestone

> Ustalone 2026-07-05 przy redesignie ŻAR. Analiza realnego `app.js`. **Nie wdrażać teraz** — osobny milestone po finalnych ustaleniach wyglądu. Tu = uzgodniony cel.

### Stan obecny (14 ekranów, `showScreen()` `app.js:406`, mapa `app.js:46-61`)

Ścieżka login→gra dla wracającego gracza = **3 kliki** (bohater → kampania → wejście). Auto-restore po F5 (`tryRestoreSession` `app.js:1745`) wchodzi wprost do gry. Deep-link `?campaign=` → prosto do gry; `?join=` → kampanie.

### Problemy (potwierdzone w kodzie)

1. **Dwa niespójne „wyjścia z gry".** `home-btn`/avatar (`app.js:1266`) → **heroes** (pomija kampanie). Powrót do listy kampanii schowany: ☰ → Ustawienia → `go-to-campaigns-btn` (`index.html:1420`, `game.js:5437`).
2. **Powrót do innej kampanii tego samego bohatera = 4 kliki** (home→heroes→bohater→campaigns→kampania).
3. **Wymuszony ekran „kampanie" nawet przy 1 aktywnej** (`selectHero` „zawsze pokazuje wybór" `heroes.js:215`), choć restore umie wejść wprost.
4. **`?join=` wylogowany → register, nie login** (`auth.js:394`) — zaproszony ze starym kontem ląduje na rejestracji.
5. Onboarding bez „pomiń" (drobiazg, jednorazowy cinematik).

### Cel — nawigacja hierarchiczna + jeden spójny „wstecz"

```
Login ──► [Bohaterowie] ──► [Kampanie bohatera] ──► Gra
              ▲  (hub)            ▲                    │
              └───────────────────┴──── ☰ menu ───────┘
                     jeden przycisk „Wyjdź z gry"
```

- **Jeden przycisk wyjścia z gry** → zawsze do **listy kampanii bieżącego bohatera** (nie heroes). Stamtąd „← Bohaterowie" 1 klik. Naprawia #1, #2 (powrót do innej kampanii = 2 kliki).
- **Auto-wejście gdy bohater ma dokładnie 1 aktywną kampanię** (jak restore); lista tylko przy ≥2. Naprawia #3.
- **`?join=` wylogowany → login** z notką „masz konto? zaloguj / [nowy gracz — rejestracja]". Naprawia #4.
- **Breadcrumb w topbarze poza grą**: `Bohaterowie › Wiga › Kampania`, człony klikalne — znosi zgadywanie „gdzie jestem".
- **Panele w grze (postać/ekwipunek/mapa/dziennik) = zakładki w obrębie gry**, nie osobny `showScreen`. Panel nakłada się na czat, swipe/„wstecz" zamyka do Opowieści — zero utraty kontekstu gry.

---

_Koniec dokumentu. Aktualizuj sekcję 7 przy każdej nowej funkcjonalności frontendu gracza._
| F-79 | Kronika bohatera | 📖 Kronika na karcie bohatera (#1098) | Modal: LEGENDA (legend_digest) + lista rozdziałów (chapter_summary / outcome / XP / tury) + sekcja blizn porzuceń (abandonment_note) | heroes.js , endpoint GET /characters/{id}/chronicle |
| F-80 | Przyciski po przerwaniu podróży (PT12) | podróż przerwana (`travel_plan.interrupt_reason` set, brak walki) → composer pokazuje 3 przyciski quick-action: 🧭 Kontynuuj podróż / 😴 Odpocznij / 🔥 Rozbij obóz (#1122) | Klik = akcja mechaniczna (omija loterię LLM): Kontynuuj → `POST /campaigns/{id}/travel-resume` (`handleTravelResume`, resume `travel_plan`; dusk→night_march, forced_camp→disabled „Padłeś ze zmęczenia"); Odpocznij → REST:long; Rozbij obóz → BUILD_CAMP. Przyciski znikają po decyzji (serwer zwraca świeże `suggested_actions`). Proza gracza dalej działa równolegle. Render: `_build_travel_interrupt_actions` (backend suggested_actions) + `sendStructuredAction` (game.js) | #1122 |
| F-81 | Trójstanowa mgła wojny mapy świata (PM6) | render mapy świata (`_wmRender`, app.js) — trzeci stan `known` obok `discovered`/`outline` | Hex `status:"known"` (backend FOW PM1 #1220) = przygaszony fill (kolor terenu × opacity 0.4) + wyblakła ikona + kropkowany bursztynowy obrys + label tylko dla landmarków. Wyraźnie różny od `discovered` (pełny fill) i `outline` (przezroczysty). Klik = cel podróży bez szczegółów lokacji (info „teren — znane z opowieści"). Legenda 3 stanów pod kanwą (`#wmap-legend`). Zasięg bąbla „known" globalnie regulowany w admin→Mapa→Generuj świat (PM7 #1226, `knowledge_bubble_radius`). Render: `_wmRender`/`_wmOnHexClick` (app.js), CSS `.wmap-legend*` | #1225 |
| F-82 | Drogi/trakty jako ciąg na mapie świata (PM5) | render mapy świata (`_wmRender`, app.js) — road-hexy known/discovered | Hexy `hex_type:"road"` (gazetteer known od startu w regionie pochodzenia, backend FOW PM1/PM2) rysowane jako **ciągły trakt**: dla każdego road-hexa pół-segment linii do środka wspólnej krawędzi z każdym sąsiadem-drogą (`_AXNB`, 6 kierunków axial) — pół-segmenty stykają się → widoczna, nieprzerwana droga. Kolor z `hex_type_config.map_color` (`#c8a86c`); `discovered` pełny (opacity 0.9), `known` przygaszony (0.5). Ikona 🛤️ na road-hexach wygaszona (ciągłość czytamy z linii). Render: blok „road network" w `_wmRender` (app.js) po pętli hexów, przed teleportami | #1224 |
