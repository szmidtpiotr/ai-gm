# 📋 KOMENDY + JAK PRACUJEMY (czytaj tu — ta strona otwiera się domyślnie)

> Ściąga Piotra — same komendy. Zadania żyją w **GitHub Issues + Milestones (faza)**; aktywną listę bierzemy z **Planu** (issues).

## 📦 Gdzie żyją zadania (system od 2026-06-19)
- **Issue = jedno zadanie. Milestone = faza** (FAZA L/LB/B/SF/5 Multiplayer/6/FIX).
- Widok = **„Plan"** (zakładka w pluginie). Mówisz **„Plan"/„tablica"/„fazy"** → wiem: GitHub issues+milestones.
- **Planowane zadanie → od razu issue + milestone.** „Dodaj X do fazy Y" → Claude zakłada issue + milestone + label.
- **Zmiana fazy = zmiana milestone** (sam możesz, w GitHub/Plan tabie).
- **Zawsze aktualizuję issue** (status in-progress→review→closed + komentarz fix/SHA). Issue = pamięć zadania.

## 🗂 Plan — ustawianie kolejności (`/github-task`, plugin v1.7.0+)
Plan tab czyta dokładny order 1→N z `.GitHubBoard/plan.json` (Claude pisze plik → ty klikasz **Refresh**).

**Wywołanie:** „ułóż plan wg pilności" · „ustaw kolejność w Plan" · „przelicz plan" · „przestaw fazy: …" · `/github-task ułóż plan`

**Co dopisać (domyślne w nawiasach):**
| Wymiar | Domyślnie | Kiedy dopisać |
|---|---|---|
| Reguła | sort wg `priority:` (high→med→low→zamknięte na dno) | inna: „najpierw security, potem bugi blokujące" |
| Zakres | wszystkie milestone | jeden: „tylko Multiplayer" |
| Fazy vs issues | order wewnątrz faz; `__phaseOrder__` zostaje | przestaw całe fazy: „MP na górę, Faza 6 na dół" |

**Przykłady które rozumiem 1:1:**
- „ułóż plan wg pilności" → regeneruję `plan.json` per milestone wg priorytetu.
- „w Multiplayer: najpierw security, potem onboarding, reszta wg numeru" → ręczna sekwencja w jednej fazie.
- „przestaw fazy: MP, Lochy L, Bugi, reszta jak jest" → ustawiam `__phaseOrder__`.

Backup `plan.json.bak` robię zawsze przed nadpisaniem.

## ⚙️ Jak wygląda praca teraz
```
PLANOWANIE: "dodaj X do fazy Y" → ja zakładam issue + milestone + label
PRACA:      bierzesz issue z Planu → /tdd → /code-review → /playwright
            → ZAWSZE aktualizuję issue → ty zamykasz po obejrzeniu na DEV
WIDOK:      Plan tab — fazy z paskami postępu, kolejność, klik → modal issue
```

## 🔁 Rytm sesji — jedno issue, 3 warstwy obrony
**test** = złamana logika · **code-review** = bug obok · **playwright** = zepsuty wygląd.
```
1. /tdd #NNN              → test + fix
2. /code-review (diff)    → 🔴 napraw (wróć do /tdd), 🔵 pomiń
3. /playwright-test-report → przejście jako gracz + zrzuty (lub /game-screen)
4. commit + push (Claude sam, develop) · issue → review + needs-testing
5. TY oglądasz na DEV → zamykasz issue
```

### 📋 Prompt na start (podmień numer — blok ma przycisk Copy)
```
Przeczytaj notes.md (góra). Robimy #NNN przez /tdd.
Przed commitem /code-review na diffie — realne bugi napraw, kosmetykę pomiń.
Na końcu /playwright-test-report + raport po polsku.
```
Warianty: dopisz „Zatrzymaj się po RED" (checkpointy) · „Auto, leć bez pytań" (wychodzisz) · „co następne?" (Claude poda z Planu).

## 🎯 7 poleceń
| Komenda | Kiedy |
|---|---|
| „stan?" | gdzie jesteśmy (Plan + STATUS) |
| `/github-task` | co robić / przesuń / status issue |
| `tdd #NNN` | wdróż jedno zadanie |
| `/mass-implement` | wychodzisz, Claude leci listą issues sam |
| `/playwright-test-report` | sprawdź UI + zgłoś bugi |
| `/game-screen` | szybki podgląd ekranu |
| `/test-inreview` | **masowy test wszystkich issue in-review** (patrz niżej) |

## 🧪 Testowanie — który kiedy
*bug widać na ekranie?* → `/playwright-test-report` · *liczby w bazie przez wiele tur?* → `/game-test-player-screenshot` · *cały tryb grywalny?* → `/game-smoke[-dungeon][-mp]` (API, szybkie) lub `-pw` (przez prawdziwe UI) · *szybki podgląd?* → `/game-screen`. (Pomijasz: `/game-test`, `/verify`, `/webapp-testing`.)

## 🎮 Multiplayer — jak testować
Trzy warstwy, od najtańszej do najdroższej:

| Narzędzie | Co sprawdza | Jak odpalić |
|---|---|---|
| **Specy Playwright** (deterministyczne, bez LLM) | okablowanie UI + kontrakty API | w kontenerze test-agent: `docker exec ai-gm-dev-test-agent-1 npx playwright test mp/ --config playwright.config.js` — 6 runnable (multicontext, round-sync, spectator, party-chat, lobby-kick) + regresje #813/#824/#812 |
| **`/game-smoke-mp N`** | grywalność drużyny przez **API** (lobby→rundy→walka→absencja→wipe) | `/game-smoke-mp 2` (lub 3/4); werdykt GRYWALNY/NIE + 12 core + CP13–26 + issue P0/P1/P2 |
| **`/game-smoke-mp-pw N`** | to samo przez **prawdziwe UI** (browser) — czego API nie widzi: ekran lobby + kick, przyciski 🗑/Opuść (#954), sync narracji u wielu graczy, panel czatu, kompozytor widza, baner walki MP | `/game-smoke-mp-pw 2`; najlepiej **nowa sesja, Sonnet 4.6, effort high** (czysty kontekst) |

- **N graczy = N osobnych kont** `tester_mp1..N` (hasło `mp_tester_2026`) — setup: `setup_mp_users.py`.
- Skrypty harness: `.claude/skills/game-smoke-mp/scripts/` (`setup_mp_users`, `setup_mp_lobby [--no-start]`, `play_mp_round`, `mp_sweep`, `snapshot_mp`).
- **PW = jeden browser = jeden gracz**: API steruje resztą, fokus na P1 + widzu, POV-switch tokenem w localStorage.
- DB tylko przez `ssh + docker exec sqlite3` (NIGDY sshfs — staleness WAL).

## 🎮 Smoke testy — „czy w ten tryb da się grać?"
Pełny obchód trybu: ~15-30 realnych tur z prawdziwym LLM, checkpoint po checkpoincie. Werdykt: GRYWALNY / Z ZASTRZEŻENIAMI / NIEGRYWALNY. Konto Demo, nic nie usuwają, raport + issue P0/P1/P2.

**Dwa warianty każdego trybu — API vs UI:**

| Tryb | API (szybkie, stan w SQL) | UI (przez przeglądarkę, dowód wizualny) |
|---|---|---|
| Solo | `/game-smoke nowa-kampania` / `gotowa-kampania` | `/game-smoke-pw nowa-kampania` / `gotowa-kampania` |
| Loch | `/game-smoke-dungeon` (`--engine`) | `/game-smoke-dungeon-pw` (`--engine`) |
| Multiplayer | `/game-smoke-mp 2\|3\|4` | `/game-smoke-mp-pw 2\|3` |

**API vs `-pw` — kiedy który:**
- **API** (`/game-smoke`…) — gra przez `play_turn.py`, dowód = SQL. Szybsze, tańsze. NIE widzi warstwy UI (popup kości, modale, kolumny stref). Domyślny wybór do weryfikacji mechaniki/stanu.
- **`-pw`** (`/game-smoke-*-pw`) — gra przez Playwright MCP w prawdziwym UI, dowód = zrzuty inline. Wolniejsze. Łapie to, czego API NIE widzi: kolumny **DYSTANS/ZWARCIE** + chipy 🏹/⚔, modal reakcji **SF10** (Przyjmij/Unik/Blok), popup kości, pasek many, menu czarów, picker mikstur, **mapę lochu** + D-pad, modale boss/porzucenie, lobby/czat MP.
- Komplementarne — pełna pewność trybu = oba (API na stan + `-pw` na to co gracz widzi).

Smoke ≠ test jednego issue. Pojedynczy bug → `/playwright-test-report #NNN` albo `/game-test-player-screenshot #NNN`.

## 🔬 `/test-inreview` — masowy test wszystkich review-issue
Odpala kompletny przegląd wszystkich otwartych issue z labelką `review`. Wpisz gdy chcesz zamknąć zaległości po fazach wdrożeń.

```
/test-inreview
```

**Co robi:**
1. Świeży skan GitHub (`review` label, open) — lista zmienia się między sesjami
2. Pyta które **milestony** testować w tej sesji (multiSelect)
3. Grupuje issue w 7 przebiegów scenariuszowych (nie per issue — per scenariusz gry)
4. Każdy przebieg = osobna sesja subagenta (czysty kontekst)
5. Triage: TESTABLE (backend+UI+DB wpięte) vs SKIP (spec-only)
6. Test → **auto-zamknij** jeśli pewny · **komentarz po polsku** jeśli nierozstrzygalne
7. Nowe bugi → issue w `Bugi i poprawki (FIX)` + label `bug`
8. `TEST_RAPORT.md` aktualizowany na bieżąco

**7 grup (kolejność):**
| Grupa | Silnik | Typowe issue |
|---|---|---|
| 1 — Nowa Kampania | game-smoke + Playwright | kreator, quest, walka, sklep, kostki, World State |
| 2 — Klasy bojowe | game-test-player | dual-wield, amunicja, short rest, pasek akcji |
| 3 — Mag + specjalne | game-test-player (Scholar) | czary ally/summon/CHA, grapple, zaskoczenie |
| 4 — Loch | game-smoke-dungeon | wszystkie L-taski + bugi zagadek |
| 5 — Admin panel | Playwright /admin/ | tabele, zakładki kampanii, sandbox, dice config |
| 6 — MP frontend | Playwright dual | GF1-GF7 + bugi HTTP 500/migracje |
| 7 — G-tasks triage | grep + Playwright | G1-G31: co wdrożone → test, reszta → SKIP |

**Zasady:**
- Wykluczone zawsze: Admin Panel Mobile · Faza R · Faza 6
- Nie naprawia podczas testów — tylko loguje. Wyjątek: < 5 min i blokuje dalsze testy.
- Sekwencyjnie (dzielą konto Demo/DB) — nie równolegle
- Tracking: milestone #12 „Test: Playwright + Pytest" (issues #888–#892)

## 🛠 Kodowanie / jakość
- **`tdd #NNN`** — główny: test→kod→sprzątanie + Playwright + aktualizuje ISSUE.
- **`/code-review`** — szuka bugów w diffie (bezpieczny, tylko czyta). `--fix` naprawia.
- **`/simplify` / `/cleanup`** — ⚠️ tylko w klatce: mały diff + osobny commit + retest. Strach o regresję słuszny.

## 🧠 Myślenie / 🎨 Design (znasz, używasz)
`/brainstorming` (przed ficzerem) · `/llm-council` (A/B) · `/deep-research` · `/game-design` · `/frontend-design` `/ui-ux-pro-max` · `/canvas-design` · `/creating-mermaid-diagrams` `/excalidraw-diagram`.

## ⚙️ Automaty (zero akcji)
caveman (zwięzłość) · RTK (kompresja komend) · ponytail (mniej kodu).

## 🔧 Pending (przesiadka na nowy system)
- `/tdd` — wywalić krok „update notes.md" (zostaje update ISSUE).
- `mass-implement` — jedzie wyłącznie z issues (LIST), FAZA-mode/notes odstaw.


## G21 #802 — Online Presence (last_seen heartbeat + members[].online)
- Przetestowane /playwright-test-report 2026-06-22, raport: https://github.com/szmidtpiotr/ai-gm/issues/802#issuecomment-4763531114
- Werdykt ✅ — backend OK, members[].online w /round/status, last_seen heartbeat działa, complete_push_sent w DB
- Dodatkowa poprawka commit 08a7e0ac: Playwright spec untracked + autopilot_consent w test schema (10/10 pytest GREEN)

## G5 #789 — MP Conflict Resolution (initiative_roll)
- Przetestowane /playwright-test-report 2026-06-22, raport: https://github.com/szmidtpiotr/ai-gm/issues/789#issuecomment-4763459059
- Werdykt ✅ — backend OK, kolumna w DB, 7/7 pytest GREEN (fix schematu testowego commit a938ea4f)

## G22 #803 — Drabina nieobecności: autopilot opt-in + auto-handoff hosta
- Przetestowane /playwright-test-report 2026-06-22, raport: https://github.com/szmidtpiotr/ai-gm/issues/803#issuecomment-4763551201
- Werdykt ✅ — 4/4 API checks PASS, kolumna autopilot_consent w DB potwierdzona, 6/6 pytest GREEN
- Uwaga: test_both_consent_levels_increment_warnings zaktualizowany (commit a5e1b408) — design zmieniony przez #804: autopilot=1 NIE podbija warnings

## G29 #810 — Ochrona promptu przed injection
- Wdrożone commit fcd8394d — _sanitize_action_text() + delimitery <<AKCJA_GRACZA>> + reguła G29 w system prompt + _MAX_ACTION_TEXT_LEN=1000
- Przetestowane /playwright-test-report 2026-06-22, raport: https://github.com/szmidtpiotr/ai-gm/issues/810#issuecomment-4763690903
- Werdykt ✅ — 12/12 pytest GREEN, API 400 dla >1000 znaków, 200 dla normalnego tekstu, backend zdrowy po rebuild

## SMOKE-PW warrior — 2026-06-24
- Kampania: #512 id=999964, [TEST] Wojownik id=2
- Werdykt: **GRYWALNY** ✅ — wszystkie P1 naprawione i zweryfikowane
- Raport Run 1: https://github.com/szmidtpiotr/ai-gm/issues/512#issuecomment-4787649086
- Raport Run 2: https://github.com/szmidtpiotr/ai-gm/issues/512#issuecomment-4788887088
- **Run 1** ✅ CP1 HUD, CP3 DB lokacja, CP4 NPC z DB, CP6 dice popup Stage 1, CP7 strefy walki, CP9 model dmg #826, CP17 czas gry | ❌ #984 Stage 2 damage popup brak | ❌ #985 Wskrzeszenie→tura wroga→śmierć loop
- **Run 2** ✅ CP2 hex ruch, CP5 skill test Medycyna, CP11 combat loot, CP12 gate narracyjny, CP13 sklep kup+sprzedaj, CP16 konsumable w walce | ⚠ CP10 SF10 reakcja odpala ale wyświetla "? vs ?" zamiast wyników → #986 | ❌ CP8 NIETETOWALNY (bandyta zawsze dogania gracza → ta sama strefa)
- **Retest #984+#985+#986** ✅ — wszystkie naprawki zweryfikowane 2026-06-24, issues zamknięte
- Screenshots: temp-img/20260624_smoke-pw-warrior-r2/ + temp-img/20260624_retest-984-985-986/

## G15 #813 — Centralne flagi balansu MP (mp_balance.py) + strojenie kar wipe
- Wdrożone commit 5b9c11a7 — nowy moduł mp_balance.py, refaktor _apply_mp_wipe, GET+PATCH /api/admin/sandbox/mp-balance
- 20 pytest GREEN
- Przetestowane /playwright-test-report 2026-06-22, raport: https://github.com/szmidtpiotr/ai-gm/issues/813#issuecomment-4763767233
- Werdykt ✅ — GET zwraca poprawne domyślne wartości (10/20/30%, floor=50, HP=0.5, scale=1.0), PATCH aktualizuje natychmiast (session-scoped)

## GF7 #927 — E2E Multiplayer flow (test-only)
- Przetestowane /playwright-test-report 2026-06-22, raport: https://github.com/szmidtpiotr/ai-gm/issues/927#issuecomment-4768142376
- Werdykt ⚠️ — backend generuje narrację, polling lobby działa, invite-by-username działa
- Znalezione bugi: #934 (brak kafelka MP), #935 (zły klucz showScreen), #936 (createLobby 500 model_id), #938 (brak migracji campaign_invites+party_messages), #939 (brak HTML czatu party + enterGame nie aktywuje MP UI)
- Priorytet napraw: #934→#935→#936 (blokują wejście do MP) → #938→#939 (blokują czat)

## #932 — POST /multiplayer/campaigns HTTP 500 (brak model_id)
- Fix: commit 4bf0c235 — model_id='default' dodany do INSERT w create_lobby()
- Pytest: 3/3 PASS (test_issue932_create_lobby_model_id.py)
- Przetestowane /playwright-test-report 2026-06-23, raport: https://github.com/szmidtpiotr/ai-gm/issues/932#issuecomment-4776267323
- Werdykt ✅ — HTTP 200 + campaign_id, model_id=default w DB, lobby widoczne w UI
