# FAZA O — Observability + Mapa węzłów (architektura)

> **Jedna faza, dwa splecione tory.** Observability (logowanie zdarzeń gry, panel analityki,
> serwer MCP — pełny opis mechaniki w `08_OBSERVABILITY_AND_MCP.md`) ORAZ interaktywna mapa
> architektury kodu (`tools/archmap/`). Łączymy je celowo: mapa „heat-map" czyta dokładnie te
> same tabele (`game_events`, `llm_call_log`), które buduje observability, a serwer MCP może
> serwować mapę. Wspólny cron, wspólne źródło danych.
>
> **Kolejność:** PO FAZIE L (lochy). Nie blokuje FAZY 5 (MP) — może iść równolegle z
> przygotowaniem MP. Tor mapy (O6) można zacząć od razu, bo pilot już istnieje.

---

## Stan wyjściowy (2026-06-16)

- **Pilot mapy gotowy:** `tools/archmap/architecture-map.html` (podsystem Combat, 27 węzłów),
  generator nakładki z GitHub issues (`overlay/update_overlay.py` — przetestowany na żywym repo,
  24/105 issues dopasowane), strażnik driftu, stub heat-map. Instrukcja: `tools/archmap/INSTRUKCJA.md`.
- **Observability — spec gotowy, kod nie:** tabele `game_events`/`llm_call_log`, `event_logger.py`,
  panel „Statystyki i Logi", serwer MCP — wszystko rozpisane w `08_OBSERVABILITY_AND_MCP.md`, nic
  jeszcze nie wdrożone. Loki/Grafana/Prometheus już działają (logi systemowe), ale nie są świadome
  zdarzeń gry.

---

## Numbers Policy (wartości startowe — do strojenia testami)

| Parametr | Wartość startowa | Plan strojenia |
|---|---|---|
| `llm_call_log` retencja | 90 dni rolling | obserwuj wzrost pliku DB; jeśli >X MB/mies. skróć |
| `game_events` retencja | bez limitu (małe wiersze) | rewizja po 3 mies. realnych danych |
| heat-map okno | 7 dni (game_events), 30 dni (combat_turns) | dostrój gdy zobaczysz rozkład ruchu |
| cron overlay | raz na dobę 03:30 (obok backup_dev) | jeśli issues zmieniają się szybciej → częściej |
| heat „gorący" próg ramki | log10(calls) skala, max 6px | dostrój wizualnie po pierwszym realnym zaciągu |

---

## Tor 1 — Observability (rdzeń, z Phase 11)

### O1 — Tabele `game_events` + `llm_call_log` + `event_logger.py`
- **Cel:** struktura do zapisu zdarzeń gry i metryk LLM, bez udziału LLM w ścieżce logowania.
- **Dla agenta:** migracja wg DDL z `08_OBSERVABILITY_AND_MCP.md` (§Part 1). Nowy serwis
  `app/services/event_logger.py` z `write_game_event(...)` i `write_llm_log(...)`. Zapis
  synchroniczny, nigdy nie blokuje pętli gry (fire-and-forget dozwolone). Migracja nie-destrukcyjna.
- **Weryfikacja:** migracja przechodzi na kopii DEV DB; ręczny `write_game_event` wstawia wiersz;
  indeksy istnieją (`idx_game_events_type_date` itd.).

### O2 — Zapis zdarzeń z serwisów (combat, śmierć, beat, LLM)
- **Cel:** realne dane w tabelach z prawdziwej rozgrywki.
- **Dla agenta:** wepnij `write_game_event` w: `combat_service` (combat_start/victory/fled — przy
  istniejącym `log_combat_turn:2893`, to ten sam punkt), `solo_death_service` (player_death),
  `campaign_plan_runtime` (beat_complete), `llm_service` (każde wywołanie → `write_llm_log`).
  Payloady wg schematów z §Part 1.
- **Weryfikacja:** rozegraj walkę w Combat Sandbox → wiersze `combat_victory`/`player_death`
  pojawiają się; każde wywołanie LLM zostawia wiersz w `llm_call_log` z latency i cache_hit.

### O3 — Panel admina „Statystyki i Logi"
- **Cel:** admin widzi zachowanie graczy bez Grafany.
- **Dla agenta:** nowa sekcja modular admin (`frontend/admin/sections/`) + endpointy
  `GET /api/admin/analytics/{dashboard,events,llm,players,errors}` (§Part 2). Karty KPI + zakładki
  Aktywność / Zdarzenia / Wydajność LLM / Błędy.
- **Weryfikacja:** sekcja ładuje się, KPI niezerowe po O2, filtry zdarzeń działają, klik zdarzenia
  rozwija JSON.

### O4 — Serwer MCP
- **Cel:** Claude (i inne agenty) odpytują dane gry naturalnym językiem.
- **Dla agenta:** `mcp_server/server.py` (FastMCP), 9 narzędzi z §Part 3, serwis w
  `docker-compose.dev.yml` (read-only mount DB). Transport stdio (lub SSE jeśli zdalnie).
- **Weryfikacja:** O5.

### O5 — Test MCP z Claude Code
- **Cel:** potwierdzić, że narzędzia działają end-to-end.
- **Dla agenta:** podłącz serwer w ustawieniach MCP, przejdź 10 przykładowych zapytań z §Part 3
  (tabela „Example Queries").
- **Weryfikacja:** każde z 10 zapytań zwraca poprawne dane. Bez issue [TASK] — to playtest narzędzia.

---

## Tor 2 — Mapa węzłów (produkcjonizacja pilota)

### O6 — Mapa: cron overlay + (opcjonalnie) wydzielenie repo
- **Cel:** nakładka mapy odświeża się sama; tool gotowy do reużycia.
- **Dla agenta:** wpis cron na `.61` (obok `backup_dev`): `30 3 * * *` → `tools/archmap/overlay/refresh.sh`.
  Zweryfikuj, że `gh` ma dostęp do repo na hoście crona. (Wydzielenie do osobnego repo `archmap` —
  decyzja Piotra: „repo potem"; gdy zechce, instrukcja w `tools/archmap/README.md §Extracting`.)
- **Weryfikacja:** po nocy `map-overlay.json` ma świeży `generated_at`; mapa pokazuje aktualne kółka.

### O7 — Mapa: pozostałe podsystemy
- **Cel:** mapa pokrywa cały system, nie tylko combat.
- **Dla agenta:** dorysuj kolejne moduły jako oddzielne klastry/pliki HTML (lub jeden większy):
  turn-flow + seam LLM (prompt-assembly — to kręgosłup gry wg skilla), admin shell, world/locations,
  dungeons (FAZA L). Każdy wg metody ze skilla (`architecture-map.md`): czytaj pliki, potwierdzaj linie,
  surface martwy kod. Aktualizuj `node-map.json` o nowe ścieżki.
- **Weryfikacja:** `drift_check.py` (z poszerzonym SCOPE) → „OK"; każdy nowy węzeł ma prawdziwą linię.

### O8 — Mapa ↔ observability: pełna heat-map
- **Cel:** ramki węzłów kolorowane realnym ruchem/błędami z `game_events`/`llm_call_log`.
- **Dla agenta:** włącz źródła `_phase11` w `heat-source.json`; dodaj mapowania
  `event_type`/`call_type` → węzeł. Dodaj na mapie węzły observability (event_logger, panel
  analityki, serwer MCP, tabele game_events/llm_call_log). **Zależność: O1+O2.**
- **Weryfikacja:** chip „Heat-map (live)" pokazuje grubsze ramki na gorących węzłach; węzły z
  błędami czerwone; liczby zgadzają się z panelem z O3.

### O9 — (Opcjonalnie) MCP serwuje mapę
- **Cel:** „pokaż mapę modułu X" / „które węzły mają otwarte bugi" przez MCP.
- **Dla agenta:** narzędzie MCP `get_architecture_map(subsystem)` zwracające węzły+nakładkę z
  `map-overlay.json`; ewentualnie serwowanie HTML.
- **Weryfikacja:** zapytanie MCP zwraca węzły combat z liczbą otwartych zadań per węzeł.

### O10 — Mapa: interaktywny UX (pływające panele, popup issue, persist layout)
- **Cel:** mapa ma być wygodnym narzędziem przeglądowym — admin układa panele po swojemu i
  czyta treść zadań bez wychodzenia z mapy.
- **Stan (zrobione w pilocie 2026-06-16):**
  - Pasek filtrów (`#topbar`) = pływający panel, przeciągany za tytuł, pozycja w `localStorage`.
  - Popup zadania/buga: klik w wiersz → modal przeciągany za pasek nagłówka (`#pophead`, uchwyt
    ⠿ + ×), ładuje **body + komentarze issue na żywo** z GitHub API (public repo, bez tokenu),
    renderuje markdown; fallback do linku GitHub przy offline/limicie 60/h.
  - Sidebar nie znika po zabraniu myszki (utrzymany do kliknięcia w tło).
- **Dla agenta (do dokończenia):**
  - Przenieść te zachowania na pełną mapę po O7 (każdy nowy plik/klaster spójny z drag/persist).
  - Rozważyć ruchomy + zwijany sidebar i przycisk „Reset układu" (czyści `localStorage`).
  - Cache treści issue z TTL (np. 10 min) zamiast wyłącznie na czas sesji; przy ryzyku limitu API
    — opcja zaciągania body do `map-overlay.json` przy nocnym cronie (offline, kosztem rozmiaru pliku).
  - Sprawdzić zachowanie na wąskim ekranie (panele nie mogą uciec poza widok).
- **Weryfikacja:** panel filtrów i popup przeciągają się i zostają po odświeżeniu; popup pokazuje
  pełną treść issue + komentarze; „Reset układu" przywraca domyślne pozycje; nic nie ucieka poza
  ekran. Bez backendu — czysty frontend mapy (oznacz w issue „## Backend — No changes").

---

## Zależności

```
O1 ─► O2 ─► O3
        └──► O8 (heat-map pełna)
O2 ─► O4 ─► O5
O6 (mapa cron) — niezależne, można od razu
O7 (mapa reszta) — niezależne od observability
O8 — wymaga O1+O2
O9 — wymaga O4 + O8
O10 (mapa UX) — niezależne; część zrobiona w pilocie, reszta po O7
```

Sugerowana kolejność: **O6 → O1 → O2 → O3 → O8 → O4 → O5 → O7 → O10 → O9.**
(O6 daje natychmiastową wartość; O8 spina dwa tory; O10 po rozszerzeniu mapy O7; O9 na końcu.)

## Zasady żelazne (jak reszta projektu)

- Tylko DEV (.61). Nigdy PROD. Migracje nie-destrukcyjne (kolumny legacy zostają).
- Logowanie zdarzeń NIGDY nie woła LLM i nie blokuje tury.
- Dostęp do DB tylko przez SSH+docker (read-only do heat), nigdy przez sshfs (psuje SQLite).
- Każde wdrożenie [TASK] = issue wg szablonu #18 (sekcja `## Files changed` obowiązkowa — to ona
  zasila nakładkę mapy). Wyjątki bez issue: O5 (playtest MCP).
- Bump `?v=` przy zmianach shared modułów JS (panel analityki).
