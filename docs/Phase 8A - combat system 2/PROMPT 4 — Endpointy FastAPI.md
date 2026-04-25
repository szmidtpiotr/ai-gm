Jesteś AI pomagającym w projekcie ai-gm (FastAPI + SQLite, Python).

⚠️ ZANIM cokolwiek zaimplementujesz — STOP i odpowiedz na pytania:
1. Czy endpoint POST /api/combat/attack już istnieje? Jeśli tak — jaka jest jego
   obecna implementacja i co z niej korzysta (frontend)?
2. Czy endpointy /api/combat/armor i /api/combat/shields już istnieją?
3. Gdzie są rejestrowane routery? (main.py, __init__.py, inne?)
   Jakie prefixy są już używane? Czy /api/combat jest zajęty?
4. Czy frontend (combat_panel.js, api.js) już wywołuje jakiś endpoint walki?
   Jeśli tak — czy zmiana sygnatury go złamie?
5. Czy Pydantic jest już używany w tym projekcie? Jaka wersja (v1 vs v2)?

Jeśli znajdziesz JAKIKOLWIEK bloker lub ryzyko złamania frontendu — opisz go i czekaj.
Jeśli wszystko bezpieczne — napisz "✅ Brak blokerów, kontynuuję" i dopiero wtedy działaj.

---

Zadanie: Dodaj endpointy REST dla systemu walki.

Przeczytaj najpierw:
- backend/app/main.py
- backend/app/routers/ (wszystkie pliki)
- frontend/js/api.js (jakie endpointy już wywołuje)
- backend/app/services/combat_service.py

Dodaj do combat routera:

1. POST /api/combat/attack
   Body: { campaign_id: int, attacker_id: str, target_id: str }
   → załaduj active_combat z DB → resolve_attack() → zwróć wynik JSON

2. GET /api/combat/armor
   → SELECT * FROM game_config_armor WHERE is_active=1

3. GET /api/combat/shields
   → SELECT * FROM game_config_shields WHERE is_active=1

4. GET /api/combat/ac/{campaign_id}
   → player_ac_from_sheet(sheet, effects) → { ac: int, breakdown: {...} }

Obsłuż błędy: 404 brak active_combat, 400 zły attacker_id.
NIE zmieniaj istniejących endpointów. Pokaż zmiany przed zapisem.