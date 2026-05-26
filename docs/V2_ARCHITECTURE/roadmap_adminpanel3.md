# Admin Panel v3 — Roadmap przeniesienia z v2

Panel v3 dostępny pod `/admin3/`. Panel v2 pozostaje niezmieniony pod `/admin2/`.

## Status

| # | Element | Priorytet | Złożoność | Status |
|---|---------|-----------|-----------|--------|
| P1 | Sekcja Mechaniki (stats/skills/DC/conditions/archetypes) | Wysoki | Średni | ✅ DONE |
| P2 | Zakładka Czary w Zawartości | Wysoki | Średni | ✅ DONE |
| P3 | Zakładka Tabele Łupów w Zawartości | Wysoki | Duży | ✅ DONE |
| P4 | Modal szczegółów kampanii (5 zakładek) | Wysoki | Duży | ✅ DONE |
| P5 | Sekcja Głos (Piper TTS) | Średni | Średni | ✅ DONE |
| P6 | Bank Pomysłów — pełna implementacja | Średni | Średni | ✅ DONE |
| P7 | Statystyki — pełne zakładki + wykresy | Średni | Duży | ✅ DONE |
| P8 | Sekcja System — pełna konfiguracja | Średni | Duży | ✅ DONE |
| P9 | Zakładki Świata: Wrogowie + Teren + Budowniczy | Niski | Średni | ✅ DONE |
| P10 | Per-user LLM settings w Graczach | Niski | Mały | ✅ DONE |

## Poza zakresem (osobne PR jeśli potrzebne)

- Zaproszenia (invites) — genealogia zaproszeń
- Wiedza (knowledge book)
- Projektant Kampanii (designer)
- REST Sandbox
- Email konfiguracja
- Visual settings

---

## Szczegóły implementacji

### P1 — Mechaniki
**Zakładki:** Statystyki | Umiejętności | DC | Kondycje | Archetypy  
**Endpointy:** `GET/POST/PATCH /api/admin/stats`, `/api/admin/skills`, `/api/admin/dc`, `/api/admin/conditions`, `/api/admin/archetypes`  
**UI:** Tabele z inline edit + modal dodawania + usuwania

### P2 — Czary (Zawartość)
**Endpointy:** `GET/POST/PATCH/DELETE /api/admin/spells`  
**UI:** Tabela z polami: klucz, label, szkoła, tier, koszt many, efekt

### P3 — Tabele Łupów (Zawartość)
**Endpointy:** `GET/POST /api/admin/loot-tables`, `GET/POST/DELETE /api/admin/loot-tables/{key}/entries`  
**UI:** Lista tabel + dwupanelowy edytor wpisów z wagami

### P4 — Modal kampanii
**Zakładki:** Przegląd | Plan GM | Tury | Mapa (hex) | Warsztat  
**Endpointy:** `/api/admin/campaigns/{id}/gm-plan`, `/turns`, `/hex-map`, `/workshop/*`  
**UI:** SVG hex grid z edit onClick, chat warsztatu, advance-scene button

### P5 — Głos
**Zakładki:** Status | Config | Głosy | TTS | STT  
**Endpointy:** `/voice/healthz`, `/voice/config`, `/voice/voices`  
**UI:** Toggles, selecty, health badge z live polling (30s)

### P6 — Bank Pomysłów
**Zakładki:** Warsztat AI | Bank  
**Endpointy:** `/api/admin/ideas/workshop/message`, `/api/admin/ideas/save`, `/api/admin/ideas` (GET/PATCH/DELETE)  
**UI:** Chat z AI + grid kart z ocenami i filtrami

### P7 — Statystyki
**Zakładki:** Przegląd | Kości | Walka | Ekonomia | Zdarzenia | LLM | MCP  
**Endpointy:** `/api/admin/analytics/{overview,dice,combat,economy,events,llm}?days=N`  
**UI:** Karty statystyk + wykresy (Canvas/CSS bars) + event log z filtrami

### P8 — System
**Zakładki:** Presety LLM | Baza danych | Konfiguracja | Komendy  
**Endpointy:** `/api/admin/llm/*`, `/api/admin/db/*`, `/api/admin/config/*`, `/api/admin/slash-commands`  
**UI:** Presets grid + DB stats + import/export + slash commands editor

### P9 — Świat (zakładki uzupełniające)
**Brakujące zakładki:** Wrogowie (move from Content → World), Teren, Budowniczy świata  
**Endpointy:** `/api/admin/enemies`, `/api/admin/hex-terrain-config`, world builder endpoints

### P10 — Per-user LLM
**Endpoint:** `GET/PUT /api/admin/accounts/{id}/llm-settings`  
**UI:** Modal w tabeli Graczy z selectem provider/model

---

*Ostatnia aktualizacja: 2026-05-25*
