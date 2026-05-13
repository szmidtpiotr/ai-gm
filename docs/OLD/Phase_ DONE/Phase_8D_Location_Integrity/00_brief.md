<!-- STATUS: DONE -->
<!-- PHASE: 8D | DATE_START: — | DATE_END: — -->

# Phase 8D — Location Integrity · Brief archiwalny

> Szczegóły w promptach `01`–15 oraz fixach `08`–11 w tym folderze.

---

## 1. Cel fazy

Spójność **lokalizacji** kampanii z narracją LLM: migracje schematu, parser intencji ruchu, hook w turach, walidator (w tym auto-create i pending approval), flagi w `game_config_meta`, panel admin (lokacje, log integrity, sesja).

---

## 2. Zakres (warstwy)

| Warstwa | Opis |
|---------|------|
| DB | `game_locations`, `location_integrity_log`, rozszerzenia sesji i meta |
| Backend | API lokacji, hook `_process_location_intent`, validator |
| Prompt | Reguły lokacji w system prompt (prompty LOC*) |
| Admin | Flagi, pending locations, session location |
| Testy | Pliki `test_phase8d_*` (opisane per prompt) |

---

## 3. Osiągnięcia

- Możliwość blokowania „nielegalnychs” ruchów z komunikatem do UI.
- Ŝieżka auto-tworzenia lokacji AI z przeglądem w panelu (wg implementacji opisanej w promptach).

---

## 4. Powiązania

- **Phase 9** — kontekst lokacji dla NPC i sklepu korzysta z aktualnej sesji / lokacji.

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodność z Briefem:** ✅ pełna — wszystkie 5 warstw (DB, backend, prompt, admin, testy) zrealizowane
- **Pokrycie testami:** `test_phase8d_*` per prompt; bardziej rozbudowane niż fazy 8A–8C — dobry wzorzec
- **Ryzyka i dług techniczny:**
  - `_process_location_intent` jako hook w turach — każda zmiana formatu odpowiedzi LLM może rozbić parser intencji; wymaga monitoringów w Loki
  - Auto-create lokacji AI — może generować śmieci w DB przy halucynacjach LLM; flaga pending approval jest odpowiednim zabezpieczeniem
  - `location_integrity_log` rośnie nieograniczenie — brak TTL / archiwizacji (do rozważenia przy dużych kampaniach)

### Decyzje przeniesione do kolejnych faz
- **Phase 9 NPC** — `npc_locations` korzysta z `game_locations.key` zdefiniowanego tutaj
- **Phase 9 Dialogue** — kontekst lokacji będzie częścią promptu dialogowego
- Czyszczenie `location_integrity_log` — kandydat na ops task

### STATUS: DONE
