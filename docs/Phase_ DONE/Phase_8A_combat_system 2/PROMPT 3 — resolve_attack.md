Jesteś AI pomagającym w projekcie ai-gm (FastAPI + SQLite, Python).

⚠️ ZANIM cokolwiek zaimplementujesz — STOP i odpowiedz na pytania:
1. Czy funkcja resolve_attack() już istnieje w combat_service.py?
   Jeśli tak — pokaż mi jej pełną sygnaturę i logikę. Co z niej korzysta?
2. Czy istnieją testy w tests/test_phase8_combat.py które testują resolve_attack?
   Jeśli tak — czy moja implementacja złamie te testy?
3. Czy funkcje log_combat_turn() i save_combat_state() istnieją?
   Jakie mają sygnatury i jakich argumentów oczekują?
4. Jaka jest dokładna struktura dict attacker i target w active_combat.combatants?
   (sprawdź w DB lub w kodzie który buduje ten obiekt)
5. Czy random jest już mockowany w testach? Jak?

Jeśli znajdziesz JAKIKOLWIEK bloker lub ryzyko złamania testów — opisz go i czekaj.
Jeśli wszystko bezpieczne — napisz "✅ Brak blokerów, kontynuuję" i dopiero wtedy działaj.

---

Zadanie: Zaimplementuj resolve_attack() w combat_service.py

Przeczytaj KONIECZNIE w całości:
- backend/app/services/combat_service.py
- backend/app/services/combat_ac_helpers.py
- backend/tests/test_phase8_combat.py

Flow (deterministyczny):

1. attack_roll = d20 + attack_bonus
   Gracz: mod(STR lub DEX) + skill["combat"] + proficiency(+2 jeśli rank≥3)
   Wróg: enemy["attack_bonus"]

2. dodge_roll = d20 + dodge_bonus
   Gracz: mod(DEX) + skill["stealth"] + proficiency
   Wróg: enemy["dodge_bonus"]
   → dodge_total >= attack_total AND nie Nat20: return hit=False, reason="dodged"

3. Nat 1 atakującego: return hit=False, reason="crit_fail"
   Nat 20: pomija unik

4. damage = roll(weapon_die) + damage_bonus
   Nat 20: rzuć dwa razy i zsumuj kości

5. defense_roll = d20 + mod(CON) + (armor.ac_bonus // 3)
   Wróg: d20 + enemy["defense_bonus"]

6. final_damage = max(0, damage_total - defense_total)

7. target["hp_current"] -= final_damage

Zwróć dict: hit, reason, attack_roll, attack_total, dodge_roll, dodge_total,
damage_roll, damage_total, weapon_die, defense_roll, defense_total,
final_damage, target_hp_after, target_dead, crit_hit, crit_fail

NIE zmieniaj sygnatur istniejących funkcji. NIE zmieniaj innych plików.
Pokaż TYLKO zmieniony fragment przed zapisem.