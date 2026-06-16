# Panel „Statystyki i Logi" — przewodnik (FAZA O, Observability)

Prostym językiem: **gdzie to jest, co w każdej zakładce, do czego służy, czego szukać i jakie problemy obserwować.**

Sekcja powstała w zadaniu **O3 (#705)**. Plik frontendu: `frontend/admin/sections/analytics.js`. Dane bierze z tabel `game_events` i `llm_call_log` (zasilanych przez `event_logger.py` z O1/O2). Endpointy backendu pod `/api/admin/analytics/*`.

---

## Jak wejść

Admin Panel (`/admin/`) → w bocznym menu sekcja **„Statystyki i Logi"**.

Na górze przycisk **⟳ Odśwież** — przeładowuje KPI + aktywną zakładkę (dane NIE odświeżają się same, klikasz ręcznie).

---

## Pasek KPI (zawsze na górze, nad zakładkami)

Cztery kafelki — szybki stan zdrowia gry w jednym rzucie oka. Źródło: `GET /api/admin/analytics/dashboard`.

| Kafelek | Co pokazuje | Do czego | Czego szukać / problem |
|---|---|---|---|
| **Aktywne kampanie** | ile kampanii ma status aktywny | puls projektu — czy ktoś gra | 0 przy spodziewanym ruchu = gracze nie wchodzą / coś blokuje wejście |
| **Tury dziś** | liczba tur narracyjnych dzisiaj | ile realnej gry się dzieje | nagły spadek do 0 mimo aktywnych kampanii = gra się wiesza na turze |
| **Avg LLM latency** | średni czas odpowiedzi LLM | czy model odpowiada szybko | > 3s = gra „muli", gracz czeka; rośnie z dnia na dzień = provider/model do zmiany |
| **Błędy 24h** | liczba błędów w ostatniej dobie | alarm | **liczba na czerwono = są błędy.** Każda > 0 → idź do zakładki **Błędy** |

> Kafelek Błędy świeci **zielono = 0**, **czerwono = >0**. To pierwsze co sprawdzasz wchodząc.

---

## Zakładka 1 — „Aktywność graczy"

Źródło: `GET /api/admin/analytics/players`. Ładuje się domyślnie po wejściu.

Tabela: **Gracz | Postać | Kampania | Ostatnia aktywność | Tury | Śmierci**.

- **Do czego:** kto teraz gra, czyją postacią, jak dawno wykonał turę, ile tur ma na koncie, ile razy zginął.
- **Czego szukać:**
  - „Ostatnia aktywność" = `przed chwilą` / `X min temu` — kto jest online realnie.
  - Wysoka kolumna **Tury** = zaangażowany gracz.
  - Kolumna **Śmierci** — kto ciągle ginie.
- **Problemy do obserwowania:**
  - Gracz z dużą liczbą tur i **0 śmierci** przez długi czas → walka może być za łatwa (balans).
  - Gracz z wysokimi **Śmierciami** względem tur → za trudno albo bug w walce.
  - „Ostatnia aktywność" sprzed wielu godzin przy „aktywnej" kampanii → ktoś porzucił sesję w połowie (utknął?).
  - Pusta tabela („Brak aktywnych graczy") mimo że ktoś gra → event_logger nie zapisuje aktywności.

---

## Zakładka 2 — „Zdarzenia gry"

Źródło: `GET /api/admin/analytics/events` (limit 50). Surowy strumień wszystkiego, co gra zaloguje.

Filtry u góry:
- **typ zdarzenia** (pole tekstowe, np. `player_death`, `combat_victory`),
- **Severity** (dropdown: debug / info / warning / error),
- **campaign_id** (pole liczbowe — zawęź do jednej kampanii),
- przycisk **Filtruj**.

Tabela: **Czas | Typ | Kampania | Severity | Dane**. Kolumna **Dane** ma rozwijane `JSON` (`<details>`) z pełnym payloadem zdarzenia.

Ikony typów (szybkie rozpoznanie): ⚔ walka start/wygrana · 🏃 ucieczka · 💀 śmierć gracza · 📖 beat fabuły · 😱 strach · ✨ miscast (magia) · 💚/🖤 rzut na śmierć udany/nieudany · ⭐ XP · 🔴 błąd LLM · 🗝 loch wyczyszczony.

- **Do czego:** dochodzenie „co się stało" w konkretnej kampanii/turze. Kolejność chronologiczna, klikasz JSON żeby zobaczyć szczegóły zdarzenia.
- **Czego szukać:**
  - Filtruj po `campaign_id` gdy gracz zgłasza buga — widzisz dokładnie sekwencję zdarzeń.
  - Severity = **warning** (bursztynowo) / **error** (czerwono) wyróżnione kolorem.
  - Filtr typu `miscast`, `player_death`, `fear_triggered` — sprawdzasz czy mechaniki odpalają się jak mają.
- **Problemy do obserwowania:**
  - Powtarzający się `miscast` / `death_save_fail` w jednej kampanii → mechanika magii/śmierci może być rozregulowana.
  - Brak spodziewanego zdarzenia (np. wygrałeś walkę, a nie ma `combat_victory`) → hook w serwisie nie emituje eventu.
  - Dużo `warning`/`error` jednego typu → systemowy problem, nie incydent.

---

## Zakładka 3 — „Wydajność LLM"

Źródło: `GET /api/admin/analytics/llm?period=…`. Czyta `llm_call_log`.

Przełącznik okresu (chipy): **24h / 7 dni / 30 dni**.

Dwie tabele obok siebie:

**Lewa — „Wg typu wywołania":** Typ | N | Avg | Cache
- **Typ** = rodzaj wywołania (narracja tury, podsumowanie, plan GM itd.),
- **N** = ile razy,
- **Avg** = średni czas,
- **Cache** = % trafień w cache (prompt caching).

**Prawa — „Najwolniejsze":** Typ | Latency | Błąd
- konkretne najwolniejsze wywołania; **Latency > 3s czerwone**; kolumna Błąd pokazuje komunikat jeśli wywołanie padło.

- **Do czego:** czy LLM jest szybki i tani. Który typ zapytania kosztuje najwięcej czasu, czy cache działa.
- **Czego szukać:**
  - Wysoki **Cache %** = dobrze (mniej płacisz, szybciej). Niski cache na częstym typie = okazja do prompt cachingu.
  - **N** pokazuje co gra woła najczęściej — tam optymalizacja daje najwięcej.
  - Prawa tabela = od razu widać najgorsze przypadki.
- **Problemy do obserwowania:**
  - **Avg** rośnie między 24h → 7d → 30d = provider degraduje albo prompt urósł.
  - **Cache 0%** na typie który powinien się cache'ować = caching nie działa / prompt zmienia się co wywołanie.
  - Wpisy z tekstem w kolumnie **Błąd** = wywołania LLM się wywalają (timeout / provider down / zły klucz).

---

## Zakładka 4 — „Błędy"

Źródło: `GET /api/admin/analytics/errors?limit=20`. To jest skrót do tego, co świeci na czerwono w KPI.

Tabela: **Czas | Źródło | Typ | Kampania | Detal**.
- **Źródło** = czerwona plakietka skąd błąd (który serwis/moduł),
- **Typ** = rodzaj zdarzenia błędu,
- **Kampania** = w której kampanii (lub —),
- **Detal** = komunikat.

- **Do czego:** jedno miejsce na wszystkie błędy z ostatniego czasu, bez grzebania w logach kontenera.
- **Czego szukać:**
  - **Czas** — czy błędy są świeże (dzieją się teraz) czy stare.
  - **Źródło** powtarzające się = jeden moduł sypie.
  - **Kampania** — czy błąd dotyczy jednej kampanii (lokalny) czy wielu (systemowy).
- **Problemy do obserwowania:**
  - Seria błędów z tym samym **Źródłem** w krótkim czasie → regresja, idź do tego serwisu.
  - `llm_error` często → patrz zakładka Wydajność LLM (provider).
  - Błędy bez `campaign_id` → problem infrastrukturalny (DB, migracja, start aplikacji), nie gameplay.

---

## Rytm pracy (jak tego używać codziennie)

1. Wejdź → spójrz na **KPI**. Kafelek **Błędy 24h** czerwony? → zakładka **Błędy**.
2. **Avg LLM latency** wysokie? → zakładka **Wydajność LLM**, sprawdź „Najwolniejsze".
3. Gracz zgłasza buga? → zakładka **Zdarzenia gry**, filtruj po jego `campaign_id`, czytaj JSON zdarzeń wokół momentu buga.
4. Sprawdzasz zaangażowanie / balans? → zakładka **Aktywność graczy** (tury vs śmierci).

> Dane nie odświeżają się same — klikaj **⟳ Odśwież** żeby pobrać aktualny stan.

---

## Powiązania (FAZA O)

- Te same tabele (`game_events`, `llm_call_log`) zasilają **mapę architektury** — chip „Heat-map (live)" w `tools/archmap/architecture-map.html` (grubsza ramka = więcej ruchu, czerwona = błędy). Patrz `tools/archmap/INSTRUKCJA.md`.
- Te same dane są też dostępne dla agenta przez **serwer MCP** (`mcp_server/server.py`, O4): narzędzia `query_game_events`, `get_llm_performance`, `get_player_stats`, `get_error_log`, `get_system_health` — czyli to, co widać w panelu, mogę odpytać programowo.
- Pełny spec fazy: `docs/V2_ARCHITECTURE/22_FAZA_O_OBSERVABILITY_ARCHMAP.md`.
</content>
</invoke>
