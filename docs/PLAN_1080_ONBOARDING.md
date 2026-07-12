# Plan wdrożenia #1080 — Auto-onboarding (kampania wprowadzająca)

> Dokument dla agenta implementującego. Analiza wykonana 2026-07-11 na branchu `develop`.
> Issue: https://github.com/szmidtpiotr/ai-gm/issues/1080
> Zasada: NIE koduj niczego poza zakresem etapów E1–E6. Wszystkie wartości liczbowe to wartości startowe (numbers policy).

## 0. TL;DR decyzji architektonicznych

1. **Onboarding = ukryty szablon kampanii** w `campaign_templates` (`status='published'`, `player_visible=0`, `created_by='seed'`) — niewidoczny w "Gotowe kampanie", ale launchowalny przez backend po `template_id`.
2. **Szablon żyje w `data/seeds/content/campaign_templates.json`** (content-as-code, full-table-replace) — NIE w `14_campaign_templates.sql`, NIE jako code-seed w `migrations_admin.py`.
3. **Trigger = po utworzeniu pierwszego bohatera**, nie przy loginie (model hero-first: przy pierwszym loginie nie ma bohatera, więc nie ma do czego przypiąć kampanii). ŻAR po `finalize-sheet` woła nowy endpoint `POST /api/onboarding/start`, gdy user ma 0 kampanii.
4. **Warunek "nowy gracz" = `COUNT(*) FROM campaigns WHERE owner_user_id=? == 0`** (wszystkie statusy). NIE używamy `users.onboarded_at` — ta kolumna steruje bypassem weryfikacji e-mail (`auth.py:189-209`); dotknięcie jej może zablokować logowanie niezweryfikowanym userom.
5. **Flaga kampanii = istniejąca, uśpiona kolumna `campaigns.is_tutorial`** (migracja już jest: `main.py:332`; `POST /campaigns` już ją przyjmuje: `campaigns.py:271,818,830`). Trzeba ją tylko dodać do SELECT-a `GET /campaigns` i do typów ŻAR.
6. **Szybki finał**: 1 akt, 4 beaty — 2 krytyczne (rozmowa w karczmie + pierwsza walka), 2 opcjonalne (handel + eksploracja). Ending primary z `requirements: ["first_combat"]`.
7. **Skip** = przycisk w grze przy `is_tutorial=1`; archiwizuje kampanię i zwalnia bohatera (hero-first: `campaign_id=NULL`, `status='idle'`).

## 1. Kontekst — co już istnieje (fakty z researchu, file:line)

### Stary szablon "Pierwsze Kroki" (do odzyskania)
- Usunięty commitem `68d3419c` (2026-07-01, właśnie pod #1080). Pełny INSERT odzyskasz: `git show 68d3419c^:data/seeds/14_campaign_templates.sql`.
- Miał 1 arc, 3 beaty: `first_combat` (kill_enemy), `first_merchant` (talk_to_npc), `first_exploration` (visit_location, optional); ending primary `requirements:["first_combat"]`; `required_npc_keys: ["innkeeper_marta","blacksmith_goran"]`.
- Oba NPC nadal istnieją w `data/seeds/content/npcs.json` (innkeeper_marta id=2, blacksmith_goran id=4).

### Szablony i launch
- Tabela `campaign_templates`: schemat `migrations_admin.py:1016-1034`; dwie bramki widoczności: `status='published'` **i** `player_visible=1` (kolumna dodana `migrations_admin.py:405`).
- Lista graczowa "Gotowe kampanie": `GET /api/campaign-templates` → `adventure_forge.py:2289-2340`, filtr `status='published' AND COALESCE(player_visible,1)=1` (linie 2296-2299). **`player_visible=0` ukrywa automatycznie.**
- Launch z szablonu: `POST /api/campaigns` → `create_campaign`, `campaigns.py:797-878`. Ładuje plan `WHERE id=? AND status='published'` (linie 806-814) — **NIE sprawdza `player_visible`**, więc ukryty szablon jest launchowalny (zweryfikuj testem). Kopiuje `gm_plan_json` verbatim, bumpuje `play_count`, stempluje `source_template_id` (844-847), seeduje narrative state (852-856).
- Przypisanie bohatera: `POST /api/characters/{id}/assign-campaign` → `characters.py:1481-1596` (session, reset HP, start hex przez `resolve_starting_hex`).
- Plan szablonu jest **autorytatywny i nigdy nie regenerowany** w runtime: `turns.py:3351-3399` — pierwsza tura tylko `generate_opening_scene()`. Wniosek: plan w seedzie musi być kompletny od razu.

### Beaty / finał
- Enum `objective_type` = `{kill_enemy, visit_location, talk_to_npc, find_item}` (`campaign_plan_runtime.py:607`). Puste `objective_value` = wildcard (dowolny cel pasuje) — `auto_complete_beats_by_event`, `campaign_plan_runtime.py:885`.
- talk_to_npc: `auto_complete_talk_to_npc` (`campaign_plan_runtime.py:960`) — przycisk `dialogue_npc_key` → token-match względem `location_npc_assignments` → fallback #1300.
- Finał: `maybe_complete_campaign` (`campaign_plan_runtime.py:259`) otwiera bramkę `finale_available=1` gdy wszystkie akty complete (= wszystkie **nie-opcjonalne** beaty visited) **oraz 0 aktywnych main questów**. Gracz kończy przez `POST /campaigns/{id}/finish` (`campaigns.py:933`).
- Walidator publikacji: `validate_winnable_plan` (`campaign_plan_runtime.py:729`) — ≥1 ending `primary`, brak orphan beats, każdy akt ≥1 zamykalny beat krytyczny. Plan onboardingu musi go przechodzić.

### ŻAR (frontend/front-v2/)
- Po loginie zawsze `/bohaterowie` (`Login.tsx:24-28`); brak jakiejkolwiek gałęzi onboardingowej.
- Kreator bohatera: `CreateCharacter.tsx`, finalizacja → `POST /characters/{id}/finalize-sheet`, potem nawigacja `currentCampaignId ? /gra/:id : /bohaterowie/:heroId/kampanie` (linie 252-253). **To jest punkt wpięcia triggera.**
- Lista kampanii: `GET /campaigns` (`useGameData.ts:64`) — backend `campaigns.py:281-311` **nie zwraca `is_tutorial`** (SELECT bez tej kolumny). Filtrowanie client-side: `Campaigns.tsx:106-117`, `Heroes.tsx:99-110` (dokładnie 1 aktywna kampania → auto-wejście do `/gra/:id` — onboarding skorzysta z tego naturalnie).
- Wzór badge na karcie kampanii: `ActiveCampaignCard`, `Campaigns.tsx:394-397` ("Mglista przygoda…").

### Seedy (content-as-code)
- `campaign_templates` **jest na liście full-table-replace** (`scripts/content_seed_lib.py:55`); deploy odpala `scripts/seed_content.py --apply` (`deploy_dev.sh:45-47`) PO migracjach. Dlatego jedyne trwałe źródło szablonu to `data/seeds/content/campaign_templates.json` — wiersz dodany gdziekolwiek indziej zostanie wyczyszczony przy deployu.
- Mapa świata: Marta przypisana m.in. do `trzech_krukow` = "Karczma Pod Trzema Krukami", hex **(23,23)** z etykietą w `docs/world/world_map_seed.json`. Goran → `vilnograd_stolica` (inna lokacja!). "Vilnograd" NIE istnieje jako etykieta na mapie seedowej.

## 2. Analiza wariantów (dlaczego tak)

| Wariant | Werdykt | Powód |
|---|---|---|
| A. Auto-create kampanii przy pierwszym loginie (czysto backend) | ODRZUCONY | Hero-first: przy pierwszym loginie user nie ma bohatera; kampania bez bohatera = martwy wiersz + zepsute auto-enter w Heroes. |
| B. Hardcoded `mode='onboarding'` bez szablonu | ODRZUCONY | Duplikuje całą maszynerię template (plan autorytatywny, start anchor, source_template_id, Story Gravity). Szablon + `is_tutorial` daje to samo taniej. |
| C. Ukryty szablon + jawny endpoint startu + trigger w ŻAR po kreatorze bohatera | **WYBRANY** | Reuse 100% istniejącej ścieżki launch; jeden nowy endpoint; UI wpina się w naturalny moment (świeży bohater, zero kampanii); "Pomiń" trywialne. |

## 3. Etapy implementacji

### E1 — Szablon seed (JSON)
Plik: `data/seeds/content/campaign_templates.json` (dopisz wiersz; nie ruszaj istniejących — uwaga, "Przeklęte Ziemie" ma tam `status:"draft"`, to celowe/istniejące dane).

- Baza: odzyskany plan z `git show 68d3419c^:data/seeds/14_campaign_templates.sql`, przepisany na kształt V2 "acts" (wzór: wiersz "Przeklęte Ziemie" w tym samym JSON-ie).
- Zawartość planu (1 akt "Pierwsze kroki", 4 beaty — mapowanie na 4 sceny z issue):

| beat_key | objective_type | objective_value | optional | Scena z issue |
|---|---|---|---|---|
| `tavern_talk` | talk_to_npc | `innkeeper_marta` | false | 1. Karczma — chat/narracja |
| `first_combat` | kill_enemy | `""` (wildcard — dowolny kill) | false | 2. Bójka — walka/HP/kości |
| `first_merchant` | talk_to_npc | `blacksmith_goran` | true | 3. Rynek — sklep/złoto |
| `first_exploration` | visit_location | `""` (wildcard) | true | 4. Wyjście — mapa/hex |

- `endings`: 1 × primary, `requirements: ["first_combat"]`, tytuł "Gotów na przygodę".
- Kolumny wiersza: `difficulty_rating=1`, `status="published"`, `player_visible=0`, `created_by="seed"`, `required_npc_keys=["innkeeper_marta","blacksmith_goran"]`, `required_beats` = 4 klucze beatów.
- `key_npcs`: Marta + Goran. `key_locations`: lokacja startowa = **karczma `trzech_krukow`** (istnieje, Marta przypisana, hex 23,23 na mapie). `start_hex_q=23, start_hex_r=23` — **zweryfikuj** faktyczny hex lokacji `trzech_krukow` w `game_locations` / `world_hexes` zanim wpiszesz.
- **NPC-y muszą być osiągalne w lokacji startowej**: Goran siedzi w `vilnograd_stolica`. Dodaj wiersz w `data/seeds/content/location_npc_assignments.json` przypisujący `blacksmith_goran` (resident/visitor) do `trzech_krukow` — inaczej scena handlu nie zadziała token-matchem.
- `rewards`: brak w v1 (`reward_key: null` wszędzie) — bez kręgosłupa nagród (#1301), za dużo maszynerii jak na tutorial. Złoto wpadnie naturalnie z lootu.
- `key_enemies`: puste — wildcard kill + encounter_service wystarczą; NIE materializujemy wrogów (to i tak dzieje się tylko w torze Kuźni/Nowej Kampanii).
- Sanity: sprawdź, że JSON-owy seed niesie kolumnę `player_visible` (dump nie pokazał końcówki wiersza) — jeśli `content_seed_lib` jej nie obsługuje, dodaj.
- Plan MUSI przejść `validate_winnable_plan` — dodaj do testów (E6).

### E2 — Endpoint startu (backend)
Nowy `POST /api/onboarding/start` (proponowane miejsce: `backend/app/api/campaigns.py` albo mały `backend/app/api/onboarding.py` + rejestracja w `main.py`).

- Auth wymagane; body `{character_id}`; walidacja: bohater należy do usera.
- Bramka: `SELECT COUNT(*) FROM campaigns WHERE owner_user_id=?` — jeśli >0 → `409` (spełnia acceptance "istniejący gracz nie dostaje ponownie"; skip/porzucenie zostawia wiersz, więc nie ma re-triggera).
- Lookup szablonu: po stałej (np. `WHERE created_by='seed' AND title='Pierwsze Kroki' AND status='published'`) — stała w jednym miejscu w kodzie.
- Wykonanie: **reużyj istniejących funkcji, nie kopiuj logiki** — ścieżka `create_campaign` (z `template_id`, `is_tutorial=1`, `mode='solo'`, `language='pl'`, tytuł np. "Wprowadzenie — Pierwsze Kroki") + `assign_hero_to_campaign`. Najprościej wywołać te same funkcje serwisowe/handlery wewnętrznie w jednej transakcji.
- Zwrot: `{ok, campaign_id}`.

### E3 — Trigger + widoczność w ŻAR
- `CreateCharacter.tsx` (finalizacja, ~linia 252): jeśli user nie ma żadnych kampanii (dane z `useCampaigns`, filtr `owner_user_id === user.id`) → `POST /onboarding/start` → `navigate('/gra/'+campaign_id)`. Błąd endpointu → fallback do obecnej nawigacji (nie blokować kreatora!).
- Backend: dodaj `is_tutorial` do SELECT-a `GET /campaigns` (`campaigns.py:286-311`).
- ŻAR: `Campaign` type (`lib/types.ts`) + `useCampaigns` + badge "Wprowadzenie" na karcie (`Campaigns.tsx`, wzór badge z linii 394-397).
- Auto-wejście z ekranu bohaterów działa bez zmian (1 aktywna kampania → prosto do gry, `Heroes.tsx:99-110`).

### E4 — "Pomiń wprowadzenie"
- Przycisk w widoku gry (`/gra/:id`), widoczny gdy `campaign.is_tutorial` (agent znajdzie właściwe miejsce w HUD/menu gry; modal potwierdzający).
- Backend: **najpierw sprawdź, czy istnieje graczowy endpoint porzucenia kampanii** (statusy `discarded/archived` w `isActiveStatus`, `Campaigns.tsx:52`, sugerują że tak). Jeśli jest — reuse. Jeśli nie — `POST /campaigns/{id}/skip-tutorial`: `status='archived'`, `ended_at=now`, zwolnienie bohatera (`characters.campaign_id=NULL, status='idle'` — wzór hero-first z delete-campaign).
- Po skip: `navigate('/bohaterowie/'+heroId+'/kampanie')` — pełny wybór normalnej rozgrywki.

### E5 — Ukrycie z "Gotowe kampanie"
- Zero kodu: `player_visible=0` załatwia filtr `adventure_forge.py:2296-2299`. Pokryj testem (GET `/api/campaign-templates` nie zawiera szablonu) + testem, że launch po `template_id` MIMO TO działa.

### E6 — Testy i weryfikacja
- `backend/tests/test_issue1080_onboarding.py` (iteracja przez `docker cp`, bez rebuildu; NIE odpalać pełnej suity):
  1. świeży user + bohater → `start` tworzy kampanię: plan == plan szablonu, `is_tutorial=1`, `source_template_id` ustawione, bohater przypisany;
  2. user z jakąkolwiek kampanią (dowolny status) → 409;
  3. szablon nieobecny w `GET /api/campaign-templates`;
  4. plan szablonu przechodzi `validate_winnable_plan`;
  5. skip: status kampanii terminalny + bohater zwolniony;
  6. beat-happy-path: event `talk_to_npc innkeeper_marta` + `kill_enemy` cokolwiek → oba krytyczne beaty visited → `finale_available=1`.
- Playwright spec w `ai_test_agent/playwright/` (bind-mount, żywy bez rebuildu): rejestracja → kreator bohatera → auto-wejście do gry → badge "Wprowadzenie" → skip → lista kampanii.
- Smoke ręczny (styl `/game-test-player`): 6–10 tur — rozmowa z Martą, sprowokowanie bójki, zakup u Gorana, wyjście z karczmy; sprawdź `finale_available` i modal finału. Cel czasowy ≤20 min ≈ 8–12 tur (wartość startowa).
- Rebuild backendu przy zmianach Pythona: `docker compose -f docker-compose.dev.yml up -d --build backend` na `.61`; ŻAR: `sudo npm run build` w `frontend/front-v2` na `.61`.
- Issue implementacyjne wg szablonu #18 (labels `enhancement`+`needs-testing`+`review` — zmiana graczowa/wizualna, kolejka Piotra).

## 4. Ryzyka / GOTCHAs (przeczytaj przed kodowaniem)

1. **Full-table-replace**: `campaign_templates` seeduje się z JSON-a z wymianą całej tabeli przy każdym deployu (`content_seed_lib.py:55`). Jedyne źródło = `content/campaign_templates.json`. Wiersz dodany SQL-em/kodem zniknie.
2. **`users.onboarded_at` — nie dotykać.** Steruje bypassem weryfikacji e-mail (`auth.py:189-209`); automatyczne stemplowanie może wywołać 403 przy drugim loginie niezweryfikowanego usera.
3. **`world_hexes` map_level=0 = własność Piotra.** Wolno tylko linkować do ISTNIEJĄCEGO hexa istniejącej lokacji (`trzech_krukow`). Żadnych nowych hexów, żadnego wipe/reseedu. Jeśli okaże się, że lokacja nie ma hexa — wybór osady startowej zatwierdza Piotr.
4. **Finał wymaga 0 aktywnych main questów.** Narrator może dopisać quest w trakcie tutorialu → bramka finału się nie otworzy mimo beatów. Smoke test MUSI to sprawdzić; mitygacja: premise/atmosphere planu instruuje "krótka przygoda, bez wątków pobocznych" (fallback #1300 też może uratować).
5. **Goran nie siedzi w karczmie startowej** — bez nowego wiersza w `location_npc_assignments.json` scena handlu nie zamknie beatu token-matchem.
6. **Launch nie sprawdza `player_visible`** (tylko `status='published'`) — to jest fundament rozwiązania; jeśli ktoś kiedyś doda ten filtr do `create_campaign`, onboarding padnie. Przybij testem (E6.1 + E5).
7. **`GET /campaigns` zwraca wszystkie kampanie wszystkich userów** (filtracja client-side) — dodanie `is_tutorial` do SELECT jest bezpieczne, ale nie próbuj przy okazji "naprawiać" filtracji (osobny temat, poza zakresem).
8. **`template_id` vs `source_template_id`**: solo-launch zostawia `template_id` NULL, stempluje `source_template_id` (`campaigns.py:844-847`). Testy mają sprawdzać `source_template_id`.
9. Wildcard `kill_enemy` = KAŻDY kill zamyka beat — zamierzone (tutorial), nie "naprawiać".
10. Wszystko frontendowe TYLKO w ŻAR (`frontend/front-v2/`); `frontend/front/` zamrożony.

## 5. Mapowanie na acceptance z issue

| Acceptance | Pokrycie |
|---|---|
| Nowy gracz po rejestracji → auto-kampania onboardingowa | E2+E3 (trigger po kreatorze bohatera — jedyny spójny moment w modelu hero-first) |
| Nie pojawia się w "Gotowe kampanie" | E1 `player_visible=0` + test E5 |
| Przejście ≤20 min | E1 (2 beaty krytyczne, ending od `first_combat`) + smoke E6 |
| 4 sceny (NPC, walka, sklep, mapa) | E1 (4 beaty; sklep i mapa opcjonalne, ale obecne w planie i narracji) |
| Istniejący gracz nie dostaje ponownie | E2 bramka COUNT(campaigns)>0 → 409 |
| "Pomiń" działa, nie blokuje gry | E4 (archiwizacja + zwolnienie bohatera → normalny wybór kampanii) |

## 6. Szacunek zakresu

- Backend: ~3 pliki (`campaigns.py` lub nowy `onboarding.py`, `main.py` rejestracja, ewent. helper skip) + 1 plik testów.
- Seedy: 2 pliki JSON (`campaign_templates.json`, `location_npc_assignments.json`).
- ŻAR: ~5 plików (`CreateCharacter.tsx`, `Campaigns.tsx`, widok gry — przycisk skip, `useGameData.ts`, `lib/types.ts`).
- Zero migracji DB (kolumna `is_tutorial` już istnieje). Zero zmian w locked mechanics.
