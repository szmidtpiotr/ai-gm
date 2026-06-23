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
- Limit: 20 tur na run (15 scenariusza + 5 zapasu — dodatkowe checkpointy walki). Po limicie: raport, nawet niekompletny.

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

## Krok 2 — Scenariusz (checkpointy)

Graj turami (`python3 ../game-test/scripts/play_turn.py --campaign ID --character ID --message "..."`),
adaptując wiadomości do narracji. Każdy checkpoint odhacz z DOWODEM (nr tury + cytat narracji
LUB wynik SQL). Kolejność elastyczna — narracja prowadzi, checklist pilnuje.

| # | Checkpoint | Dowód (SQL przez ssh+docker exec, sqlite3 /data/ai_gm.db) |
|---|---|---|
| 1 | Otwarcie renderuje scenę; HUD HP/złoto/XP poprawne; **(Mag)** HUD mana widoczna, wartość = `current_mana/max_mana` ze `sheet_json` | screenshot + wartości vs `characters.sheet_json` |
| 2 | **Ruch hex ≥2×** ("idę na północ", "idę do [lokacja]") | `session_flags.current_hex` ZMIENIA SIĘ po turze ruchu |
| 3 | LLM używa lokacji Z BAZY (nie wymyśla) | klucz lokacji w `game_sessions.current_location_id` istnieje w `game_locations` z `ai_generated=0`; policz nowe `approved=0` po runie |
| 4 | Rozmowa z NPC przypisanym do lokacji | imię NPC z `location_npc_assignments`/`npc_keys` pojawia się w narracji |
| 5 | Quest: przyjęcie + widoczny postęp; karta rzutu umiejętności pokazuje **margines ±N** i **stopień sukcesu** (sukces krytyczny / sukces / porażka / porażka krytyczna) — S1 | wiersz w `character_quests`; margines widoczny w logach tury |
| 6 | **Walka: pełny cykl + model #826 + strefy T34 + reakcje SF10:** (a) baner walki ma kolumny **DYSTANS / ZWARCIE** i chipy inicjatywy 🏹/⚔; (b) atak melee na wroga w innej strefie → komunikat "poza zasięgiem", tura **NIE** spada; (c) Zbliż się / Cofnij się → tura spada, strefa zmieniona w `combatants`; (d) pancerz = redukcja obrażeń: `armor = max(0, ac_base−10)`, min 1 dmg na cios, Nat20 ignoruje pancerz; (e) margines ataku ≥5 pkt ponad obronę celu → +1 dmg bonus widoczny w odpowiedzi; (f) gdy wróg trafia gracza posiadającego skill `dodge`/`shield_block` → modal **Przyjmij / Unik / Blok** wyświetlony; (g) *(Warrior/Rogue z łukiem)* dystansowy atak konsumuje 1 strzałę z plecaka; po walce loot przyznany | HP przed/po z `active_combat.combatants`; `advance_turn` wywołany; `session_flags.combat` = null po końcu; wpis loot w `character_inventory`; ammo count spada o ≥1 |
| 7 | Gate: atak bez wroga w scenie → blok | tura "atakuję smoka" w karczmie → odmowa, brak walki |
| 8 | Sklep: kupno LUB sprzedaż ze zmianą złota = cena z katalogu; **(u rzemieślnika `is_crafter=1`)** cennik afiksów: reroll 100/350/700g, apply 150/500/1200g | delta złota w `sheet_json`; kwota = wartość z `game_config_items/weapons` lub cennika afiksów |
| 9 | Odpoczynek + wydanie XP; **(Mag)** alternatywna ścieżka: nauka nowego czaru lub upgrade rangi za XP (75/50/100 XP; ścieżka Zaklęcia, nie tylko skille) | zmiana XP/skill_rank/spell_rank w `sheet_json` |
| 10 | Zegar gry tyka, pora dnia się zmienia | `ingame_hours` rośnie między turami |
| 11 | *(tylko gotowa-kampania)* beat fabularny odpala | stan beatów/GM Plan w admin lub DB przed/po |
| 12 | **(Mag w walce)** Mana spada po rzuceniu czaru; **(Nat1)** miscast = mana tracona + komplikacja bez obrażeń za rzut; **(czar AoE)** trafienie wielokrotnych celów; po śmierci wszystkich wrogów walka kończy się | `sheet_json.current_mana` przed/po; wynik tury `route=spell_attack` lub `spell_effect`; N/D jeśli archetype ≠ scholar |
| 13 | Konsumpcja w walce: Akcja → Mikstura → picker → wypicie HP wzrasta + tura spada; mikstura znika z plecaka (lub N/D brak konsumpcji w ekwipunku) | HP w `combatants` przed/po; `character_inventory` count po turze; `advance_turn` wywołany |
| 14 | Spójność: narracja NIE twierdzi nic sprzecznego ze stanem | przegląd 15 tur; każda sprzeczność = defekt |

Screenshot (skrypt z `/game-screen`, procedura kopiowania jak w /game-test-player-screenshot
Step 7a) PO checkpointach: 1, 6, 9 — minimum 3 na run.

## Krok 3 — Defekty

Każde ❌ = issue:

```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE — <opis>" \
  --label "bug,smoke-defect,needs-testing" --body "<tryb, tura, oczekiwane vs faktyczne, SQL/screenshot>"
```

Priorytety: **P0** = scenariusz nieprzechodzalny (blokuje grę) · **P1** = psuje doświadczenie
(sprzeczność narracja↔stan, brak feedbacku, martwa mechanika, złe liczby obrażeń/cen) · **P2** = kosmetyka. Priorytet w tytule.

## Krok 4 — Raport

Komentarz do issue trybu (#512 lub #513):

```
## 🎮 game-smoke <tryb> — <data>
**Kampania:** id | **Bohater:** id | **Archetype:** warrior/scholar/rogue | **Tur zagranych:** N

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Checkpointy
| # | Checkpoint | Wynik | Dowód |
(14 wierszy: ✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
### Screenshoty (3+, z opisem co widać)
```

Po obu trybach: zaktualizuj notes.md wg wyniku — `[x]` TYLKO gdy oba runy ukończone
i wszystkie P0 zgłoszone.

## Gotchas

- Rate limit TPM → 502: czekaj 60 s; model `gpt-4.1-mini` w configu kampanii zmniejsza koszt.
- `route=skill_test`: wyślij "Staram się jak mogę." i kontynuuj; sprawdź czy margines widoczny.
- Dice popup w turach przez UI nie dotyczy play_turn.py (API path).
- **CP6b — strefa:** sprawdź `combatants[].zone` w `active_combat`; domyślne: Warrior→engaged, Scholar→ranged; wróg-łucznik→ranged.
- **CP6d — pancerz:** `armor = max(0, enemy.ac_base − 10)`; jeśli enemy.ac_base=12 → armor=2; cios za 5 dmg → min max(1, 5−2)=3 dmg. Nat20 = bez redukcji.
- **CP6f — reakcja SF10:** warunek pojawienia się modala: gracz ma skill `dodge` lub `shield_block` z rank ≥1 I wróg trafia (nie Nat1 wroga). Jeśli bohater nie ma tych skilli (brak w `sheet_json.skills`) → modal nie musi się pojawić → odnotuj w dowodzie.
- **CP12 (Mag):** `current_mana` spada o koszt czaru po rzucie; po mana=0 czary zablokowane. Miscast (Nat1 rzutu) = mana pełna tracona + komplikacja. Jeśli wróg oparł się czarowi nie-atakującemu → zwrot ½ many (D-spell model B7).
- Nie wymuszaj checkpointów łamiąc fikcję ("pokaż mi sklep NATYCHMIAST") — graj naturalnie;
  jeśli po 15 turach checkpoint nieosiągnięty organicznie → oznacz N/D z powodem, to też wynik.
