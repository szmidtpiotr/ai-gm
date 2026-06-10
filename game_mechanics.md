# Game Mechanics — Redesign od Podstaw

> **Cel tego dokumentu:** Zaprojektować jak gra POWINNA działać, naprawić fundamentalne błędy projektowe, i zdefiniować kolejność implementacji od zera.
>
> **Ostatnia aktualizacja:** 2026-06-09
>
> ---
>
> ## INSTRUKCJA DLA AGENTÓW LLM
>
> **Ten plik jest głównym źródłem kontekstu projektowego dla całego projektu AI-GM.**
>
> Kiedy pracujesz nad GitHub Issues, TDD, lub jakimkolwiek zadaniem implementacyjnym:
>
> 1. **Szukaj kodu zadania** w **CZĘŚĆ 7** (linia ~840) — master lista implementacyjna. **Schemat kodów:** A=Faza -1, B=Faza 0, C=Faza 1, D=Faza 2, E=Faza 3, F=Faza 4, G=Faza 5 (MP), H=Faza 6. Numery sekwencyjne w obrębie sekcji (B1, B2, ..., B7). **FAZA -1, FAZA 0, FAZA 1 (C1–C19) i FAZA 2 (D1–D14) ukończone; FAZA 3 w toku (E1–E14 ✅) — patrz sekcja WYKONANE na końcu pliku.**
> 2. **Szukaj kontekstu decyzji projektowej** w sekcji tematycznej (CZĘŚĆ X = Afiksy, CZĘŚĆ AB = Walka/Rany, CZĘŚĆ AC = Multiplayer, CZĘŚĆ AF = Ekonomia, CZĘŚĆ AG = Infrastruktura, itd.).
> 3. **Każda decyzja projektowa** ma blok `> **Zasada projektowa**` + `> **Dlaczego?**` + `> **Co odrzucono?**` — przeczytaj je zanim zaczniesz kodować.
> 4. **GitHub Issues** powinny mieć w tytule kod zadania (`[TASK] B1 — ...`) i odwoływać się do tej sekcji w treści.
> 5. **notes.md** w katalogu głównym = bieżące notatki robocze (otwarte pytania, decyzje z sesji). Sprawdź go gdy coś nie jest jasne.
> 6. **Zasada synchronizacji:** Gdy dodajesz nowe zadanie do CZĘŚĆ 7 (tabela fazy), **zawsze** dodaj ten sam wpis do `notes.md` jako `- [ ] XNN — opis` w odpowiedniej sekcji fazy. Zaktualizuj też tabelę progress na górze notes.md (Total column). Jeśli tworzysz GitHub Issue — dodaj link `[#NNN]` obok wpisu w notes.md.
>
> ### Mapa sekcji (szybka nawigacja)
>
> | Sekcja | Temat |
> |--------|-------|
> | CZĘŚĆ 7 | **Master lista implementacyjna** — start tutaj |
> | CZĘŚĆ 1–6 | Diagnoza + architektura (World State, Questy, XP, Admin Queue, Onboarding) |
> | CZĘŚĆ X | Unified Effects System + Affix System |
> | CZĘŚĆ Y | System Narracji Kampanii (tagi, parsery, Narrative State) |
> | CZĘŚĆ Z | Gotowe Kampanie (Campaign Templates, Forge) |
> | CZĘŚĆ AA | Lochy (Dungeon Mode) |
> | CZĘŚĆ AB | Walka, Rany, Model Wroga |
> | CZĘŚĆ AC | Multiplayer |
> | CZĘŚĆ AD | Flow UI poza grą (ekrany, nawigacja) |
> | CZĘŚĆ AE | Admin Panel (audyt admin_panel_v3, strangler-fig migration) |
> | CZĘŚĆ AF | Złoto i Ekonomia (sinki, crafting, durability) |
> | CZĘŚĆ AG | Infrastruktura (.170=RTX3060, .16=GTX1660, workload rules) |
> | CZĘŚĆ 10 | Zasady projektowe (5 reguł) |
> | CZĘŚĆ 10b | Observability — odłożone do prod deployment |
> | **WYKONANE** | **Fazy zakończone (FAZA -1 A1-A12, FAZA 0 B1-B7, FAZA 1 C1-C19) — na końcu pliku** |
>
> ### Kluczowe zależności (nie łam ich)
>
> ```
> Effects (F1) → Afiksy (F2) → Crafting (F6) + Admin buildery
> Rany (C4/10/11) → Walka MP (G7)
> World State (F0) → ALL: Gate, MP, NPC pamięć, Narracja
> Onboarding karty (FONB) → PO systemach które uczą
> ```
>
> ---

---

## PROCEDURY WSTĘPNE — Zanim zaczniemy właściwe prace

> Te kroki muszą zostać wykonane PRZED rozpoczęciem Fazy 0 (World State) i jakiejkolwiek implementacji.
> Bez tych fundamentów: praca deweloperska będzie zakłócać graczy, a codebase będzie zanieczyszczony.
>
> **Status:** Zaplanowane — nie wykonane.

---

### PROCEDURA A3: Przywrócenie środowiska PROD na 192.168.1.62

**Problem który rozwiązuje:**

Aktualnie DEV (.61) pełni rolę zarówno środowiska deweloperskiego jak i środowiska dla graczy. Efekt:
- Zmiany w kodzie i restarty serwera przerywają aktywne sesje graczy
- Nie wiadomo czy bug zgłoszony przez gracza pochodzi z nowego kodu czy z restartu podczas gry
- Nie można testować agresywnie bez ryzyka zepsucia doświadczenia graczy

**Docelowy stan:**

```
192.168.1.61 = DEV (programista + Claude)
    → Tu developujesz, testujesz, eksperymentujesz
    → Claude ZAWSZE pracuje tutaj — nigdy na .62
    → Gracze NIE grają tutaj
    → Restartuj kiedy chcesz

192.168.1.62 = PROD (tylko gracze)
    → Gracze zawsze grają tutaj
    → Kod aktualizowany TYLKO przez skrypt deploy z GitHub main
    → Claude NIE edytuje plików bezpośrednio na .62
    → Restart tylko w maintenance window z powiadomieniem
```

**KRYTYCZNA ZASADA — ochrona przed przypadkowym edytowaniem PROD:**

> Zdarzało się że Claude implementował zmiany na .62 zamiast .61 — wprowadzało to bałagan i niespójności między środowiskami. Zasada: **kod na .62 pochodzi WYŁĄCZNIE z GitHub main, nigdy z bezpośredniej edycji.**

**Workflow deweloperski:**

```
Claude pracuje na .61 (DEV)
  → edytuje pliki przez sshfs mount
  → testuje lokalnie na .61
  → commit + push do GitHub main
        │
        ▼
Admin uruchamia na .62 (PROD):
  ./scripts/deploy_from_github.sh
        │
        ▼
Skrypt: git reset --hard origin/main
        + docker compose up --build
```

**Skrypt `deploy_from_github.sh` (do stworzenia na .62):**

```bash
#!/bin/bash
# PROD DEPLOY — tylko z GitHub main
# Nie edytuj plików bezpośrednio na tym serwerze!
set -e

REPO_DIR="/home/piotrszmidt/ai-gm"
cd "$REPO_DIR"

echo "Fetching latest from GitHub..."
git fetch origin main

echo "Resetting to origin/main (discards any local changes)..."
git reset --hard origin/main

echo "Building and restarting containers..."
docker compose -f docker-compose.yml up -d --build --remove-orphans

echo "PROD deploy complete."
docker compose -f docker-compose.yml ps
```

Kluczowe: `git reset --hard origin/main` gwarantuje że PROD zawsze = dokładnie GitHub main. Żadne lokalne zmiany na .62 nie przetrwają.

**Kroki wykonania A3:**

1. Skopiuj `docker-compose.yml` (prod) na .62
2. Skopiuj aktualną bazę danych z .61 → .62 (snapshot stanu gry)
3. Utwórz `scripts/deploy_from_github.sh` na .62
4. Zweryfikuj że gracze mogą grać na .62
5. Zaktualizuj NGINX Proxy Manager (.4): `aigm.studio-colorbox.com` → .62

**Czas szacunkowy:** 30-60 minut

**Maintanence notification:** Zanim gracze zostaną przeniesieni na .63, wyślij powiadomienie przez Telegram z 24h wyprzedzeniem.

---

### PROCEDURA A4: Oznaczanie wersji deployów

**Problem który rozwiązuje:**

Gracz zgłasza bug. Nie wiadomo: istniał przed ostatnim deployem czy pojawił się po nim?

**Rozwiązanie:**

Każdy deploy na PROD otrzymuje numer wersji. Logi błędów są tagowane numerem wersji.

**Implementacja (mała zmiana):**

Dodaj `APP_VERSION` do `.env` lub `docker-compose.yml`:
```
APP_VERSION=v48
```

Wstrzyknij do logów strukturalnych (jeden wiersz w `logging.py`):
```python
logger.bind(app_version=os.getenv("APP_VERSION", "dev"))
```

Efekt: każdy log błędu zawiera wersję. Gracz zgłasza bug w sobotę 14:23 → sprawdzasz logi → widisz `v47` → deploy v47 był w piątek 16:00 → bug pochodzi z nowego kodu.

**Czas szacunkowy:** 30 minut

---

### PROCEDURA A1: Sprzątanie codebase przed przebudową

**Problem który rozwiązuje:**

Projekt zawiera ~900 MB martwego kodu z poprzednich prób budowania systemu z innymi agentami. Zanim zaczniesz przebudowę, usuń śmieci — inaczej trudno odróżnić co jest nowe a co stare.

**Wyniki audytu dead code (wykonanego 2026-06-04):**

Audyt przeszedł cały codebase i sklasyfikował pliki jako aktywne / dead / niepewne.

**Bezpieczne do usunięcia (pewność 100%):**

| Co | Lokalizacja | Rozmiar | Powód |
|----|-------------|---------|-------|
| GitHub Actions runner | `actions-runner/` | **887 MB** | Porzucone CI/CD |
| Voice service (Piper/TTS/STT) | `voice-service/` | **708 MB** | Outsourcowane, Piper obsolete — zastąpiony własnym rozwiązaniem |
| Observability stack (Grafana/Loki) | `observability/`, `observability-dev/`, `observability-data/` | **~266 MB** | Zastąpiony własną implementacją w backendzie (2026-06-05) |
| Legacy admin panel v2 | `frontend/admin_panel_v2/` | małe | Zastąpiony przez v3 |
| Dead service | `backend/app/services/combat_v2_service.py` | 637 linii | Nigdy nie importowany |
| Temp images | `temp-img/` | 4.6 MB | Scratch space |
| Output dir | `output/` | 140 KB | Śmieci |

**Łącznie: ~1.9 GB do usunięcia.** Aktywny kod nie jest dotykany.

> **Decyzja: Grafana/Loki (2026-06-05):** Zewnętrzny stack observability zastępowany własną implementacją w backendzie. Elastyczniejsze, bez zewnętrznych zależności, prostsze w utrzymaniu.

**Do dodania do .gitignore:**
```gitignore
data/
data-dev/
backups/
.claude/settings.local.json
.claude/worktrees/
__pycache__/
*.pyc
backend/.venv/
backend/.pytest_cache/
.pytest_cache/
install-summary.txt
```

**Dodatkowe pliki do usunięcia z korzenia projektu:**

| Plik | Decyzja | Powód |
|------|---------|-------|
| `install-summary.txt` | ❌ Usuń + gitignore | Generated output z lokalnymi IP/URL — nie należy do repo |
| `install-summary.example.txt` | ❌ Usuń | Obsolete — przykład pliku który i tak będzie regenerowany |
| `install.sh` | ⚠️ Zachowaj tymczasowo | Koncepcja przydatna dla setup .62, ale wymaga przepisania (usuwa voice-service i observability). Przepisać przed deployem PROD. |

**Nowy `install.sh` (do napisania przy A3):**
Skrypt setup dla nowej maszyny bez voice-service i Grafana/Loki. Zawierać będzie `deploy_from_github.sh` jako docelowy mechanizm update PROD.

**Komendy wykonania (na .61):**
```bash
ssh claude@192.168.1.61 'cd /home/piotrszmidt/ai-gm && \
  rm -rf actions-runner/ \
  temp-img/ \
  output/'

# Na lokalnie (przez sshfs):
rm -rf frontend/admin_panel_v2/
rm backend/app/services/combat_v2_service.py
```

**Migracja admin2 → admin3 (więcej niż `rm`):**

> **Decyzja (2026-06-05):** Aktywny panel to admin_panel_v3. admin_panel_v2 do usunięcia, ale usunięcie wymaga najpierw potwierdzenia parzystości funkcji i odpięcia trasy `/admin2/`.

Samo `rm -rf admin_panel_v2/` nie wystarczy — trzeba dokończyć zastąpienie:

| # | Krok | Opis |
|---|------|------|
| A6 | Audyt parzystości | Potwierdzić że admin3 pokrywa WSZYSTKIE sekcje admin2 (mechanics, content, world, players, campaigns, narrator, analytics, workshops, sandbox, voice, system). Lista braków przed usunięciem. |
| A7 | Odpiąć trasę `/admin2/` | Usunąć serwowanie `/admin2/` (nginx / static mount). Zostaje tylko `/admin3/` (lub `/admin/`). |
| A8 | Zaktualizować dokumentację | `CLAUDE.md` wciąż opisuje admin_panel_v2 jako aktywny ("the active admin interface at /admin2/") — przepisać na v3. Zaktualizować tabelę sekcji i Reference Files. |
| A9 | Usunąć katalog | Dopiero po A6..A3: `rm -rf frontend/admin_panel_v2/`. |

> **Dlaczego nie usunąć od razu?** Jeśli admin3 nie pokrywa którejś sekcji admin2 (np. konkretny edytor), usunięcie odetnie admina od tej funkcji. Audyt parzystości (A6) musi to wykluczyć. Patrz: audyt admin3 (CZĘŚĆ AE).

**Do weryfikacji przez człowieka przed usunięciem:**

| Co | Lokalizacja | Pytanie |
|----|-------------|---------|
| Niezarejestrowany router | `backend/app/routers/campaign_workshop.py` | Celowo wyłączony (WIP) czy można usunąć? |
| Niezarejestrowany router | `backend/app/routers/ideas_workshop.py` | j.w. |
| Nieużywany moduł | `backend/app/api/slash_command_registry.py` | Można usunąć? |
| Test dead routerów | `backend/tests/test_phase8_workshop.py` | Usunąć razem z routerami? |

> **Nota:** `mcp_server/` w korzeniu projektu to aktywny MCP server używany przez Claude — **nie usuwać**.

**Czas szacunkowy:** 15 minut (po decyzji o niepewnych plikach)

---

### PROCEDURA A5: Maintenance workflow dla PROD

**Problem który rozwiązuje:**

Brak procedury = gracze dowiadują się o restarcie gdy sesja pada. Zły user experience.

**Nowy workflow deployów na PROD:**

```
1. Napisz co zmieniasz (changelog jednozdaniowy)
2. Deploy i test na DEV (.61)
3. Jeśli OK: wyślij powiadomienie Telegram:
   "🔧 Aktualizacja serwera za ~30 min. Zapisz postęp."
4. Poczekaj 30 minut (gracze kończą tury)
5. Deploy na PROD (.63): ./scripts/deploy_prod.sh
6. Weryfikacja: sprawdź health endpoint
7. Poinformuj graczy: "✅ Aktualizacja zakończona. Nowa wersja: v49"
```

**Czas szacunkowy:** 10 minut na napisanie SOP

---

### PROCEDURA A1 (uzupełnienie): Niezarejestrowane routery

Dwa routery istnieją w kodzie ale nie są zarejestrowane w `main.py`:
- `backend/app/routers/campaign_workshop.py`
- `backend/app/routers/ideas_workshop.py`

**Status:** Zostawione tymczasowo. **Do usunięcia gdy potwierdzono że zbędne** (przy przebudowie campaign monitor i warsztatu pomysłów w Fazie 3 lub 4 zostanie podjęta decyzja).

---

### PROCEDURA A2: Audyt i unifikacja schematu bazy danych

**Problem który rozwiązuje:**

Przed budową World State musimy wiedzieć czy "źródło prawdy" (baza danych) ma spójny i poprawny kształt. Aktualnie w bazie istnieją **trzy różne systemy opisywania efektów** dla obiektów gry:

```
game_config_items       → effect_json jako blob JSON
                          Przykład: {"stat_mods":{"AC":4}, "enables":["climbing"]}

game_config_consumables → OSOBNE KOLUMNY (effect_type, effect_dice, effect_bonus)
                          Przykład: effect_type="heal_hp", effect_dice="2d6", effect_bonus=4

game_config_conditions  → effect_json z innym schematem niż items
                          Przykład: {"damage_per_turn":3, "skip_turn":true, "duration":"3 turns"}

game_config_weapons     → effect_json przeważnie NULL, brak systemu efektów
```

To jest chaos. LLM dostaje różne dane w różnych formatach zależnie od tabeli. Admini nie wiedzą co wpisać bo nie ma dokumentacji schematu.

**Ten problem jest tak głęboki że wymaga osobnego redesignu** — patrz SEKCJA "Redesign effect_json" poniżej w Fazie 4.

**Co zrobić TERAZ (przed Fazą 0):**

Nie przepisujemy schematu teraz. Ale dokumentujemy co istnieje żeby World State wiedział skąd brać dane.

Zadania audytu:
1. Sprawdź czy wszystkie wymagane kolumny istnieją dla każdej tabeli (czy migracje były uruchamiane)
2. Sprawdź spójność FK (czy `loot_table_key` w `game_config_enemies` ma odpowiadające rekordy w `game_config_loot_tables`)
3. Sprawdź czy `game_config_skills` ma wszystkie umiejętności które są używane w kodzie
4. Zidentyfikuj "sieroty" — rekordy które są w bazie ale nigdzie nie używane

**Czas szacunkowy:** 30-60 minut (można zlecić agentowi)

---

### Kolejność wykonania procedur wstępnych

```
A1: Sprzątanie codebase  (15 min)
        ↓
A2: Audyt schematu DB  (30-60 min)
        ↓
A3: Przywrócenie PROD na .63  (60 min)
        ↓
A4: Wersjonowanie deployów  (30 min)
        ↓
A5: Maintenance workflow  (10 min)
        ↓
    → GOTOWE do Fazy 0 (World State)
```

**Łączny czas procedur wstępnych:** ~3 godziny

---

## Legenda statusów

| Symbol | Znaczenie |
|--------|-----------|
| 🔴 | Krytyczny problem — blokuje całą grę |
| 🟡 | Ważny problem — psuje doświadczenie |
| 🟢 | Dobry pomysł — zachować |
| ❌ | Odrzucony design — zastąpiony lepszym |
| ✅ | Zaakceptowany design |
| 📐 | Do zaprojektowania w tej sesji |

---

## CZĘŚĆ 1 — Co było nie tak (Diagnoza)

Zanim zaprojektujemy nowe rozwiązania, musimy zrozumieć *dlaczego* stare nie działało.

### Błąd #1 🔴 — LLM jako "agent decydujący"

**Co było:** LLM decyduje o wszystkim — kiedy jest walka, co gracz dostaje, które lokacje istnieją, kiedy quest jest ukończony.

**Dlaczego to nie działa:**

LLM to model językowy. Jego zadaniem jest generowanie przekonującego tekstu. Nie jest deterministyczny — ta sama sytuacja może dać różne wyniki. Dwa konkretne przykłady które już wystąpiły w grze:

- Gracz siedzi w zamkniętej celi. Mówi "atakuję goblina". LLM *opisuje* goblina choć go nie było w scenie, a potem inicjuje walkę z nieistniejącym wrogiem. → **Bug 2**
- Gracz jest w interesującym miejscu. LLM pisze dobry opis ale nigdy nie sugeruje ruchu. Gracz tkwi na jednym hexie przez 50 tur. → **Bug 1**

Nie można naprawić tych bugów "lepszym promptem". LLM będzie *lepiej* — ale nie *zawsze poprawnie*. Przy 1000 turach na miesiąc, nawet 99% skuteczność = 10 błędów dziennie.

**Poprawny design:**

> **Zasada #1:** LLM jest *narratorem*. Mechanika jest *decydentem*.

Mechanika mówi co jest *możliwe*. LLM opisuje *jak to wygląda*.

```
❌ Stare podejście:
Player: "Atakuję goblina"
→ LLM decyduje: "Goblin jest tu" → inicjuje walkę

✅ Nowe podejście:
Player: "Atakuję goblina"
→ Mechanika sprawdza: scene_enemies = [] → BRAK goblina
→ Mechanika blokuje akcję ATTACK
→ LLM dostaje sygnał: "brak wrogów w scenie"
→ LLM narruje: "Rozglądasz się, ale w pobliżu nie ma nikogo"
```

---

### Błąd #2 🔴 — World State nie istnieje, ale wszystko na nim zależy

**Co było:** Zaplanowaliśmy World State jako "opcję do rozważenia". Tymczasem bez niego nie działa:
- Pamięć NPC (E10 w game_flow)
- Walidacja walki (Bug 2)
- Sugestia ruchu po mapie (Bug 1)
- System questów (E12)

To jak zaplanować windę w budynku który nie ma jeszcze ścian.

**Poprawny design:**

World State budujemy JAKO PIERWSZE, bo wszystko inne zależy od niego. Szczegóły w Części 2.

---

### Błąd #3 🟡 — "Admin-free" = "Admin nieobecny" (nieprawda)

**Co było:** Zasada mówiła że admin może wyjechać na wakacje, a gra działa.

**Dlaczego to nieprawda:**

Przy 10 aktywnych graczach dziennie, LLM generuje dziesiątki nowych rekordów: wrogów, lokacji, przedmiotów. Każdy wchodzi do kolejki PENDING. Admin musi każdy przejrzeć i zatwierdzić. Przy długiej nieobecności: setki niezatwierdzonych rekordów. Gracze grają w "mrożony świat" — nic nowego nie wchodzi globalnie.

**Poprawny design:**

Admin-free oznacza *Admin-asynchroniczny* — admin pracuje kiedy może, nie kiedy musi. Ale potrzebujemy systemu który nie tworzy kolejki niemożliwej do obsłużenia:

- **Auto-screening:** LLM sam ocenia swój output. Rekordy spełniające wymagania idą do "szybkiej ścieżki" w admin panelu
- **Auto-approve dla prostych przypadków:** Wróg podobny do istniejących (goblin-wariant) → auto-approve z flagą do późniejszej rewizji
- **Admin review dla unikalnych:** Nowy typ wroga którego nie ma w bazie → czeka na admina

---

### Błąd #4 🔴 — 2 z 3 archetypów nie mają progresji

**Co było:** System XP ma 15 źródeł, ale wydawanie XP działa tylko dla Uczonego (kupno zaklęć). Wojownik i Łotr akumulują XP bez celu.

**Jak to wygląda dla gracza:**
> Gracz gra Wojownikiem 3 godziny. Zdobywa 400 XP. Idzie odpocząć. System pyta czy chce wydać XP. Nie ma na co — tylko zaklęcia, a Wojownik ich nie ma. Czuje się oszukany.

**Poprawny design:** Przed otwarciem gry dla testerów: spend_skill i spend_stat muszą działać dla wszystkich archetypów.

---

### Błąd #5 🟡 — Brak pętli feedbacku dla gracza

**Co było:** Gracz nie wie że ma pending XP. Nie wie że może odpocząć. Nie wie że quest istnieje dopóki nie wpisze komendy. Gra nie "mówi" co robić.

W RPG to zabójstwo zaangażowania. Gracz po 10 turach nie wie czy robi postęp.

**Poprawny design:** Stały HUD który pokazuje:
- Aktualny XP (ile do następnego wydania)
- Aktywne questy (tytuł + cel)
- Stan odpoczynku (czy mogę teraz odpocząć?)
- Czas gry (Dzień N, godzina X)

---

### Błąd #6 🟡 — Brak onboardingu

**Co było:** Nowy gracz tworzy postać bez wyjaśnienia co znaczy STR 14 vs STR 8, do czego służy Charyzma, czym różni się Wojownik od Łotra mechanicznie.

**Poprawny design:** Kreator musi wyjaśniać każdy wybór w prostym języku na ekranie.

---

## CZĘŚĆ 2 — Nowa Architektura: World State

World State to "źródło prawdy" o tym co teraz dzieje się w grze gracza. Każda taktyczna decyzja mechaniki jest oparta o World State, nie o "co LLM zrozumiał z ostatnich N tur".

### Co to jest World State (prosto)

Wyobraź sobie tablicę w pokoju gry. Na tablicy napisane jest:
- Gdzie teraz stoi bohater (hex, lokacja)
- Kto jest w scenie (wrogowie, NPC)
- Jakie questy są aktywne
- Jaki jest czas w grze

Każda akcja gracza jest sprawdzana względem tablicy *zanim* LLM cokolwiek powie. Po wykonaniu akcji tablica jest aktualizowana.

### Schemat World State

```
WORLD STATE (per sesja, per bohater)
├── POZYCJA
│   ├── current_hex: (4, 7)
│   ├── current_terrain: "forest"
│   └── current_location: "Karczma Pod Jeleniem" | null
│
├── SCENA (co teraz jest w aktualnym miejscu)
│   ├── scene_enemies: ["goblin", "goblin_chief"]  ← LLM je wprowadza, mechanika śledzi
│   ├── scene_npcs: ["karczmar_jan", "podroznik"]
│   └── scene_cleared: false  ← true gdy wszyscy wrogowie pokonani
│
├── AKTYWNE QUESTY
│   ├── [{key: "znajdz_marte", title: "...", objective: "..."}]
│   └── (max N aktywnych jednocześnie — do ustalenia)
│
├── STAN BOHATERA
│   ├── player_conditions: ["poisoned"]
│   ├── short_rests_used: 1  ← ile krótkich odpoczynków od ostatniego długiego
│   └── can_long_rest: true | false  ← czy lokacja jest bezpieczna
│
└── CZAS
    ├── ingame_hours: 57  (od startu kampanii)
    └── game_day: 3
```

### Jak World State jest używany przy każdej turze

```
Gracz wpisuje akcję
        │
        ▼
1. Parser Intencji
   "Atakuję goblina" → intent: ATTACK, target: "goblin"
        │
        ▼
2. Gate Mechaniki (deterministyczny — nie LLM)
   Sprawdza World State:
   - ATTACK → scene_enemies zawiera "goblin"? TAK → przejdź dalej
   - ATTACK → scene_enemies zawiera "goblin"? NIE → blokuj, odpowiedz: "Brak celu"
        │
        ▼
3. Kontekst dla LLM
   Backend dołącza TYLKO relevantny fragment World State:
   - Dla walki: scene_enemies + player_conditions
   - Dla rozmowy z NPC: scene_npcs + pamięć NPC z World State
   - Dla ruchu: current_hex + discovered_hexes + available_directions
        │
        ▼
4. LLM narruje
   Dostaje: akcja gracza + relevantny kontekst + tożsamość bohatera + ostatnie N tur
   Zwraca: narrację + opcjonalne tagi mechaniczne
        │
        ▼
5. Mechanika wykonuje
   Parsuje tagi z odpowiedzi LLM
   Aktualizuje World State
   Zapisuje do bazy
```

### Dlaczego to rozwiązuje Bug 1 i Bug 2

**Bug 2 (walka z nieistniejącym wrogiem):**
```
Stare: Gracz "atakuję goblina" → LLM decyduje że goblin jest → walka
Nowe:  Gracz "atakuję goblina" → Gate sprawdza scene_enemies=[] → BLOK
       Gracz nigdy nie widzi walki z powietrzem
```

**Bug 1 (gracz nie rusza):**
```
Stare: LLM opisuje świat ale nie sugeruje ruchu (zależy od prompta)
Nowe:  Po każdej turze mechanika sprawdza: czy minęło X tur bez zmiany hex?
       Jeśli tak → backend wymusza kontekst "eksploracja" dla LLM
       LLM dostaje instrukcję: "sugeruj ruch do nowej lokacji"
       Sugestia ruchu pojawia się jako pill automatycznie co N tur braku ruchu
```

---

## CZĘŚĆ 3 — Redesign Systemu Questów

### Problem z obecnym designem

W `game_flow.md` zaprojektowaliśmy: LLM emituje `[QUEST_START]` → quest powstaje. `[QUEST_COMPLETE]` → XP przyznane.

**Dlaczego to jest podatne na halucynacje:**
- LLM może zapomnieć emitować `[QUEST_COMPLETE]` (quest nigdy nie kończy się)
- LLM może emitować `[QUEST_COMPLETE:klucz_który_nie_istnieje]` (XP za nic)
- Gracz może manipulować LLM żeby "opowiedział" o ukończeniu questa

### Nowy design: Backend-driven quests

> **Zasada:** Questy są *obiektami mechaniki* — nie elementami narracji. LLM opisuje quest, mechanika go śledzi.

**Jak to działa:**

```
1. LLM może ZAPROPONOWAĆ quest:
   [QUEST_SUGGEST: key="znajdz_karte", title="Zagubiona Karta", 
    objective_type="find_item", objective_value="stara_mapa"]
   
   Backend waliduje:
   - czy key jest unikalny?
   - czy objective_type jest prawidłowy (enum)?
   - czy objective_value istnieje w bazie?
   → Jeśli TAK: quest tworzony w character_quests
   → Jeśli NIE: tag ignorowany, LLM może narracyjnie opisać "zadanie" ale XP nie będzie

2. Mechanika śledzi postęp:
   Gdy gracz bierze przedmiot "stara_mapa" → backend sprawdza aktywne questy
   Czy jakiś quest ma objective_type="find_item" AND objective_value="stara_mapa"?
   → TAK → mechanika automatycznie zamyka quest + przyznaje XP
   → Nie potrzeba [QUEST_COMPLETE] od LLM

3. LLM narruje zakończenie:
   Backend informuje LLM: "quest znajdz_karte jest teraz ukończony"
   LLM opisuje moment narracyjnie
```

**Typy celów questów (objective_type):**

| Typ | Opis | Przykład |
|-----|------|---------|
| `find_item` | Zdobądź konkretny przedmiot | znajdź starą mapę |
| `kill_enemy` | Pokonaj określonego wroga | zabij szefa bandytów |
| `visit_location` | Dotrzyj do lokacji | odwiedź wieżę maga |
| `talk_to_npc` | Porozmawiaj z NPC | spotkaj się z leśniczym |
| `survive_turns` | Przeżyj N tur | przetrzymaj oblężenie przez 5 tur |
| `custom` | Cel niestandardowy — zamykany ręcznie przez LLM lub admina | uratuj księżniczkę |

> **Dlaczego `custom` istnieje?** Nie wszystko da się opisać deterministycznie. Ale `custom` jest flagowany jako "wymaga uwagi" i LLM musi wyraźnie oznaczyć kiedy warunek jest spełniony narracyjnie. To ogranicza halucynacje do jednej kategorii.

---

## CZĘŚĆ 4 — Redesign Progresji (XP Spend dla wszystkich)

### Problem

XP istnieje dla wszystkich → XP można wydać tylko jako Uczony → 2/3 archetypów nie ma progresji.

### Rozwiązanie: Universalny system wydawania XP

Wszystkie opcje dostępne tylko podczas **długiego odpoczynku** (już tak zdefiniowane w game_flow.md).

**Tabela wydatków XP (do zbilansowania w testach):**

| Akcja | Archetype | Koszt | Limit |
|-------|-----------|-------|-------|
| Podniesienie rangi umiejętności (1→2) | Wszyscy | 75 XP | rank_ceiling |
| Podniesienie rangi umiejętności (2→3) | Wszyscy | 150 XP | rank_ceiling |
| Nauka nowej umiejętności | Wszyscy | 100 XP | max 2 nowe per level |
| +1 do statystyki | Wszyscy | patrz tabela progresji | max 1 per level |
| Nauka nowego zaklęcia | Uczony | 75 XP | lista zaklęć |
| Upgrade zaklęcia R2 | Uczony | 50 XP | - |
| Upgrade zaklęcia R3 | Uczony | 100 XP | - |

**Tabela progresji statystyki (+1 STR):**

Koszt rośnie z obecnym poziomem statystyki:

| Obecna wartość | Koszt +1 |
|---------------|----------|
| 8–10 | 50 XP |
| 11–13 | 100 XP |
| 14–16 | 200 XP |
| 17–18 | 400 XP |
| 19+ | Niedostępne |

> **Dlaczego rosnące koszty?** Statystyka 20 = gracz 4x mocniejszy niż przy 12. Bez rosnącego kosztu gracze z dużą ilością czasu przepompowaliby jedną statystykę i złamali balans.

> **Dlaczego max 1 upgrade stat per level?** Zabezpieczenie przed "min-maxingiem" — gracz który zignoruje historię i po prostu farmuje XP na jedną statystykę nie powinien mieć nieograniczonego dostępu do upgradów.

**UI podczas długiego odpoczynku:**

Gdy gracz deklaruje długi odpoczynek w bezpiecznej lokacji:
1. Modal odpoczynku wyświetla opcje: "Ucz się" / "Śpij"
2. Jeśli wybiera "Ucz się": widzi swoje dostępne XP i listę co może kupić
3. Po wyborze: animacja (np. "Ćwiczysz z mieczem całą noc") + zakup
4. Może kupić wiele rzeczy jeśli ma dość XP
5. "Śpij": regeneracja HP/many bez wydawania XP

---

## CZĘŚĆ 5 — Redesign Admin Queue (Auto-screening)

### Problem

Każdy AI-generowany rekord idzie do admin queue. Przy 10 graczach × 10 tur × 3 nowe rekordy = 300 rekordów dziennie. Admin nie da rady.

### Nowy design: 3-poziomowa weryfikacja

```
LLM generuje nowy rekord (lokacja / wróg / przedmiot)
        │
        ▼
POZIOM 1: Automatyczna walidacja techniczna (backend, 0ms)
- Czy wszystkie wymagane pola są wypełnione?
- Czy wartości są w sensownym zakresie? (HP 1-9999, nie -5 ani 50000)
- Czy klucz jest unikalny?
        │
    FAIL → rekord odrzucony automatycznie, LLM dostaje info
    PASS ↓
        │
        ▼
POZIOM 2: Auto-scoring (LLM self-evaluation, ~1s)
Backend wysyła rekord do osobnego LLM call:
"Oceń czy ten wróg jest balansowo sensowny: [dane]
Odpowiedz JSON: {score: 1-10, reason: str, auto_approve: bool}"
        │
    score < 5 → odrzucony automatycznie
    score 5-7 → idzie do admin queue (wymaga uwagi)
    score 8-10 AND auto_approve=true → auto-zatwierdzony lokalnie
        │
        ▼
POZIOM 3: Admin review (opcjonalny, async)
Admin przegląda rekordy w wolnej chwili:
- Auto-zatwierdzone lokalnie → "fast track" — admin może globalnie zatwierdzić jednym kliknięciem
- Do rewizji → normal review
- Odrzucone → log (do wglądu)
```

> **Dlaczego LLM ocenia własny output?** LLM jest dobry w ocenianiu struktury i sensowności — dużo lepszy niż przy generowaniu kreatywnym. "Czy goblin z HP=5 i atak=d4 jest sensowny?" to proste pytanie dla LLM, nawet jeśli generowanie goblina z dokładnie tymi parametrami jest podatne na błędy.

> **Ryzyko:** LLM może "zatwierdzać" własne błędy. Dlatego poziom 2 to tylko pre-screening — admin zawsze może zrewidować i cofnąć.

---

## CZĘŚĆ 6 — Redesign Onboardingu

### Problem

Nowy gracz nie rozumie mechaniki. Archetypy opisane jako "Wojownik — siła fizyczna" to za mało. Co to znaczy mechanicznie? Jak STR 14 różni się od STR 8 w praktyce? A potem czeka go cała reszta: rzuty kością, walka, strefy, rany, XP, złoto, śmierć. Za dużo by wyłożyć naraz, za ważne by pominąć.

### Zasada naczelna: gra uczy gry, nie LLM

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Mechaniki uczy BACKEND (deterministyczne karty + kodeks), nie LLM. LLM może co najwyżej miękko podpowiadać w trybie tutorial, ale nigdy nie jest źródłem prawdy o zasadach.

> **Dlaczego?**
> LLM halucynuje zasady. Jeśli oddasz tłumaczenie mechaniki LLM-owi ("wyjaśnij graczowi jak działa walka"), w turze 3 powie poprawnie, a w turze 30 wymyśli regułę której nie ma. Mechanikę zna kod — więc kod uczy. To ta sama zasada co w całym redesignie: mechanika decyduje, LLM narruje. Tutaj: mechanika uczy, LLM co najwyżej zachęca.

> **Co odrzucono i dlaczego?**
> - **Główna nauka przez tutorial z LLM** (pierwotny pomysł CZĘŚCI 6) — prostsze, ale LLM myli zasady i nie działa poza tutorialem (gracz który pominie samouczek nigdy nie pozna mechaniki). Odrzucone jako mechanizm główny, zachowane jako miękki dodatek.

### Cztery warstwy onboardingu

Od miękkiej (klimat) do twardej (zasady), uczone w kolejności w jakiej gracz ich potrzebuje.

#### Warstwa 1 — Kreator: uczy KIM jesteś, nie matematyki

Progresywne opisy w kreatorze. Cel: gracz rozumie swoją postać i styl gry, nie cały system naraz.

Krok 1 (Archetyp):
```
Zamiast: "Wojownik — siła fizyczna, walka wręcz"
Powinno być:
"⚔️ WOJOWNIK
Mocna strona: Walka. Każdy udany cios zadaje więcej obrażeń niż u innych.
Słaba strona: Magia. Nie może używać zaklęć.
Styl gry: Wchodzisz w środek walki, atakiem rozwiązujesz problemy.
Przykładowa akcja: 'Uderzam goblin toporem z całej siły'"
```

Krok 2 (Statystyki) — każda staty ma tooltip "co to robi w praktyce":
```
"STR 14 — Twoje ataki wręcz zadają +2 do obrażeń. Możesz nosić ciężką zbroję bez kary."
"STR 8  — Ataki wręcz zadają -1 do obrażeń. Lekkie bronie polecane."
```

Krok 3 (Umiejętności) — każda z przykładem kiedy się przyda:
```
"SKRADANIE (DEX) — Przechodzisz niepostrzeżenie obok straży.
 'Czołgam się za wrogiem zanim go zauważy'"
```

#### Warstwa 2 — Karty just-in-time (RDZEŃ)

> **Decyzja (2026-06-05):** Główny mechanizm nauki. Backend śledzi `seen_mechanics` per gracz; pierwszy raz gdy mechanika się odpala, frontend pokazuje jednorazową kartę wyjaśniającą.

```
Pierwszy test umiejętności → karta:
  "🎲 RZUT KOŚCIĄ
   d20 + twoje umiejętności vs trudność.
   Wyrzucisz ≥ próg = sukces. 20 = zawsze sukces, 1 = zawsze porażka."

Pierwsza walka      → karta: inicjatywa + strefy (ZWARCIE/DYSTANS) + atak/ucieczka
Pierwsza rana       → karta: "Jesteś ranny — bijesz słabiej. Lecz się albo uciekaj."
Pierwsze PD do wydania → karta: "Masz Punkty Doświadczenia. Odpocznij długo by je wydać."
Pierwsze złoto      → karta: sklep, kupno/sprzedaż
Pierwszy rzut na śmierć → karta: death saves
```

Gracz zamyka kartę, nigdy więcej jej nie widzi. Działa w KAŻDEJ kampanii (nawet gdy pominie tutorial). Uczy DOKŁADNIE gdy potrzebne, nie zalewa na starcie.

> **Dlaczego just-in-time, a nie wszystko na starcie?** Wyłożenie 8 mechanik przed pierwszą turą = gracz nic nie zapamięta (brak kontekstu). Karta przy pierwszym wystąpieniu trafia w moment gdy gracz właśnie tego doświadcza — wtedy się uczy.

> **Dlaczego `seen_mechanics` per gracz, nie per bohater?** Gracz uczy się gry RAZ. Drugi bohater nie powinien znów dostawać kart "jak działa rzut kością" — gracz już to wie. Stan przypięty do konta gracza, nie do postaci.

#### Warstwa 3 — Kodeks (zawsze dostępny)

Panel pomocy "Wiedza" — player-facing wersja knowledge booka (który już istnieje w adminie). Gracz w każdej chwili sprawdza "Jak działa walka?", "Co to strefy?". Wysuwany, nieinwazyjny, niewymuszony. Dla tych co zapomną kartę albo wrócą po przerwie.

#### Warstwa 4 — Tutorial kampania (opcjonalna, miękka)

> **Decyzja (2026-06-05):** Tryb "Moja Pierwsza Przygoda" domyślnie WŁĄCZONY dla nowego gracza, z wyraźnym przyciskiem "Pomiń". Łagodny start bez przymusu.

Krótka kampania (5-10 tur) gdzie LLM dostaje instrukcje by podpowiadać narracyjnie ("strażnik wygląda groźnie — może warto rzucić na Skradanie?"):
- Tura 1-2: narracyjne wprowadzenie bez walki
- Tura 3: pierwsza walka ze słabym wrogiem
- Tura 4-5: prosty quest
- Tura 6+: przejście w normalną kampanię

> **Uwaga:** tutorial to miękki DODATEK, nie fundament nauki. Twarda nauka zasad = warstwa 2 (karty). Tutorial daje tylko łagodniejszy, prowadzony pierwszy raz. Gracz który kliknie "Pomiń" i tak nauczy się przez karty.

### Dlaczego karty > tutorial-LLM

| | Tutorial-LLM (pierwotny pomysł) | Karty just-in-time (decyzja) |
|---|---|---|
| Poprawność zasad | ❌ LLM halucynuje z czasem | ✅ deterministyczne |
| Działa poza tutorialem | ❌ tylko w samouczku | ✅ każda kampania |
| Timing nauki | front-loaded (tura 3-5) | dokładnie gdy mechanika fire'uje |
| Powtórka / przypomnienie | ❌ jednorazowe | ✅ kodeks zawsze pod ręką |

### Status implementacji (CZĘŚĆ 6)

| Element | Status |
|---------|--------|
| Onboarding cinematic (intro + wybór motywu) | ✅ działa (kosmetyka, nie mechanika) |
| Warstwa 1: progresywne opisy w kreatorze | ❌ obecnie suche etykiety — do rozbudowy |
| Warstwa 2: karty just-in-time + `seen_mechanics` | ❌ do zbudowania (rdzeń) |
| Warstwa 3: kodeks player-facing (z knowledge book) | ❌ admin ma, gracz nie |
| Warstwa 4: tutorial kampania domyślnie-ON/pomijalna | ❌ do zbudowania |

### Zadania implementacyjne

| # | Zadanie | Priorytet |
|---|---------|-----------|
| E23 | `seen_mechanics` per gracz (tabela/pole) + endpoint mark-seen | 1 |
| E24 | Karty just-in-time: rzut, walka, rana, PD, złoto, death save — trigger przy pierwszym wystąpieniu | 1 |
| E25 | Warstwa 1: rozbudowa opisów kreatora (archetyp/staty/skille z mechanicznym sensem + przykłady) | 2 |
| E26 | Kodeks player-facing (reuse knowledge book) — wysuwany panel pomocy | 2 |
| E27 | Tutorial kampania "Moja Pierwsza Przygoda" domyślnie-ON + przycisk Pomiń + instrukcje LLM | 3 |

---

## CZĘŚĆ 7 — Master Lista Implementacji (Kolejność Budowania)

> **Filozofia:** Każda faza musi być w pełni działająca zanim zaczniesz następną. Nie buduj dachu bez ścian. Lista obejmuje WSZYSTKIE rodziny zadań z całego dokumentu.

> **Aktualizacja 2026-06-05:** Przepisano z pierwotnej listy (F0-F4) na pełną listę pokrywającą sekcje X, Y, Z, AA–AG + nowe rodziny zadań.

---

### FAZA 1 — Rdzeń pętli (core loop) ✅ UKOŃCZONA (C1–C19, 2026-06-06, v1.2.3)

> ✅ Cała faza zakończona — pełne notatki implementacyjne w sekcji **WYKONANE** na końcu pliku. Tabela poniżej pozostaje jako referencja zakresu.
> Podstawowe gameplay musi działać bezbłędnie. Zależności krytyczne: Gate(B3) + World State(B1).

| Kod | Zadanie | Zależy od |
|---|---|---|
| C1 | Fix Bug 1 — LLM musi sugerować ruch hex po N turach bez zmiany lokacji | B3 |
| C2 | Walidacja ruchu mechaniczna (nowy hex, terrain, lokacja check, update World State) | C1 |
| C3 | Fix Bug 2 — Gate walki (scene_enemies check przed każdym ATTACK) | B3 |
| C4 | Unifikacja wound_penalty: refactor z sheet-only na hp_current/hp_max (dotyczy każdego kombatanta) | — |
| C5 | Symetria ran: wound_penalty dla wrogów (nie tylko gracza) | C4 |
| C6 | Ujednolicenie progów ran frontend/backend (frontend ma inne progi niż vitality_service) | C4 |
| C7 | XP Spend — endpoint spend_skill (wszystkie archetypy) | — |
| C8 | XP Spend — endpoint spend_stat (wszystkie archetypy) | C7 |
| C9 | UI długiego odpoczynku — modal "Ucz się" (lista zakupów XP) | C7, C8 |
| C10 | System questów — QUEST_SUGGEST tag + walidacja backend | B2 |
| C11 | Mechaniczne śledzenie postępu questów (auto-complete per akcja) | C10 |
| C12 | `[SPEND_GOLD:X]` tag — kwota z tabeli/configu, NIE z LLM | — |
| C13 | Instrukcja "tylko złoto GP" w system_prompt (usunięcie waluty srebrnej) | — |
| C14 | Hero-first fix: startCharacterWizard() tylko z Heroes screen, NIGDY z _finalCreateCampaign | — |
| C15 | Error boundary dla API failures (toast zamiast białego ekranu) | — |
| C16 | Delete confirmation modals (kampania, postać) | — |
| C17 | Kontekst ekwipunku postaci — injection listy posiadanych przedmiotów i złota do LLM przy każdej turze | — |
| C18 | Fix Bug 3 — kampanie zawsze startują na nowych hexach na obrzeżach mapy zamiast reużyć istniejących hexów | C14 |
| C19 | Fix Bug 4 — bohater startujący nową kampanię dostaje ostatni stan HP zamiast pełnego | — |

---

### FAZA 2 — Systemy + Narracja

> Budowa na rdzeniu. Wymaga działającej Fazy 1.

| Kod | Zadanie | Zależy od |
|---|---|---|
| D1 | Pending flow przedmiotów (GRANT_ITEM nieznanego klucza → auto-screen → pending=true) | B3 |
| D2 | Pending flow wrogów (analogicznie do D1) | B3 |
| D3 | NPC pamięć w World State (NPC_MEMORY tag → context injection przy kolejnej wizycie) — ✅ `13678bf` | B2 |
| D4 | Auto-screening admin queue (Poziom 1 tech validation + Poziom 2 LLM scoring) | — |
| D5 | Item VIEW — podgląd przedmiotu w inventory (tooltip/modal z pełnym opisem) | — |
| D6 | Narracja: tagi, parsery, Narrative State struktura (dawne D6/D6/D6) | B1 |
| D7 | Encountery generyczne (adventure_hooks + gameconfig_encounter_templates unifikacja) | B3 |
| D8 | Ekran profilu gracza (konto, znajomi, ustawienia LLM) | — |
| D9 | Ekran kampanii — 5 trybów (Nowa/Gotowa/Loch/Loch-kafelki/Multiplayer) | C14 |
| D10 | Onboarding animacja + wybór motywu (nowy gracz) | — |
| D11 | Confirm password na rejestracji | — |
| D12 | Szybka nawigacja Hub → Gra (bez przeładowania) | — |
| D13 | Mobile layout — weryfikacja responsywności wszystkich ekranów | — |
| D14 | Bugfix: `update_item` ustawia approved=1 przy edycji przedmiotu z approved=0 (`current.approved or 1` traktuje 0 jako fałsz) — znaleziony przy D1/#376 | — |

---

### FAZA 3 — Jakość + Treść ✅ KOMPLETNA (E1–E28, E27 deferred→Faza 4) 2026-06-09

> Retencja graczy i zawartość. Wymaga działającej Fazy 1+2. E1–E14 zaimplementowane (GitHub #416–429); E15–E28 następna iteracja.

| Kod | Zadanie | Zależy od |
|---|---|---|
| E1 | Player HUD (HP/Mana, Złoto, Questy, XP bar, Czas) — aktualizacja per tura | C7 |
| E2 | Kreator bohatera — tooltips (archetyp, statystyki, umiejętności z przykładami) | — |
| E3 | Ekran zakończenia kampanii (podsumowanie + LLM epitafium) | — |
| E4 | Ekran śmierci (epitafium + statystyki + Wskrześ/Nowy bohater) | C4 |
| E5 | Zamknięcie dostępu do kampanii martwego bohatera (hero_status=dead) | E4 |
| E6 | Narracja: kompresja, historia, tagi narracyjne | D6 |
| E7 | Rozbudowa `campaign_templates` (required_npc_keys, required_beats, player_visible) | B1 |
| E8 | Ekran wyboru gotowej kampanii dla gracza (karty, trudność, opisy) | E7 |
| E9 | Story Gravity: trigger = next_required_beat nie odpalony przez N tur; progi w admin (5/10/15 tur), poziom 3 domyślnie OFF | E7 |
| E10 | Forge: walidacja wymaganych NPC/lokacji przy publikacji szablonu | — |
| E11 | Template Narrative State pre-seeding (narrative_hooks z szablonu → World State przy starcie) | E7 |
| E12 | Workflow publikacji szablonów (draft → review → published) | — |
| E13 | Encountery generyczne — rozbudowa puli adventure_hooks | D7 |
| E14 | Skalowanie encounterów per poziom gracza | E13 |
| E15 | Snapshot stanu przy wejściu do lochu | B1 |
| E16 | Przywróć snapshot przy śmierci w lochu + restart | E15 |
| E17 | Rarity tierów loot w lochach (5 tierów, mapowanie difficulty→rarity) | E15 |
| E18 | Cooldown UI lochów w Admin Panelu | — |
| E19 | LLM Vision: obrazek → opis kafelka (task na maszynie .170) ✅ #434 | H3 |
| E19b | AI prompt generator + ai-create endpoint dla kafelków ✅ #459 | — |
| E19c | Compositor redesign: cienka ramka + flat door markers + generate-description ✅ #460 | — |
| E20 | Admin UI tile manager (obrazki, drzwi, opisy kafelków) ✅ #435 (covered by E19b/E19c) | — |
| E21 | Wejście do lochu z mapy hex kampanii ✅ #436 | B1 |
| E22 | Resume niedokończonego runu lochu ✅ #437 | E15 |
| E23 | Seen_mechanics tracking per gracz (nie per postać) ✅ #438 | — |
| E24 | Backend trigger kart onboarding (first mechanic occurrence) ✅ #439 | E23, Faza 1+2 |
| E25 | Karty onboarding UI (nieblokujące overlay, "Rozumiem") ✅ #440 | E24 |
| E26 | Biblioteka kart (gracz może wrócić do przeczytanych) ✅ #441 | E25 |
| E27 | Karty dla nowych mechanik (afiksy, crafting, MP) — dodać gdy systemy gotowe ⏳ Faza 4 | Faza 4 |
| E28 | Tutorial kampania "Moja Pierwsza Przygoda" ✅ #443 | E25 |

---

### FAZA 4 — Rozbudowa: Efekty, Afiksy, Ekonomia

> Główne systemy depth-u. Kluczowa zależność: Effects→Afiksy→Crafting.

| Kod | Zadanie | Zależy od |
|---|---|---|
| F1 | Unified Effects System — przepisanie effect_json na typed objects (🟡 #461: `damage_bonus`+`heal_on_hit`+`ac_bonus`(schema) ✅; F1b compat ✅; F1d DSL ✅; remaining: `condition_apply`, ac_bonus engine) | C4 |
| F2 | Affix System — game_config_affixes + affixes_json na inventory row (🟡 #462: tabela+silnik walki affix damage_bonus+GET /admin/affixes; loot-roll afiksów w toku) | F1 |
| F3 | Admin buildery afiksów i efektów | F2 |
| F4 | `[SPEND_GOLD:X]` tag z tabeli/configu (jeśli nie w Fazie 1) | — |
| F5 | Włączenie + konfiguracja wskrzeszenia jako gold sink | — |
| F6 | Sink afiksów: NPC is_crafter, nałóż/reroll afiks (T1=150g, T2=500g, T3=1200g) | F2 |
| F7 | Trwałość (durability): punktowa per cios, penalty przy 0, naprawa tier_rate×brak_pkt | F1 |
| F8 | Napady: encounter kradnący % złota | D7 |
| F9 | Dynamiczny asortyment sklepu (lokacja+poziom) | — |
| F10 | CHA na kupno (nie tylko sprzedaż) | — |
| F11 | Unifikacja ceny → jeden price_gp | F2 |
| F12 | Anti-farm: malejąca cena przy spam-sprzedaży | — |
| F13 | Background expire wynajmu (sweep) | — |
| F14 | Usunięcie martwego economy_service kodu | — |
| F15 | Balans walki → mikstury potrzebne | balans |
| F16 | Balans całości (ceny, dropy, sinki) — playtest | wszystko wyżej |
| F17 | Hidden Trait system (LLM sugeruje z puli, trigger kontekstowy, LLM narruje reveal) | F1 |
| F18 | Rosnące progi XP (konfigurowalne z Admin Panelu) | playtest |
| F19 | Globalne stany NPC (śmierć NPC między kampaniami) | B2 |
| F20 | Mechaniczne efekty pory dnia (noc/świt bonusy, game_config) | B1 |
| F21 | World State History UI dla admina (zakładka, diff między turami) | B5 |

---

### FAZA 5 — Multiplayer

> Po solidnym solo. MP zależy od WSZYSTKICH systemów solo.

| Kod | Zadanie | Zależy od |
|---|---|---|
| G1 | Timer enforcement — background sweep co ~30s w main.py (domknij rundę po deadline) | — |
| G2 | Absencja: token [BRAK AKCJI], licznik ostrzeżeń, reset po powrocie | G1 |
| G3 | Vote-to-kick + auto-kick 2-os (host potwierdza) + zaproszenie zastępstwa | G2 |
| G4 | World State integracja MP (jeden żeton drużyny, współdzielony stan) | B1 |
| G5 | Conflict resolution: inicjatywa jako kolejność; feedback "Cel już martwy/zabrany"; reużywa turn_order | G4 |
| G6 | Ruch drużyny: głosowanie hex (wszyscy głosują, host bez veta); remis = brak ruchu | G4 |
| G7 | Walka MP — reuse silnika turowego solo (ludzie w turn_order, sekwencyjnie) | Faza 1 walka |
| G8 | Auto-roll kości przez kod w rundzie MP (zamiana roll_cues na realne rzuty) | G4 |
| G9 | Timer walki skrócony (2 min) + push "Twoja kolej" per tura | G7 |
| G10 | Loot per-gracz z filtrem klasy + złoto dzielone równo | Faza 1 loot, F2 |
| G11 | Catch-up po powrocie (narracje pominiętych rund + sprasowane podsumowanie) | G2 |
| G12 | Spóźnialscy: wprowadzenie narracyjne + start bez pełnej drużyny | G4 |
| G13 | Kick → bohater do `idle` z zachowaniem XP/złota/przedmiotów | — |
| G14 | Handel między graczami (later) | — |
| G15 | Skalowanie trudność/loot wg liczby graczy (playtest) | playtest |

---

### FAZA 6 — Observability + Długoterminowe

> Po produkcyjnym deploymencie. Dobudowujemy per potrzeba.

| Kod | Zadanie | Zależy od |
|---|---|---|
| CZĘŚĆ 11 | Observability design: co logować, schemat metryk, lekki log writer w backendzie | PROD deployment |
| H2 | H2 text-to-speech — per single player opt-in (zasobożerny) | H3, host .16 |
| H3 | Konfiguracja image gen pipeline na .170 (FLUX.1-schnell + ComfyUI) | — |
| H4 | Konfiguracja Ollama na .170 dla offline content gen (admin AI Kreator) | — |
| H5 | GPU pipeline: tile → LLM Vision → opis → DB (dungeon tiles offline) | H3, H4 |

---

### PRZEKROJOWO — Admin panel (strangler-fig per faza)

| Etap | Co portować | Kiedy |
|---|---|---|
| A10/S2 | Nowa skorupa + shared utils | Faza -1 |
| FADM-P0..P3 | ✅ Skorupa + overview/mechanics/content | 2026-06-08 |
| FADM-P4..P7 | world/map/campaigns/dungeons — następna iteracja | z Fazą 2 |
| FADM-P8 | ⏭ SKIPPED stałe — Forge zostaje w admin3 jako standalone tool | — |
| FADM-P9..P12 | ✅ players/tools/system/drobne (invites/push/bugreports) | 2026-06-08 |
| FADM-P13 | Port ekranu logowania admina do modularnego shella (#449) | Faza 3 |
| FADM-P14 | Port Forge (Kuźnia) → `sections/forge.js` (#450) | po P13 |
| FADM-P15 | Anti-grób: usuń Forge z monolitu + rewire bounce/banner (#451) | po P13+P14 |
| FADM-P16 | Migracja testów Playwright admin3 → /admin/ (#452) | po P14 |
| FADM-P17 | Decommission admin3 (pliki + nginx + docs) (#453) | po P13..P16 |

---

### Kluczowe zależności (blokery)

```
Effects (F1) → Afiksy (F2) → Crafting (F6) + Admin buildery (F3)
Rany (C4/10/11) → Walka MP (G7)
World State (F0) → MP integracja (G4) + NPC pamięć (D3) + Narracja (FNAR)
Karty onboarding (E24) → po systemach które uczą
```

---

> **Uwaga o kolizjach kodów (2026-06-05):** Dawne D6/D6 (narracja) przenumerowane → FNAR-x. Dawne F2 (encountery) przenumerowane → FENC-x. Nowe kody FNAR/FENC w sekcjach Y/AA.

---

## CZĘŚĆ 8 — Podsumowanie priorytetów (Backlog)

> Te zadania powinny być wpisane jako GitHub Issues i powiązane z TaskMaster.

### Krytyczne (blokują grę)

| # | Zadanie | Zależy od |
|---|---------|-----------|
| B2 | World State: rozbudowa session_flags | — |
| B3 | Gate Mechaniki (middleware) | B2 |
| C1 | Fix Bug 1: LLM sugeruje ruch | B3 |
| C3 | Fix Bug 2: Gate dla walki | B3 |
| C7 | XP Spend: spend_skill endpoint | — |
| C8 | XP Spend: spend_stat endpoint | C7 |

### Wysokie (core loop)

| # | Zadanie | Zależy od |
|---|---------|-----------|
| B4 | Parser intencji gracza | B3 |
| C2 | Walidacja ruchu przez mechanikę | C1 |
| C10 | Quest system: QUEST_SUGGEST | B2 |
| C11 | Quest system: mechanical tracking | C10 |
| C9 | UI długiego odpoczynku (Ucz się) | C7+C8 |
| C12 | SPEND_GOLD tag | — |
| C13 | System prompt: tylko złoto GP | — |
| E1 | Player HUD | — |
| E2 | Kreator: wyjaśnienia w UI | — |
| E3 | Ekran zakończenia kampanii | — |
| E4 | Ekran śmierci | — |
| E5 | Blokada kampanii martwego bohatera | — |

### Średnie (polish + admin)

| # | Zadanie | Zależy od |
|---|---------|-----------|
| B1 | World State snapshots tabela | B2 |
| B5 | Auto-zapis snapshotu per tura | B1 |
| D1 | Pending flow: przedmioty | B2 |
| D2 | Pending flow: wrogowie | B2 |
| D3 | NPC pamięć w World State | B2 |
| D4 | Auto-screening admin queue | — |
| E28 | Tutorial kampania | — |
| F18 | Rosnące progi XP | — |
| F21 | World State History UI | B5 |

### Niskie (rozbudowa / przyszłość)

| # | Zadanie | Zależy od |
|---|---------|-----------|
| B6 | Admin UI: World State per tura | B5 |
| F17 | Hidden trait system | — |
| F19 | Globalne stany NPC | — |
| F20 | Mechaniczne efekty pory dnia | — |

---

## CZĘŚĆ 9 — Co zachowujemy z game_flow.md

Nie wszystko w istniejącym designie jest złe. Te rzeczy są poprawne i zachowujemy je:

| Element | Dlaczego zachować |
|---------|-------------------|
| Jeden globalny świat (lokacje wspólne) | Dobra decyzja designu |
| Zdarzenia per kampania (A1) | Rozsądna granica złożoności |
| Tożsamość bohatera seed per tura (80-120 tokenów) | Rozwiązuje problem pamięci LLM |
| Długi odpoczynek jako moment wydawania XP | Dobry rytm gry |
| Wskrzeszenie (5 trybów, admin-config) | Dobra mechanika |
| Zegar gry (ingame_hours, konfigurowalny) | Dobrze zaimplementowany |
| 3 konta XP (pending/available/lifetime) | Elegancki design |
| Audit log złota | Dobry pomysł |
| Pula umiejętności za mała (#333) | Poprawnie zidentyfikowane |

### Zatwierdzone elementy UI — zostają bez zmian

> **Decyzja (2026-06-05):** Te dwie implementacje UI podobają się właścicielowi i zostają w obecnej formie. Oznaczone 🔒 — nie zmieniać bez wyraźnej zgody.

| Element | Status | Dlaczego zachować |
|---------|--------|-------------------|
| **Animacja rzutu kostką** podczas testów umiejętności | ✅ 🔒 | Mechanika i wygląd rzutu d20 w teście są dobre — animacja daje napięcie i czytelność wyniku. Wzorzec dla rzutów w MP (auto-roll przez kod też powinien pokazać tę animację). |
| **Popup w trakcie drogi między hexami** | ✅ 🔒 | Dobra implementacja — pokazuje zdarzenie/encounter w czasie podróży bez wyrywania gracza z kontekstu mapy. |

---

---

## CZĘŚĆ X — Redesign: Unified Effects System (zamiennik effect_json)

> **Priorytet:** Faza 4 — po zbudowaniu World State, questów i progresji.
> **Zależy od:** Bazy działającego systemu mechanicznego (Faza 0-2).
>
> **Czemu to ważne:** Aktualny `effect_json` to największy problem dla admina i LLM.
> Bez redesignu: LLM będzie halucynował efekty, admini nie będą rozumieli co wpisywać.

### Diagnoza: Co jest złe w effect_json

**Problem 1 — Trzy różne formaty dla tego samego konceptu**

```
Przedmiot (items):      effect_json = {"stat_mods":{"AC":4}, "enables":["climbing"]}
Konsumable:             effect_type + effect_dice + effect_bonus (osobne kolumny!)
Stany (conditions):     effect_json = {"damage_per_turn":3, "skip_turn":true}
Bronie (weapons):       effect_json prawie zawsze NULL
```

Jeden koncept ("co robi ten obiekt") jest opisany na cztery różne sposoby. Nie ma jednego źródła prawdy.

**Problem 2 — Nieustrukturyzowany blob JSON**

Admin musi wiedzieć że:
- Klucz to `stat_mods` (nie `stat_modifiers`, nie `modifiers`, nie `stats`)
- Wewnątrz `stat_mods` klucze to `AC`, `STR`, `DEX` (nie `armor_class`, nie `strength`)
- Dla consumable nie używa się `effect_json` tylko `effect_type + effect_dice`
- Dla weapons `effect_json` prawie nie istnieje

Nikt tego nie wie bo nie ma dokumentacji. Admin w panel wpisuje co mu się wydaje. Połowa wpisów jest niepoprawna.

**Problem 3 — LLM halucynuje przy generowaniu**

Gdy LLM ma wygenerować nowy przedmiot z efektem, zgaduje format. Przykłady rzeczy które LLM robi źle:
```
LLM generuje: {"damage_bonus": 3}     ← niepoprawny klucz
Powinno być:  {"stat_mods": {"atk": 3}}  ← poprawny klucz (jeśli w ogóle taki istnieje)

LLM generuje: {"heals": "2d6"}        ← wymyślony klucz
Powinno być:  effect_type="heal_hp", effect_dice="2d6"  ← ale to w innej tabeli!
```

**Problem 4 — Brak silnika mechanicznego który parsuje efekty**

Aktualnie `note` (specjalne zdolności broni/przedmiotów) jest **tekstem informacyjnym** który nigdzie nie jest parsowany przez silnik walki. Napisano w CLAUDE.md: "note is currently informational text only". Efekty specjalne przedmiotów NIE DZIAŁAJĄ mechanicznie.

---

### Nowy design: Structured Effects System

> **Zasada:** Każdy efekt to typowany obiekt. Admini wybierają z dropdown, nie wpisują JSON. LLM generuje z udokumentowanego schematu DSL.

**Unified Effect Object:**

Zamiast wielu formatów — jedna struktura:

```python
Effect = {
    "type": string,      # co robi (patrz tabela typów poniżej)
    "target": string,    # na kogo działa
    "value": int,        # o ile (opcjonalne)
    "dice": string,      # kość (opcjonalne, format: "NdX")
    "stat": string,      # która statystyka (opcjonalne)
    "condition": string, # który stan (opcjonalne)
    "duration": string,  # jak długo
    "trigger": string    # kiedy się aktywuje
}
```

Każdy przedmiot/broń/konsumable/stan ma listę efektów: `effects: [Effect, Effect, ...]`

**Tabela typów efektów:**

| type | Co robi | Wymagane pola |
|------|---------|---------------|
| `stat_mod` | Modyfikuje statystykę | stat, value, trigger, duration |
| `heal_hp` | Przywraca HP | value lub dice |
| `restore_mana` | Przywraca manę | value lub dice |
| `damage` | Zadaje obrażenia | value lub dice, target |
| `apply_condition` | Nakłada stan | condition, duration |
| `remove_condition` | Usuwa stan | condition |
| `enable_action` | Odblokuje możliwość | value (klucz akcji) |
| `skill_bonus` | Bonus do umiejętności | stat, value |
| `damage_per_turn` | Obrażenia co turę (DOT) | value, duration |

**Tabela trigger (kiedy efekt działa):**

| trigger | Kiedy |
|---------|-------|
| `on_equip` | Gdy założony (pasywny) |
| `on_use` | Gdy użyty (aktywny) |
| `on_hit` | Gdy trafisz wrogiem |
| `on_receive_hit` | Gdy trafią ciebie |
| `per_turn` | Co turę (DOT/HOT) |
| `on_rest` | Przy odpoczynku |

**Przykłady nowego formatu:**

```python
# Kolczuga (zbroja)
effects: [
    {"type": "stat_mod", "stat": "AC", "value": 4, "trigger": "on_equip", "duration": "permanent"}
]

# Eliksir leczenia
effects: [
    {"type": "heal_hp", "dice": "2d6", "value": 4, "trigger": "on_use", "target": "self"}
]

# Trucizna (konsumable)
effects: [
    {"type": "apply_condition", "condition": "poisoned", "trigger": "on_hit", "duration": "turns:3"}
]

# Miecz płomieni (broń)
effects: [
    {"type": "stat_mod", "stat": "atk", "value": 1, "trigger": "on_equip", "duration": "permanent"},
    {"type": "damage", "dice": "1d4", "damage_type": "fire", "trigger": "on_hit", "target": "enemy"}
]

# Stan: Ogłuszony
effects: [
    {"type": "stat_mod", "stat": "DEX", "value": -3, "trigger": "on_equip", "duration": "turns:1"},
    {"type": "stat_mod", "stat": "STR", "value": -2, "trigger": "on_equip", "duration": "turns:1"}
]
# Uwaga: "skip_turn" też powinien być typowanym efektem, nie bool
```

---

### Admin UI dla efektów

Zamiast pola JSON, admin widzi builder:

```
[+ Dodaj efekt]

Efekt 1:
  Typ: [stat_mod ▼]
  Statystyka: [AC ▼]
  Wartość: [+4]
  Trigger: [on_equip ▼]
  Czas trwania: [permanent ▼]

Efekt 2:
  Typ: [damage ▼]
  Kość: [1d4]
  Typ obrażeń: [fire ▼]
  Trigger: [on_hit ▼]
  Cel: [enemy ▼]
```

Admin nigdy nie widzi JSON. System generuje go wewnętrznie.

---

### LLM i nowy format

LLM dostaje w system prompcie dokumentację typów efektów. Gdy generuje nowy przedmiot (pending flow), używa DSL:

```
[ITEM_CREATE: key=fire_sword, label="Ognisty Miecz", effects=[
  {type:stat_mod, stat:atk, value:+1, trigger:on_equip, duration:permanent},
  {type:damage, dice:1d4, damage_type:fire, trigger:on_hit, target:enemy}
]]
```

Backend waliduje: czy typ istnieje w enum? Czy wymagane pola są wypełnione? Jeśli nie → rekord odrzucony (nie halucynuje efektów).

---

### Redesign Skills — trigger_keywords problem

**Aktualny problem:**

Umiejętności mają `trigger_keywords` — listę polskich słów które "wyzwalają" check. Przykład dla Atletyki:
```
wspinamy wspinasz wspinac wdrapuje wdrapac skacze przeskakuje...
```

To jest kruche. Gracz pisze "Gramolę się na skałę" → keyword matcher nie znajdzie "gramolę" → brak triggera. Albo fałszywy trigger: "skaczę do wniosków" (metaforyczne skakanie).

**Poprawny design:**

LLM emituje skill check z kluczem:
```
[SKILL_CHECK: key=athletics, dc=14, reason="wspinaczka na skałę"]
```

Backend waliduje:
- Czy `key` istnieje w `game_config_skills`?
- Czy `dc` jest w sensownym zakresie (8-24)?

LLM zna listę kluczy umiejętności z system promptu. Nie potrzebuje keyword matchingu.

`trigger_keywords` → usunąć w redesignie, zastąpić przez system prompt który instruuje LLM jakie klucze używać w jakich sytuacjach.

---

### Unifikacja tabel przedmiotów

Aktualnie przedmioty są w trzech oddzielnych tabelach: `game_config_weapons`, `game_config_items`, `game_config_consumables`. To powoduje problemy:

**Zduplikowane kolumny** (ta sama kolumna w każdej tabeli): `key, label, description, is_active, weight_kg, note, ai_generated, approved, rarity, template_id`

**Różne nazwy tej samej rzeczy:** `value_gp` (weapons + items) vs `base_price` (consumables) — to samo pole, dwie nazwy.

**Items ma dwa systemy efektów naraz:** `effect_json` (blob) ORAZ `effect_type + effect_dice + effect_bonus + effect_target` (osobne kolumny). Oba współistnieją.

**character_inventory XOR constraint:** System TRAKTUJE wszystkie typy jak jedną kategorię "przedmioty" w inventory (jeden slot = jeden klucz), ale przechowuje je w 3 osobnych tabelach z 3 osobnymi FK.

**Rozwiązanie dwuetapowe:**

**Etap 1 — Faza 2:** VIEW `game_item_catalog` — LLM odpytuje jeden widok zamiast 3 tabel. Zero migracji, szybkie.

**Etap 2 — Faza 4:** Pełna unifikacja do jednej tabeli `game_items` z `item_class` discriminatorem. Razem z redesignem effects (F4-6a do F4-6f). Migracja konwertuje stare formaty do nowych Effect Objects.

Po unifikacji: `character_inventory` traci XOR constraint, używa jednego `item_key` + `item_class`.

---

### System Afiksów — przedmioty wyjątkowe

To jest sposób, w jaki bohater zdobywa broń i przedmioty **lepsze niż sklepowe**. W sklepie kupisz zwykły miecz. Ale na zabitym wrogu albo w lochu możesz znaleźć ten sam miecz, który dodatkowo płonie ogniem — i tylko ten jeden taki egzemplarz.

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Wyjątkowe moce przedmiotów trzymamy jako **afiksy** doklejane do konkretnego egzemplarza, a nie jako osobne wpisy w katalogu. Baza ("miecz krótki") zostaje jedna, tania i kupowalna. Wariacja — ogień, dodatkowe obrażenia, ciche stąpanie — siedzi na sztuce, którą trzyma gracz, nie na definicji w katalogu.

> **Dlaczego?**
> Chcemy modułu, który można rozbudowywać bez przepisywania bazy. Admin dodaje nową moc raz (np. "Ognisty") i od tej chwili działa ona na każdej pasującej broni w całej grze. Nie trzeba tworzyć ręcznie "ognistego miecza", "ognistego topora" i "ognistego sztyletu" osobno — jeden afiks pokrywa wszystkie. Katalog nie puchnie. Drop może losować afiksy z puli, więc dwa miecze z tego samego lochu mogą być różne. To jest dokładnie cel postawiony przez właściciela: "nie hardcodować pełnej bazy możliwości, tylko móc dodawać je później".

> **Co odrzucono i dlaczego?**
> - **Każdy egzemplarz jako pełna kopia z własnymi efektami** — daje maksymalną swobodę (LLM wymyśla unikat na miejscu), ale jest nie do opanowania w balansie i trudny dla admina. Odrzucone.
> - **Nazwane unikaty w katalogu** (admin tworzy "Ognisty Miecz Króla" jako osobny wpis) — najprostsze, ale katalog puchnie i nie ma losowych wariacji dropów. Odrzucone jako model główny; może wrócić później jako dodatek dla bossów i przedmiotów fabularnych.

> **Co się zepsuje, jeśli odwrócić tę decyzję?**
> Jeśli wrócimy do "wszystko w katalogu", to każda nowa moc wymaga ręcznego wpisu dla każdego typu broni osobno, a losowe dropy znikają. Grind w lochach traci sens, bo zawsze wypada ten sam przedmiot.

#### Jak to działa

Przedmiot wyjątkowy składa się z dwóch warstw:

```
WARSTWA 1 — Baza (z katalogu, tania, kupowalna)
   "miecz krótki": 1d6 obrażeń, 10 sztuk złota, każdy sklep go ma
          │
          │  drop z wroga albo loch dokleja afiks
          ▼
WARSTWA 2 — Egzemplarz (konkretna sztuka u gracza w plecaku)
   "miecz krótki" + afiks "Ognisty" + afiks "Ostry"
```

Afiks to **nazwana paczka efektów** — używa tego samego silnika Effect Objects opisanego wyżej w tej części. Przykłady:

```
"Ognisty"     → przy każdym trafieniu dodaj 1d4 obrażeń od ognia
"Ostry"       → +1 do trafienia, na stałe gdy broń założona
"Cichy chód"  → +2 do testów skradania, gdy zbroja założona
```

**Co widzi gracz w plecaku:**

```
🗡 Ognisty Miecz krótki (Ostry)
   1d6 cięte + 1d4 ogień przy trafieniu
   +1 do trafienia
```

Czytelna nazwa na wierzchu — przedrostek i przyrostek pochodzą z afiksów. Pod spodem system pamięta: baza to `miecz_krotki`, afiksy to `ognisty` i `ostry`. Siła przedmiotu to suma efektów bazy plus wszystkich afiksów.

#### Praca admina — trzy oddzielne czynności

Admin nie pracuje z jednym wielkim formularzem. Pracuje z trzema rzeczami, które się nie mieszają:

**A. Baza przedmiotu** — robiona raz, prawie nigdy nie zmieniana.
Admin tworzy "miecz krótki": nazwa, kość obrażeń (1d6), cena (10), typ (miecz). **Bez żadnych efektów.** To czysta, tania rzecz, którą każdy może kupić.

**B. Pula afiksów** — tu admin pracuje, gdy chce dodać do gry nową moc.
Nowa zakładka w panelu: **Zawartość → Afiksy**. Admin klika "+ Nowy afiks" i wypełnia formularz:

```
Nazwa wyświetlana:  [Ognisty]
Pozycja w nazwie:   [przedrostek ▼]      → da "Ognisty Miecz krótki"
Pasuje do:          [☑ bronie] [☐ zbroje] [☐ konsumpcja]
Filtr typu broni:   [miecz, topór, sztylet]   (puste = każda broń)
Tier (siła):        [2]                  → pojawia się w lochach od tieru 2
Waga losowania:     [15]                 (jak często wypada, w skali wagi)

EFEKTY (wybierane z list, nie wpisywane jako kod):
  [+ Dodaj efekt]
  Efekt 1: Typ=[obrażenia ▼] Kość=[1d4] Rodzaj=[ogień ▼] Kiedy=[przy trafieniu ▼] Cel=[wróg ▼]

[Zapisz afiks]
```

Admin **nigdy nie pisze kodu ani JSON.** Po zapisaniu "Ognisty" każdy miecz, topór i sztylet wypadnięty w lochu tier 2 lub wyższym może go dostać. Dodanie kolejnych mocy ("Mroźny", "Ostry", "Cichy chód") to ten sam formularz za każdym razem.

**C. Reguły dropu** — ustawiane raz, potem zostają.
"Ile afiksów może mieć przedmiot z danego tieru?" Na przykład: tier 1 daje 0–1 afiks, tier 5 daje 2–3 afiksy. Admin ustawia to raz w konfiguracji lochu albo wroga.

#### Skąd LLM wie o afiksach

LLM **nie wymyśla** afiksów. Kiedy wróg ginie albo gracz otwiera skrzynię, to backend (kod, nie AI) losuje afiksy z puli `game_config_affixes` według tieru i wag. LLM dostaje gotowy wynik i tylko opisuje go narracyjnie ("ostrze rozbłyska płomieniem, gdy je podnosisz"). To jest zgodne z naczelną zasadą: mechanika decyduje, LLM narruje.

#### Zmiany w schemacie bazy danych

| Tabela | Zmiana |
|---|---|
| `game_config_affixes` | **NOWA** — definicje afiksów: `key, label, position (prefix/suffix), applies_to (weapon/armor/consumable), weapon_type_filter, tier, weight, effects_json` |
| `character_inventory` | **+kolumna** `affixes_json` — lista kluczy afiksów na egzemplarzu |
| Loot / dungeon config | pola `affix_count_min` / `affix_count_max` per tier |
| Silnik efektów (F4-6f) | rozszerzony: liczy efekty bazy **plus** efekty wszystkich afiksów egzemplarza |

#### Status implementacji

| Element | Status |
|---------|--------|
| Silnik efektów na poziomie katalogu (Effect Objects) | ❌ — projekt, Faza 4 (F4-6a–f) |
| Tabela `game_config_affixes` | ❌ — nowa, do stworzenia |
| Kolumna `affixes_json` w `character_inventory` | ❌ — do dodania |
| Losowanie afiksów przy dropie wg tieru | ❌ — do napisania |
| Admin UI — zakładka Afiksy | ❌ — do zbudowania |
| Silnik liczący efekty (baza + afiksy egzemplarza) | ❌ — rozszerzenie F4-6f |

---

### Zadania implementacyjne (Faza 4)

| # | Zadanie | Opis |
|---|---------|------|
| F4-6a | Projektuj nowy schemat `effects` | JSON Schema dla Effect Object, enum typów |
| F4-6b | Projektuj tabelę `game_items` | Zunifikowana tabela z `item_class` discriminatorem |
| F4-6c | Migracja danych | Konwertuj 3 tabele → `game_items`, stary `effect_json` → Effect Objects |
| F4-6d | Zaktualizuj `character_inventory` | Usuń XOR, jeden `item_key` + `item_class` |
| F4-6e | Admin UI — Effects Builder | Zastąp pole JSON wizualnym builderem |
| F4-6f | Silnik mechaniczny dla efektów | Kod parsujący Effect Objects i aplikujący w walce/spoczynku |
| F4-6g | LLM instrukcja | Zaktualizuj system prompt: DSL dla generowania efektów, klucze umiejętności |
| F4-6h | Usuń trigger_keywords | Zastąp listą kluczy w system prompcie |

**Etap pośredni (Faza 2):**

| # | Zadanie | Opis |
|---|---------|------|
| D5 | VIEW `game_item_catalog` | UNION ALL trzech tabel, ujednolicone nazwy kolumn, LLM odpytuje widok |

---

---

## CZĘŚĆ Y — System Narracji Kampanii (Nowa Kampania / Dynamiczna)

> **Dotyczy:** trybu "Nowa Kampania" gdzie LLM buduje historię autonomicznie, bez udziału admina.
> **Gotowe Kampanie** omawiane osobno.

### Problem który rozwiązuje ten projekt

Aktualny system ma `gm_plan_json` — plan gdzie historia MA iść (akty, cele scen, haki NPC/lokacji). To już istnieje i działa jako szkielet.

Ale brakuje drugiej warstwy: **co się już wydarzyło**. LLM ma skończone okno kontekstu. W turze 40 nie "pamięta" że w turze 5 gracz obiecał karczmarkowi że znajdzie jego córkę. W turze 50 nie wie że NPC o imieniu Aldric zdradził bohatera — chyba że to jest w ostatnich N turach. Historia "wycieka" ze świadomości LLM w miarę gry.

```
Istniejące: GM Plan = dokąd historia idzie (przyszłość)
Brakujące:  Narrative State = co się wydarzyło + co obiecano (przeszłość)
```

Bez Narrative State: LLM narruje w próżni, może sobie zaprzeczyć, traci ciągłość.

---

### Dwuwarstwowy System Narracji

> **Warstwa 1: GM Plan** (już istnieje, zachowujemy i rozbudowujemy)
> Gdzie historia IDZIE — akty, cele scen, haki, roadmap.
>
> **Warstwa 2: Narrative State** (NOWE — do zbudowania)
> Co się wydarzyło + co zostało narracyjnie obiecane.

Razem tworzą pełny kontekst narracyjny który LLM dostaje skompresowany każdą turę.

---

### Jak historia buduje się dynamicznie (bez admina)

**Krok 1: Start kampanii — LLM generuje GM Plan**

LLM dostaje:
- Tożsamość bohatera (z kreatora: wygląd, osobowość, więzi, traumy)
- Hex startowy + typ terenu
- World State startowy (NPC w lokacji startowej, dostępni wrogowie, czas gry)

Generuje:
- `premise` — premise kampanii (2-3 zdania: o czym ta historia jest)
- `arcs` — 3 akty narracyjne z celami scen, hakami NPC i lokacji
- `main_quest` — główny cel kampanii

To jest jeden call LLM przy starcie. Wynik zapisany w `campaigns.gm_plan_json`. **Admin nie musi nic robić.**

**Krok 2: Każda tura — LLM narruje i aktualizuje**

LLM dostaje skompresowany pakiet:

```
[TOŻSAMOŚĆ]       — seed bohatera (80-120 tokenów, każdą turę)
[GM PLAN]         — aktualny akt + cele scen + haki (300-500 tokenów)
[NARRATIVE STATE] — skrót wydarzeń + aktywne obietnice (150-300 tokenów)
[WORLD STATE]     — aktualna scena, wrogowie, NPC, hex (relevantne pola)
[OSTATNIE N TUR]  — surowe tury (ostatnie 8-12)
```

LLM odpowiada narracją + opcjonalnymi tagami które aktualizują stan.

**Krok 3: Mechanika parsuje tagi i aktualizuje stan**

Po odpowiedzi LLM, backend parsuje tagi i aktualizuje odpowiednie warstwy:

```
[BEAT_COMPLETE: key=...]        → GM Plan: oznacza beat jako ukończony, sprawdza czy postępować do następnej sceny
[NARRATIVE_EVENT: key=..., note=...]  → Narrative State: loguje kluczowe zdarzenie (do skrótu)
[NARRATIVE_SEED: key=..., hint=...]   → Narrative State: loguje obietnicę/hak do użycia w przyszłości
[ARC_ADVANCE: to_arc=...]       → GM Plan: przesuwa do następnego aktu
[QUEST_SUGGEST: ...]            → Quest System (jak w C10)
[LOCATION_CREATE: ...]          → Lokacje (jak w Etapie 5)
```

---

### Narrative State — co przechowuje

Nowe pole w `campaigns.engine_private_json` (lub osobne `campaign_narrative_state`):

```python
NarrativeState = {
    "events": [
        # Kluczowe zdarzenia ze gry, skrócone
        {
            "key": "met_aldric",
            "note": "Gracz spotkał Aldrica, który zaoferował pomoc za wynagrodzenie",
            "turn": 5
        },
        {
            "key": "aldric_betrayal",
            "note": "Aldric zdradził gracza — przekazał informacje wrogom",
            "turn": 23
        }
    ],
    "seeds": [
        # Narracyjne obietnice / haki które LLM "zasadził" — do wykorzystania w przyszłości
        {
            "key": "innkeeper_daughter",
            "hint": "Karczmarz Marta wspomniała o zaginionej córce na północy",
            "status": "active",  # active | used | expired
            "planted_turn": 3
        }
    ],
    "chapter_summaries": [
        # Skompresowane podsumowania starszych rozdziałów
        {
            "turns": "1-15",
            "summary": "Bohater przybył do wioski, odkrył zaginięcia, znalazł wskazówkę prowadzącą do lasu..."
        }
    ],
    "current_situation": "Bohater jest w karczmie, ma mapę do ruin, Aldric jest wrogiem",  # max 100 tokenów
}
```

---

### Rozwiązanie problemu: LLM zapomina po N turach

**Problem:** Okno kontekstu LLM jest skończone. Przy grze 50+ tur, tury 1-20 wypadają z kontekstu.

**Rozwiązanie: Automatyczna kompresja narracyjna**

Backend uruchamia kompresję co 10-15 tur (lub przy przejściu do nowego aktu):

```
Automatyczny background job:
1. Weź tury X-(X+15) które będą wkrótce wypadać z kontekstu
2. Wyślij do LLM: "Streść tę część historii w 150 tokenach.
   Wymień 3 kluczowe zdarzenia. Wymień aktywne obietnice/haki."
3. Zapisz skrót jako chapter_summary w Narrative State
4. Pełne tury nadal w DB (dla admina, debugowania) — ale nie wysyłane do LLM
```

**Co LLM dostaje zamiast starych tur:**
```
[ROZDZIAŁ 1 - skrót]
Bohater przybył do wioski na hex (3,7). Spotkał karczmarkę Martę.
Odkrył że ludzie znikają. Aldric zaoferował pomoc. Znaleziono mapę.
Aktywne obietnicy: pomóc Marcie znaleźć córkę (innkeeper_daughter).

[ROZDZIAŁ 2 - skrót]
Bohater dotarł do ruin. Aldric zdradził — wrogowie wiedzieli o przybyciu.
Walka przy bramie. Znaleziono tajemniczy klucz. Wróg uciekł.

[OSTATNIE 10 TUR - pełne]
...
```

Dzięki temu historia może trwać 200 tur i zachowywać spójność.

---

### Diagramy przepływu

**Start kampanii:**

```
Gracz klika "Nowa Kampania"
        │
        ▼
Backend zbiera seed:
  - tożsamość bohatera (sheet_json.identity)
  - hex startowy + terrain
  - World State (NPC w lokacji, dostępne zasoby)
        │
        ▼
LLM generuje GM Plan:
  premise + 3 akty + main_quest
        │
        ▼
Zapisz do campaigns.gm_plan_json
Inicjuj Narrative State (pusty)
        │
        ▼
LLM generuje pierwsze zawiązanie akcji
(seed: tożsamość + GM Plan premise + hex)
        │
        ▼
→ Pętla gry zaczyna się
```

**Każda tura:**

```
Gracz wpisuje akcję
        │
        ▼
Gate mechaniki (World State check)
        │
        ▼
Build kontekst dla LLM:
  - Tożsamość (80-120 tok)
  - GM Plan: aktualny akt (300-500 tok)
  - Narrative State: current_situation + seeds (150-300 tok)
  - World State: relevantne pola (50-200 tok)
  - Ostatnie 8-12 tur (2000-4000 tok)
        │
        ▼
LLM narruje
(odpowiedź + opcjonalne tagi)
        │
        ▼
Backend parsuje tagi:
  BEAT_COMPLETE   → aktualizuj GM Plan
  NARRATIVE_EVENT → dodaj do events
  NARRATIVE_SEED  → dodaj do seeds
  ARC_ADVANCE     → przesuń do nowego aktu
  QUEST_SUGGEST   → stwórz quest
  LOCATION_CREATE → stwórz lokację (pending)
        │
        ▼
Aktualizuj World State
Zapisz turę do campaign_turns
Sprawdź: czy kompresja narracyjna potrzebna?
        │
        ▼
→ Gracz widzi narrację, pętla się powtarza
```

---

---

### C17 — Kontekst Ekwipunku Postaci (Character Context Injection)

> **Zadanie C17** z listy implementacyjnej Fazy 1.

#### Problem który rozwiązuje

LLM przy każdej turze dostaje wyłącznie imię postaci i ostatnie tury narracji. Nie wie co postać nosi, ile ma złota, ani jaką bronią walczy. Skutek: LLM swobodnie **wymyśla stan ekwipunku**. Typowy przykład: gracz zaczyna nową kampanię z sztyletkiem i skórzanym pancerzem, a LLM otwiera sesję sceną "obudziłeś się bez niczego — miecza nie ma, sakiewka pusta". Gracz widzi w ekwipunku sztylet i pancerz — sprzeczność jest oczywista.

> **Zasada projektowa (zatwierdzona 2026-06-06):**
> Przy każdym wywołaniu LLM (narratywa zwykła i otwarcie kampanii) backend wstrzykuje do bloku systemowego skrócony opis aktualnego ekwipunku postaci: broń w dłoni, założona zbroja, kluczowe przedmioty w plecaku i stan złota. LLM dostaje to jako fakt — nie może go zmienić bez mechanicznego powodu.

> **Dlaczego?**
> LLM nie ma dostępu do bazy danych. Jeśli nie dostanie listy przedmiotów w prompcie, **wymyśla ją** — i wymyśla źle, bo dramatyczne otwarcia z utratą ekwipunku to klasyczny motyw literacki. Bez injektu gracz nie może ufać narracji: "mam miecz według inventory, ale narracja mówi że nie mam". To podkopuje immersję i powoduje zamieszanie przy każdej kampanii.

> **Co odrzucono i dlaczego?**
> - **Nic nie robić, liczyć na historię tur** — tury zawierają narrację, ale nie jawny stan ekwipunku. LLM musiałby wnioskować co postać ma z kontekstu — zawodne, zwłaszcza przy nowych kampaniach gdzie nie ma historii tur.
> - **Pełna lista wszystkich przedmiotów** — zbyt wiele tokenów. Plecak może zawierać dziesiątki wpisów (narrative items, zwoje, klucze). Wysyłamy tylko mechanicznie istotne: broń, zbroja, złoto, + max 5 kluczowych narrative items.

#### Jak to działa krok po kroku

**Co wstrzykujemy (blok `[EKWIPUNEK]`):**

```
[EKWIPUNEK POSTACI — FAKTY MECHANICZNE]
Broń w dłoni: Sztylet (1d4+DEX obrażeń)
Zbroja: Skórzany Pancerz (AC 12)
W plecaku: krótki łuk, strzały ×20, lina 10m, pochodnia ×2, racja żywnościowa ×3
Złoto: 36 GP
[Kluczowe przedmioty fabularne: Księga z czarną pieczęcią kruków, Żelazny klucz z wroną]
```

LLM dostaje ten blok PRZED ostatnimi turami, jako część systemu. Nie może narracyjnie usunąć ani zmienić tych przedmiotów — jedyna zmiana ekwipunku następuje przez mechaniczne tagi (`Grant Item`, `SPEND_GOLD`) przetwarzane przez backend.

**Skąd bierzemy dane:**

```
character_inventory WHERE character_id = X
  → equipped (is_equipped=1): broń + zbroja → "w dłoni / na sobie"
  → nie-equipped (is_equipped=0), item_type != 'narrative': plecak (max 10)
  → narrative items z label != NULL: kluczowe przedmioty fabularne (max 5)

characters.gold_gp → stan złota
```

**Miejsce injektu w kodzie:**

Funkcja `buildmessages` w `backend/app/core/turn_engine.py` (linia 61) aktualnie wstrzykuje tylko imię postaci. C17 dodaje wywołanie `_build_inventory_block(conn, character_id)` → wynik doklejany do bloku `system_content`.

Identyczna zmiana dla otwarcia kampanii w `_maybe_auto_generate_gm_plan_and_opening` (`backend/app/api/turns.py`) oraz `finalize_character_sheet` (`backend/app/api/characters.py`).

#### Status implementacji

| Element | Status |
|---------|--------|
| Inventory w DB (`character_inventory`) | ✅ Istnieje |
| Złoto w DB (`characters.gold_gp`) | ✅ Istnieje |
| Injection ekwipunku do `buildmessages` | ❌ C17 — do zbudowania |
| Injection ekwipunku do otwarcia kampanii | ❌ C17 — do zbudowania |
| Instrukcja w system_prompt: "nie zmieniaj ekwipunku bez tagu" | ❌ C17 — do zbudowania |

---

### C18 — Fix Bug 3: Kampanie na Istniejących Hexach (Campaign Hex Reuse)

> **Zadanie C18** z listy implementacyjnej Fazy 1. Powiązane: C14 (hero-first fix), C2 (walidacja ruchu mechaniczna).

#### Problem który rozwiązuje

Każda nowa kampania dostaje losowy `start_hex` generowany od zera — typowo trafia na obrzeże mapy (wysokie q/r), tam gdzie nie ma jeszcze żadnej aktywności gracza. Skutek: **gracz ma wiele kampanii każda na innym, pustym hexie** — mapy się nie łączą, świat wygląda jak archipelag izolowanych wysepek, a nie spójne terytorium.

Poprawne zachowanie: nowa kampania powinna startować na hexie który już istnieje w `world_hexes` gracza (odkryty, niezerowy ruch) albo — gdy gracz zaczyna od zera — na standardowym hexie startowym (0,0) lub najbliższym odkrytym hexie.

> **Zasada projektowa (zatwierdzona 2026-06-06):**
> Hex startowy kampanii to **wybór z istniejących odkrytych hexów gracza**, nie generowanie nowych. Gdy gracz nie ma jeszcze żadnego hexu — startujemy na (0,0). System nigdy nie tworzy kampanii na losowych obrzeżach — losowość pojawia się tylko w zawartości locha lub encountera, nie w pozycji na mapie.

> **Dlaczego?**
> Mapa świata to kluczowy element ciągłości gry — gracz powinien widzieć jak jego przygody pokrywają jedno spójne terytorium. Generowanie nowych hexów per kampania łamie tę ciągłość: gracz widzi wiele rozrzuconych punktów bez połączenia. Dodatkowo: każdy nowy obrzeżny hex oznacza nowy, pusty region bez contentu — gracz ląduje "w nieznanym" bez kontekstu zamiast wracać do znajomego świata.

> **Co odrzucono i dlaczego?**
> - **Losowy hex na mapie** — problem który mamy teraz. Gracz nie wraca do świata, tworzy nowe.
> - **Stały hex (0,0) zawsze** — za sztywne. Gracz który odkrył już 20 hexów chciałby kontynuować z innego punktu.
> - **Hex z poprzedniej kampanii tego bohatera** — dobry domyślny, ale wymaga że bohater miał już kampanię. Jako fallback — tak.

#### Jak to działa krok po kroku

```
Przy tworzeniu kampanii:
1. Pobierz world_hexes WHERE discovered=TRUE AND należące do gracza/bohatera
2. Jeśli bohater miał poprzednią kampanię → użyj jej ostatniego current_hex
3. Else jeśli discovered_hexes > 0 → użyj centrum odkrytego obszaru (mediana q,r)
4. Else → (0,0) jako hex startowy
5. NIE generuj nowych hexów na obrzeżach
```

**Gdzie leży bug w kodzie:**

Funkcja tworzenia kampanii (`POST /api/campaigns` w `backend/app/api/campaigns.py`) ustawia `start_hex_q` / `start_hex_r` przed wywołaniem `create_campaign()`. Sprawdź jak wartości są obliczane — najprawdopodobniej brak zapytania do `world_hexes` lub losowanie w stylu `random.randint(max_q+1, max_q+5)`.

#### Status implementacji

| Element | Status |
|---------|--------|
| `world_hexes` tabela z odkrytymi hexami | ✅ Istnieje |
| Wybór hexu startowego z istniejących | ✅ C18 — `_find_character_existing_hex()` |
| Fallback na (0,0) gdy brak odkrytych | ✅ C18 — zaimplementowany |
| Test: nowa kampania ląduje na istniejącym hexie | ✅ C18 — 7 testów GREEN |

---

### C19 — Fix Bug 4: Reset HP przy starcie nowej kampanii (Full HP on New Campaign)

> **Zadanie C19** z listy implementacyjnej Fazy 1. Powiązane: C4 (unifikacja wound_penalty), C14 (hero-first).

#### Problem który rozwiązuje

Bohater jest bytem niezależnym — może grać wiele kampanii po kolei. Gdy gracz kończy jedną kampanię (lub porzuca ją w połowie) i zaczyna nową, bohater wchodzi do nowej przygody z **ostatnim zarejestrowanym stanem HP** — np. 3/45 HP po ciężkiej walce. Gracz widzi postać umierającą już na starcie nowej historii bez żadnego sensu narracyjnego.

Poprawne zachowanie: każda **nowa** kampania to nowa przygoda — bohater wchodzi w nią z pełnym HP (`hp_max`). Stara kampania (jeśli wznowiona) powinna pamiętać stan z ostatniej tury.

> **Zasada projektowa (zatwierdzona 2026-06-06):**
> Tworzenie nowej kampanii zawsze resetuje `hp_current` bohatera do `hp_max`. Wznowienie istniejącej kampanii (gracz wraca do kampanii w toku) zachowuje ostatni stan HP bez zmian. Mechanicznie: reset HP następuje w momencie `POST /api/campaigns` (tworzenie), nie przy `selectCampaign()` (wybór istniejącej).

> **Dlaczego?**
> Bohater jest jak postać w serialu — między sezonami wraca do zdrowia, nie kontynuuje z kończącą się krwią. Nowa kampania = nowa historia. Stara kampania = ta sama historia kontynuowana. Bez resetu: gracz który ukończył kampanię z 2/45 HP wchodzi do następnej jako "prawie martwy" bez wyjaśnienia — to narusza immersję i jest zwykłym błędem UX.

> **Co odrzucono i dlaczego?**
> - **Narracyjne wytłumaczenie niskiego HP** (LLM opisuje "wracasz z ran") — nie rozwiązuje problemu mechanicznego; LLM może to opisać, ale HP powinno być pełne.
> - **Reset HP tylko gdy bohater idle** — hero_status=idle oznacza brak kampanii, ale kampania może być zakończona przy `status=active`. Prościej: reset przy tworzeniu, nie przy statusie.
> - **Brak resetu — pełna ciągłość HP** — mogłoby mieć sens w trybie roguelike (permadeath across campaigns), ale nie w tym projekcie. Kampanie są niezależnymi historiami.

#### Jak to działa krok po kroku

```
POST /api/campaigns (tworzenie nowej kampanii):
1. Pobierz bohatera z characters WHERE id = hero_id
2. Oblicz hp_max (formula: archetype_base + CON_mod × level)
3. UPDATE characters SET hp_current = hp_max WHERE id = hero_id
4. Następnie utwórz kampanię z tym bohaterem

selectCampaign() / wznowienie (istniejąca kampania):
- NIE resetuj HP — zachowaj hp_current z bazy
```

**Gdzie leży bug w kodzie:**

Endpoint `POST /api/campaigns` (`backend/app/api/campaigns.py`) tworzy kampanię i przypisuje bohatera. Brakuje kroku resetu `hp_current = hp_max` przed przypisaniem. Formula `hp_max` jest w `vitality_service.py` lub `character_service.py` — użyć istniejącej funkcji, nie duplikować.

#### Status implementacji

| Element | Status |
|---------|--------|
| `hp_current` / `hp_max` w `characters` | ✅ Istnieje |
| Formula hp_max (`vitality_service`) | ✅ Istnieje |
| Reset HP przy tworzeniu kampanii | ✅ C19 — `maybe_reset_hp_for_new_campaign()` |
| Zachowanie HP przy wznowieniu kampanii | ✅ Działa (brak resetu = poprawne) |
| Test: nowa kampania → hp_current == hp_max | ✅ C19 — 7 testów GREEN |

---

### Co jest spójne z istniejącym kodem

| Element | Status |
|---------|--------|
| `gm_plan_json` jako struktura arkuszów | ✅ Istnieje (schema V2, arcs) |
| Generowanie GM Plan przy starcie | ✅ Istnieje (`gm_plan_generation_service.py`) |
| `BEAT_COMPLETE` tag → postęp planu | ✅ Istnieje |
| Admin Panel: podgląd GM Plan | ✅ Istnieje (tab "Plan GM") |
| Admin Panel: Warsztat edycji planu | ✅ Istnieje (kampania workshop) |

### Co jest nowe

| Element | Status |
|---------|--------|
| Narrative State (events, seeds, summaries) | ❌ Do zbudowania |
| `[NARRATIVE_EVENT]` tag parser | ❌ Do zbudowania |
| `[NARRATIVE_SEED]` tag parser | ❌ Do zbudowania |
| `[ARC_ADVANCE]` tag parser | ❌ Częściowo (jest "następna scena" przycisk w admin) |
| Automatyczna kompresja narracyjna (background job) | ❌ Do zbudowania |
| Context builder: łączy GM Plan + Narrative State + World State | ❌ Do zbudowania (aktualnie osobne) |
| Narrative seeds injection do LLM (użyj obietnicy z tury 3 w turze 20) | ❌ Do zbudowania |

---

### Zadania implementacyjne (Faza 2 / 3)

| # | Zadanie | Faza | Opis |
|---|---------|------|------|
| D6 | Narrative State struktura | 2 | Dodaj `narrative_state` do `campaigns.engine_private_json` |
| D6 | Tag parsers | 2 | `[NARRATIVE_EVENT]` i `[NARRATIVE_SEED]` parsery |
| D6 | Context builder | 2 | Łączy GM Plan + Narrative State + World State w jeden skompresowany kontekst |
| E6 | Kompresja narracyjna | 3 | Background job co N tur generuje chapter_summary |
| E6 | Seeds injection | 3 | Aktywne seeds wstrzykiwane do kontekstu LLM co turę |
| E6 | ARC_ADVANCE automation | 3 | Automatyczny postęp do nowego aktu po BEAT_COMPLETE |

---

---

## CZĘŚĆ Z — Gotowe Kampanie (Campaign Templates)

> **Dotyczy:** trybu "Gotowa Kampania" gdzie admin pisze szkielet historii, LLM wypełnia szczegóły.
>
> **Związek z Nową Kampanią:** identyczna pętla gry i World State — różni się TYLKO źródłem GM Planu.

---

### Kluczowa różnica: skąd pochodzi GM Plan

```
Nowa Kampania:   LLM generuje GM Plan przy starcie (unikalna historia)
Gotowa Kampania: Admin pisze GM Plan z góry → kopiowany do kampanii gracza
```

Wszystko inne — World State, walka, questy, przedmioty, NPC — działa identycznie.

---

### Co dają gotowe kampanie (i czego nie dają)

**Dają:**
- Spójne doświadczenie (wszyscy gracze widzą ten sam świat, tę samą historię)
- Admin kontroluje kluczowe punkty fabuły (kto zdradzi, gdzie jest finał, jaki jest antagonista)
- Testowalność — admin może zagrać swój scenariusz i sprawdzić czy działa
- Powtarzalność dla nowych graczy — kampania która "jest znana" ma mniejsze ryzyko losowych błędów

**Nie dają (i nie powinny):**
- Pełnej skryptowości — każda turę każdego dialogu pisanej z góry (to niemożliwe do utrzymania)
- Gwarancji że gracz "przejdzie" fabułę — gracz może ignorować główny wątek

---

### Trzypoziomowa struktura gotowej kampanii

> **Poziom 1 — Stały (admin pisze, nie zmienia się):** główny wątek, kluczowi antagoniści, finał
> **Poziom 2 — Adaptacyjny (LLM wypełnia w runtime):** dialogi, opisy, scenariusze spotkań
> **Poziom 3 — Dynamiczny (LLM generuje swobodnie):** wątki poboczne, losowe napotkania, adaptacja do postaci

Przykład: admin pisze "W Akcie 2 gracz odkrywa że zaufany NPC to szpieg". LLM NARRUJE to odkrycie dostosowując do postaci, czasu, miejsca — ale samo odkrycie **musi nastąpić**.

---

### Co zawiera kompletny szablon kampanii

Aktualnie `campaign_templates` ma: `title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids, start_hex_q/r, status`.

**Brakujące pola do dodania:**

| Pole | Typ | Opis |
|------|-----|------|
| `required_npc_keys` | JSON list | NPCe którzy MUSZĄ istnieć w świecie dla tej kampanii (klucze z `npcs` tabeli) |
| `required_location_keys` | JSON list | Lokacje których kampania wymaga (klucze z `game_locations`) |
| `recommended_archetypes` | JSON list | Które archetypy kampania jest zaprojektowana dla (pusta = wszystkie) |
| `estimated_turns` | INT | Oczekiwana długość (dla gracza: "krótka/średnia/długa") |
| `narrative_hooks` | JSON list | Pre-seeded narrative seeds dla Narrative State przy starcie |
| `content_warnings` | TEXT | Ostrzeżenia dla graczy (krew, śmierć NPC, motywy traumy itp.) |
| `required_beats` | JSON list | Kluczowe punkty fabularne które MUSZĄ nastąpić (mechanizm story gravity) |
| `player_visible_description` | TEXT | Opis dla gracza przy wyborze ("Mroczna przygoda w nawiedzonym lesie...") |

---

### Mechanizm "Story Gravity" — gdy gracz ignoruje fabułę

**Problem:** gracz decyduje się ignorować główny wątek i farmuje lochy. Kampania stoi.

**Rozwiązanie — Story Gravity:**

Backend śledzi jak długo dany beat (punkt fabularny) jest aktywny bez postępu. Jeśli przekracza N tur:

```
Beat "antagonist_reveals_plan" jest aktywny od 15 tur bez BEAT_COMPLETE
        │
        ▼
Backend wstrzykuje do kontekstu LLM:
"[STORY GRAVITY] Beat 'antagonist_reveals_plan' nie postąpił od 15 tur.
 W tej turze LLM MUSI wyreżyserować spotkanie lub zdarzenie które naturalnie
 prowadzi do tej sceny. Nie ignoruj tego — to wymagany punkt fabularny."
        │
        ▼
LLM narruje naturalne zdarzenie które prowadzi do beatu
(np. posłaniec przynosi wiadomość, zasadzka antagonisty, przypadkowe spotkanie)
```

Gracz nie wie że jest "railroadowany" — LLM sprawia to narracyjnie naturalnie.

> **Dlaczego to działa?** Profesjonalni GM w RPG robią to cały czas. Gracz odchodzi od głównego wątku → GM sprawia że wątek "odnajduje" gracza. To nie psuje poczucia wolności — tylko sprawia że historia się nie zatrzymuje.

---

### Jak gracz wybiera gotową kampanię

Aktualnie: UI ma przycisk "Gotowa Kampania" ale nie jest jasne jak wygląda ekran wyboru.

**Nowy design ekranu wyboru:**

```
Dostępne Kampanie:

[Karta kampanii]
  Tytuł: "Cienie Zagubionych Królestw"
  Trudność: ★★★☆☆ (Średnia)
  Klimat: "Mroczny, polityczny, intrygi"
  Długość: Średnia (~20-30 tur)
  Zagrane: 14 razy przez innych graczy
  Ostrzeżenia: Śmierć postaci, zdrada
  
  Krótki opis dla gracza:
  "Wróciłeś do miasta po latach nieobecności.
   Ale coś tu jest nie tak — ludzie znikają,
   a stary znajomy prosi o dyskretną przysługę..."
  
  [Zacznij tę kampanię]
```

**Co admin ustawia:**
- `player_visible_description` (krótki opis, nie spoileruje fabuły)
- `difficulty_rating` (1-5)
- `estimated_turns`
- `content_warnings`
- `recommended_archetypes` (opcjonalnie)

---

### Forge — workflow tworzenia gotowych kampanii (admin)

Forge (`adventure_forge.py`) już istnieje jako endpoint. Workflow admin:

```
Admin wchodzi do Forge (Admin Panel → Kampanie → Kuźnia)
        │
        ▼
LLM zadaje pytania: klimat, konflikt, antagonista, finał, NPCe, lokacje
        │
        ▼
LLM generuje szkic kampanii (premise + 3 akty + kluczowi NPCe + lokacje)
        │
        ▼
Admin przegląda, edytuje, dopracowuje
        │
        ▼
Admin weryfikuje czy wymagane NPCe i lokacje istnieją w bazie
(jeśli nie → tworzy je przez Smart Entry lub wskazuje na istniejące)
        │
        ▼
Admin testuje kampanię na koncie testowym
        │
        ▼
Admin publikuje (status: draft → published)
        │
        ▼
Kampania pojawia się u graczy na ekranie wyboru
```

---

### Replayability (grywalność dla różnych postaci)

Ta sama gotowa kampania, ale z różnymi postaciami:

- **Szkielet historii** jest taki sam (admin-pisany) — główny wątek, finał, antagonista
- **Narracja** różni się (LLM adaptuje do tożsamości postaci)
- **Podejście gracza** różni się (Wojownik przebija się siłą, Uczony manipuluje, Łotr kradnie)
- **Side content** różni się (LLM-generowane wątki poboczne)

Gracz który zagrał "Mgły nad ruinami" Wojownikiem i zaczyna od nowa Uczonym przeżyje inaczej mimo tej samej struktury.

---

### Co jest spójne z istniejącym kodem

| Element | Status |
|---------|--------|
| `campaign_templates` tabela | ✅ Istnieje |
| `adventure_forge.py` router (LLM-assisted design) | ✅ Istnieje |
| Kopiowanie `gm_plan_json` z szablonu do kampanii | ✅ Istnieje (w `campaigns.py` przy tworzeniu) |
| `start_hex_q/r` (startowy hex) | ✅ Istnieje w templates |
| Szablony są w bazie (kilka draftów) | ✅ Istnieją ale nie opublikowane |

### Co jest nowe / brakuje

| Element | Status |
|---------|--------|
| `required_npc_keys`, `required_location_keys` w templates | ❌ Brak — nowe pola |
| `required_beats` (mechanizm story gravity) | ❌ Brak |
| Story Gravity: backend śledzi stagnację beatu | ❌ Brak |
| `player_visible_description`, `content_warnings` | ❌ Brak |
| Ekran wyboru kampanii dla gracza (UI) | ❌ Brak lub niekompletny |
| Narrative State pre-seeding z szablonu (`narrative_hooks`) | ❌ Brak |
| Admin: weryfikacja czy wymagane NPCe/lokacje istnieją | ❌ Brak w Forge workflow |

---

### Zadania implementacyjne (Faza 3)

| # | Zadanie | Opis |
|---|---------|------|
| E7 | Rozbuduj `campaign_templates` | Dodaj brakujące pola (required_npc_keys, required_beats, player_visible itp.) |
| E8 | Ekran wyboru kampanii (gracz) | UI z kartami kampanii, opisami, trudnością |
| E9 | Story Gravity mechanizm | Trigger: `next_required_beat` z GM planu nie odpalony przez N tur (nie ogólna aktywność). Progi konfigurowalne z Admin Panelu: 5 tur = hint, 10 tur = instrukcja, 15 tur = forced scene (domyślnie OFF — zbyt agresywne). |
| E10 | Forge: walidacja wymaganych NPC/lokacji | Admin widzi czy template jest "gotowy" do publikacji |
| E11 | Template Narrative State pre-seeding | `narrative_hooks` z szablonu → Narrative State przy starcie kampanii |
| E12 | Publikacja szablonów | Workflow: draft → review → published (już częściowo jest) |

---

### System Encounterów — stan istniejący i redesign

> **Dobra wiadomość:** System jest bardziej rozbudowany niż zakładano. `encounter_service.py` z `maybe_inject_encounter()` istnieje i działa.

**Co działa:**
- Triggery: `hex_enter`, `n_turns`, `combat_end`
- Filtrowanie po biomie (`biomes: ["forest", "swamp"]`)
- Prawdopodobieństwo per encounter (`trigger_probability`)
- Hex-specific pula (`world_hexes.forge_encounter_pool`)

**Problem: Dwie tabele encounterów które się nie znają:**
- `adventure_hooks` (encounter w draft_data) ← używane przez encounter_service ✅
- `gameconfig_encounter_templates` ← istnieje ale odcięta od systemu ❌

Ujednolicić w redesignie (jak items).

**Skalowanie wrogów — ISTNIEJE w kodzie:**
```
HP   = base_hp × (1 + 0.1 × (poziom - 1))    → lvl 5 = 1.4×, lvl 10 = 1.9×
AC   = base_ac + (poziom - 1) ÷ 3             → +1 co 3 poziomy
Dmg_bonus = (poziom - 1) ÷ 2                  → +1 co 2 poziomy
```
Liniowe. Do weryfikacji w testach czy wystarczające na wyższych poziomach.

---

### Trzypoziomowa pula encounterów (projekt)

**Poziom 1 — Generyczna pula globalna:**
N standardowych encounterów z tagami biome/trigger, dostępnych we wszystkich kampaniach. Auto-skalowanie poziomu (działa już dla wrogów w combat_service).

**Poziom 2 — Kampania-specyficzne (Forge):**
Admin podczas tworzenia kampanii dodaje encounter jako hook_type. Przypisywane do konkretnych hexów (`forge_encounter_pool`). Mechanizm istnieje — brakuje hook_type=encounter w Forge UI.

**Poziom 3 — Dynamiczne z gry gracza (ryzykowne, Faza 4):**
LLM w dynamicznej kampanii generuje "ciekawe spotkanie" → auto-zapis pending → auto-screening LLM (jakość/balans) → jeśli score wysoki: admin fast-track queue.

> **Ryzyko:** LLM generuje dziesiątki encounterów dziennie. Bez mocnego auto-screeningu baza zapełni się śmieciami. Wymaga tego samego 3-poziomowego mechanizmu co admin queue (D4). Dlatego to Faza 4 a nie wcześniej.

**Encounter tags (nowe — do zbudowania):**

Encountery potrzebują tagów które określają kiedy mogą być ingestowane:

| Tag | Kiedy encounter może się pojawić |
|-----|----------------------------------|
| `trigger:travel` | Podczas podróży między hexami |
| `trigger:hex_enter` | Przy wejściu na konkretny hex |
| `trigger:combat_end` | Po zakończeniu walki |
| `trigger:rest` | Podczas odpoczynku (ktoś przychodzi w nocy) |
| `biome:forest` | Tylko w lesie |
| `biome:urban` | Tylko w mieście/wiosce |
| `level:1-3` | Tylko dla graczy poziomów 1-3 |
| `campaign_type:dynamic` | Tylko w dynamicznych kampaniach |
| `campaign_id:42` | Tylko w konkretnej kampanii |

System łączy tagi: encounter odpala gdy WSZYSTKIE jego tagi pasują do aktualnego kontekstu.

---

### Zadania implementacyjne dla encounterów

| # | Zadanie | Faza | Opis |
|---|---------|------|------|
| F2-9b | Ujednolicenie tabel encounterów | 2 | Scalenie adventure_hooks i gameconfig_encounter_templates |
| F2-9c | Encounter hook_type w Forge | 2 | Admin tworzy encountery w Forge (jak NPCe i wrogów) |
| F2-9d | Encounter przy travel flow | 2 | maybe_inject_encounter() wywoływany przy akceptacji SUGGEST_MOVE |
| E13 | Generyczna pula encounterów | 3 | N standardowych encounterów z tagami biome/trigger/level |
| E14 | Rozbudowa systemu tagów | 3 | Nowe tagi trigger:rest, campaign_type, campaign_id |
| F2 | Dynamiczne encountery z gameplay | 4 | LLM capture → auto-screening → pending queue |

---

---

---

## CZĘŚĆ AA — Lochy (Dungeon Mode)

> **Tryb:** Farmowanie. Szybkie rundy nastawione na walkę, zagadki i loot. Brak fabuły.
> **Kluczowa zasada:** Loch to izolowany sandbox — śmierć w lochu NIE zabija postaci.

---

### Czym są Lochy

Lochy to oddzielny tryb gry dostępny:
- Z głównego menu (bez aktywnej kampanii)
- Z poziomu kampanii — gdy bohater natrafi na wejście do lochu na hex mapie

Gracz wchodzi do lochu → eksploruje kafelkowane pomieszczenia → pokonuje bossa → dostaje loot i XP → wraca do świata.

---

### Zasada Sandbox — Śmierć bez konsekwencji

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Śmierć w lochu NIE jest śmiercią postaci. Loch restartuje się, a bohater wraca na hex z którego wchodził ze STANEM IDENTYCZNYM jak przy wejściu (HP, mana, warunki, inventory).

```
Gracz wchodzi do lochu z hex (4,7) z HP=18/20
        │
        ▼
System robi SNAPSHOT stanu wejścia:
  {hp: 18, mana: 12, conditions: [], inventory: [...]}
        │
        ▼
Gracz gra loch...
        │
   ┌────┴────┐
   │         │
WYGRANA    ŚMIERĆ
   │         │
   ▼         ▼
Przywróć   Przywróć
snapshot   snapshot
+loot      hex (4,7)
+XP        restart lochu
        │
        ▼
Bohater na hex (4,7) z HP=18/20
(jak przed lochim)
```

**Dlaczego nie przez system śmierci kampanii?** Loch to farmowanie — permanent death tu byłoby zbyt karalne i odstraszałoby od grindu. Restart jest właściwą mechaniką dla arcade-style dungeons.

---

### Architektura kafelkowa (Tile System)

**Kafelek (tile)** = jedno pomieszczenie lochu. Zawiera:
- Obrazek (z puli generowanych grafik)
- Opis pomieszczenia (LLM generuje z obrazka, admin koryguje)
- Układ drzwi: kombinacja N/S/W/E (np. kafelek ma wyjścia: Północ + Wschód)
- Typ wyzwania: combat / zagadka / skrzynia / odpoczynek / pułapka

**Jak działa nawigacja:**

```
Gracz jest w pokoju X, wychodzi przez "drzwi północne"
        │
        ▼
Backend szuka w bazie: kafelek który ma "drzwi południowe"
(żeby pasowało do wyjścia przez które przyszedł gracz)
        │
        ▼
Losuje z pasujących kafelków → wyświetla nowy pokój
        │
        ▼
Gracz wykonuje wyzwanie w nowym pokoju
→ drzwi (inne niż te przez które wszedł) otwierają się
→ wybiera następne wyjście → powtarza
```

**Baza kafelków zawiera:**
- Obrazek (URL/ścieżka do grafiki)
- Układ drzwi (flagi: has_north, has_south, has_east, has_west)
- Opis pomieszczenia dla LLM (tekst generowany z obrazka)
- Typ pomieszczenia (combat/riddle/chest/rest/trap)
- Atmosfera (ciemna lochowa, magiczna, lodowa itp.)

---

### Workflow obrazków → opisy

> **Problem:** Generatory obrazu nie słuchają precyzyjnych instrukcji układu drzwi. Rozwiązanie: najpierw generuj obrazki, potem opisuj co jest na obrazku.

```
1. Generuj 50-100 obrazków pomieszczeń (dowolny generator)
        │
        ▼
2. LLM Vision patrzy na każdy obrazek i generuje:
   - Opis atmosfery (co widać, klimat)
   - Wykrywa gdzie są drzwi/wyjścia (N/S/E/W)
   - Sugeruje typ pomieszczenia
        │
        ▼
3. Admin przegląda, koryguje opisy i układy drzwi
        │
        ▼
4. Tile trafia do dungeon_tiles bazy
        │
        ▼
5. LLM podczas gry używa description z tile do narracji pokoju
   → spójność: opis = to co gracz widzi na obrazku
```

---

### Poziomy trudności i loot

Admin tworzy lochy z konfiguracją trudności. Każdy loch definiuje:

| Parametr | Opis | Przykład |
|----------|------|---------|
| `rooms` | Liczba pokoi (bez bossa) | 4 (łatwy) / 8 (trudny) |
| `enemy_pool` | Klucze wrogów do losowania | ["goblin", "skeleton"] |
| `boss_enemy` | Klucz boss-wroga (ostatni pokój) | "dungeon_boss_lich" |
| `loot_tier` | Tier lootu dla zwykłych pokoi | "standard" / "rich" |
| `cooldown_hours` | Przerwa po ukończeniu | Konfigurowalne z Admin Panelu |
| `min_level` | Minimalny poziom gracza | 1 / 3 / 5 |

**Skalowanie wrogów:** wrogowie skalują do poziomu gracza (istniejący system HP×1.4× na poziomie 5 itd.)

**System lootu — Rarity jako "item power":**

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Zamiast budować nowy system `item_lvl` — używamy istniejącego pola `rarity` (1-5). Loot boss gwarantowany = rarity zgodna z trudnością lochu.

| Trudność lochu | Boss gwarantowany drop | Zwykłe pokoje |
|----------------|----------------------|---------------|
| Łatwy (4 pokoje) | rarity 2 | losowe rarity 1-2 |
| Średni (6 pokoi) | rarity 3 | losowe rarity 2-3 |
| Trudny (8 pokoi) | rarity 4 | losowe rarity 2-4 |
| Ekstremalny (10+) | rarity 5 | losowe rarity 3-5 |

**Dungeon-exclusive items:**
- Flaga `source_exclusive = "dungeon"` w bazie przedmiotów
- Te przedmioty NIGDY nie dropują poza lochami
- Używamy do "grind-worthy" itemów — powód by wracać do lochów

---

### Zapis postępu — jak działa resume

Bieżący stan runu przechowywany w `session_flags.dungeon_run`:
```json
{
  "dungeon_key": "loch_ruin",
  "current_tile_id": 42,
  "rooms_cleared": 3,
  "entry_snapshot": {
    "hp": 18, "mana": 12, "conditions": [], "gold_gp": 150
  },
  "rewards_so_far": [],
  "started_at": "2026-06-05T10:00:00Z"
}
```

Przy powrocie: gracz widzi "Masz niedokończony loch" → może wznowić lub porzucić.  
Porzucenie = cooldown NIE startuje (stracone postępy ale nie blokuje).  
Ukończenie lub śmierć = cooldown startuje.

---

### Stan kodu vs nowy design

| Element | Status |
|---------|--------|
| Tile-based system (`dungeon_tile_service.py`) | ✅ Istnieje, aktywny |
| N/S/E/W dopasowanie kafelków | ✅ Istnieje |
| `dungeon_run` w session_flags | ✅ Istnieje |
| Cooldown per character | ✅ Istnieje |
| Skalowanie wrogów | ✅ Istnieje |
| Snapshot stanu przy wejściu | ✅ `source="dungeon_enter"` w `world_state_snapshots` — HP, złoto, inventory |
| Przywrócenie snapshotu przy śmierci/wyjściu | ❌ Brak |
| Obrazki + opisy per tile | ⚠️ Tabela istnieje, zawartość mała |
| LLM Vision workflow (obrazek → opis) | ✅ `scripts/vision_describe_tiles.py` na .170 (llava:7b + `needs_description` filter) |
| Admin UI: tile manager (obrazki, drzwi, opis) | ⚠️ Częściowy |
| `source_exclusive = "dungeon"` flag | ✅ Istnieje |
| Rarity jako tier lootu per trudność | ✅ `RARITY_TIERS` + `dungeon_difficulty` + `get_loot_rarity_for_difficulty()` |
| Cooldown konfigurowalny z Admin Panelu | ✅ Edytowalny z `/admin/#dungeons` + `dungeon_difficulty` też |

---

### Zadania implementacyjne

| # | Zadanie | Faza |
|---|---------|------|
| E15 | Snapshot stanu przy wejściu do lochu | 3 |
| E16 ✅ | Przywróć snapshot przy śmierci + restart lochu — #431 (2026-06-09) | 3 |
| E17 | Rarity tierów loot w lochach: 5 tierów (Zwykły/szary, Ulepszony/zielony, Rzadki/niebieski, Epicki/fioletowy, Legendarny/złoty). Mapowanie difficulty→rarity: D1=Zwykły–Ulepszony, D2=Ulepszony–Rzadki, D3=Rzadki–Epicki, D4=Epicki–Legendarny, D5 boss=Epicki–Legendarny (guaranteed). | 3 |
| E18 | Cooldown UI w Admin Panelu | 3 |
| E19 | LLM Vision: obrazek → opis kafelka | 3 |
| E20 | Admin UI: tile manager (obrazki, drzwi, opisy) | 3 |
| E21 | Wejście do lochu z hex mapie kampanii | 3 |
| E22 | Resume niedokończonego runu | 3 |

---

## CZĘŚĆ AB — System Walki, Ran i Modelu Wroga

> **Sesja:** 2026-06-05 — audyt istniejącego silnika walki + decyzje balansowe.
> **Stan kodu:** Silnik walki (`combat_service.py`, 2853 linii) jest dojrzały i działa. Ta sekcja dokumentuje co JEST, co wymaga poprawki, i zapadłe decyzje.

### Co działa dobrze (zachowujemy)

**Rozwiązanie ataku:** `d20 + stat_mod + skill_rank + proficiency + wound_penalty` vs obrona celu. Nat 20 = auto-trafienie + podwójne obrażenia. Nat 1 = auto-pudło. Proficiency +2 gdy skill_rank ≥ 3. Zgodne z zablokowaną mechaniką w `system_prompt.txt`.

**Inicjatywa:** raz na walkę dla wszystkich uczestników (`d20 + DEX_mod`), sortowanie malejące, remis → gracz wygrywa. Kolejność trzymana w `turn_order`. Runda bumpuje gdy pierwszy aktor dostaje kolejną turę. **Zgodne z założeniem:** jeden rzut inicjatywy na walkę, potem rundy wg modyfikatorów.

**Skalowanie wrogów:** `hp_base × (1 + 0.1 × (poziom_gracza − 1))`. Lvl 5 = 1.4×, lvl 10 = 1.9×. Już działa, nie ruszać.

### System stref (engaged / ranged) — POTWIERDZONE OK

> **Wątpliwość gracza (2026-06-05):** "czy zmiana strefy nie powinna zabierać tury? inaczej strategia ruchu nie ma sensu". **Weryfikacja kodu: zmiana strefy JUŻ zabiera turę.** Wątpliwość rozwiązana — system działa poprawnie.

Dwa różne zdarzenia, nie mylić:

| Zdarzenie | Zabiera turę? | Dlaczego |
|---|---|---|
| Akcja "Zbliż się / Cofnij się" (`change_player_zone`) | **TAK** — toggle strefy + `advance_turn()` | Ruch to decyzja strategiczna, musi kosztować turę |
| Zablokowany atak melee na wroga w innej strefie | **NIE** — komunikat "poza zasięgiem", gracz próbuje znów | Kara za zły klik nie powinna palić tury |

Czyli strategia ruchu MA sens: by trafić wroga w innej strefie, gracz traci turę na zbliżenie. To koszt.

**UI stref — potwierdzone że istnieje:**
- Baner walki = 2 kolumny **DYSTANS** / **ZWARCIE** (`app.js`), każdy combatant trafia do swojej kolumny.
- Chipy inicjatywy mają glif: 🏹 (ranged) / ⚔ (engaged).
- Przycisk zmienia label "Zbliż się" ↔ "Cofnij się" wg strefy gracza.

Gracz widzi kto gdzie stoi. **Do rozważenia (niski priorytet):** wizualne "linie frontu" zamiast tekstowych kolumn — polish UI, nie mechanika.

### System ran — DECYZJA: symetryczny (gracz + wrogowie)

"Rana" to kara, którą dostaje każdy, kto walczy z niskim zapasem zdrowia. Im bliżej śmierci, tym słabiej bije.

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Rany działają **symetrycznie** — zarówno bohater, jak i wrogowie, gdy spadną nisko na zdrowiu, biją słabiej. Ten sam próg, ta sama kara, niezależnie od tego, czy to gracz, czy potwór.

> **Dlaczego?**
> Symetria tworzy taktykę: opłaca się dobić rannego wroga, zanim ten zdąży cię trafić, bo ranny przeciwnik jest mniej groźny. Bez symetrii (kara tylko dla gracza) ranny wróg na 1 HP bije tak samo mocno jak na pełnym zdrowiu — gracz nie ma powodu, by skupiać ogień, a sam czuje się tylko karany. Symetria jest też sprawiedliwa: świat działa wedle tych samych reguł dla obu stron.

> **Co odrzucono i dlaczego?**
> - **Tylko gracz, łagodne kary** — prościej, ale brak taktyki "dobij rannego" i gracz czuje się jednostronnie karany. Odrzucone.
> - **Tylko kosmetyka** (etykiety bez kar mechanicznych) — najbezpieczniejsze dla balansu, ale rany przestają cokolwiek znaczyć w walce. Odrzucone.
> - **Zostawić jak jest** (kary tylko dla gracza, obecne progi) — nie rozwiązuje asymetrii ani niespójności front/back. Odrzucone.

> **Co się zepsuje, jeśli odwrócić tę decyzję?**
> Jeśli usuniemy karę wrogom, znika taktyka skupiania ognia — gracz równie dobrze może rozkładać ataki na wszystkich. Walka staje się mniej ciekawa, a permadeath bardziej frustrujący (gracz karany, wróg nie).

**Docelowe progi ran (po unifikacji, do walidacji w playteście):**

| HP % | Etykieta | Kara mechaniczna |
|---|---|---|
| > 50% | (brak) | — |
| 26–50% | Ranny | 0 — tylko klimat/narracja |
| 11–25% | Poważnie ranny | −1 do trafienia |
| 1–10% | Na skraju śmierci | −2 do trafienia, −1 DEX |

> **Dlaczego łagodniej niż obecny frontend?**
> Obecny frontend pokazuje karę już od 51% HP. Przy permadeach to grozi "spiralą śmierci": jesteś ranny → bijesz słabiej → dostajesz więcej → bijesz jeszcze słabiej → giniesz bez szansy na odwrót. Przesunięcie pierwszej realnej kary na ≤25% HP daje graczowi okno na ucieczkę lub leczenie. Liczby to wartość startowa — do dostrojenia po testach.

**Stan obecny — DWA problemy:**

**Problem #1 — dwie różne tabele ran (niespójność front/back):**

Backend (`vitality_service.py` — `wound_penalty()`, NAPRAWDĘ stosowane w `weapon_rules.py` i `skill_service.py`):

| HP % | Kara ATK | Kara DEX | Tier |
|---|---|---|---|
| > 25% | 0 | 0 | brak |
| 11–25% | −1 | 0 | severe |
| 1–10% | −2 | −1 | critical |

Frontend (`app.js` — `getWoundLabel()`, tylko wyświetlanie, INNE progi):

| HP % | Etykieta | mechEffect w tooltipie |
|---|---|---|
| 51–75% | Ranny | (brak) |
| 26–50% | Ciężko Ranny | (brak) |
| 11–25% | Poważnie Ranny | −1 ATK |
| 1–10% | Na Skraju Śmierci | −2 ATK, −1 DEX |

Gracz widzi w tooltipie kary które backend stosuje przy innych progach. **Trzeba zunifikować na JEDNĄ tabelę** (źródło: backend `vitality_service`, front tylko czyta).

**Problem #2 — rany NIE dotyczą wrogów.** `wound_penalty()` bierze `sheet` (karta gracza). Wróg nie ma sheet — ma uproszczone `attack_bonus`. Ranny wróg na 1 HP bije tak mocno jak na full. **Decyzja: dodać symetrię.**

**Rozwiązanie:**
1. Zunifikować progi/etykiety — jedna tabela, front czyta z backendu (lub mirror z identycznymi liczbami).
2. Przerobić `wound_penalty()` by działało na `hp_current / hp_max` **dowolnego combatanta** (nie tylko na `sheet`), żeby dało się policzyć dla wroga.
3. Podpiąć karę wroga w ścieżce ataku wroga (`resolve_enemy_attack`).

### Model wroga — uproszczony, NIE jak gracz (udokumentowane)

> **Pytanie gracza (2026-06-05):** "czy wrogowie traktowani są tak samo jak gracze — statystyki i skille?" **Odpowiedź: NIE, wrogowie są uproszczeni. Celowo.**

| | Gracz | Wróg |
|---|---|---|
| Statystyki | 7 pełnych (STR/DEX/CON/INT/WIS/CHA/LCK) | brak — tylko `dex_modifier` |
| Skille | pełna pula z rankami | brak |
| Atak | `d20 + stat_mod + skill_rank + proficiency + wound` | `d20 + attack_bonus` (jedna liczba) |
| Obrona | `AC = 10 + DEX_mod + archetyp` | `ac_base` (stała) |
| HP | formuła archetyp + CON×lvl | `hp_base × skalowanie_poziomem` |
| Rany | tak | **dodać** (decyzja: symetria) |

**Dlaczego tak:** admin tworzy wroga wpisując 4 liczby (HP, AC, atak, kość obrażeń) — wróg gotowy. Gdyby wróg miał 7 statów + skille, tworzenie = koszmar. Asymetria jest **zaletą projektową**, nie błędem. Symetria ran nie zmienia tego — wound_penalty liczy się z HP%, którego wróg już używa.

### Efekty broni (`on_hit_save`) — działa, czeka na Unified Effects

Broń może mieć dodatkowy efekt przy trafieniu: normalne obrażenia ZAWSZE, plus ofiara robi rzut obronny (save) — jak nie zda, łapie warunek (np. Płonący → obrażenia co turę). Już działa (`weapon_rules.py`). To dokładnie fundament pod afiksy "ognisty miecz" (patrz CZĘŚĆ X — System Afiksów). Po redesignie Effect Objects ten mechanizm staje się jednym z triggerów (`on_hit`).

### Death saves i leczenie — działa (zachowujemy)

**Death saves** (`solo_death_service.py`): eskalująca drabina DC 10→13→16→19 per kolejne 0-HP w tej samej walce. 3 porażki = śmierć. Nat 1 = 2 porażki naraz. Nat 20 = sukces (porażki NIE resetują się — drabina per-walka). Śmierć = koniec kampanii + epitafium LLM.

**Leczenie** (`rest_service.py`):
- Krótki odpoczynek: `1d6 + CON_mod` HP, max 2× między długimi, +1h zegara.
- Długi odpoczynek: full HP + mana, flush pending_xp → xp_available, reset death_saves + short_rests, +8h zegara.
- Oba wymagają `safe_for_rest` (lokacja/hex). Niebezpieczny hex = brak odpoczynku.

### Status implementacji (CZĘŚĆ AB)

| Element | Status |
|---------|--------|
| Rozwiązanie ataku (d20 + modyfikatory, Nat 20/1) | ✅ działa, 🔒 zablokowane mechaniką |
| Inicjatywa raz na walkę + rundy | ✅ działa zgodnie z założeniem |
| Skalowanie HP wrogów do poziomu gracza | ✅ działa |
| Strefy engaged/ranged — zmiana strefy kosztuje turę | ✅ działa |
| UI stref (kolumny DYSTANS/ZWARCIE + glify) | ✅ działa |
| Efekty broni `on_hit_save` | ✅ działa, czeka na Unified Effects |
| Death saves (drabina DC, epitafium) | ✅ działa |
| Leczenie (krótki/długi odpoczynek) | ✅ działa |
| Tabela ran spójna front ↔ back | ⚠️ dwie różne tabele — do unifikacji (C4) |
| Rany dla wrogów (symetria) | ❌ wróg nie dostaje kary — do dodania (C5, C6) |
| Wizualne linie frontu w UI | ❌ opcjonalny polish (D6) |

### Zadania implementacyjne

| # | Zadanie | Faza |
|---|---------|------|
| C4 | Unifikacja tabeli ran — jedna prawda (backend), front czyta te same progi/etykiety | 1 |
| C5 | `wound_penalty()` działa na `hp_current/hp_max` dowolnego combatanta (nie tylko sheet) | 1 |
| C6 | Symetria ran — podpiąć karę wroga w `resolve_enemy_attack` | 1 |
| D6 | (opcja, niski prio) Wizualne linie frontu w UI stref zamiast kolumn tekstowych | 2 |

---

## CZĘŚĆ AC — Tryb Multiplayer (gra wieloosobowa)

> **Sesja:** 2026-06-05 — projekt docelowy + audyt istniejącego kodu.
> **Stan kodu:** Plumbing (lobby, zaproszenia, czat, rundy, host-handoff) gotowy w ~70-80%. Integracja z mechaniką gry = 0%. Ta sekcja definiuje stan docelowy.

Multiplayer to ta sama gra co solo, w której **2 do 4 osób gra wspólnie jedną przygodę**, opowiadaną przez LLM. Gracze mają osobnych bohaterów, ale dzielą jeden świat, jedną historię i jedno miejsce na mapie.

### Naczelna zasada: MP = solo dla wielu, nie osobna gra

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Tryb multiplayer to **przełożenie pełnej mechaniki solo** (rzuty, walka, HP, World State, XP, ekwipunek, questy) na grę wieloosobową. Nie jest to osobny, lekki tryb narracyjny. Wszystkie zasady solo obowiązują; multiplayer dokłada warstwę synchronizacji wielu graczy na wierzch.

> **Dlaczego?**
> Obecny kod traktuje MP jako oddzielny silnik — `trigger_narration` woła LLM bezpośrednio, omijając całą mechanikę. Efekt: w MP nie ma walki, rzutów, HP ani postępu. To dwie różne gry. Gracz, który zagrał solo, w MP dostaje uboższe doświadczenie. Cel: jedno doświadczenie, tylko z większą liczbą ludzi.

> **Co odrzucono i dlaczego?**
> - **MP jako lekki tryb storytellingu** (obecny stan kodu) — prostszy, ale rozjeżdża się z solo i rozczarowuje graczy znających pełną grę. Odrzucone.

> **Co się zepsuje, jeśli odwrócić tę decyzję?**
> Gdyby MP zostało osobnym silnikiem, każda nowa mechanika solo (afiksy, questy, zegar) wymagałaby drugiej implementacji dla MP albo nigdy by tam nie trafiła. Podwójne utrzymanie, trwała rozbieżność.

### Dwa tryby tury

> **Decyzja (2026-06-05):** Gra ma dwa modele tury, przełączane automatycznie wg sytuacji.

Problem: akcje eksploracji można rozstrzygać jednocześnie, ale walki — nie (atak na ślepo na wroga, którego ktoś już zabił).

| Tryb | Kiedy | Model | Timer |
|---|---|---|---|
| **Narracyjny** | eksploracja, dialog, skradanie | **jednoczesny** — wszyscy oddają akcje, LLM tworzy jedną wspólną narrację 3-osobową | długi (np. 24h, ustawialny) |
| **Walka** | od startu do końca walki | **sekwencyjny wg inicjatywy** — jeden aktor naraz | krótki (np. 2 min) |

> **Dlaczego walka sekwencyjna, a nie jednoczesna?**
> Walka jednoczesna rodzi sprzeczności nie do rozwiązania: dwóch graczy oddaje na ślepo atak na goblina o 5 HP — pierwszy go zabija, drugi marnuje turę na trupa. W modelu sekwencyjnym każdy widzi aktualny stan, gdy przychodzi jego kolej. Co najlepsze — **silnik walki solo już jest turowy z inicjatywą** (`turn_order` obsługuje wielu aktorów). MP nie buduje walki od nowa: podstawia ludzkich graczy w miejsce aktorów w kolejce inicjatywy. Wrogowie i sojusznicy rozstrzygają się natychmiast, bez czekania.

**Jak wygląda walka w MP (przykład):**

```
Walka start → inicjatywa dla WSZYSTKICH (gracze + wrogowie + sojusznicy)
   Kolejność: Mira(18) → Goblin(14) → Aldric(11) → Ksawery(7)

Tura Miry    → push "Twoja kolej" → Mira atakuje → goblin pada
             → push do WSZYSTKICH "Goblin zginął — stan się zmienił"
Tura Goblina → już martwy, pomijany
Tura Aldrica → widzi aktualny stan (goblin martwy) → wybiera inny cel
Tura Ksawerego → ...
```

> **Tradeoff do świadomości:** walka 5 rund × 4 graczy = do 20 ludzkich tur × 2 min = ~40 min w trybie async. Push "Twoja kolej" pcha grę naprzód. Akceptowalne dla gry asynchronicznej, ale długie. Stąd krótki timer walki (2 min) vs długi narracyjny.

### Synchronizacja: timer tury + obsługa nieobecności

Gra jest z założenia **asynchroniczna** — gracze nie muszą być online jednocześnie. Bloker: gracz znika na długo i blokuje resztę.

**Mechanizm tury:**
1. LLM podaje narrację → wszyscy gracze mają X czasu (timer) na odpowiedź.
2. Backend czeka aż **wszyscy oddadzą** (może być szybciej niż timer) **lub minie czas**.
3. Gdy wszyscy oddali → narracja od razu. Gdy minie czas → narracja z brakującymi oznaczonymi.

> **Decyzja (2026-06-05) — egzekucja timera przez lekki background task:**
> Timer wymaga procesu, który budzi rundę po deadline. Rozwiązanie: lekki task w `main.py` (sweep co ~30–60s), który znajduje rundy z minionym `deadline`, domyka je i wysyła push PWA.

> **Dlaczego cron, a nie leniwe sprawdzanie przy pollingu?**
> Leniwe sprawdzanie (przy każdym pollingu gracza) nie zadziała, gdy wszyscy są offline — nikt nie odpala triggera, więc runda wisi w nieskończoność, a push o deadline nie wychodzi. Skoro chcemy powiadomień PWA przy końcu tury, **musi** istnieć proces działający niezależnie od obecności graczy. Jeden lekki task, zero zewnętrznej infrastruktury.

**Obsługa nieobecności (system ostrzeżeń):**

> **Decyzja (2026-06-05):** Kod oznacza brak akcji, LLM tylko narruje pasywność. 3 ostrzeżenia → głosowanie nad wyrzuceniem.

```
Gracz nie oddał akcji w czasie tury:
   → push PWA "Twoja kolej mija!"
   → kod oznacza akcję jako [BRAK AKCJI — postać bierna]
   → LLM narruje pasywność: "Ksawery stał z boku, przysłuchując się rozmowie"
   → +1 ostrzeżenie (licznik KOLEJNYCH pominięć)

Powrót gracza (oddanie akcji) → licznik ostrzeżeń RESET do 0

Po 3 KOLEJNYCH ostrzeżeniach:
   → gracze dostają opcję "Vote to kick"
   → w grze 2-osobowej: auto-kick za potwierdzeniem hosta (brak kworum na głosowanie)
```

> **Dlaczego kod oznacza absencję, a nie LLM?**
> Zgodnie z zasadą "mechanika decyduje, LLM narruje". Gdyby LLM sam decydował o nieobecności, mógłby dać brakującemu graczowi korzystną akcję albo całkiem o nim zapomnieć. Kod wstawia jawny token `[BRAK AKCJI]`, LLM tylko ubiera go w słowa. Pewność zamiast nadziei.

> **Dlaczego licznik liczy KOLEJNE pominięcia, nie życiowe?**
> Gdyby liczył wszystkie pominięcia w kampanii, po 30 turach każdy uzbierałby 3 i zostałby kandydatem do wyrzucenia. Reset przy powrocie karze tylko realną, ciągłą nieobecność.

**Walka a nieobecność:** brakujący bohater stoi w inicjatywie, pomija turę (broni się), ale **może oberwać** od wrogów. To realistyczne i blokuje exploit "idę AFK, żeby uniknąć śmierci".

### Drużyna jako jeden żeton na mapie

> **Decyzja (2026-06-05):** Drużyna porusza się jako JEDNA jednostka — jeden hex, jeden współdzielony World State.

> **Dlaczego?**
> Gdyby każdy gracz miał osobną pozycję, mielibyśmy 4 osobne World State i 4 osobne wątki świata do pogodzenia — chaos nie do opanowania w grze opowiadanej przez jeden LLM. Drużyna jako żeton trzyma jeden spójny świat.

- **Gracz nieobecny przez kilka tur:** jego bohater jest wleczony z drużyną narracyjnie ("Ksawery podąża machinalnie, zamyślony"). Mechanicznie pozycja bohatera = pozycja drużyny, zawsze.
- **Gracz wraca po N turach:** dostaje **catch-up** — narracje pominiętych rund pokazane przy wejściu (`get_rounds_history` już istnieje) plus jedna sprasowana linijka: "Pod twoją nieobecność drużyna przeszła do jaskini i pokonała gobliny". Ostrzeżenia reset. Bohater na aktualnej pozycji z aktualnym stanem.
- **Konflikt ruchu** (sprzeczne kierunki od obecnych graczy): warstwa rozstrzygania kodu wybiera kierunek — głosowanie / host rozstrzyga remis / LLM narruje, że drużyna się spiera i zostaje. **Reguła do dopracowania** (część szerszego problemu współdzielonego World State, niżej).

### Współdzielony World State — konflikt zapisów (problem otwarty)

> **Status: do zaprojektowania.** Faza 0 wprowadza Gate Mechanic walidujący akcję względem World State PRZED LLM. W MP 4 graczy waliduje względem TEGO SAMEGO snapshotu rundy:

```
World State: w pokoju leży jeden klucz.
Gracz A: "podnoszę klucz" → Gate: klucz jest → OK
Gracz B: "podnoszę klucz" → Gate: klucz jest (ten sam snapshot) → OK
Konflikt: dwóch graczy ma ten sam klucz.
```

HP / ekwipunek / XP są per-bohater (bezpieczne). Ale **współdzielone obiekty świata** (klucz, drzwi, nastawienie NPC, czy wróg żyje) są kontestowane. Potrzebna warstwa rozstrzygania konfliktów PO bramce a PRZED narracją: kod decyduje kto pierwszy, reszta dostaje zaktualizowany stan ("klucz już zabrany"). **Do zaprojektowania w Fazie integracji MP.**

### Łup i ekonomia w MP

> **Decyzja (2026-06-05):** Każdy gracz nagrodzony osobnym losowaniem klasowym; złoto dzielone równo.

- **Przedmioty:** każdy gracz po walce robi własny random roll z **filtrem klasy** — uczony dostaje broń archetypową (laska) i przedmioty INT, wojownik/łotr miecz i przedmioty STR/DEX. Każdy czuje nagrodę.
- **Złoto:** wspólna pula z walki **dzielona równo** między wszystkich graczy.

> **Dlaczego osobny roll per gracz?**
> W co-op każdy uczestnik musi czuć, że walka mu się opłaciła. Pojedynczy roll z tabeli wroga (jak solo) nagrodziłby tylko jednego. Filtr klasy zapobiega bezużytecznym dropom (laska dla wojownika).

> **Flaga do zbalansowania:** osobny roll = 4× drop na walkę vs solo. Ryzyko inflacji. Łagodzić niższymi wagami/tierami dla MP. Liczby do dostrojenia w playteście.

**Notatki na później (poza zakresem teraz):**
- **Handel między graczami** (sprzedaż/wymiana przedmiotów) — wartościowe, ale złożone (transakcje, zgody, anti-scam). Tylko notatka, nie teraz.
- **Skalowanie "mniej graczy = lepszy łup, trudniejsze walki"** — pomysł na nagrodę za grę w mniejszym składzie. Wymaga balansu trudność↔nagroda. Brak konkretnej formuły na teraz — notatka.

### Whisper — czysta komunikacja graczy

> **Decyzja (2026-06-05):** Whisper obsługuje KOD, nigdy LLM.

Gracze mogą szeptać w czacie gry (`/whisper @gracz`) — wiadomość prywatna, **nieczytana przez grę**, służy tylko komunikacji gracz↔gracz.

> **Dlaczego kod, a nie LLM?**
> Gwarancja prywatności. Gdyby szept kiedykolwiek trafił do promptu, LLM mógłby go wyciec do narracji. Tylko kod może twardo zagwarantować, że szept nigdy nie wejdzie do kontekstu LLM. Już tak działa: `whisper_to` filtrowany server-side, `trigger_narration` go nie widzi. Zachować.

### Dołączanie i wychodzenie z gry

- **Host startuje bez pełnej drużyny** — gra może ruszyć z niekompletnym składem.
- **Spóźnialscy wprowadzani narracyjnie** przez LLM ("drużyna spotkała go na trakcie") — rola narracji, nie sztywna mechanika.
- **Kick → bohater do stanu `idle`, nie kasowany.** Gracz może grać tym samym bohaterem dalej solo. **Zebrane XP, złoto i przedmioty zostają u bohatera**, nawet jeśli kick nastąpił w połowie kampanii.
- **Host-handoff** (host wychodzi → następny zaakceptowany gracz zostaje hostem) — już zaimplementowane, z jednorazowym `host_note`.
- **Zastępstwo:** po wyrzuceniu gracza host może zaprosić nowego na jego miejsce.

### Status implementacji (CZĘŚĆ AC)

| Element | Status |
|---------|--------|
| Lobby, zaproszenia (username + link), max_players | ✅ działa |
| Membership lifecycle (pending/accepted/declined/removed/left) | ✅ działa |
| Host-handoff przy wyjściu hosta | ✅ działa |
| Czat party + whisper (kod, nie LLM) | ✅ działa |
| Runda narracyjna jednoczesna (zbierz akcje → 1 narracja) | ✅ działa |
| Push PWA (narracja gotowa, gracz dołączył) | ✅ działa |
| Historia rund + restore przy wejściu | ✅ działa |
| **Pełna mechanika solo w MP** (rzuty, HP, XP, World State) | ❌ ZERO integracji — rdzeń pracy |
| **Walka w MP** (sekwencyjna wg inicjatywy, reuse silnika solo) | ❌ do zbudowania |
| Rzuty kością (auto-roll przez kod w rundzie) | ❌ `roll_cues` to dziś martwe sugestie |
| **Egzekucja timera** (cron sweep + push przy deadline) | ❌ deadline zapisany, nieegzekwowany |
| Absencja: `[BRAK AKCJI]` + narracja pasywna + ostrzeżenia | ❌ do zbudowania |
| Vote-to-kick + auto-kick 2-os + reset po powrocie | ❌ (jest tylko host-kick pre-game) |
| Drużyna jako jeden żeton + catch-up po powrocie | ⚠️ historia jest, jeden-żeton/catch-up do zbudowania |
| Konflikt współdzielonego World State | ❌ do zaprojektowania |
| Loot per-gracz klasowy + złoto dzielone | ❌ do zbudowania |
| Handel między graczami | 📝 notatka na przyszłość |
| Skalowanie mniej-graczy=lepszy-loot | 📝 notatka, brak formuły |

### Zadania implementacyjne

> **Faza:** Multiplayer to duży blok zależny od Fazy 0 (World State) i Fazy 1 (rdzeń mechaniki). Realny dopiero po nich. Oznaczone jako Faza MP.

| # | Zadanie | Zależy od |
|---|---------|-----------|
| G1 | Egzekucja timera — background sweep w `main.py` (domknij rundę po deadline, push) | — |
| G2 | Absencja: token `[BRAK AKCJI]`, narracja pasywna, licznik kolejnych ostrzeżeń + reset | G1 |
| G3 | Vote-to-kick + auto-kick 2-os (host potwierdza) + zaproszenie zastępstwa | G2 |
| G4 | Integracja World State z rundą MP (jeden żeton drużyny, współdzielony stan) | Faza 0 |
| G5 | Conflict resolution World State: gracze składają akcje jednocześnie (okno czasowe), backend przetwarza wg inicjatywy (wyższa init = pierwsza). Gracz z niższą init dostaje feedback gdy stan świata się zmienił ("Cel już martwy", "Przedmiot już zabrany"). Reużywa `turn_order` z combat_service. | G4 |
| G7 | Walka w MP — reuse silnika turowego solo, ludzie w `turn_order`, sekwencyjnie | Faza 1 (walka) |
| G8 | Auto-roll kości przez kod w rundzie (zamiana `roll_cues` na realne rzuty) | G4 |
| G9 | Timer walki skrócony (2 min) + push "Twoja kolej" per tura | G7 |
| G10 | Loot per-gracz z filtrem klasy + złoto dzielone równo | Faza 1 (loot), afiksy |
| G11 | Catch-up po powrocie (narracje pominiętych rund + sprasowane podsumowanie) | G2 |
| G12 | Spóźnialscy: wprowadzenie narracyjne + start bez pełnej drużyny | G4 |
| G13 | Kick → bohater do `idle` z zachowaniem XP/złota/przedmiotów | — |
| G14 (later) | Handel między graczami | — |
| G15 (later) | Skalowanie trudność/loot wg liczby graczy | playtest |

---

## CZĘŚĆ AD — Flow poza grą (UI/UX paneli)

> **Sesja:** 2026-06-05 — audyt 17 ekranów "skorupy" wokół rozgrywki.
> **Stan kodu:** Flow istnieje i jest w większości kompletny. Struktura poprawna, ale jeden problem strukturalny + zakleszczenia + drobne UX.

To jest cała ścieżka gracza ZANIM zacznie właściwą rozgrywkę: logowanie, profil, wybór bohatera, tworzenie postaci, wybór i tworzenie kampanii.

### Mapa flow (stan obecny)

```
login → [rejestracja / weryfikacja maila / odzyskiwanie hasła]
  ↓ (nowy gracz) onboarding (animacja + wybór motywu)
  ↓
BOHATEROWIE (hub) ──→ profil (konto, LLM "Connect", znajomi, usuń konto)
  ↓ wybór bohatera
  ├─ idle  → panel idle → KAMPANIE
  └─ aktywny → KAMPANIE
       ↓
KAMPANIE (hub) — 5 trybów: Nowa / Gotowa / Loch / Loch-kafelki / Multiplayer
  ├─ Nowa → nazwa → styl (haki/szablon) → [tworzy kampanię] → KREATOR → gra
  ├─ Gotowa → siatka szablonów → KREATOR → gra
  ├─ Multiplayer → tworzenie lobby → lobby → gra
  └─ karta istniejącej kampanii → wejście do gry
```

**Ogólny werdykt:** struktura poprawna i kompletna (pełny auth, hub hero-first, kreator 4-kroki, 5 trybów). Problemy: jeden strukturalny (kolejność hero↔kampania), kilka zakleszczeń, drobne UX.

### Problem strukturalny: kolejność hero ↔ kampania

> **Zasada projektowa (zatwierdzona 2026-06-05): Hero-first.**
> Bohater powstaje RAZ na ekranie Bohaterowie, przez kreator. Tworzenie kampanii NIGDY nie odpala kreatora postaci — gracz wybiera tryb, a istniejący bohater wchodzi w kampanię. Bohater jest niezależnym bytem, używanym wielokrotnie w różnych kampaniach.

> **Dlaczego?**
> Obecny kod ma dwie sprzeczne ścieżki tworzenia bohatera: (1) Bohaterowie → "Nowy Bohater" → kreator (poprawnie), oraz (2) Kampanie → Nowa Kampania → styl → tworzy kampanię → kreator (`_finalCreateCampaign → startCharacterWizard`, app.js:1879). Druga ścieżka jest sprzeczna: na ekran Kampanie wchodzisz już mając wybranego bohatera (przez selectHero), a mimo to deep-flow odpala kreator nowej postaci. To łamie model hero-first opisany w CLAUDE.md ("Heroes are independent entities... Deleting a campaign frees the hero").

> **Co odrzucono i dlaczego?**
> - **Campaign-first** (każda kampania rodzi własną postać) — łamałby reused bohaterów i cały model hero-first. Odrzucone.
> - **Hybryda kontekstowa** (kreator jako fallback gdy brak bohatera) — działa, ale zostawia dwie ścieżki i niejasność. Odrzucone na rzecz czystego hero-first.

> **Co się zepsuje, jeśli odwrócić tę decyzję?**
> Powrót do campaign-first oznacza, że bohater nie może być używany w wielu kampaniach ani grać dalej solo po multiplayer — fundament hero-first znika.

**Naprawa:** ścieżka tworzenia kampanii (Nowa/Gotowa) zakłada istniejącego, wybranego bohatera i prowadzi prosto do gry. Kreator postaci dostępny WYŁĄCZNIE z ekranu Bohaterowie. Jeśli gracz nie ma żadnego bohatera, ekran Kampanie kieruje go najpierw do kreatora (jednorazowo), nie tworzy postaci w pętli kampanii.

### Zakleszczenia (stuck-states) — do naprawy

| Ekran | Problem | Ryzyko | Naprawa |
|---|---|---|---|
| Lobby MP | host nie kliknie "Rozpocznij" → goście utknęli na zawsze | 🔴 wysokie | timeout lobby / wskaźnik "host nieaktywny" / auto-zamknięcie |
| Onboarding | animacja CSS padnie → brak "pomiń" → utknięcie na kroku 1 | 🟡 średnie | przycisk "Pomiń" + auto-advance po timeout |
| Weryfikacja maila | mail nie dotarł → resend bez końca, brak przejścia | 🟡 średnie | limit resendów + link do wsparcia |
| campaign-style / prebuilt | fetch haków/szablonów wisi "Ładowanie…" bez końca | 🟡 średnie | timeout + komunikat błędu + retry |

### UX i odporność — do naprawy

| Problem | Skutek | Naprawa |
|---|---|---|
| Swipe-delete na kartach bohatera i kampanii | łatwo przypadkiem usunąć (zwł. przy scrollu), brak undo | undo-toast albo drugie potwierdzenie; usunięcie bohatera = destrukcyjne, wymaga twardego potwierdzenia |
| Hard-back z kreatora | gubi draft postaci bez ostrzeżenia | dialog potwierdzenia przed wyjściem |
| Brak globalnego error boundary | nieudany load = pusty ekran wyglądający jak "brak danych" | toast błędu + przycisk ponów dla loadHeroes/loadCampaigns |
| idle vs aktywny bohater | niewidoczne dla gracza, dwie ścieżki z selectHero | ujednolicić albo pokazać stan jawnie |

### Powiązane, już udokumentowane luki (z game_flow.md ETAP 2-4)

- Traumy nie zapisywane przy tworzeniu postaci → naprawić (seed)
- `hidden_trait` (ukryta cecha) nie zaimplementowane → zaprojektować
- Pula umiejętności za mała (#333) → osobny task

### Status implementacji (CZĘŚĆ AD)

| Element | Status |
|---------|--------|
| Logowanie + rejestracja + weryfikacja + reset hasła | ✅ działa |
| Onboarding (cinematic + motyw) | ✅ działa — D10 [#385] karty motywu + zapis |
| Hub Bohaterowie (hero-first) | ✅ działa |
| Profil (konto, LLM Connect, znajomi, usuń) | ✅ działa |
| Kreator postaci 4-kroki (animacje kostki/skilli) | ✅ działa, ⚠️ hard-back gubi draft |
| Hub Kampanie + 5 trybów | ✅ działa |
| Tworzenie kampanii (Nowa/Gotowa/Multiplayer) | ✅ działa |
| **Kolejność hero↔kampania spójna z hero-first** | ❌ podwójna ścieżka kreatora — do naprawy |
| Zabezpieczenia przed zakleszczeniami (lobby/onboarding/mail/loading) | ❌ brak timeoutów/skipów |
| Ochrona przed przypadkowym usunięciem (undo/potwierdzenie) | ❌ swipe-delete bez undo |
| Globalny error boundary | ❌ brak |

### Zadania implementacyjne

| # | Zadanie | Priorytet |
|---|---------|-----------|
| C14 | Hero-first: usunąć kreator z deep-flow kampanii; kreator tylko z ekranu Bohaterowie (fallback gdy brak bohatera) | 1 |
| D8 | Lobby MP: timeout / wskaźnik nieaktywnego hosta / auto-zamknięcie | 1 |
| D9 | Onboarding: przycisk "Pomiń" + auto-advance po timeout | 2 |
| D10 | Loading-states: timeout + błąd + retry (hooks, templates, prebuilt) | 2 |
| C15 | Globalny error boundary: toast + ponów dla loadHeroes/loadCampaigns | 2 |
| C16 | Ochrona usuwania: undo-toast albo twarde potwierdzenie (bohater + kampania) | 2 |
| D11 | Kreator: dialog potwierdzenia przy hard-back | 3 |
| D12 | Weryfikacja maila: limit resendów + link wsparcia | 3 |
| D13 | idle vs aktywny: ujednolicić ścieżkę lub pokazać stan jawnie | 3 |

---

## CZĘŚĆ AE — Audyt Panelu Admina (admin_panel_v3)

> **Sesja:** 2026-06-05 — audyt aktywnego panelu admina.
> **Stan kodu:** Panel działa i jest podłączony do prawdziwego backendu. Architektonicznie kruchy — jeden monolityczny plik.

To jest narzędzie admina (GM) do zarządzania całą grą: treścią, światem, graczami, kampaniami, mechaniką. Aktywna wersja to **admin_panel_v3**, serwowana pod `/admin3/`.

### Stan ogólny

> **Werdykt:** Funkcjonalny i w większości produkcyjnie podłączony, ale architektonicznie kruchy i nosi ślady szybkiego nadrabiania.

**Co jest dobre:**
- Wszystkie ~163 endpointy które panel woła **istnieją w backendzie** (sprawdzone przeciw routerom). Brak zmyślonych tras.
- Wcześniej raportowany dryf nazw pól API (drawer gracza, bank pomysłów) **naprawiony** — `new_password`, `uses_remaining`, `quality_rating` itd. zgodne z backendem.
- Centralna warstwa API (`apiFetch`) — Bearer token, obsługa 401, parsowanie błędów. Spójna.
- Lazy-loading sekcji z guardami, działa.

**Co jest kruche:**
- **Jeden plik 18 954 linii / 1.06 MB**, 539 funkcji, zero modularności. HTML + CSS + JS inline. Każda zmiana = nawigacja po monolicie.
- **Osierocona sekcja** `section-knowledge` — renderowana, ale bez przycisku nav i poza dispatch'em `_load()`. Nieosiągalna, duplikuje żywą zakładkę Narzędzia→Wiedza.
- **~700 linii zduplikowanego kodu** — 4 prawie identyczne funkcje modala obrazków (enemy/npc/item/location), różnią się tylko kluczem encji.
- **Mock dane wbudowane w wysyłany HTML** — dziesiątki sztywnych wierszy demo (broń, wrogowie, kampanie). Podmieniane przy `_load*`, ale **migają jako fałszywe dane** i ryzyko: jeśli loader cicho padnie, zostają na ekranie jako prawdziwe.
- **Loadery przy błędzie tylko `console.warn`** — brak komunikatu dla admina, zostaje przestarzały/pusty UI.
- **Reszta dryfu kontraktu** — defensywne `x ?? y ?? z` zgadywanie nazw pól (np. `dg.active_runs ?? active_runs_count ?? runs_active`, sandbox `hp_current` którego backend nigdy nie zwraca). Działa, ale to niezweryfikowane kontrakty — mogą pęknąć przy zmianie odpowiedzi backendu bez żadnego testu który to złapie.
- 2× natywny `alert()` w handlerach push (reszta używa toastów).

### Sekcje panelu (14 nawigowalnych)

| Sekcja | Zarządza |
|---|---|
| Przegląd (overview) | Statystyki + feed tur/audytu + 6 pod-zakładek analityki |
| Gracze | Konta, drawer gracza (LLM, hasło, wskrzeszenia, aktywność) |
| Kampanie | Lista live + modal 5 zakładek (przegląd/plan/tury/mapa/warsztat) |
| Zawartość | Broń / zbroje / przedmioty / konsumpcja / zaklęcia |
| Bestiariusz (world) | NPC / wrogowie / tabele łupów / pending review |
| Mapa | Builder hex / generacja świata / lokacje / teren / review |
| Mechaniki | Staty / skille / DC / warunki / archetypy |
| Lochy | Lochy / zagadki / kafelki / kategorie kafelków |
| Kuźnia (forge) | AI agent / haki / szablony / encountery — projektant kampanii (największa, ~3260 linii) |
| Zaproszenia | Generacja, email, drzewo genealogii zaproszeń |
| Zgłoszenia | Bug reporty testerów + sync GitHub |
| Push | Subskrypcje web-push, test |
| Narzędzia | Test runner / combat sandbox / rest sandbox / wiedza / MCP / obrazki |
| System | 12 pod-zakładek: LLM / baza / config / komendy / wskrzeszenia / email / visual / teksty / głos / narracja / tryby gry / imagegen |

### Powiązanie: zastąpienie admin2 → admin3

Patrz **PROCEDURA A1 → Migracja admin2 → admin3** (kroki A6..A4). Audyt parzystości (A6) musi potwierdzić że admin3 pokrywa wszystkie sekcje admin2 przed usunięciem. Wstępne porównanie: admin3 pokrywa sekcje admin2 (dashboard→overview, narrator→system/narracja, analytics→overview/analityka, sandbox→narzędzia, voice→system/głos). **Do zweryfikowania ręcznie:** czy "Bank pomysłów" (workshops z admin2) ma odpowiednik w admin3 (prawdopodobnie pod Kuźnią).

### Strategia przebudowy: modularny strangler-fig

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Panel admina przebudowujemy metodą **strangler-fig**: budujemy nową, cienką, modularną skorupę i przenosimy do niej sekcje **jedna po drugiej**, równolegle z fazami przebudowy backendu. admin3 żyje jako tymczasowy fallback dla jeszcze-nieprzeniesionych sekcji. Wizualnie dziedziczymy wygląd admin3; architektonicznie budujemy moduły.

> **Dlaczego ta metoda, a nie naprawa monolitu w miejscu?**
> Modularności nie da się osiągnąć łatając monolit — wyciągnięcie 14 sekcji i bibliotek z jednego pliku 18.9k linii to i tak rewrite, tylko trudniejszy (wszystko splątane). Dodatkowo backend redesign i tak unieważni połowę sekcji: unifikacja 3 tabel przedmiotów w jedną, `effect_json` → Effects Builder, afiksy (nowa sekcja), World State viewer, skille bez `trigger_keywords`. Te sekcje przepisujemy niezależnie. Łatanie w miejscu zostawia smrody (mock-dane, ciche błędy, zgadywane kontrakty) chyba że każdy wytropisz osobno.

> **Co odrzucono i dlaczego?**
> - **Naprawa admin3 w miejscu** — mniej ruchu na starcie, ale modularność trudna, smrody zostają. Odrzucone.
> - **Pełny rewrite naraz** — najczystszy wynik, ale blokuje obsługę admina w przerwie, brak testu przyrostowego, najwyższe ryzyko. Odrzucone.

> **Co się zepsuje, jeśli złamać tę strategię?**
> Bez twardej zasady "sekcja w jednym miejscu" (niżej) powstanie czwarty grób — nowy panel obok admin3 obok admin2, wszystkie półfunkcjonalne. To dokładnie ten antywzorzec, który teraz sprzątamy (A1).

**Co przenosimy z admin3 (nie wyrzucamy):**

| Element | Dlaczego zachować |
|---|---|
| Wygląd / CSS / język wizualny | Podoba się, działa — skorupa dziedziczy zmienne CSS |
| Warstwa `apiFetch` (auth/401/błędy) | Spójna — przenosimy jako shared util |
| `_ROW_REGISTRY` (generyczne tabele) | Audyt: dobra abstrakcja — rdzeń biblioteki tabel |
| Mapa 163 zweryfikowanych endpointów | Lista co wołać — bezcenna przy porcie |

**Architektura nowej skorupy:**

```
admin/
  index.html         ← cienka skorupa: nav + mount point (~200 linii)
  shared/
    api.js              ← apiFetch (z admin3)
    table.js            ← _ROW_REGISTRY (z admin3)
    form.js             ← form-from-schema
    effects_builder.js  ← NOWE (CZĘŚĆ X — Effect Objects)
    affix_builder.js    ← NOWE (CZĘŚĆ X — Afiksy)
    toast.js, modal.js
  sections/
    content.js          ← export async init(panel)
    world.js
    players.js
    ...                 ← jedna sekcja = jeden plik
```

Edycja jednej funkcji = otwierasz jeden mały plik, nie monolit. To jest cel modularności.

**Workflow przenoszenia (per sekcja):**

```
1. Implementacja modułu sekcji w nowej skorupie
2. Precyzyjny checklist akceptacji dla właściciela
     (np. "/admin/#content → Broń → dodaj broń z afiksem ognia →
      sprawdź zapis + tabelę + edycję inline")
3. Właściciel weryfikuje w przeglądarce na DEV
4. Po OK: przepięcie trasy sekcji → USUNIĘCIE wersji z admin3
5. GitHub issue (konwencja: enhancement + needs-testing)
```

> **Kluczowe: kolejność portu napędza plan backendu.** Sekcję budujemy wtedy, gdy robimy jej system. Faza 0 (World State) → moduł World State viewer. Faza 4 (Effects/Afiksy) → moduł content + Affix/Effects builder. Sekcje bez zmian backendu (players, invites, push) → port mechaniczny na końcu. Admin to nie osobna faza — każda faza backendu zawiera swój moduł admina.

> **🔒 Twarda zasada anty-grób:** Sekcja istnieje w DOKŁADNIE JEDNYM miejscu naraz. Po porcie i akceptacji kopia w admin3 jest usuwana NATYCHMIAST (nie "na wszelki wypadek"). Migracja skończona, gdy admin3 ma zero sekcji → kasujemy admin3 całe. To różnica między strangler-fig a czwartym grobem.

### Status implementacji (CZĘŚĆ AE)

| Element | Status |
|---------|--------|
| Wszystkie endpointy istnieją w backendzie | ✅ zweryfikowane |
| Dryf nazw pól (gracze, bank pomysłów) | ✅ naprawiony |
| Warstwa API + auth + błędy | ✅ spójna |
| 14 sekcji podłączonych | ✅ działa |
| Osierocona sekcja `knowledge` | ⚠️ nieosiągalna, duplikat — usunąć |
| Zduplikowane modale obrazków (~700 linii) | ⚠️ kandydat do de-dup |
| Mock dane w wysyłanym HTML | ⚠️ ryzyko fałszywych wierszy przy cichym błędzie loadera |
| Loadery bez komunikatu błędu (tylko warn) | ⚠️ stały/pusty UI bez sygnału |
| Reszta `?? ?? ` zgadywania pól (dungeons, sandbox) | ⚠️ niezweryfikowane kontrakty |
| Modularność (1 plik 18.9k linii) | 🔄 w toku — FADM-P0 (#402, 2026-06-08): skorupa `admin/` + shared utils żyją pod `/admin/`, sekcje portowane jedna po drugiej (monolit kurczy się do FADM-DONE) |

### Zadania implementacyjne

**Budowa skorupy (raz, na starcie):**

| # | Zadanie | Priorytet |
|---|---------|-----------|
| A10 | ✅ 2026-06-08 (#402) — Cienka skorupa `admin/index.html` + nav (14 sekcji) + hash-router + mount point, dziedzicząca CSS/wygląd admin3 | 1 |
| A11 | ✅ 2026-06-08 (#402) — Shared utils: `api.js` (apiFetch + APIError), `table.js` (esc + renderTable), `toast.js`, `modal.js`, `form.js` — wyciągnięte z admin3 | 1 |
| F3 | `effects_builder.js` + `affix_builder.js` — nowe komponenty (CZĘŚĆ X) | wraz z Fazą 4 |

**Port sekcji (każda wraz z fazą jej systemu backendowego):**

| # | Zadanie | Priorytet |
|---|---------|-----------|
| FADM-P1 | Port każdej sekcji do modułu + checklist akceptacji + przepięcie trasy + usunięcie kopii z admin3 | per faza |
| FADM-P2 | Przy porcie naprawiać znalezione smrody: brak mock-danych w HTML, błąd loadera widoczny dla admina, przypięte kontrakty (nie `?? ?? `), de-dup modali obrazków, toasty zamiast `alert()` | per sekcja |
| FADM-P3 | Pominąć osieroconą `section-knowledge` (nie portować — usunąć, duplikat Narzędzia→Wiedza) | per faza |
| FADM-DONE | Gdy admin3 ma zero sekcji → `rm -rf admin_panel_v3/`, trasa `/admin/` jako jedyna | ostatnie |
| A6..A4 | Migracja/usunięcie admin2 — patrz A1 (niezależne, równoległe) | 1 |

> **Nota:** dawne FADM-1..6 (knowledge, kontrakty, mock-dane, loadery, de-dup, alert) NIE są osobnymi taskami na admin3 — są wchłonięte do FADM-P2/P3 i naprawiane przy okazji portu danej sekcji. Nie łatamy monolitu, który i tak znika.

### Realignment 2026-06-08 — start faktycznej przebudowy

> **Decyzja (2026-06-08):** Praca nad sekcją D **wstrzymana**. Audyt wykazał że `admin_panel_v3/index.html` to nadal **monolit 19 447 linii / 1 MB / 14 sekcji inline**, a A10/A11 ("wydzielone utils") **nie istnieją jako pliki**. `frontend/admin/` nie istnieje. Zaczynamy faktyczny strangler-fig wg tego planu.

> **Dlaczego teraz?** Każdy D-feature (D5/D6/D7) dorzucany do monolitu zwiększa dług portu. Im później start, tym większy port przy FADM-DONE. Wyrównujemy zanim sekcja D urośnie dalej.

Plan rozbity na konkretne issues (epic [#401](https://github.com/szmidtpiotr/ai-gm/issues/401)):

| Etap | Issue | Sekcja / zakres |
|---|---|---|
| FADM-P0 | #402 | Bootstrap skorupy `admin/` + shared utils (api/table/toast/modal/form) |
| FADM-P1 | #403 | overview ✅ 2026-06-08 (port 1:1 + components.css współdzielony; usunięte z monolitu) |
| FADM-P2 | #404 | mechanics ✅ 2026-06-08 (port 1:1; mechPatchEdit shared → pozostał w monolicie; usunięte z monolitu) |
| FADM-P3 | #405 | content (+ D5 item VIEW) ✅ 2026-06-08 (6 tabów; D5 item VIEW modal; Smart Entry port; loot tab wyeksponowany; usunięte z monolitu) |
| FADM-P4 | #406 | world (+ D7 encountery) ✅ 2026-06-08 (4 taby: NPC/Wrogowie/Łupy/Oczekujące; openLootEntriesModal port; image modals; usunięte z monolitu) |
| FADM-P5 | #407 | map ✅ 2026-06-08 (5 tabów: budowniczy SVG/generuj/lokacje/teren/oczekujące; world builder + submapy + obrazy lokacji; −1758 z monolitu) |
| FADM-P6 | #408 | campaigns ✅ 2026-06-08 (8-tabowy modal: overview/plan/turns/map/npcs/workshop/world/inspector; tabela+karty toggle; admin komendy; Warsztat; −958 z monolitu) |
| FADM-P7 | #409 | dungeons ✅ 2026-06-08 (4 taby: lochy/zagadki/kafelki/kategorie; tile grid + image studio; stab-bar wiring; −1773 z monolitu) |
| FADM-P8 | #410 | forge (+ D7 hook_type) |
| FADM-P9 | #411 | players |
| FADM-P10 | #412 | tools (sandbox/Playwright/Inspector) |
| FADM-P11 | #413 | system (LLM presety + config) |
| FADM-P12 | #414 | misc (invites/push/bugreports) |
| FADM-DONE | — | `rm -rf admin_panel_v3/` — po Fazie 4 |

Brief wykonawczy agenta: `docs/V2_ARCHITECTURE/10_ADMIN_REBUILD_STRANGLER.md`.

---

## CZĘŚĆ AF — Złoto i Ekonomia

> **Sesja:** 2026-06-05 — audyt kodu ekonomii + projekt zdrowej pętli.
> **Stan kodu:** Mechanika przepływu złota działa (portfel, audit log, sklep). Ale ekonomia to jednokierunkowy kran — złoto tylko rośnie. Ta sekcja projektuje sinki.

Złoto to jedyna waluta w grze. Gracz gromadzi je zabijając wrogów, sprzedając łupy i dostając nagrody. Problem: nie ma na co go wydawać w sposób który realnie je zużywa.

### Diagnoza: jednokierunkowy kran

> Audyt kodu (2026-06-05) potwierdził: 3+ źródła złota, 1 sink (i ten domyślnie wyłączony).

```
FAUCETY (wpływ):                    SINKI (odpływ):
  • loot z walki (random/wróg)        • sklep kup (value_gp)
  • sprzedaż w sklepie (50%×CHA)      • wynajem (10%/turę)
  • starter gold                      • wskrzeszenie (opcjonalne, DOMYŚLNIE OFF)
  • [GRANT_GOLD:X]
```

**Skutek:** długa kampania + tani wrogowie = farma złota bez końca. Złoto traci wartość, nagrody przestają cieszyć, sklep staje się nieistotny (stać cię na wszystko).

> **Co działa dobrze (zachowujemy):** `gold_gp` to jedno źródło prawdy (legacy `gold` martwe). Każda zmiana złota jest journalowana w `character_gold_log` z powodem — admin widzi każdą transakcję. To dobry fundament.

### Decyzja: ekonomia czterech sinków (pętla ARPG)

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Wprowadzamy cztery uzupełniające się odpływy złota: (1) crafting/upgrade afiksów — główny, (2) ekonomia konsumpcji, (3) wskrzeszenie ON + naprawy, (4) pasywne dreny + napady. Razem tworzą zdrową pętlę grindu.

> **Dlaczego cztery, a nie jeden?**
> Pojedynczy sink (np. tylko napady) albo nie wystarcza, albo frustruje. Cztery różne kanały dają graczowi wybór JAK wydaje złoto: jedne są pożądane (kupuję moc przez afiksy), inne to koszt życia (nocleg, naprawa), inne to ryzyko (napad). Łącznie złoto realnie krąży, a gracz nie czuje się tylko karany. Wzorzec ARPG (Diablo/PoE): grinduj → złoto+itemy → pompuj złoto w moc → trudniejszy content → więcej złota.

> **Co odrzucono i dlaczego?**
> - **Brak sinków / tylko audit log** (obecny stan + game_flow Decyzja 4) — najprostsze, ale ekonomia puchnie bez końca. Odrzucone.
> - **Tylko napady (#334) jako jedyny sink** — anti-hoarding, ale utrata zarobionego złota jako jedyny mechanizm jest karząca i frustrująca. Odrzucone jako jedyny, zachowane jako jeden z czterech.

> **Co się zepsuje, jeśli odwrócić tę decyzję?**
> Bez sinków grind traci sens — po kilku godzinach gracz ma więcej złota niż kiedykolwiek wyda, sklep i nagrody stają się dekoracją, a cały system łupów (afiksy, loot tables) przestaje motywować.

**Zdrowa pętla:**

```
grind loch / walka → złoto + przedmioty
   ├─→ crafting afiksów (GŁÓWNY sink) → mocniejszy sprzęt → trudniejszy content
   ├─→ konsumpcja (mikstury na groźne walki)
   └─→ koszty: wskrzeszenie (śmierć) · naprawy (użycie) · dreny (życie) · napady (ryzyko)
            ↑ to wszystko zżera nadmiar złota z grindu
```

### Sink 1 — Crafting / upgrade afiksów (główny)

> Najważniejszy odpływ, bo gracz wydaje CHĘTNIE — kupuje moc, nie płaci kary.

- NPC rzemieślnik (płatnerz / enchanter) z flagą `is_crafter=1` (analogicznie do `is_shop`).
- Dwie operacje na posiadanym egzemplarzu:
  - **Nałóż afiks** — dodaj losowy afiks z puli pasującej do typu/tieru na wolny slot. Koszt = f(tier).
  - **Reroll afiksu** — wymień istniejący afiks na inny losowy z puli. Koszt wyższy niż nałożenie.
- Koszt skaluje z tierem afiksu (wartość startowa, do playtestu): np. `base × tier²` — tier 1 tani, tier 5 drogi.
- Zużywa złoto z grindu, domyka pętlę z systemem afiksów (CZĘŚĆ X).

> **Dlaczego losowy afiks, nie wybór?** Losowość napędza powtarzalny grind złota (reroll aż trafisz dobry afiks) — to silnik sinka. Wybór afiksu zabiłby powtarzalność.

### Sink 2 — Ekonomia konsumpcji

- Mikstury (HP/mana), zwoje, bomby — zużywane w walce, odkupowane w sklepie. Katalog konsumpcji już istnieje.
- Warunek działania: walki muszą być na tyle groźne, by mikstury były realnie potrzebne (inaczej nikt nie kupuje). Wiąże się z balansem walki + limitem darmowego leczenia (krótki odpoczynek już ograniczony do 2×).
- Powtarzalny dren proporcjonalny do trudności gry.

### Sink 3 — Wskrzeszenie ON + naprawy (trwałość)

- **Wskrzeszenie:** włączyć (`resurrection_config.enabled=true`), tryb `gold_percent` np. 25% złota. Już zbudowane (`resurrection_service`), wystarczy konfiguracja. Podatek od śmierci.
- **Naprawy / trwałość (NOWA mechanika):** broń i zbroja mają `durability` spadające z użyciem; przy 0 tracą bonusy do czasu naprawy. Płatnerz naprawia za złoto = f(wartość, brakująca trwałość). Wymaga nowej kolumny `durability` na egzemplarzu (`character_inventory`).

> **Uwaga balansowa:** trwałość bywa karząca. Wartości startowe łagodne (powolny spadek, tania naprawa) — do dostrojenia. Może być wyłączalna z admina jak wskrzeszenie.

### Sink 4 — Pasywne dreny + napady (#334)

- **`[SPEND_GOLD:X]`** — narracyjne wydatki (nocleg, cło, czynsz, trening, łapówka). Symetryczny do `[GRANT_GOLD]`, dziś brakuje.
- **Kwotę ustala MECHANIKA, nie LLM z głowy.** Zgodnie z zasadą "mechanika decyduje, LLM narruje": nocleg = stała z configu lokacji, cło = % złota, łapówka = skalowana do DC przekupstwa. LLM emituje intencję wydatku, kod podstawia kwotę z tabeli. Inaczej LLM zażąda 5 albo 500 GP za to samo.
- **Napady (#334):** encounter typu "bandyci" może ukraść % złota przy porażce lub zaskoczeniu. Naturalny odpływ + napięcie. Anti-hoarding bez sztucznych limitów.

### Rozjazdy design ↔ kod (do naprawy)

| Co | Design (game_flow) | Kod naprawdę | Akcja |
|---|---|---|---|
| Asortyment sklepu | dynamiczny (lokacja+poziom) z zatwierdzonych kluczy | sztywny `shop_inventory_json`, brak restocku | zbudować dynamiczny dobór |
| CHA na cenę | kup i sprzedaż | tylko sprzedaż | dodać CHA do kupna |
| Cena przedmiotu | jedno pole | `value_gp` (broń/item) vs `base_price` (konsumpcja) | unifikacja → jeden `price_gp` (z CZĘŚCIĄ X) |
| Wycena egzemplarza | — | baza nie liczy afiksów | sprzedaż/koszt egzemplarza = baza + wartość afiksów |
| Limit farmy | — | brak — nieskończona sprzedaż łupów | malejąca cena przy spam-sprzedaży / limit |
| Wynajem wygasa | przy terminie | leniwie, tylko przy wejściu do sklepu | background expire (jak G1 sweep) |
| Martwy kod | — | `generate_combat_loot/claim_loot` (używa `sheet["gold"]`) | usunąć |

### Status implementacji (CZĘŚĆ AF)

| Element | Status |
|---------|--------|
| `gold_gp` jedno źródło + audit log `character_gold_log` | ✅ działa |
| Loot z walki / starter gold / `[GRANT_GOLD]` | ✅ działa |
| Sklep kup/sprzedaż/wynajem/trade-in | ✅ działa |
| CHA na sprzedaż | ✅ działa |
| Wskrzeszenie jako sink | ⚠️ zbudowane, ale domyślnie OFF — włączyć+skonfigurować |
| **Sink 1: crafting/upgrade afiksów** | ❌ do zbudowania (zależy od afiksów, CZĘŚĆ X) |
| **Sink 2: ekonomia konsumpcji (realnie potrzebna)** | ⚠️ katalog jest, brak presji popytu (balans walki) |
| **Sink 3: trwałość + naprawy** | ❌ nowa mechanika + kolumna `durability` |
| **Sink 4: `[SPEND_GOLD]` + napady** | ❌ tag i napady do zbudowania |
| Asortyment dynamiczny sklepu | ❌ sztywny |
| CHA na kupno | ❌ brak |
| Unifikacja `value_gp`/`base_price` | ❌ rozjazd (z CZĘŚCIĄ X) |
| Anti-farm sprzedaży | ❌ brak |
| Usunięcie martwego loot kodu | ❌ do zrobienia |

### Zadania implementacyjne

| # | Zadanie | Zależy od |
|---|---------|-----------|
| F4 | `[SPEND_GOLD:X]` tag — kwota z tabeli/configu, nie z LLM | — |
| F5 | Włączyć + skonfigurować wskrzeszenie jako sink (gold_percent) | — |
| F6 | Sink afiksów: NPC `is_crafter`, nałóż/reroll afiks. Koszty (skalibrowane do ~70-80g/sesja): T1=150g, T2=500g, T3=1200g dodanie; T1→T2=350g, T2→T3=700g upgrade. | afiksy (CZĘŚĆ X) |
| F7 | Trwałość: punktowa (np. broń 200pkt), spada per uderzenie OTRZYMANE. Przy 0pkt: penalty bonusu (domyślnie -50%, konfigurowalne w admin). Naprawa: `tier_rate × brakujące_pkt` (T1=20g/pkt, T2=50g/pkt, T3=100g/pkt). Kolumny `durability_current`/`durability_max` w `character_inventory`, NULL dla consumables. | egzemplarze |
| F8 | Napady (#334): encounter kradnący % złota przy porażce/zaskoczeniu | encountery |
| F9 | Dynamiczny asortyment sklepu (lokacja+poziom, z zatwierdzonych kluczy) | — |
| F10 | CHA na kupno (nie tylko sprzedaż) | — |
| F11 | Unifikacja ceny → jeden `price_gp` + wycena egzemplarza z afiksami | unifikacja przedmiotów (CZĘŚĆ X) |
| F12 | Anti-farm: malejąca cena przy spam-sprzedaży tego samego typu | — |
| F13 | Background expire wynajmu (sweep, jak G1) | — |
| F14 | Usunąć martwy `generate_combat_loot`/`claim_loot` z economy_service | — |
| F15 | Ekonomia konsumpcji: balans walki tak, by mikstury były potrzebne | balans walki |
| F16 | Balans całości (ceny, dropy, koszty sinków) — playtest | wszystko wyżej |

---

## CZĘŚĆ AG — Infrastruktura i rozmieszczenie obciążeń

> **Sesja:** 2026-06-05 — informacja od właściciela o dostępnym sprzęcie.
> **Po co tu:** Decyduje GDZIE uruchamiamy które zadanie. Zła decyzja (np. lokalny LLM w multiplayer) zabije wydajność.

### Mapa infrastruktury

| Element | Gdzie | IP | Rola |
|---|---|---|---|
| Gra (backend + frontend) | LXC w Proxmox | — | Główny serwer aplikacji |
| Routing domeny | Nginx Proxy Manager | 192.168.1.4 | `studio-colorbox.com` → LXC, terminacja certów |
| **Desktop / GPU offline** | Desktop Piotra | **192.168.1.170** | RTX 3060 12GB + 64GB DDR5 + Ryzen 7700 — generowanie obrazków, Ollama, zadania offline |
| **Voice host** | Dedykowana maszyna | **192.168.1.16** | GTX 1660 — Piper TTS + Whisper STT. Kernel pinned -23. |
| Whisper STT | .16 | 192.168.1.16 | Rozpoznawanie mowy — działa sprawnie, zostaje |
| H2 | planowany na .16 | 192.168.1.16 | Text-to-speech, zasobożerny — per-gracz opt-in TYLKO |

> **FINF-1 ZAMKNIĘTE (2026-06-05):** RTX 3060 = 192.168.1.170 (desktop Piotra), GTX 1660 = 192.168.1.16 (voice host).

### Zasada rozmieszczenia obciążeń

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Maszyna GPU (RTX 3060) służy do zadań OFFLINE / asynchronicznych, gdzie czas wykonania nie jest krytyczny. Live'owy LLM rozgrywki — zwłaszcza multiplayer — NIGDY nie idzie na lokalny GPU; zostaje na szybkim dostawcy (cloud/OpenAI-compatible).

> **Dlaczego?**
> RTX 3060 12GB jest za wolna dla narracji na żywo przy 2-4 graczach — runda multiplayer czekałaby zbyt długo na generację. Ale przy generowaniu treści w tle (uzupełnianie danych, obrazki, opisy kafelków) czas użycia "nie stanowi problemu" — może mielić ile chce. Rozdzielamy więc dwa profile: szybki online (rozgrywka) vs wolny offline (tworzenie).

> **Co się zepsuje, jeśli złamać tę zasadę?**
> Podpięcie lokalnego LLM pod live multiplayer = rundy trwające minuty na samej generacji, gra nie do grania. Stąd twarda granica.

### Co gdzie

| Zadanie | Gdzie | Dlaczego |
|---|---|---|
| Narracja rozgrywki solo | szybki dostawca (cloud) | gracz czeka na turę na żywo |
| **Narracja multiplayer** | szybki dostawca (cloud) — **NIGDY lokalny GPU** | 2-4 graczy czeka na jedną rundę, lokalny za wolny |
| Generowanie obrazków (kafelki lochów, portrety wrogów, art przedmiotów) | maszyna GPU | offline, czas nieistotny |
| LLM Vision: obrazek → opis kafelka (CZĘŚĆ AA, E19) | maszyna GPU (Ollama vision) | proces tworzenia kafelków, async |
| Masowe uzupełnianie danych / AI Kreator w adminie | maszyna GPU (Ollama) | tworzenie treści, czas użycia nieistotny |
| Whisper STT (mowa→tekst) | obecny setup | działa sprawnie |
| H2 (tekst→mowa) | maszyna GPU, **opt-in per pojedynczy gracz** | zasobożerny — nie globalnie, włączany na życzenie jednego gracza |

### Implikacje dla udokumentowanych systemów

- **Multiplayer (CZĘŚĆ AC):** potwierdza wybór szybkiego dostawcy dla `trigger_narration`. Lokalny GPU wykluczony.
- **Lochy — kafelki (CZĘŚĆ AA):** workflow obrazek→opis (E19) i generowanie obrazków kafelków idą na maszynę GPU offline. Idealne dopasowanie — to praca tworzenia, nie rozgrywki.
- **Afiksy / content (CZĘŚĆ X):** masowe generowanie wpisów (afiksy, przedmioty, wrogowie) może iść na lokalny Ollama w trybie tworzenia — taniej niż cloud, czas nieistotny.
- **Głos:** Whisper STT zostaje; H2 jako opcja per-gracz, nie domyślnie włączona globalnie (ochrona zasobów GPU).

### Status / zadania

| # | Zadanie | Priorytet |
|---|---------|-----------|
| FINF-1 | Potwierdzić host/IP maszyny GPU (RTX 3060) — czy to .170/.16 czy osobny | — |
| H3 | Pipeline generowania obrazków na GPU (kafelki, portrety) — endpoint/kolejka offline | wraz z lochami |
| H4 | Lokalny Ollama dla masowego uzupełniania treści w adminie (tryb tworzenia) | wraz z content |
| H5 | H2 jako opcja per-gracz (toggle), nie globalna | wraz z głosem |

---

## CZĘŚĆ 10b — Observability i Monitoring

> **Status (2026-06-05):** ODŁOŻONE — projektujemy dopiero gdy World State działa i gra jest w produkcyjnym deploymencie. Pierwsza faza: tylko to co już stoi (Grafana/Loki na PROD). Wracamy po Fazie 0 + prod deployment.

> **Zasada projektowa (zatwierdzona 2026-06-05):**
> Priorytetem jest World State i rdzeń gry. Observability dobudowujemy per potrzeba po produkcyjnym wdrożeniu.

### Kluczowa obserwacja

World State history per tura (zadanie B1/B5) sprawia że większość stanu gry jest **już zapisana w bazie** bez potrzeby zewnętrznych narzędzi (Grafana/Loki). Snapshot World State na każdą turę = de facto audit log co się działo.

### Co World State history daje "za darmo"

- Stan sceny w każdej chwili (kto był, co się wydarzyło)
- Historia ruchów gracza po mapie
- Historia questów (kiedy aktywne, kiedy ukończone)
- Historia walki (przez `combat_turns`)
- Historia złota (przez `character_gold_log`)
- Historia XP (przez `character_xp_grants`)

### Co jeszcze potrzebuje logowania (do analizy)

Poniższe tematy do omówienia w dedykowanej sesji projektowej:

| Obszar | Pytanie |
|--------|---------|
| Wydajność LLM | Czas odpowiedzi per tura, czas per call, provider |
| Błędy i wyjątki | Co logować, gdzie przechowywać, jak alarmować |
| Aktywność graczy | Kiedy grają, jak długo, gdzie odchodzą |
| Admin queue | Czas oczekiwania pending rekordów, throughput admin review |
| Halucynacje LLM | Jak wykryć i zalogować gdy LLM emituje niepoprawny tag |
| Kampanie | Dropout rate (kiedy gracze porzucają kampanię), średnia długość |

### Decyzja architektoniczna (2026-06-05)

Własna implementacja observability w backendzie zamiast Grafana/Loki stack. World State history jest głównym źródłem danych. Dodatkowe metryki jako tabele w SQLite lub lekki log writer w backendzie.

**Zadanie do dodania:**
- **H1: Projekt systemu monitoringu** — analiza co logować, projekt schematu, implementacja lekkiego log writera w backendzie

---

## CZĘŚĆ 10 — Zasady które rządzą redesignem

Na koniec — 5 zasad które powinny kierować każdą decyzją przy implementacji:

### Zasada 1: Mechanika decyduje, LLM narruje
Żadna akcja mechaniczna (walka, ruch, quest, wydanie XP) nie może zależeć wyłącznie od intencji LLM. LLM opisuje wynik — mechanika go realizuje.

### Zasada 2: World State jest jedyną prawdą
Jeśli czegoś nie ma w World State, dla mechaniki nie istnieje. LLM może "opisać" coś czego nie ma — mechanika tego nie wykona.

### Zasada 3: Gracz zawsze wie co może zrobić
Gracz nie powinien zgadywać. HUD, opisy, podpowiedzi — gra mówi co jest możliwe.

### Zasada 4: Progresja musi być namacalna dla każdego gracza
Po każdej sesji gracz powinien móc wskazać co urosło w jego postaci. Nie "może wydaję XP", a "wydałem 75 XP i mam Atletykę R2".

### Zasada 5: Admin-asynchroniczny, nie Admin-nieobecny
Admin zatwierdza kiedy może, nie kiedy musi. System nie powinien czekać na admina żeby działać — ale świat rośnie dzięki adminowi.

---

---

## WYKONANE

> Sekcje przeniesione tutaj po ukończeniu implementacji. Kolejność taka sama jak w oryginalnym planie.

---

### FAZA -1 — Procedury wstępne ✅ UKOŃCZONA (2026-06-05)

Wszystko poniżej musi być gotowe przed startem Fazy 0.

| Kod | Zadanie | Zależy od |
|---|---|---|
| A1 | Dead code cleanup (~1.9GB) — usunięcie nieużywanych zasobów | — |
| A2 | Audyt schematu DB — lista tabel do migracji/usunięcia | — |
| A3 | PROD restoration na .62 + freeze starego kodu (tag v1.0-legacy) | A1 |
| A4 | Version tagging (git tag) | A3 |
| A5 | Maintenance notification workflow (banner dla graczy podczas deployów) | A3 |
| A6 | Parity check admin2 vs admin3 (czy admin3 pokrywa wszystkie sekcje admin2) | — |
| A7 | Redirect /admin → /admin3 | A6 |
| A8 | Usunięcie admin2 z serwera | A7 |
| A9 | Usunięcie `frontend/admin_panel_v2/` z repo | A8 |
| FINF-1 | ~~Potwierdzenie IP hosta GPU~~ ✅ ZAMKNIĘTE — RTX3060=.170, GTX1660=.16 | — |
| A10 | Nowa skorupa admin panelu (thin shell + nav) | — |
| A11 | Shared utilities admin (api.js, toast.js, modal.js, table.js) | A10 |
| A12 | Game config seed — `data/game_config_seed.sql` w git; skrypty export/import | A3 |

#### Notatki implementacyjne

**A1** — Usunięto ~1.9 GB martwego kodu: `actions-runner/` (887 MB), `voice-service/` (708 MB), `observability/` (~266 MB), `output/`, `temp-img/`, `combat_v2_service.py`. Usunięto `frontend/admin_panel_v2/` po weryfikacji parzystości z admin3 (A6–A9). Zaktualizowano `.gitignore` o `data/`, `backups/`, `__pycache__/`, `*.pyc`, `.venv/`.

**A2** — Przeprowadzono audyt schematu bazy danych: przegląd tabel `game_config_*`, `campaigns`, `characters`, `users`, `game_sessions`. Zidentyfikowano trzy różne formaty `effect_json` w różnych tabelach (problem opisany w CZĘŚCI X) oraz brakujące kolumny w `game_locations`. Wyniki audytu stały się podstawą migracji dla B1/B2 i projektu ekonomii (CZĘŚĆ AF).

**A3** — PROD przeniesiony na 192.168.1.62, stary deploy na .63 zamrożony tagiem git `v1.0-legacy`. Nginx Proxy Manager (.4) przekierowany: `aigm.studio-colorbox.com` → `.62`. Skrypt `deploy_from_github.sh` stworzony na .62 — kod PROD pochodzi wyłącznie z `git main`, bezpośrednia edycja plików na serwerze prod jest zabroniona.

**A4** — Wprowadzono system tagów git (v1.0.0, v1.1.0, v1.2.0…). Frontend i admin panel wyświetlają numer wersji jako klikalną odznakę w nagłówku. Kliknięcie odznaki otwiera popup z sekcją changelog dla aktualnej wersji.

**A5** — Zdefiniowano i wdrożono workflow deployów z 30-minutowym powiadomieniem przez Telegram przed każdym restartem PROD. Skrypt `deploy_prod.sh` wykonuje `git fetch origin main` + `reset --hard` + rebuild obrazu Docker + healthcheck automatycznie.

**A6–A9** — Audyt parzystości admin2 vs admin3 potwierdził pełne pokrycie wszystkich sekcji. Trasa `/admin2/` przekierowana na `/admin3/`. Katalog `frontend/admin_panel_v2/` usunięty z repozytorium. Dokumentacja (`CLAUDE.md`) zaktualizowana — `admin_panel_v3` jako jedyny aktywny panel.

**A10–A11** — Nowa skorupa `admin_panel_v3` z dynamicznym ładowaniem sekcji przez sidebar nav. Shared utilities: `api.js` (`adminFetch` + `APIError`), `toast.js`, `modal.js`, `table.js`, `smart_entry.js` — każdy moduł sekcji korzysta z tych samych helperów bez duplikacji kodu.

**A12** — Statyczny SQL seed z zatwierdzoną zawartością gry (`game_config_*`) wersjonowany w git jako `data/game_config_seed.sql`. Skrypty `export_seed.sh` / `import_seed.sh` w `scripts/`. Dane graczy (`characters`, `campaigns`, `users`) są w `.gitignore` — prywatne i nie trafiają do repozytorium.

---

### FAZA 0 — World State (fundament danych) ✅ UKOŃCZONA (2026-06-06)

> **Blokuje wszystko dalej.** Nic nie działa mechanicznie poprawnie bez World State.

| Kod | Zadanie | Zależy od |
|---|---|---|
| B1 | Tabela `world_state_snapshots` (campaign_id, turn_number, state_json) | — |
| B2 | Rozbudowa `session_flags`: scene_enemies, scene_npcs, active_quests, player_conditions | B1 |
| B3 | Gate Mechaniki — middleware walidujący akcje gracza PRZED LLM | B2 |
| B4 | Parser intencji gracza (ATTACK/MOVE/TALK/REST → walidacja przez Gate) | B3 |
| B5 | Auto-zapis snapshotu World State po każdej turze narracyjnej | B1 |
| B6 | Admin UI — World State History (zakładka w Campaign Monitor, diff między turami) | B5 |
| B7 | DEV Inspector — panel diagnostyczny dla adminów (intent + gate + world state per kampania) | B5 |

#### Notatki implementacyjne

**B1** — Stworzono tabelę `world_state_snapshots` (kolumny: `id`, `campaign_id`, `turn_number`, `snapshot_json`, `snapshot_source`, `created_at`) z migracją w `migrations_admin.py`. Serwis `world_state_service.py` implementuje `save_snapshot()`, `get_latest_snapshot()`, `build_snapshot()` i `auto_save_snapshot()` jako jeden punkt zapisu stanu sceny.

**B2** — Pięć kolumn live World State dodanych do `game_sessions`: `scene_enemies` (JSON list), `scene_npcs` (JSON list), `scene_cleared` (bool), `active_quests` (JSON list), `player_conditions` (JSON list). Helpery `get_world_state_flags()` i `set_world_state_flags()` w `world_state_service.py` z typowaną serializacją JSON — klucze nieznane są cicho ignorowane.

**B3** — Gate Mechanic w `turns.py` sprawdza intencję gracza (B4) względem World State PRZED wywołaniem LLM. ATTACK blokowany gdy `scene_enemies=[]`, MOVE blokowany gdy hex niedostępny, REST wymaga bezpiecznej lokacji. Blok nie pobiera tury — gracz dostaje komunikat i może zmienić akcję bez utraty kolejki.

**B4** — Parser intencji klasyfikuje tekst gracza na: ATTACK, MOVE, TALK, REST, EXPLORE lub OTHER. Regex-based matching na polskie wyrażenia kluczowe. Wynik parsowania trafia do Gate (B3) jako podstawa decyzji o dopuszczeniu akcji.

**B5** — `auto_save_snapshot()` wywołuje `build_snapshot()` — zbiera aktualny stan z `game_sessions` (enemies, npcs, quests, conditions) + `MAX(turn_number)` z `campaign_turns` — i zapisuje z `source="auto"`. Podpięte do 3 ścieżek w `turns.py`: main streaming DONE, skill_test keyword early exit i skill_test resolve endpoint. Prune do 50 snapshotów per kampania.

**B6** — Zakładka "🌍 Stan Świata" w Campaign Monitor admina wyświetla listę snapshotów z timeline oraz podgląd JSON stanu (wrogowie, NPC, questy, warunki) dla każdego snapshotu. Endpointy `GET /api/admin/campaigns/{id}/world-state` i `/world-state/latest` w `admin.py`; `snapshot_json` automatycznie parsowany z JSON string na dict przy zwrocie.

**B7** — DEV Inspector — panel diagnostyczny w zakładce kampanii, widoczny dla adminów i graczy z `debugMode`. Endpoint `GET /api/admin/dev-inspector/{campaign_id}` zwraca: `last_intent`, `gate_result`, `world_state` flags, `session_flags`, aktualną lokację. Przycisk "🔍" dostępny z player UI dla adminów bez opuszczania ekranu gry.

---

### FAZA 1 — Rdzeń pętli ✅ UKOŃCZONA (C1–C19, 2026-06-06, v1.2.3)

> Podstawowe gameplay działa bezbłędnie. Walka, ruch, progi ran, XP spend, questy, ekonomia złota, hero-first flow — wszystko deterministyczne. Harness testów C1–C19 + panel Playwright w admin3 (v1.2.3).

| Kod | Zadanie | Zależy od |
|---|---|---|
| C1 | Fix Bug 1 — LLM sugeruje ruch po 5 turach bez zmiany lokacji (STORY_STALE) | B3 |
| C2 | Walidacja ruchu mechaniczna (hex, terrain check, World State update) | C1 |
| C3 | Fix Bug 2 — Gate walki: ATTACK blokowany gdy scene_enemies=[] | B3 |
| C4 | Unifikacja wound_penalty: hp_current/hp_max → modifier (utility) | — |
| C5 | Symetria ran: wound_penalty dla wrogów (nie tylko gracza) | C4 |
| C6 | Synchronizacja progów ran frontend/backend przez endpoint | C4 |
| C7 | XP Spend — spend_skill endpoint (wszystkie archetypy, poprawne koszty) | — |
| C8 | XP Spend — spend_stat endpoint (koszty z tabeli, ceiling=19, CON→hp_max) | C7 |
| C9 | UI długiego odpoczynku — modal "Ucz się" (lista zakupów XP) | C7, C8 |
| C10 | System questów — QUEST_SUGGEST tag + walidacja backend | B2 |
| C11 | Mechaniczne śledzenie postępu questów (auto-complete per akcja) | C10 |
| C12 | `[SPEND_GOLD:X]` tag — kwota z tabeli/configu, NIE z LLM | — |
| C13 | Instrukcja "tylko złoto GP" w system_prompt (usunięcie waluty srebrnej) | — |
| C14 | Hero-first fix: startCharacterWizard() tylko z Heroes screen | — |
| C15 | Error boundary dla API failures (toast zamiast białego ekranu) | — |
| C16 | Delete confirmation modals (kampania, postać) | — |
| C17 | Kontekst ekwipunku — injection listy przedmiotów i złota do LLM per tura | — |
| C18 | Fix Bug 3 — kampanie startują na istniejących hexach, nie nowych obrzeżach | C14 |
| C19 | Fix Bug 4 — bohater startuje nową kampanię z pełnym HP (reset hp_current=hp_max) | — |

#### Notatki implementacyjne

**C1** — Po 5 turach gracza w tym samym hexie bez zmiany lokacji, backend wstrzykuje sygnał `STORY_STALE` do kontekstu LLM. LLM otrzymuje instrukcję: zaproponuj ruch, wywołaj nowe wydarzenie lub encounter. Licznik resetuje się przy każdej zmianie hex lub lokacji.

**C1 Follow-up (#391)** — TRAVEL_HINT pills: jeśli gracz jest w STORY_STALE (5+ tur), backend sugeruje kierunki ruchu w formie `[TRAVEL_HINT: [Lokacja1] [Lokacja2] ... — wskaż bohaterowi bezpieczne kierunki]`. Źródło: `discovered_hexes` z session_flags (fallback: query nearby approved game_locations z world_hex_q/r). Max 5 pillsów. LLM wykorzystuje te sugestie do naturalnego zaproponowania kierunku ruchu.

**C2** — Backend sprawdza przed aktualizacją World State czy docelowy hex jest odkryty i czy terrain jest dostępny dla postaci. Poprawna zmiana lokacji aktualizuje `current_hex` i `current_location` w `session_flags`. Ruch do nieznanego hexu blokowany z komunikatem — gracz nie może teleportować się poza mapę.

**C3** — Gate walki blokuje akcję ATTACK gdy `scene_enemies=[]` w World State aktywnej kampanii. Gracz otrzymuje komunikat "Brak celu w scenie" zamiast narracji walki z nieistniejącym wrogiem. Blok nie pobiera tury — gracz może wybrać inną akcję.

**C4** — `wound_penalty_from_hp(current_hp, max_hp)` zwraca modifier od 0 do -4 zależnie od procentu HP: pełnia zdrowia = 0, ranny = -1, ciężko ranny = -2, krytyczny = -3, umierający = -4. Jeden punkt prawdy dla kary za rany, używany przez `combat_service`, `vitality_service` i synchronizowany z frontendem przez endpoint C6.

**C5** — `wound_penalty_from_hp()` stosowany do rzutów ataku wroga gdy jego HP jest niskie. Wróg ranny trafia rzadziej — ta sama formuła i te same progi co dla gracza. Symetria mechaniki eliminuje sytuację gdzie gracz jest karany za rany, a wróg nie.

**C6** — Endpoint `GET /api/mechanics/wound-thresholds` zwraca progi ran (`wounded`, `critical`, `dying`) z backendu. Frontend pobiera progi z API zamiast hardkodować wartości w JS. Jeden punkt prawdy eliminuje rozbieżności między UI a silnikiem walki.

**C7** — `POST /api/characters/{id}/xp/spend-skill` — wydawanie XP na umiejętności: nowa nauka = 100 XP, rank 1→2 = 75 XP, rank 2→3 = 150 XP. Limit `rank_ceiling=3`. Dostępny dla wszystkich archetypów (Wojownik, Łotr, Uczony) — nie tylko Uczonego jak wcześniej.

**C8** — `POST /api/characters/{id}/xp/spend-stat` — wydawanie XP na +1 do statystyki zgodnie z tabelą kosztów z game_mechanics.md (50/100/200/400 XP zależnie od obecnej wartości). Sufit=19 — wartość 20+ niedostępna mechanicznie. Wzrost CON automatycznie przelicza `hp_max` przez formułę `CON_mod × level`.

**C9** — Modal "Ucz się" w długim odpoczynku: lista zakupów XP (umiejętności + statystyki) z kosztami, spina endpointy C7/C8. Gracz wydaje zgromadzone XP podczas odpoczynku.

**C10** — Tag `QUEST_SUGGEST` emitowany przez LLM przechwytywany i walidowany w backendzie; sugerowany quest zapisywany do stanu kampanii (nie hallucynowany w narracji).

**C11** — Postęp questów śledzony mechanicznie: per akcja gracza backend sprawdza warunki ukończenia i auto-completuje kroki questa, niezależnie od narracji LLM.

**C12** — Tag `[SPEND_GOLD:X]` pobiera kwotę z tabeli/configu (NIE z LLM) — eliminuje halucynowane ceny. Złoto odejmowane deterministycznie.

**C13** — System prompt wymusza "tylko złoto GP" — usunięta waluta srebrna, spójna ekonomia jednowalutowa.

**C14** — Hero-first: `startCharacterWizard()` wywoływany tylko z ekranu Heroes, nigdy z `_finalCreateCampaign` — bohater jest niezależnym bytem tworzonym przed kampanią.

**C15** — Error boundary dla błędów API: zamiast białego ekranu pokazuje się toast z komunikatem, gra nie wywala się przy chwilowym błędzie sieci/backendu.

**C16** — Modale potwierdzenia przy usuwaniu kampanii i postaci — chroni przed przypadkową utratą danych.

**C17** — Kontekst ekwipunku: lista posiadanych przedmiotów + złoto wstrzykiwane do LLM przy każdej turze, dzięki czemu narrator wie czym gracz faktycznie dysponuje.

**C18** — Fix Bug 3: nowe kampanie startują na istniejących hexach mapy zamiast generować nowe na obrzeżach — świat jest spójny między kampaniami.

**C19** — Fix Bug 4: bohater rozpoczynający nową kampanię dostaje pełne HP (`hp_current = hp_max`) zamiast ostatniego stanu z poprzedniej rozgrywki.

---

### FAZA 2 — Systemy + Narracja ✅ UKOŃCZONA (D1–D14, 2026-06-08)

> Pending flows, NPC pamięć, auto-screening, narracja, encountery, UI gracza, onboarding — pełna warstwa systemów nad rdzeniem.

| Kod | Zadanie | GitHub |
|---|---|---|
| D1 | Pending flow przedmiotów (GRANT_ITEM nieznanego klucza → auto-screen → pending=true) | [#376](https://github.com/szmidtpiotr/ai-gm/issues/376) |
| D2 | Pending flow wrogów (analogicznie do D1) | [#377](https://github.com/szmidtpiotr/ai-gm/issues/377) |
| D3 | NPC pamięć w World State (NPC_MEMORY tag → context injection) ✅ | [#378](https://github.com/szmidtpiotr/ai-gm/issues/378) |
| D4 | Auto-screening admin queue (tech validation + LLM scoring) | [#379](https://github.com/szmidtpiotr/ai-gm/issues/379) |
| D5 | Item VIEW — podgląd przedmiotu w inventory (tooltip/modal) | [#380](https://github.com/szmidtpiotr/ai-gm/issues/380) |
| D6 | Narracja: tagi, parsery, Narrative State struktura | [#381](https://github.com/szmidtpiotr/ai-gm/issues/381) |
| D7 | Encountery generyczne + gate safe_for_rest + dwell decay + interwał config | [#382](https://github.com/szmidtpiotr/ai-gm/issues/382) |
| D8 | Ekran profilu gracza (konto + edycja email, LLM settings) | [#383](https://github.com/szmidtpiotr/ai-gm/issues/383) |
| D9 | Ekran kampanii — 5 trybów hub + dostępność per dane | [#384](https://github.com/szmidtpiotr/ai-gm/issues/384) |
| D10 | Onboarding animacja + wybór motywu (nowy gracz) | [#385](https://github.com/szmidtpiotr/ai-gm/issues/385) |
| D11 | Confirm password na rejestracji | [#386](https://github.com/szmidtpiotr/ai-gm/issues/386) |
| D12 | Szybka nawigacja Hub → Gra (bez przeładowania) | [#387](https://github.com/szmidtpiotr/ai-gm/issues/387) |
| D13 | Mobile layout — weryfikacja responsywności wszystkich ekranów | [#388](https://github.com/szmidtpiotr/ai-gm/issues/388) |
| D14 | Bugfix: `update_item` nadpisywał approved=0 → approved=1 | [#399](https://github.com/szmidtpiotr/ai-gm/issues/399) |

---

### FAZA 3 — Jakość + Treść ⚠️ CZĘŚCIOWO UKOŃCZONA (E1–E14, 2026-06-09)

> E1–E14 wdrożone. E15–E28 (lochy, onboarding karty, tutorial) — następna iteracja.

| Kod | Zadanie | GitHub |
|---|---|---|
| E1 | Player HUD (HP/Mana, Złoto, Questy, XP bar, Czas) — aktualizacja per tura | [#416](https://github.com/szmidtpiotr/ai-gm/issues/416) |
| E2 | Kreator bohatera — tooltips (archetyp, statystyki, umiejętności z przykładami) | [#417](https://github.com/szmidtpiotr/ai-gm/issues/417) |
| E3 | Ekran zakończenia kampanii (podsumowanie + LLM epitafium) | [#418](https://github.com/szmidtpiotr/ai-gm/issues/418) |
| E4 | Ekran śmierci (epitafium + statystyki + Wskrześ/Nowy bohater) | [#419](https://github.com/szmidtpiotr/ai-gm/issues/419) |
| E5 | Zamknięcie dostępu do kampanii martwego bohatera (hero_status=dead) | [#420](https://github.com/szmidtpiotr/ai-gm/issues/420) |
| E6 | Narracja: kompresja chapter_summary + seeds injection + ARC_ADVANCE automation | [#421](https://github.com/szmidtpiotr/ai-gm/issues/421) |
| E7 | Rozbudowa `campaign_templates` (required_npc_keys, required_beats, player_visible) | [#422](https://github.com/szmidtpiotr/ai-gm/issues/422) |
| E8 | Ekran wyboru gotowej kampanii dla gracza (karty, trudność, opisy) | [#423](https://github.com/szmidtpiotr/ai-gm/issues/423) |
| E9 | Story Gravity: escalation przez N tur bez wymaganego beatu (5/10/15, L3 domyślnie OFF) | [#424](https://github.com/szmidtpiotr/ai-gm/issues/424) |
| E10 | Forge: walidacja wymaganych NPC/lokacji przy publikacji szablonu | [#425](https://github.com/szmidtpiotr/ai-gm/issues/425) |
| E11 | Template Narrative State pre-seeding (narrative_hooks z szablonu → World State) | [#426](https://github.com/szmidtpiotr/ai-gm/issues/426) |
| E12 | Workflow publikacji szablonów (draft → review → published) | [#427](https://github.com/szmidtpiotr/ai-gm/issues/427) |
| E13 | Encountery generyczne — rozbudowa puli adventure_hooks (biome/trigger/level) | [#428](https://github.com/szmidtpiotr/ai-gm/issues/428) |
| E14 | Skalowanie encounterów per poziom gracza (level_min/level_max band gating) | [#429](https://github.com/szmidtpiotr/ai-gm/issues/429) |

#### Notatki implementacyjne

**E1** — Player HUD: pasek HP/Mana, złoto, lista aktywnych questów, XP bar do następnego progu, czas in-game (dzień/godzina). Endpoint `GET /api/campaigns/{id}/quests` zwraca active_quests z World State. Aktualizowany po każdej turze narracyjnej — `app.js` `_loadCreatorHelp()` + helper `_renderRunStats()`.

**E2** — Kreator bohatera: tooltips na kartach archetypu (`data-tooltip` atrybut + CSS `::after` pseudo-element), mechaniczne przykłady przy każdej statystyce i umiejętności. Backend: `GET /api/mechanics/creator-help` zwraca `_CREATOR_ARCHETYPES`, `_CREATOR_STATS` (7 kanonicznych statystyk z LCK), `_CREATOR_SKILL_EXAMPLES`. Fix: LCK brakował w `game_config_stats` → `_CREATOR_STATS` jako twarda lista override.

**E3/E4** — Ekrany zakończenia kampanii i śmierci: `_renderRunStats(elId, stats)` wyświetla kafelki ze statystykami runu (tury, złoto, NPC, questy). Backend: `campaign_run_stats(conn, campaign_id, character_id)` w `solo_death_service.py` zwraca te liczby. Ekran śmierci: Wskrześ (płatne) / Nowy bohater. Ekran zakończenia: LLM epitafium + statystyki.

**E5** — Kampanie martwego bohatera: zablokowany dostęp gdy `hero_status=dead`. GET `/api/campaigns/{id}` zwraca `hero_blocked=true` + `hero_status=dead`. POST `/api/campaigns/{id}/turns` zwraca HTTP 423 Locked + msg "Cannot continue — hero is dead". ✅ 420

**E6** — Narracja: `chapter_summary` kompresja starych tur (ponad N), `seed_events` injekcja do kontekstu LLM. Tag `[ARC_ADVANCE:arc_id]` parsowany w `turns.py` (obie ścieżki: streaming + narrative) → wywołuje `advance_arc()` w `campaign_plan_runtime.py`. `_ANY_NARRATIVE_RE` rozszerzony o ARC_ADVANCE strip.

**E7** — `campaign_templates`: 3 nowe kolumny przez migrację w `migrations_admin.py`: `required_npc_keys TEXT DEFAULT '[]'`, `required_beats TEXT DEFAULT '[]'`, `player_visible INTEGER DEFAULT 1`. Admin Forge UI (admin3): pola w edytorze szablonu.

**E8** — Player-facing kampania gotowa: `_openReadyCampaignPicker()` + `_launchReadyCampaign()` w `app.js`. Backend: `list_published_templates()` filtruje `player_visible=1` AND `status=published`. Gracz widzi karty z trudnością/opisem, wybiera → nowa kampania startuje z pre-seeded narrative state.

**E9** — Story Gravity: `story_gravity_service.py` — `compute_story_gravity(campaign_id, conn)` zlicza tury bez wymaganego beatu i zwraca `{level: 0-3, message: str}`. Config per instancja w `game_config_meta` (klucz `story_gravity_config`): progi L1/L2/L3 (5/10/15 tur), L3 domyślnie wyłączony. UI konfiguracji: modularny panel System → Narracja (`frontend/admin/sections/system.js`), sekcja `systab-narration`.

**E10** — Forge validate: `validate_template_publish(template_id, conn)` w `adventure_forge.py` — sprawdza czy `required_npc_keys` istnieją w tabeli `npcs`, `required_beats` istnieją w `_plan_beat_keys(plan)`. Zwraca `{"valid": bool, "missing_npcs": [], "missing_beats": []}`. Admin UI: `_toggleTemplatePublish()` używa raw `fetch()` (nie `apiFetch`) by parsować strukturalny 422 JSON.

**E11** — Template pre-seeding: `seed_narrative_state_from_plan(campaign_id, plan, conn)` w `narrative_state_service.py`. Przy starcie kampanii z szablonu: `narrative_hooks` z `gm_plan_json` → `session_flags.narrative_seeds`. LLM dostaje kontekst narracyjny od pierwszej tury.

**E12** — Workflow szablonów: 3 stany (draft/review/published) — endpointy `PATCH /api/admin/forge/templates/{id}` z walidacją przejść. Nieznane statusy → 422. Admin Forge UI (admin3): `_renderTplWorkflow(status)` — badges kolorowe, przyciski akcji (Wyślij do review / Cofnij / Opublikuj / Cofnij do review), `forgeSetTemplateStatus()`.

**E13** — `encounter_seed_service.py`: `GENERIC_ENCOUNTERS` lista 5 predefiniowanych spotkań (wilki/bandyci/gobliny/nieumarli/łobuzy) z biome/trigger/level tagami. `seed_generic_encounters()` idempotentny (marker `__generic_encounter__` w draft_data). Wywołany w `main.py` lifespan startup.

**E14** — Level gating w `encounter_service.py`: `encounter_matches(enc, *, trigger, hex_type, hero_level)` — sprawdza biome/trigger/level_min/level_max. `_hero_level_for_campaign()` helper. `maybe_inject_encounter()` refaktoryzowany: candidates loop używa `encounter_matches()` zamiast ad-hoc logiki.

## Poprawki standalone (poza fazami A-H)

- #456 — SB-2: `scene_enemies` / `player_conditions` zawsze puste — naprawione: `initiate_combat()` → `set_world_state_flags(scene_enemies=[...])`, `end_combat()` → clear, `auto_save_snapshot()` → `_sync_player_conditions()` z arkusza postaci. Commit po deploy DEV (TDD 4/4 + Playwright 2/2). ✅
- #457 — SB-3/SB-4: keyword scan nadpisywał `SKILL_TEST_PENDING` — guard przed skanem w `create_turn` + ścieżce streaming; fix `is_admin` w `slash_registry_key_for_dispatch` (HTTP 500 na slash komendy). ✅
- #458 — SB-5: test umiejętności zablokowany po `committed_d20` — SB-3/SB-4 guard rozszerzony: gdy `committed_d20` ustawione → auto-resolve inline (`resolve_skill_test` + LLM prose + save turn + clear state); gdy brak → re-surface (backward compat SB-3/SB-4). ✅
- #455 — SB-1: `GET /admin/campaigns/{id}/known-npcs` brakujący endpoint — zwraca NPC ze świata (odwiedzone lokacje) + NPC z pamięci narracyjnej (`campaign_known_npcs`), deduplikacja po label. ✅
- #459 — E19b: Dungeon tile AI prompt generator — `POST /api/admin/dungeon-tiles/generate-image-prompt` (LLM → English FLUX prompt) + `POST /api/admin/dungeon-tiles/ai-create` (LLM → nowy kafelek z nazwą i promptem); UI: ✨ Generuj prompt AI w Image Studio + ✨ Generuj kafelek AI w toolbarze kategorii. Bugfix: `call_type` w 3 wywołaniach `generate_chat()`. ✅
