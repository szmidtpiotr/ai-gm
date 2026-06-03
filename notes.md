# 📋 Wspólna notatka pracy — DEV_AIGM
_Aktualizowana na bieżąco przez agenta. Ostatnia aktualizacja: 2026-06-03 (sesja 2)_

---

## ✅ Naprawione (needs-testing)

| # | Fix | Commit |
|---|---|---|
| #253–261 | Security hardening | `c9a0c63`–`7bdd29c` |
| #238 | Session restore po logout | `d7f5219` |
| #327 | Łuk → ranged zone start | `a2f26cc` |
| #241 | Compound action → pełna narracja | `4410185` |
| #236 | Skill test narration fallback | `48e1c23` |
| #325 | Post-resurrection briefing | `be8103b` |
| #323 | Ally NPC w walce (backend) | `a098307` |
| #329 | Martwy bohater → ended kampania widoczna + death screen | `9096ef0` |
| **#330** | Combat ends jako `player_dead` gdy gracz umrze (nie `victory`) | `3a14d3a` |

**Duplikaty zamknięte:** #278, #279, #280, #282, #283, #285, #286, #326, #284, #281

---

## 🔴 Następne (priorytet)

| # | Prio | Opis |
|---|---|---|
| ~~#324~~ | MED | ✅ handleEnemyTurn → apiRequest (auth headers) `7a7ae5b` |
| **#328** | MED | Dwa testy pod rząd nieuzasadnione fabularnie |
| #239 | MED | Combat log widoczny po zalogowaniu |
| #240 | MED | Czas narracji rozmija się z czasem gry |
| #242 | MED | GM używa generic atmosphere |
| #243 | MED | NPC oznaczony jako enemy w pokojowej scenie |
| #251/#252 | MED | Narrative items w inventory |

---

## 📝 Pending
- **#323 frontend:** `current_turn = ally` → `POST /combat/ally-turn`

---

## ⚠️ Do weryfikacji na DEV
- Zaloguj/wyloguj → auto-restore (#238)
- Łuk → ranged zone start (#327)
- Złożona akcja → pełna narracja (#241)
- Skill test → GM odpowiada (#236)
- Wskrzeszenie → tura orientuje (#325)
- Zgon → ended kampania widoczna + death screen (#329)
- Walka: gracz umiera → `player_dead` nie `victory` (#330)
