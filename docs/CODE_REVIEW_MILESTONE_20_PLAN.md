# Code Review — Milestone #20 — Plan naprawczy i instrukcje wdrażania

Audyt: 2026-07-04. Milestone: [#20 code-review](https://github.com/szmidtpiotr/ai-gm/milestone/20). Issues: **#1154–#1188** (35 szt.).

Ten dokument mówi: **w jakiej kolejności naprawiać, co spinać w jedną sesję, jak testuję każdą partię, jak wdrażać na DEV.** Śledzenie postępu = same issues (label `needs-testing` = czeka na weryfikację wizualną, zamknięcie po sprawdzeniu na DEV).

---

## Zasada ogólna: jedna sesja = jedna spójna partia

Nie każde issue osobno (za drobne, dużo narzutu) i nie wszystko naraz (nie da się testować). Grupowanie po **wspólnym pliku / wspólnym mechanizmie / wspólnym teście**. Każda sesja: issue → fix → mój test → update issue (SHA + `needs-testing`) → STOP + raport po polsku. Ty potem drążysz przez RSS/issue i akceptujesz.

Każda partia dostaje **jeden pytest** (mechanika) i, gdy dotyka UI, **jeden Playwright/game-test** (to co API nie widzi). Nie odpalam pełnego suite (8–9 min, dużo pre-existing faili) — tylko pliki danej partii.

---

## Kolejność fal (twarde zależności)

```
FALA 1  Security          →  FALA 2  Fundament migracji  →  FALA 3  Gameplay P1
(gołe routery, leak,          (schema_migrations —            (bugi tur/combat/gold)
 XSS, double-mount)            kasuje klasę replay/clobber)
                                       │
FALA 4  Cleanup martwy kod  ←──────────┘         FALA 5  Feature'y + twardnienie
(po fali 2, żeby nie                             (NPC/lobby/podgląd/lock/auth-layer)
 kasować rzeczy w trakcie ruchu)
```

Fundament (F2) przed gameplayem (F3), bo część bugów gameplay to skutek replay migracji. Cleanup (F4) po F2, żeby nie ruszać martwego kodu który migracje jeszcze dotykają.

---

## SESJA 1 — Security P0 (gołe routery + leak)
**Issues:** #1154 (routery bez auth), #1155 (leak api_key), #1156 (double-mount + auth characters), #1174 (push.js XSS)
**Razem?** #1154+#1155+#1156 jedna sesja (wspólny mechanizm: auth na routerach, backend). #1174 osobno lub doklejone (frontend, inny plik).
**Mój test:** pytest — dla każdego dotkniętego endpointu: bez tokena → 401/403, z tokenem → 200. Curl żywy na `:8100` powtórzony (był 200, ma być 401). Dla #1174: pytest że render escapuje `<script>` w username.
**Uwaga:** to nie zmienia zachowania panelu z tokenem — po fixie przejść panel admina, wszystkie sekcje mają ładować dane.

## SESJA 2 — Fundament migracji (najważniejsza)
**Issues:** #1162 (replay nadpisuje edycje admina), #1163 (świeża DB 2 restarty + brak wersjonowania), #1164 (podwójny seed meta), #1165 (indeks campaign_turns), #1166 (backup.sh zły plik)
**Razem?** #1162+#1163+#1164 JEDNA sesja — wszystkie rozwiązuje `schema_migrations` (applied-set) + zmiana seedów na `INSERT OR IGNORE`. #1165 doklejony (jedna migracja indeksu). #1166 osobno (skrypty bash).
**Mój test:** pytest na kopii DB — (a) uruchom migracje 2× z rzędu, edycja admina (waga lootu, rank_ceiling) PRZETRWA drugi przebieg; (b) świeża pusta DB → jeden przebieg → schemat kompletny (wszystkie kolumny z RAW obecne, zero "no such table" w logu). **Walidacja względem kopii PROD-shaped** (pamięć: migracje testować na kopii prod, nie tylko świeżej DEV).
**To jest zmiana wysokiego ryzyka** — pełny backup DB DEV przed, i osobny przegląd przez Ciebie zanim tknie PROD.

## SESJA 3 — Gameplay P1 backend
**Issues:** #1157 (/move zły wiersz), #1158 (sell_item atomowość), #1159 (gold_at_end), #1160 (AoE obrona #826), #1161 (hazard)
**Razem?** Podział po pliku:
- 3a: #1157 + #1159 (oba dotyczą złej referencji sesji/kolumny — turn_commands + kronika)
- 3b: #1158 + #1161 (oba transakcje złota — shop_service + gambling; wspólny wzorzec atomowości)
- 3c: #1160 osobno (combat_service, wymaga weryfikacji w Sandbox)
**Mój test:** pytest per partia. #1160 dodatkowo: Sandbox (reużywa produkcyjny engine — patrz CLAUDE.md) — AoE na cel w zbroi ma być zredukowany. #1159: pełne przejście kampanii → `gold_at_end` == realne złoto, nie 0.

## SESJA 4 — API/routery P1
**Issues:** #1167 (workshop niezarejestrowany → patrz decyzja #1188), #1168 (dublet tras), #1169 (martwe wywołania admin), #1170 (Scholar /api/spells), #1171 (Enter double-turn front)
**Razem?** #1167+#1188 razem (decyzja: Warsztat restore = register, Bank retire = usuń). #1168 osobno (rejestracja). #1169 osobno (frontend admin, 4 wywołania). #1170 osobno (frontend player). #1171 → patrz sesja 7 (spięte z backend lockiem #1186).
**Mój test:** #1167 pytest że `/workshop/message` odpowiada 200 po register; #1170 game-test-player Scholar: modal Awansuj pokazuje zaklęcia + nauka działa; #1169 curl że naprawione ścieżki dają 200/poprawną metodę.

## SESJA 5 — Frontend P1 reszta
**Issues:** #1172 (JWT stale token), #1173 (MP Enter resubmit)
**Razem?** Osobno (różne pliki), ale jedna sesja czasowo.
**Mój test:** #1172 — wymusić wygaśnięcie tokena, potem recap/journal/bugreport → nie 401. #1173 game-smoke-mp: Enter podczas narracji nie resubmituje rundy.

## SESJA 6 — Cleanup martwy kod (partiami, przez /cleanup)
**Issues:** #1175 (backend), #1176 (player), #1177 (admin), #1178 (DB kolumny/endpointy), #1179 (infra drift), #1180 (test fixtures)
**Razem?** KAŻDE osobno — cleanup to seria małych git-izolowanych partii z kwarantanną (skill `/cleanup` tego pilnuje: static → adversarial proof → approval → pytest+smoke+trace). NIE kasować DB tabel.
**Mój test:** skill `/cleanup` ma własne bramki (pytest + smoke + runtime trace + kwarantanna). Ja tylko odpalam per partia i raportuję co usunięte.
**Uwaga:** #1176 i #1184 (restore lobby) NACHODZĄ — `tryRestoreLobbySession` jest na liście martwego kodu ALE robimy z niego feature. Zrobić #1184 PRZED #1176, żeby nie skasować. Tak samo `showCurrentTileImageModal` (#1185 przed #1176) i `increment_npc_purchase_count` (#1183 przed #1175).

## SESJA 7 — Feature'y + twardnienie (zatwierdzone)
**Issues:** #1183 (NPC pamięta zakupy), #1184 (restore lobby), #1185 (podgląd pokoju), #1186 (backend turn-lock), #1187 (auth-layer)
**Razem?** Każdy feature osobno (różne systemy). #1186 spięty z #1171 (jedna spójna ochrona podwójnej tury: front guard + back lock — zrobić razem). #1187 PO sesji 1 (najpierw punktowe łaty, potem warstwa).
**Kolejność wewn.:** #1184/#1185/#1183 przed sesją 6 cleanup (patrz wyżej). #1186+#1171 razem. #1187 na końcu.
**Mój test:** per issue — pytest + odpowiedni smoke (mp/dungeon/player) jak w treści każdego issue.

---

## Forma moich testów — ściąga

| Typ zmiany | Mój test |
|---|---|
| Backend logika (combat, gold, migracje, auth) | `pytest tests/test_<obszar>.py` — tylko plik partii, przez `docker cp` bez rebuild |
| Combat/mechanika | + Sandbox (`/admin2/` ⚔) — reużywa produkcyjny engine |
| Endpoint (auth, dublety, martwe) | żywy `curl` na `:8100` — status przed/po |
| Player UI | `/game-test-player #NNN` (8–12 tur) lub `/game-smoke-pw` (UI-only mechaniki) |
| Multiplayer | `/game-smoke-mp` |
| Dungeon | `/game-smoke-dungeon` |
| Martwy kod | skill `/cleanup` (własne bramki + kwarantanna) |

Nigdy pełny suite — Ty go odpalasz manualnie per faza.

---

## Instrukcje wdrażania (per sesja, na DEV `.61`)

```bash
# 1. Branch roboczy (nigdy prosto na main)
ssh claude@192.168.1.61 'cd ~/ai-gm && sudo -u piotrszmidt git checkout develop && sudo -u piotrszmidt git pull'

# 2. Szybka iteracja TDD — docker cp bez rebuild (backend baked w image!)
docker cp backend/tests/test_<x>.py    ai-gm-dev-backend-1:/app/tests/test_<x>.py
docker cp backend/app/services/<y>.py  ai-gm-dev-backend-1:/app/app/services/<y>.py
ssh claude@192.168.1.61 'rtk docker exec ai-gm-dev-backend-1 pytest tests/test_<x>.py -v'

# 3. Gdy zielone — trwały deploy (backend code = MUSI --build)
ssh claude@192.168.1.61 'cd ~/ai-gm && docker compose -f docker-compose.dev.yml up -d --build backend'
# frontend: bind-mount, ale bump ?v= w importach; ngin.conf → restart kontenera (nie reload)

# 4. Weryfikacja
#    https://aigm-dev.studio-colorbox.com/  + konsola przeglądarki
#    dla migracji (sesja 2): BACKUP przed → ./scripts/backup.sh; sprawdź log startu na "no such table"

# 5. Commit + push (auto, develop, ref issue)
ssh claude@192.168.1.61 'cd ~/ai-gm && sudo -u piotrszmidt git add -A && sudo -u piotrszmidt git commit -m "fix(#NNN): <opis>" && sudo -u piotrszmidt git push'
#    potem: komentarz na issue z SHA + label needs-testing
```

**Ważne pułapki (z pamięci projektu):**
- Backend code jest **wpieczony w image** — `docker compose restart` NIE łapie zmian Pythona, trzeba `--build` (albo `docker cp` do iteracji).
- Testy w kontenerze: `/app/tests/`, nie `backend/tests/`.
- Prawdziwa baza DEV to `/data/ai_gm.db` (nie `ai_gm_dev.db` — 0 bajtów; to dokładnie bug #1166).
- Nigdy sshfs do SQLite — tylko `docker exec sqlite3`.
- PROD (`.62`/`main`) — nic bez jawnej zgody. Ten milestone to DEV.

---

## Decyzja: Warsztat vs Bank Pomysłów (#1188)

**Bank Pomysłów** (`ideas_workshop.py` → `campaign_ideas`, **0 wierszy**) — **pokryty przez Kuźnię**. Kuźnia (`adventure_forge.py`) ma nowszy pełny pipeline: chat → `adventure_ideas` (6 wierszy, żywe) → hooks → `campaign_templates` (4) → launch. → **RETIRE.**

**Campaign Warsztat** (`campaign_workshop.py` → patch `gm_plan_json` **żywej** kampanii) — **NIE pokryty.** Kuźnia rusza `gm_plan_json` tylko dla szablonu (pre-launch). Konwersacyjne łatanie planu działającej kampanii nie istnieje nigdzie indziej. → **RESTORE** (register w main.py, auth już w pliku).
