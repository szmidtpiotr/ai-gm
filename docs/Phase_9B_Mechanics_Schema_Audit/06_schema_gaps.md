# Luki i nadmiary w schemacie — przedmioty, umiejętności, czary

**Status:** lista robocza (Sesja 6b, 2026-05-02) — skonsolidowana z uchwałami **[S1]–[S6]** i macierzą. Źródła: [`01_schema_inventory.md`](01_schema_inventory.md), [`02_code_usage_matrix.md`](02_code_usage_matrix.md), [`04_decisions_log.md`](04_decisions_log.md) (**[AUDIT]**). **Projekt pod przegląd:** propozycje zamykające część luk — [`07_extended_design_spec.md`](07_extended_design_spec.md); po akceptacji wpisy **[S12]–[S20]** (m.in. zakładki **[S15]**, stack/Figma **[S16]**, Azure **[S17]**, **centralny resolver LLM [S18]**). **Zasada [S6] §2:** stany złożone planować **parametrycznie w JSON**; unikać osobnej kolumny SQL na każdy wariant — patrz też wiersz „Warunki / typy efektów” poniżej.

## Cel

Wypisać:

- **Braki:** czego **nie da się** zapisać w bazie przy planowanych mechanikach.
- **Nadmiary:** które kolumny są **nieużywane** albo tylko „opis bez liczenia”.

## Tabela robocza (do wypełnienia)

| Obszar | Potrzeba mechaniczna | Czy jest kolumna / tabela? | Uwagi |
|--------|----------------------|----------------------------|--------|
| Broń / magia ([S1]) | Magia: pojedynczy cel vs **AOE**, ewent. szkoła / zasięg | **`targeting`**, **`aoe_radius_m`**, **`magic_school`** — **[S12]**; mapa/siatka — **[S19]** (MVP bez mapy w silniku) | Migracja + import; taktyka geometryczna — poza MVP |
| Umiejętności ([S1]) | Umiejętność **dwuręczność** z modyfikatorami | `game_config_skills` + rangi na arkuszu — **klucz umiejętności** trzeba ustalić | Po Sesji 4 upewnić się, że jest w `dice` / rzutach |
| Umiejętności (**[S4]** / **[S10]**–**[S10e]**) | Skala bonusów 1–5, koszty XP, magazyn XP | **[S10d]** + **[S10e]**: grant MG + **tabela kategorii XP** (np. typ wroga, quest) | **Wdrożone (część):** spend XP, `xp_award`, grant + log; **do migracji:** **[S10e]**; koszty statów w meta; fabularnie tylko MG — technicznie owner (**[S10d]** doprecyzowanie) |
| Kampania / LLM (**[S11]**, **[S11a]**, **[S11b]**, **[S10c]**) | Roadmapa, cele sceny, pamięć > 8 tur | **`campaigns.gm_plan_json`** + `campaign_ai_summaries` w prompcie (**[S11a]**); znacznik końca odcinka: **POST …/advance-scene** | **[S11b]:** plan po zapisie postaci przed 1. narracją; **dwa rekordy** rollupu (gracz vs MG); SoT = `campaign_turns`; cooldown odświeżenia w MP; **W1** (merge JSON) vs **W2** (tabela beatów); strukturalne questy pod XP; PATCH planu — admin/debug |
| Przedmioty | Spójny zapis efektów (mikstury, przedmioty specjalne) | **`effect_json` v0** wspólny z warunkami — **[S13]** **accepted**; płaskie `effect_*` do **usunięcia** (bez migracji treści; wzorce na start) | Walidacja zapis/import; LLM → propozycja JSON z opisu |
| Przedmioty | AC z pancerza w liczeniu obrony | `ac_bonus`; na start **jedna liczba** „na całość”, potem lokacje ([**S2**](../04_decisions_log.md)) | Implementacja obrony + później hit locations |
| Czary | Osobna kategoria vs przedmioty / bronie | **`game_config_weapons`** + `weapon_type = spell`; pola **`targeting`**, **`aoe_radius_m`**, etykieta **`magic_school`** — **[S12]** **accepted** | **Migracja** + import przez **catalog snapshot**; AOE w walce bez geometrii do czasu **[S19]** / fazy mapy |
| Przedmioty | Klasy; przedmioty wymagające magii | `allowed_classes`; flaga **wymaga_magii** w JSON / schemacie | [**S2**](../04_decisions_log.md): bez magii nie użyjesz magicznego aktywowania |
| Wrogowie vs postać (**[S14]**, [**S5b**](../04_decisions_log.md) superseded) | Jedna tabela; **zgodne znaczenia** jak PC, pola **sparse**; generator **[S20]**; **`skills_json`** pod konfrontacje | Migracja **`skills_json`**; kod rzutów vs `game_config_skills` | Walka: OK; testy umiejętności NPC: po migracji |
| Warunki vs przedmioty ([**S6**](../04_decisions_log.md)) | Jeden schemat JSON + pole/kategoria „stan” vs „bonus wyposażenia” | **[S13]** — wspólny szkielet; `effect_category` w JSON | Walidator + lista typów **krótka, rozszerzalna** |
| Warunki — typy efektów (**[S6]** §2) | Parametryzacja **wielu** stanów złożonych (rzuty cykliczne, utrata kontroli, DC z **[S5]**) | Enum `type` w `effects[]` — startowy zestaw w §3 **[S13]**, rozbudowa w iteracjach | Implementacja: DC z **[S5]** w polach `dc_key` itd. |
| Konsumable | Jedna ścieżka `item_key` | Nadal istnieje `game_config_consumables` + `consumable_key` w starym loot | Migracja do **`game_config_items`** + ujednolicenie loot/skupów (**[S6]**) |
| DC (**[S5]** / **[S9]**) | Klucz poziomu → liczba | `resolve_dc_for_roll` + `/roll … hard` — [**wdrożone**](../../backend/app/services/dice.py) | LLM nadal powinien mapować narrację na klucz z `game_config_dc` |
| Umiejętności (**[S4b]**) | `linked_stat` z bazy w teście umiejętności | `dice.skill_linked_stat_for_test()` + `config_service.get_runtime_config()`; alias `melee_attack`↔`attack` | Zrobione w `dice.py`; rozszerzyć aliasy jeśli inne klucze rozjadą się z DB |
| Umiejętności (**[S4]**) | `rank_ceiling` vs rzeczywista ranga na karcie | Do weryfikacji przy zapisie postaci / API | Walidacja przy awansie |
| Broń / rzuty (**[S1]**) | Spójność `weapon_type` z rodzajem ataku w kodzie | Macierz: potwierdzić grep `combat_service` / `dice` | Implementacja taktyki / ataku |
| Import treści (**Sesja 7**) | Pełne kolumny przy wdrożeniu JSON | `import_config` wstawia **węższy** zestaw kolumn broni niż pełny schemat; `import_catalog_snapshot` używa dynamicznego INSERT | Ryzyko **ucięcia** pól broni przy złym torze importu — rozstrzyga **[S7]** |

*(Dopisuj kolejne wiersze w kolejnych sesjach.)*

---

## Odnośniki

- Agenda: [Sesja 6b](03_discussion_agenda.md#sesja-6b--luki-w-kolumnach-przedmioty-umiejętności-czary).
