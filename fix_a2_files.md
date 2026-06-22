# 918-A2 — migracja fixtur testowych (per-plik)

Jedno zadanie = jeden plik testowy. Cel: zazielenić jego testy naprawiając DRYF FIXTUR (schemat testowej DB), bez zmiany asercji ani logiki.

<!-- MASS-ZAKRES:START -->
**Środowisko:** runtime/git przez SSH `claude@192.168.1.61`, repo `/home/piotrszmidt/ai-gm`, git jako `piotrszmidt`. Testy: `docker cp <plik> ai-gm-dev-backend-1:/app/tests/<plik>` + `docker exec ai-gm-dev-backend-1 python -m pytest tests/<plik> -p no:cacheprovider -q`.

**Zadanie:** każda linia listy = ścieżka pliku testowego (`tests/...`) do migracji #918-A2. Zazieleń jego testy naprawiając wyłącznie dryf fixtur.

**Recipe (sprawdzony na combat/spell):**
1. `import _fixtures_schema as fx` + `sys.path.insert(0, str(Path(__file__).resolve().parent))` (helper: `backend/tests/_fixtures_schema.py`, 15 tabel).
2. Dla tabel `game_config_*`: `fx.create_tables(conn, "game_config_enemies", ...)` PRZED INSERT-ami; usuń inline `CREATE TABLE game_config_*` (INSERT-y zostają).
3. Brakujące kolumny core-tabel — dodaj wg REALNEGO schematu (`PRAGMA table_info(<tabela>)` na `/data/ai_gm.db`): najczęściej `campaigns.mode`, `npcs.is_crafter`, `characters.*`.
4. Brakująca TABELA (np. `game_items`, `campaign_templates`, `character_spells`, `character_xp_grants`) — utwórz wg realnego schematu (PRAGMA) + seed mirrorujący to, co plik już seeduje w `game_config_*` (żeby asercje stock/ceny miały dane).
5. Guard #928 (`test_issue928_schema_helper.py`) musi zostać zielony po zmianie.

**GATE (NIE zmieniaj, opisz powód):**
- błąd to NIE fixtura: `ImportError: cannot import name '_infer_table'`/removed-function, logika, lub **asercja damage** (#826 margin / crit+surprise ×4) — to klasa **#943**, decyzja Piotra. → `MASS_STATUS: GATE — nie-fixtura (#943/logic): <co>`.
- feature gap (funkcje/param nigdy nie istniały, np. #323 `execute_ally_auto_attack`) → GATE.

**Pipeline:** pytest tego pliku zielony (lub GATE). NIE /tdd, NIE playwright (to test-infra). NIE zmieniaj asercji testów ani kodu silnika. Commit per plik z ref #942.

**Mapowanie id:** linie nie mają #NNN — `FIX<n>` = n-ta linia listy (plik z linii).
<!-- MASS-ZAKRES:END -->

## KOLEJNOŚĆ

- [ ] 1. tests/test_issue461_f1_final.py
- [ ] 2. tests/test_issue461_f1_remaining.py
- [ ] 3. tests/test_issue462_f2_affix_loot.py
- [ ] 4. tests/test_issue466_crafter_service.py
- [ ] 5. tests/test_issue469_dynamic_shop.py
- [ ] 6. tests/test_issue470_cha_buy_price.py
- [ ] 7. tests/test_issue471_price_unification.py
- [ ] 8. tests/test_phase9a_shop.py
- [ ] 9. tests/test_phase9b_t18_consumables_item_key.py
- [ ] 10. tests/test_phase9b_t22_weapon_targeting.py
- [ ] 11. tests/test_phase9b_t23_enemy_skills_json.py
- [ ] 12. tests/test_phase9b_t25_effect_json_migration.py
- [ ] 13. tests/test_phase9b_t17_effect_json_validation.py
- [ ] 14. tests/test_phase8c_loot_service.py
- [ ] 15. tests/test_phase8c_inventory_api.py
- [ ] 16. tests/test_phase8e_inventory_panel.py
- [ ] 17. tests/test_8h_item_system.py
- [ ] 18. tests/test_l8_dungeon_boss.py
- [ ] 19. tests/test_dungeon_tile_service.py
- [ ] 20. tests/test_issue511_U3_mp_flag.py
- [ ] 21. tests/test_loc3_location_guard.py
- [ ] 22. tests/test_admin_cheat.py
