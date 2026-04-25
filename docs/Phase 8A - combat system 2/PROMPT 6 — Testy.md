Jesteś AI pomagającym w projekcie ai-gm (FastAPI + SQLite, Python).

⚠️ ZANIM cokolwiek zaimplementujesz — STOP i odpowiedz na pytania:
1. Czy plik test_combat_attack_resolve.py już istnieje?
2. Jak działają istniejące testy? Czy używają unittest, pytest, czy własnego runnera?
   (przeczytaj test_phase8_combat.py jako wzorzec)
3. Czy jest conftest.py lub setup który inicjalizuje testową DB?
   Czy testy używają prawdziwej DB czy mocków?
4. Czy funkcja resolve_attack() wymaga działającej DB do testów?
   Jeśli tak — jak to obejść (mock, fixture, in-memory SQLite)?
5. Czy player_ac_from_sheet() odpyta DB (game_config_armor) podczas testów?
   Jeśli tak — jak zmockować _load_armor_row()?

Jeśli znajdziesz JAKIKOLWIEK bloker — opisz go i czekaj na moją decyzję.
Jeśli wszystko bezpieczne — napisz "✅ Brak blokerów, kontynuuję" i dopiero wtedy działaj.

---

Zadanie: Napisz testy dla resolve_attack() i AC helpers.

Przeczytaj najpierw:
- backend/tests/test_phase8_combat.py (wzorzec stylu)
- backend/app/services/combat_service.py
- backend/app/services/combat_ac_helpers.py

Utwórz backend/tests/test_combat_attack_resolve.py:

1. test_player_ac_no_armor()
   DEX 14, brak ekwipunku → AC = 10 + 2 = 12

2. test_player_ac_leather_and_shield()
   leather(+2) + wooden_shield(+2), DEX 16 → AC = 10 + 3 + 2 + 2 = 17

3. test_player_ac_heavy_caps_dex()
   plate_mail(+8, max_dex=0), DEX 18 → AC = 10 + 0 + 8 = 18

4. test_resolve_attack_dodge_success()
   Mock: attacker d20=8, target d20=18 → hit=False, reason="dodged"

5. test_resolve_attack_crit_fail()
   Mock: attacker d20=1 → hit=False, reason="crit_fail"

6. test_resolve_attack_hit_and_damage()
   Mock: attack=15, dodge=5, damage_die=6, defense=3 → hit=True, final_damage=3

7. test_resolve_attack_nat20_double_damage()
   Mock: attack_roll=20 → crit_hit=True, damage_roll > single die

Użyj unittest.mock.patch dla random.randint i _load_armor_row.
Dopasuj styl do istniejących testów w projekcie.
Pokaż plik przed zapisem. Na końcu podaj komendę do uruchomienia testów.