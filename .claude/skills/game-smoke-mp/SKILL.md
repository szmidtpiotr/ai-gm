---
name: game-smoke-mp
description: >-
  Full-mode smoke playtest of AI-GM MULTIPLAYER: Claude drives 2–4 real player accounts through
  a real-LLM party session (lobby → join → shared rounds → combat → absence/sweep → wipe) and
  verifies each checkpoint against the live DB. Not tied to one issue — the deliverable is a
  checkpoint table + P0/P1/P2 defect issues. Use when: the user types /game-smoke-mp 2|3|4, asks
  "czy multiplayer jest grywalny end-to-end", or runs the FAZA G/5 smoke milestone. For testing
  ONE MP issue use /game-test-player-screenshot instead.
---

# game-smoke-mp — obchód trybu multiplayer

Cel: odpowiedzieć **"czy w multiplayer da się grać drużyną?"** — nie "czy endpoint odpowiada".
Gra się PRAWDZIWE rundy z PRAWDZIWYM LLM, z N osobnych kont graczy. Werdykt bez zagranych rund
jest nieważny.

## ⛔ KONTRAKT

- Weryfikacja TYLKO przez realne rundy. Żadnych skrótów przez serwisy/SQL zamiast rund.
- Dedykowane konta `tester_mp1..tester_mp4` (+ `tester_mp_spec`). NIGDY user_id=1013, NIGDY
  Mizel 999420, NIGDY heros Piotra. Demo user 1 = tylko admin do zakładania kont.
- Kampanii / postaci / kont po teście NIE usuwać.
- Odczyt DB **tylko do weryfikacji** i **wyłącznie przez `ssh + docker exec sqlite3`** (backend
  trzyma SQLite w WAL — sshfs daje nieświeże odczyty; `snapshot_mp.py` robi to poprawnie).
- Limit: **8 rund** core (rozszerzone 13–21 w drugim runie). Po limicie raport, nawet niekompletny.
- `multiplayer_enabled` musi być ON (sprawdź/ustaw w adminie przed testem).

## Wywołanie

```
/game-smoke-mp 2          # 2-osobowa drużyna (domyślnie)
/game-smoke-mp 3
/game-smoke-mp 4
/game-smoke-mp 3 --spectator   # + 1 widz
```

## Krok 1 — Setup (skrypty w `scripts/`)

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-smoke-mp/scripts
python3 setup_mp_users.py --count 3 [--spectator]      # konta + bohaterowie (idempotentne)
python3 setup_mp_lobby.py --count 3 [--spectator] --title "#MP-smoke"
```

`setup_mp_lobby.py` tworzy lobby (host = tester_mp1, **round_timer_minutes=1** by sweep był tani),
zaprasza i akceptuje wszystkich (host też wybiera swojego bohatera → tworzy się
`character_campaign_state`), opcjonalnie dodaje widza i **startuje** grę. Zwraca `campaign_id` +
listę `members` (potrzebną dalej jako `--members-json`).

> **Runda otwarcia:** start rezerwuje rundę 1 ze statusem `done` (narracja otwarcia, async, bez
> akcji graczy). Pierwsza interaktywna runda to runda 2.

## Krok 2 — Gra rundami

```bash
MEMBERS='<tablica members z setup_mp_lobby>'
python3 play_mp_round.py --campaign CID --members-json "$MEMBERS" \
    [--actions '["...","..."]'] [--absent USER_ID] [--withdraw USER_ID] [--wait 160]
# po rundzie z nieobecnym graczem (deadline minął):
python3 mp_sweep.py --campaign CID            # force-sweep + injected time + narracja
python3 play_mp_round.py --campaign CID --members-json "$MEMBERS" --narration-only
```

`play_mp_round.py` wysyła akcję każdego aktywnego gracza (osobny `client_action_id`), czeka aż
runda → `done`, i pobiera narrację **tokenem każdego gracza osobno** (prywatne notatki/roll_facts
są per-user). Pole `blocked` w wyniku = runda odrzuciła akcję (np. `round_closed`) — to defekt,
nie sukces. `snapshot_mp.py --campaign CID` daje pełny stan do weryfikacji checkpointów.

## Krok 2 — Scenariusz (checkpointy core, ≤8 rund)

Kolejność elastyczna — narracja prowadzi, checklist pilnuje. Każdy ✅ z DOWODEM (nr rundy +
cytat narracji LUB wynik `snapshot_mp.py` / `ssh+docker exec sqlite3`).

| # | Checkpoint | Mechanika (G) | Dowód |
|---|---|---|---|
| 1 | Lobby: mode, max_players, timer | U3 | `campaigns.mode='multiplayer'`, `max_players=N`, `round_timer_minutes` |
| 2 | Wszyscy dołączają + wybierają bohatera | base | `campaign_members`: N `status='accepted'`, każdy `character_id`, jeden `role='owner'` |
| 3 | *(jeśli --spectator)* widz bez bohatera | G19 #800 | member `role='spectator'`, `character_id=NULL` |
| 4 | Host startuje → runda 1 + narracja otwarcia (wspólna) | base | runda 1 istnieje; narracja ta sama dla wszystkich graczy |
| 5 | **Synchronizacja rundy**: wszyscy oddają → collecting→narrating→done | G30 #801 | N wierszy `campaign_round_actions`; runda `done`; `narrative_json` ≠ null; jedna wspólna narracja |
| 6 | Inicjatywa + konflikt celu ("Cel już martwy") | G5 #789 | akcje mają `initiative_roll`; dwóch na jednego wroga → niższa inicj. dostaje notkę |
| 7 | Prywatne notatki + roll_facts tylko własnej postaci | G8 #792 | `narration` tokenem A pokazuje notatki A, nie B |
| 8 | Współdzielony bohater: stan bitwy per-kampania, progresja globalna | G16 #784 | HP/mana w `character_campaign_state` (per campaign_id); XP/złoto/ekwipunek globalnie |
| 9 | Walka MP: start, kolejność, wrogowie auto | G7 #791 | `/combat/start` + `/combat/action`; kolejność zawiera graczy; wrogowie po graczach |
| 10 | Powalenie, nie śmierć: HP 0 = nieprzytomny, da się ocucić | G17 #794 | stan = unconscious (nie `dead`); ocucenie przywraca ~25–50% HP |
| 11 | Czat party publiczny + **prywatność szeptu** | G19 #800 / #950 | publiczna wiadomość widoczna dla wszystkich; szept `whisper_to` tylko dla celu; treść szeptu **nieobecna w promptcie LLM** |
| 12 | Spójność narracji w drużynie | G28 | przegląd rund: brak sprzeczności ze stanem; spójny ton |

Screenshoty (`/game-screen`, ≥2 konteksty graczy): po CP2 (lobby z N graczami), CP9 (kolejność
walki), CP11 (czat/szept lub ostatnia runda) — minimum 3.

## Krok 2b — Checkpointy rozszerzone (drugi run / opcjonalnie)

| # | Checkpoint | G | Dowód |
|---|---|---|---|
| 13 | Drabina absencji: brak akcji → `[BRAK AKCJI]`/`[AUTOPILOT]`, `absence_warnings++` | G22 #803 | `--absent U` + `mp_sweep.py`; `campaign_members.absence_warnings`, marker w akcji |
| 14 | Auto-przekazanie hosta po progu absencji | G22 #803 | `campaigns.host_user_id`/`role='owner'` przechodzi na najaktywniejszego |
| 15 | Vote-kick: większość (2-os = host sam); wyrzucony heros → idle, zachowuje XP/złoto | G3 #787 / G13 #799 | `campaign_kick_votes`; member `status='kicked'`; heros `status='idle'`, sheet bez zmian |
| 16 | Wycofanie akcji w `collecting` | G24 #805 | `--withdraw U`: wiersz usunięty, runda nadal `collecting` |
| 17 | Późny dołączający: onboarding raz + catch-up | G12/G25 | `pending_intro=1` → wyczyszczone; `GET /catchup` zwraca kontekst |
| 18 | Kara za wipe: % złota wg poziomu, ocknięcie 50% HP | G15 #813 | delta złota wg `mp_balance.WIPE_GOLD_PCT_BY_LEVEL`; `<50 gp` zwolnione |
| 19 | Warstwowe streszczenia: L1 per runda, L2 rozdział ~10 | G18 #796 | `campaign_round_summaries` layer=1; layer=2 po ≥10 |
| 20 | Cisza nocna: sweep nie zamyka rundy w nocy | G27 #808 | czas w oknie ciszy → `mp_sweep.py` nic nie robi |
| 21 | Idempotencja: ten sam `client_action_id` → jedna akcja | G30 #801 | dwa submitty z tym samym id → jeden wiersz |

## Krok 3 — Defekty

Każde ❌ = issue:

```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE-MP — <opis>" \
  --label "bug,smoke-defect,needs-testing" \
  --body "<tryb mp-N, runda, oczekiwane vs faktyczne, snapshot_mp/SQL/screenshot>"
```

**P0** = drużyna nie posuwa rundy do przodu (blokuje tryb) · **P1** = psuje doświadczenie
(sprzeczność narracja↔stan, **wyciek prywatności**, martwa mechanika) · **P2** = kosmetyka.

## Krok 4 — Raport

```
## 🎮 game-smoke-mp <N graczy> — <data>
Kampania: id | Gracze: u1,u2,… (+widz) | Rund zagranych: N

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Checkpointy (12 core + opcjonalnie 13–21)
| # | Checkpoint | Wynik | Dowód |   (✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
### Screenshoty (3+, co widać, z którego kontekstu gracza)
```

## Znane pułapki

- **Koszt**: N graczy × rundy × narracja 2-fazowa (planner→narrator). Wymuś `gpt-4.1-mini`,
  core run ≤8 rund.
- **Nie czekaj zegara** — zamykaj rundy `mp_sweep.py` (wstrzyknięty czas, domyślnie +90 s; mały
  zasięg rażenia — zamyka tylko rundy świeżo po deadline). Lobby ma timer=1 min jako zabezpieczenie.
- Endpoint submit zwraca **HTTP 200 nawet przy odmowie** (`round_closed`) — patrz pole `blocked`
  w wyniku `play_mp_round.py`, nie tylko kod HTTP.
- Prywatne notatki/roll_facts są **per-token** — pobieraj narrację tokenem każdego gracza.
- Sprawdzenie prywatności szeptu = bramka P1: przeszukaj zapisany prompt/kontekst rundy pod kątem
  treści szeptu; każde trafienie = wyciek.
- **Znany blocker (stan 2026-06-23):** po rundzie otwarcia (`done`) `submit_action` zwraca
  `round_closed` dla każdej rundy ≠ `collecting`, a nic nie otwiera kolejnej `collecting`
  (`get_or_create_current_round` jest martwym kodem, brak endpointu „następna runda”). Skutek:
  drużyna nie wychodzi poza narrację otwarcia → CP5+ blokowane. To defekt P0 (luka silnika, nie
  testów) — zgłoszony osobno; gdy naprawiony, harness gra pełne rundy bez zmian.
```
