Jesteś AI pomagającym w projekcie ai-gm (FastAPI + SQLite, Python).

⚠️ ZANIM cokolwiek zaimplementujesz — STOP i odpowiedz na pytania:
1. Czy plik combat_ac_helpers.py już istnieje? Jeśli tak — pokaż mi jego zawartość.
2. Czy w combat_service.py istnieje już jakaś funkcja licząca AC gracza lub wroga?
   Jeśli tak — czy mój nowy plik ją zduplikuje lub z nią skoliduje?
3. Jak wygląda struktura sheet_json gracza? (znajdź przykład w DB lub kodzie)
   Czy klucze stats, equipment_slots, defense są pewne, czy mogą być None?
4. Jaka jest metoda połączenia z DB w tym projekcie? (get_conn, get_db_path, inne?)
5. Czy coś importuje już z combat_service.py co może się zepsuć po dodaniu nowego pliku?

Jeśli znajdziesz JAKIKOLWIEK bloker lub ryzyko kolizji — opisz go i czekaj na moją decyzję.
Jeśli wszystko bezpieczne — napisz "✅ Brak blokerów, kontynuuję" i dopiero wtedy działaj.

---

Zadanie: Utwórz backend/app/services/combat_ac_helpers.py

Przeczytaj najpierw:
- backend/app/services/combat_service.py
- backend/app/db.py

Zaimplementuj funkcje:

1. _stat_mod(sheet, stat) → int
   floor((value - 10) / 2), domyślna wartość 10

2. _load_armor_row(armor_key) → Optional[dict]
   SELECT z game_config_armor WHERE key=? AND is_active=1

3. _load_shield_row(shield_key) → Optional[dict]
   SELECT z game_config_shields WHERE key=? AND is_active=1

4. player_ac_from_sheet(sheet, combat_effects=None) → int
   base = sheet["defense"]["base"] lub 10
   dex_contribution = min(mod(DEX), max_dex_bonus z pancerza)
   + armor_bonus + shield_bonus + suma ac_bonus z combat_effects
   return max(1, suma)

5. enemy_ac_from_row(enemy_row, combat_effects=None) → int
   ac = ac_base + armor.ac_bonus + shield.ac_bonus + suma efektów
   return max(1, ac)

Dodaj type hints. NIE modyfikuj żadnych istniejących plików.
Pokaż mi plik przed zapisem.