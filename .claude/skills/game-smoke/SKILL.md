---
name: game-smoke
description: >-
  Full-mode smoke playtest of AI-GM: Claude plays 15 real LLM turns as a player through a
  complete mechanics scenario (movement, NPC, quest, combat, shop, rest+XP, beats) and verifies
  each checkpoint against the DB. Not tied to a single issue — the deliverable is a checkpoint
  table + P0/P1/P2 defect issues. Use when: the user types /game-smoke nowa-kampania or
  /game-smoke gotowa-kampania, or asks "czy tryb X jest grywalny end-to-end". For testing ONE
  specific issue use /game-test-player-screenshot instead.
---

# game-smoke — obchód całego trybu gry

Cel: odpowiedzieć na pytanie **"czy w ten tryb da się grać?"** — nie "czy endpoint odpowiada".
Gra się PRAWDZIWE tury z PRAWDZIWYM LLM. Werdykt bez zagranych tur jest nieważny.

## ⛔ KONTRAKT (jak w /game-test-player)

- Weryfikacja TYLKO przez realne tury gry. Żadnych skrótów przez serwisy/SQL zamiast tur.
- Tylko konto Demo (user_id=1). Nigdy user_id=1013.
- Kampanii i postaci po teście NIE usuwać.
- SQL wyłącznie do ODCZYTU (weryfikacja checkpointów), przez SSH+docker exec (nigdy sshfs).
- Limit: 18 tur na run (15 scenariusza + 3 zapasu). Po limicie: raport, nawet niekompletny.

## Wywołanie

```
/game-smoke nowa-kampania
/game-smoke gotowa-kampania
```

## Krok 1 — Setup

Reużyj infrastruktury `/game-test-player`:

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 scripts/setup_hero_pool.py          # zwraca warrior_id/scholar_id/rogue_id
```

- **nowa-kampania:** `python3 scripts/setup_campaign.py --issue 512 --archetype warrior`
  (kampania `#512`; jeśli istnieje z turami — utwórz świeżą przez API z tytułem `#512-runN`).
- **gotowa-kampania:** kampania musi powstać Z SZABLONU. Sprawdź realny endpoint
  (`GET /api/campaign-templates` → tworzenie kampanii z `template_id`/`template_key` — zweryfikuj
  w `backend/app/api/campaigns.py` i hubie `frontend/front/js/app.js`, NIE zgaduj pól).
  Wybierz pierwszy opublikowany szablon. Tytuł `#513-runN`.

## Krok 2 — Scenariusz (checkpointy = kryteria U27)

Graj turami (`python3 ../game-test/scripts/play_turn.py --campaign ID --character ID --message "..."`),
adaptując wiadomości do narracji. Każdy checkpoint odhacz z DOWODEM (nr tury + cytat narracji
LUB wynik SQL). Kolejność elastyczna — narracja prowadzi, checklist pilnuje.

| # | Checkpoint | Dowód (SQL przez ssh+docker exec, sqlite3 /data/ai_gm.db) |
|---|---|---|
| 1 | Otwarcie renderuje scenę, HUD pokazuje HP/złoto/XP | screenshot + wartości vs `characters.sheet_json` |
| 2 | **Ruch hex ≥2×** ("idę na północ", "idę do [lokacja]") | `session_flags.current_hex` ZMIENIA SIĘ po turze ruchu |
| 3 | LLM używa lokacji Z BAZY (nie wymyśla) | klucz lokacji w `game_sessions.current_location_id` istnieje w `game_locations` z `ai_generated=0`; policz nowe `approved=0` po runie |
| 4 | Rozmowa z NPC przypisanym do lokacji | imię NPC z `location_npc_assignments`/`npc_keys` pojawia się w narracji |
| 5 | Quest: przyjęcie + widoczny postęp | wiersz w `character_quests` |
| 6 | Walka: pełny cykl (start→ciosy→koniec→loot) | `campaign_turns.route`, HP przed/po, wpis loot |
| 7 | Gate działa: atak bez wroga w scenie → blok | tura "atakuję smoka" w karczmie → odmowa, brak walki |
| 8 | Sklep: kupno LUB sprzedaż ze zmianą złota | delta złota w `sheet_json` = cena z katalogu |
| 9 | Odpoczynek + wydanie XP (modal "Ucz się") | zmiana XP/skill ranku w `sheet_json` |
| 10 | Zegar gry tyka, pora dnia się zmienia | `ingame_hours` rośnie między turami |
| 11 | *(tylko gotowa-kampania)* beat fabularny odpala | stan beatów/GM Plan w admin lub DB przed/po |
| 12 | Spójność: narracja NIE twierdzi nic sprzecznego ze stanem | przegląd 15 tur; każda sprzeczność = defekt |

Screenshot (skrypt z `/game-screen`, procedura kopiowania jak w /game-test-player-screenshot
Step 7a) PO checkpointach: 1, 6, 9 — minimum 3 na run.

## Krok 3 — Defekty

Każde ❌ = issue:

```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE — <opis>" \
  --label "bug,smoke-defect,needs-testing" --body "<tryb, tura, oczekiwane vs faktyczne, SQL/screenshot>"
```

Priorytety: **P0** = scenariusz nieprzechodzalny (blokuje grę) · **P1** = psuje doświadczenie
(sprzeczność narracja↔stan, brak feedbacku, martwa mechanika) · **P2** = kosmetyka. Priorytet w tytule.

## Krok 4 — Raport

Komentarz do issue trybu (#512 lub #513):

```
## 🎮 game-smoke <tryb> — <data>
**Kampania:** id | **Bohater:** id | **Tur zagranych:** N

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Checkpointy
| # | Checkpoint | Wynik | Dowód |
(12 wierszy: ✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
### Screenshoty (3+, z opisem co widać)
```

Po obu trybach: zaktualizuj notes.md (U4b) wg wyniku — `[x]` TYLKO gdy oba runy ukończone
i wszystkie P0 zgłoszone.

## Gotchas

- Rate limit TPM → 502: czekaj 60 s; model `gpt-4.1-mini` w configu kampanii zmniejsza koszt.
- `route=skill_test`: wyślij "Staram się jak mogę." i kontynuuj.
- Dice popup w turach przez UI nie dotyczy play_turn.py (API path).
- Nie wymuszaj checkpointów łamiąc fikcję ("pokaż mi sklep NATYCHMIAST") — graj naturalnie;
  jeśli po 15 turach checkpoint nieosiągnięty organicznie → oznacz N/D z powodem, to też wynik.
