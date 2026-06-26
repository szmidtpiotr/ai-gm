---
name: game-smoke-race
description: >-
  Race-specific playability smoke test for AI-GM dwarf race (#969).
  Verifies 12 checkpoints across warrior + scholar archetypes: racial stat mods,
  twardy jak kamień, kowalskie oko (shop discount + repair), wzrok górnika,
  rdzeń-magia starting spells, miscast threshold, race lock, narrator injection,
  and 3-turn combat/magic runs without errors. Two run variants:
  /game-smoke-race warrior (CPs 1-6, 10-11) and /game-smoke-race scholar (CPs 7-9, 12).
  Use when: user types /game-smoke-race warrior or /game-smoke-race scholar.
  For automated mechanics check use the pytest suite; for UI wizard/badge use Playwright spec.
---

# game-smoke-race — testy grywalności rasy krasnolud

Cel: odpowiedzieć na pytanie **„czy granie krasnoludem jest kompletne i działające end-to-end?"**
Dwanaście checkpointów — 7 mechanicznych + 2 narracyjne + 3 turowe. Werdykt bez zagranych tur
w prawdziwej kampanii jest nieważny.

## ⛔ KONTRAKT

- Weryfikacja przez REALNE tury (`play_turn.py`) i SQL ODCZYTU. Żadnych skrótów.
- Tylko konto Demo (`user_id=1`). Nigdy `user_id=1013` (Piotr/Mizel).
- Kampanii i postaci po teście NIE usuwać.
- SQL wyłącznie do ODCZYTU — przez SSH+docker exec, nigdy sshfs.
- Limit: 15 tur na run. Po limicie → raport, nawet niekompletny.

## Wywołanie

```
/game-smoke-race warrior      # Run A: krasnolud wojownik (CPs 1-6, 10-11)
/game-smoke-race scholar      # Run B: krasnolud uczony (CPs 7-9, 10, 12)
/game-smoke-race all          # oba runy sekwencyjnie
```

## Krok 1 — Setup (oba runy)

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-smoke-race
python3 scripts/setup_dwarf_pool.py
# → {"warrior_id": int, "scholar_id": int, "ok": true}
```

Następnie utwórz kampanię testową dla każdego runu:

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player

# Run A — wojownik
python3 scripts/setup_campaign.py --issue 969 --archetype warrior
# jeśli kampania #969 istnieje z turami, utwórz #969-warrior-runN przez API

# Run B — uczony
python3 scripts/setup_campaign.py --issue 969 --archetype scholar
# tytuł #969-scholar-runN
```

> **Uwaga:** `setup_campaign.py` używa `HERO_NAMES` z puli bazowej (Wojownik/Uczony).
> Krasnoludy mają inne ID niż standardowa pula. Po zwróceniu `campaign_id` z setup_campaign,
> przypisz krasnoluda do kampanii ręcznie przez API:
>
> ```bash
> curl -s -X POST http://192.168.1.61:8100/campaigns/CAMPAIGN_ID/assign-hero \
>   -H "Content-Type: application/json" \
>   -d '{"character_id": WARRIOR_ID}'
> ```
>
> Lub użyj `POST /campaigns/{id}/select-hero` zależnie od endpointu — sprawdź w
> `backend/app/api/campaigns.py` przed wysłaniem.

## Krok 2 — Checkpointy

### Run A — Krasnolud Wojownik

Graj turami z `play_turn.py`, odhaczyj każdy checkpoint z dowodem.

| # | Checkpoint | Dowód wymagany |
|---|---|---|
| CP1 | `characters.race='dwarf'` w DB; `sheet_json.stats.CON≥12` (base +2) | `sqlite3 /data/ai_gm.db "SELECT race, sheet_json FROM characters WHERE id=WARRIOR_ID"` → CON≥12 |
| CP2 | Modyfikatory rasowe CON+2/STR+1/CHA-1/DEX-1 odzwierciedlone w sheet | delta stats vs base wartości archetypowe |
| CP3 | Twardy jak kamień: narracja opisuje odporność krasnoluda gdy wróg trafia typem `rdzen`/`dark`/`poison`; HP spada o 2 mniej niż normalnie | compare HP delta; LLM narrative mentions resistance; `combat_turns` log |
| CP4 | Kowalskie oko — sklep: krasnolud płaci 15% mniej (base_price × 0.85); narracja lub gold delta potwierdza zniżkę | gold przed/po: `delta = ceil(base_price × 0.85)` nie `base_price`; `character_gold_log` |
| CP5 | Kowalskie oko — reperuj: tura "reperuj broń" lub przycisk; HP+20, gold-20 | HP i gold w `sheet_json` przed/po; `characters.sheet_json` po turze |
| CP6 | Wzrok górnika w lochu: tura wejścia do lochu; narracja krasnoluda opisuje wyraźne widzenie bez opisu ciemności; GET darkvision_bonus zwraca `perception_bonus=3` | `session_flags.dungeon_run` po wejściu; backend log lub tura zawierająca "percepcja" |
| CP10 | System message zawiera `Rasa postaci: dwarf` — widoczne w logach LLM lub diagnostyce | `docker exec ai-gm-dev-backend-1 grep "Rasa postaci" /proc/1/fd/1` (tail logs) lub sprawdź `campaign_turns.messages_json` dla ostatniej tury |
| CP11 | 3 tury bojowe krasnoludem bez HTTP 500; HP zmienia się w walce; przynajmniej jedna tura z wrogiem | `play_turn.py` × 3; każdy zwraca `http_status=200`; `active_combat.combatants[].hp` zmienia się |

### Run B — Krasnolud Uczony

| # | Checkpoint | Dowód wymagany |
|---|---|---|
| CP7 | Rdzeń-magia startowe czary: `character_spells` zawiera `vein_tremor`+`rdzen_shield`, NIE `magic_bolt` | `sqlite3 /data/ai_gm.db "SELECT spell_key FROM character_spells WHERE character_id=SCHOLAR_ID"` |
| CP8 | Miscast threshold: Nat1 i Nat2 to miscast dla krasnoluda; narracja opisuje rdzeń-flavour (żyła, krew, metal) | tura zakończona Nat1 lub Nat2 rzutem; narracja zawiera rdzeń-klimat; `is_miscast(2, "dwarf")=True` |
| CP9 | Race lock: próba nauki human-only czaru (np. `magic_bolt`) → odmowa endpointu 400 lub narracja odmowy | `curl -X POST http://192.168.1.61:8100/characters/SCHOLAR_ID/spells -d '{"spell_key":"magic_bolt"}'` → 400 |
| CP10 | (jak Run A) System message zawiera `Rasa postaci: dwarf` | jak wyżej |
| CP12 | 3 tury magiczne krasnoludem uczonym: rzucanie Rdzeń-czarów; mana spada po rzucie; narracja używa rdzeń-klimat (nie ogień/luz) | `sheet_json.current_mana` przed/po; każda tura `http_status=200` |

## Krok 3 — Defekty

Każde ❌ = issue:

```bash
gh issue create --repo szmidtpiotr/ai-gm \
  --title "[BUG] SMOKE-RACE — <opis>" \
  --label "bug,smoke-defect,needs-testing" \
  --body "<run, checkpoint, oczekiwane vs faktyczne, SQL/screenshot>"
```

Priorytety: **P0** = rasa niegrywalna (crash, mechanika całkiem nie działa) · **P1** = mechanika działa
ale źle (złe liczby, brak narrativeu rasy, czar nie daje efektu) · **P2** = kosmetyka, brak flavor.

## Krok 4 — Raport

Komentarz do issue #969:

```
## 🎮 game-smoke-race <warrior|scholar> — <data>
**Wojownik:** char_id | **Uczony:** char_id | **Kampania A:** id | **Kampania B:** id
**Tur zagranych:** N (warrior) + N (scholar)

### Werdykt Run A (warrior): GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
### Werdykt Run B (scholar): ...

### Checkpointy
| # | Checkpoint | Wynik | Dowód |
(12 wierszy: ✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
```

## Automatyczne testy (do uruchomienia niezależnie)

```bash
# Pytest — 10 checkpointów mechanicznych (bez LLM, szybko):
ssh claude@192.168.1.61 'cd /home/piotrszmidt/ai-gm && \
  docker cp backend/tests/playability/test_race_playability.py \
    ai-gm-dev-backend-1:/app/tests/playability/test_race_playability.py && \
  docker exec ai-gm-dev-backend-1 mkdir -p /app/tests/playability && \
  docker exec ai-gm-dev-backend-1 pytest tests/playability/test_race_playability.py -v'

# Playwright spec — UI: wizard step 0, badge, shop:
ssh claude@192.168.1.61 'docker exec ai-gm-dev-test-agent-1 \
  npx playwright test --config=playwright/playwright.config.js \
  playwright/ux/race/race_smoke.spec.js 2>&1 | tail -20'
```

## Gotchas

- Krasnolud startuje z `vein_tremor`+`rdzen_shield` — rzucaj te czary w Run B, nie `magic_bolt`.
- Miscast (Nat1/Nat2 dla krasnoluda) — fragment narracji różni się od human-miscast; szukaj
  słów "żyła", "trzęsienie", "Rdzeń" w narrativeu.
- Twardy jak kamień: wymaga wroga z `damage_type` w `{rdzen, dark, poison}`. Serwery DEV mają
  wrogów "Goblin" (fizyczny) — wybierz locha z Krypta lub szukaj trujących wrogów (Pająk = `poison`).
- Kowalskie oko sklep: zniżka obowiązuje ZAWSZE, nie tylko u kowala. Sprawdź gold_delta.
- `is_miscast(2, "dwarf")` → `True`; `is_miscast(2, "human")` → `False`.
