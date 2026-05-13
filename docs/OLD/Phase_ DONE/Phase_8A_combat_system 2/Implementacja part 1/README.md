# Cursor Prompts — Phase 8A Combat System

## Jak używać

1. Otwórz Cursor w projekcie `ai-gm`
2. Przejdź do pierwszego kroku (step_1.1_database_migration.txt)
3. **Skopiuj cały prompt** do Cursor chat
4. Cursor najpierw wykona **SAFETY CHECK** (sprawdzi blokery)
5. Jeśli nie ma problemów, Cursor zaimplementuje kod
6. Zweryfikuj **Acceptance Criteria** ręcznie lub przez testy
7. Przejdź do kolejnego kroku

---

## Kolejność wykonania (WAŻNE — dependency-aware)

### ETAP 1: Foundation
1. `step_1.1_database_migration.txt` — Tabela active_combat
2. `step_1.2_enemy_catalog_injection.txt` — Enemies w system prompt

### ETAP 2: Combat Initiation
3. `step_2.1_combat_start_detection.txt` — Wykrywanie [COMBAT_START:key]

### ETAP 3: Initiative & Turns
4. `step_3.1_initiative_system.txt` — Rzuty na inicjatywę
5. `step_3.2_turn_management.txt` — Zarządzanie turami

### ETAP 4: Attack Resolution
6. `step_4.1_player_attack.txt` — Atak gracza (z placeholderami)
7. `step_4.2_enemy_attack.txt` — Atak wroga

### ETAP 5: Combat UI
8. `step_5.1_enemy_turn_button.txt` — Przycisk "Tura wroga"

### ETAP 6: Combat End
9. `step_6.1_enemy_death_loot.txt` — Śmierć wroga + loot
10. `step_6.2_player_death.txt` — Śmierć gracza + death screen

### ETAP 7: Victory UI
11. `step_7.1_loot_popup.txt` — Popup z lootem

### ETAP 8: Testing
12. `step_8.1_e2e_testing.txt` — Testy end-to-end

---

## ⚠️ Ważne zasady

- **NIE PRZESKAKUJ kroków** — każdy krok zależy od poprzednich
- **Sprawdź SAFETY CHECK** zanim Cursor cokolwiek zmieni
- **Zweryfikuj Acceptance Criteria** po każdym kroku
- **Commituj do Git** po każdym ukończonym kroku
- **Testuj na bieżąco** — nie czekaj do końca z testami

---

## 📚 Pliki referencyjne

Cursor prompts odnoszą się do wygenerowanych plików:
- `active_combat_ddl.sql` — Schema tabeli
- `combat_resolver_example.py` — Przykładowy kod z placeholderami
- `phase8a_implementation_plan.md` — Pełny plan (ten dokument)

---

## 🐛 Jeśli coś pójdzie nie tak

1. **Cursor zgłasza blocker w SAFETY CHECK:**
   - Przeczytaj co znalazł
   - Zdecyduj: rozwiąż konflikt ALBO pomiń ten krok (jeśli konflikt jest OK)

2. **Acceptance criteria nie spełnione:**
   - Sprawdź logi backend + frontend console
   - Użyj debuggera lub print statements
   - Poproś Cursor o fix: "Fix issue: [opis problemu]"

3. **Test E2E failuje:**
   - Wróć do kroku który nie działa
   - Użyj prompt: "Debug step X.X — [opisz co nie działa]"

---

## ✅ Ready for Phase 8B

Po ukończeniu wszystkich 12 kroków:
- Sprawdź **FINAL CHECKLIST** w `phase8a_implementation_plan.md`
- Zmerguj branch `phase-8-combat-system` do `main`
- Zaktualizuj Notion (Combat System 2.0)
- Rozpocznij Phase 8B: Combat Frontend Polish
