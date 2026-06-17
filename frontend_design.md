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
  2. EKRAN WALKI (combat) — baner walki z dwiema strefami: ZWARCIE (melee) i DYSTANS (ranged); wrogowie jako chipy z paskiem HP w odpowiedniej strefie; licznik rundy; wskaźnik czyja tura; przyciski akcji (Atak / Akcja / Zbliż się).
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

## 5. (zarezerwowane) — Notatki z Fazy 0

> Po wygenerowaniu kierunków wklej tu screeny/linki i decyzję, który kierunek wybrany i dlaczego.

- Kierunek wybrany: _do uzupełnienia_
- Powód: _do uzupełnienia_

---

## 6. Design Tokens (uzupełnić po Fazie 0)

> Placeholder. Po wyborze kierunku wklej tu finalne tokeny — staną się źródłem prawdy dla Fazy 1.

```
Kolory:
  --bg-primary:      (np. #0a0908)
  --surface:         ?
  --accent:          (np. #c9a54a — złoto)
  --success:         ?
  --danger:          ?
  --text-primary:    ?
  --text-muted:      ?
Typografia:
  --font-heading:    (np. Cinzel / Playfair)
  --font-body:       (np. Lora / IM Fell)
  skala:             12–24px
Spacing / radius / cienie: ?
Dymki: GM vs gracz vs system — kolory/wyrównanie
```

(Wartości referencyjne ze starego UI: bg `#0a0908`, accent złoto `#c9a54a`, fonty Cinzel/Playfair/IM Fell/Lora. Można wziąć jako punkt wyjścia kierunku "Dark Grimoire".)

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
| F-09 | Lista kampanii | `#campaigns-screen` | Wybór kampanii, typ przygody (Nowa/Gotowa/Loch), aktywne, empty state | — |
| F-10 | Nowa kampania | `#new-campaign-screen` | Kreator nazwy kampanii | — |
| F-11 | Kreator postaci | `#character-wizard-screen` | 4 kroki: tożsamość → archetyp → staty → finalizacja | — |
| F-12 | Ekran gry | `#game-screen` | Główny gameplay: nagłówek + log narracji + composer; hostuje panele combat/inventory/settings | — |
| F-13 | Lobby (MP) | `#lobby-screen` | Multiplayer pre-game: team builder, zaproszenia, timer | — |

### 7.2 Modale i overlaye (~30)

| ID | Modal | Trigger | Kluczowe elementy | React |
|---|---|---|---|---|
| F-20 | Rzut kośćmi (3D) | rzut na test / combat / `/roll` | canvas 3D, d4–d100, karta wyniku | — |
| F-21 | Karta postaci (panel) | nagłówek / swipe | zakładki Staty / Ekwipunek / Czary (mag) / Wygląd | — |
| F-22 | Ustawienia (panel) | ikona koła zębatego / swipe | push, wygląd tekstu (font/rozmiar/preview), metadane dymków, voice (TTS/STT), theme, sekcja admin | — |
| F-23 | Dziennik (panel) | ikona dziennika | Zadania / Wątki / Kronika, recap "Poprzednio…", regen | — |
| F-24 | Akcja walki (sheet) | "Akcja" w walce | Czar / Ruch / Unik-Blok / Zapasy; ikona+nazwa+koszt+opis | — |
| F-25 | Atak (sheet) | "Atak" w walce | warianty ataku (melee/ranged/spell) | — |
| F-26 | Wybór czaru | mag rzuca czar | pula many + lista czarów | — |
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
| F-37 | Mapa lochu (overlay) | przycisk mapy w lochu | SVG: nieznane/aktualne/oczyszczone kafelki | — |
| F-38 | Ukończenie lochu | loch oczyszczony | łup, cooldown, "Wyjdź" | — |
| F-39 | Śmierć w lochu (L13) | śmierć w lochu | checkpoint restore, kara XP, cooldown | — |
| F-40 | Porzucenie lochu (L13) | próba porzucenia | potwierdzenie + info restore/cooldown | — |
| F-41 | Wznowienie lochu (L13) | niedokończony loch | "Kontynuuj" / "Porzuć" | — |
| F-42 | Boss lochu (L13) | boss pokonany | "Wyjdź z łupem" / "Idź głębiej" | — |
| F-43 | Mapa świata (panel) | ikona mapy / podróż | SVG hex mapa + potwierdzenie podróży | — |
| F-44 | Paleta komend | Ctrl+/ / ikona | search, lista komend, nawigacja | — |
| F-45 | Zaproszenie | przycisk invite | email + wiadomość, submit | — |
| F-46 | Zgłoszenie buga | FAB (tylko tester) | typ, obserwacja/reprodukcja, submit | — |
| F-47 | Cinematic podróży | aktywacja podróży | full-screen: ikona, tytuł, atmosfera, progress | — |

### 7.3 Komponenty gameplay

| ID | Komponent | Opis | React |
|---|---|---|---|
| F-50 | Composer | pole akcji + licznik znaków + mic STT + paleta + wyślij + overlay "czytanie TTS" | — |
| F-51 | Log narracji | dymki gracza/GM/system, metadane (nazwa/tura/data — toggle), fade-in, auto-scroll, slash-popup | — |
| F-52 | Karta rzutu | nazwa testu, modyfikator, suma, werdykt (sukces/porażka/krytyk) | — |
| F-53 | Baner walki | runda, czyja tura, arena z 2 strefami (ZWARCIE/DYSTANS), chipy wrogów (HP/nazwa/portret), aktywny aktor, axis hint "← bliżej · dalej →" | — |
| F-54 | Paski HP/Mana/XP | nagłówek (HP, Mana-mag) + karty w sheecie + XP bar z meta | — |
| F-55 | Warunki/statusy | sekcja buffów/debuffów/ran; pasek statusu gracza w walce (SF4) | — |
| F-56 | Ekwipunek | złoto, diagram anatomii (8 slotów), plecak (stackable), itemy fabularne (lore), equip przez klik/drag | — |
| F-57 | Sklep / NPC | interakcja przez narrację; siatka itemów z cenami; kup/sprzedaj | — |
| F-58 | Quest/cele | pasek questa w nagłówku + sekcja questów w sheecie + sekcje dziennika (Zadania/Wątki/Kronika) | — |
| F-59 | Crit flash | wiązki na Nat 20 / Nat 1 przez ekran | — |

### 7.4 Systemy (podsystemy do opakowania)

| ID | System | Opis | React |
|---|---|---|---|
| F-70 | 3D Dice | `dice.js` + three.js + cannon: scena, fizyka, geometrie d4–d100, parser notacji "1d20+5", detekcja ściany, SFX. **Zostawić silnik, dać React wrapper.** | — |
| F-71 | Multiplayer | `multiplayer_ui.js`: lobby, status bar (timer + licznik zgłoszeń), rundy, dymki akcji innych graczy, whispery, party chat, join przez token `?join=`, polling 2s/5s | — |
| F-72 | Voice | `voice.js`: TTS (GET `/voice/tts`), STT (WS `/voice/stt` + MediaRecorder, auto-stop na ciszy), toggles w localStorage, health/config check | — |
| F-73 | PWA | meta tagi, theme-color, apple-mobile-web-app, push (`#enable-push-btn`), service worker (poza scope `front/`), `sendBeacon` na unload | — |
| F-74 | Client logging | `clog.js`: RUM — page load, click `[data-clog]`, errory, unload beacon, session ID, batch flush 2.5s → POST `/api/client-logs` | — |

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

_Koniec dokumentu. Aktualizuj sekcję 7 przy każdej nowej funkcjonalności frontendu gracza._
