# Agenda dyskusji — kolejność tematów

Spotkania można dzielić na sesje 60–90 min. Po każdej sesji: wpisać uchwały do [`04_decisions_log.md`](04_decisions_log.md).

**Bieżący tryb (2026-05):** jedna sesja = jeden blok z listy poniżej; omawiamy **punkt po punkcie**, bez przeskakiwania do implementacji kodu. Asystent aktualizuje pliki fazy po każdej zamkniętej porcji ustaleń.

---

## Sesja 0 — Słownik (15 min)

**Cel:** Ustalić, co znaczy „pole jest używane w grze”.

- **Wariant A:** tylko kod deterministyczny (walka, `resolve_roll`, walidatory).
- **Wariant B:** A + dozwolone interpretacje GM/LLM według opisów w `config_service`.
- **Wariant C:** wszystko, co widzi gracz w UI.

**Wyjście:** Jedno zdanie-definicja w [`00_brief.md`](00_brief.md) (sekcja do dopisania) + wpis w `04_decisions_log.md`.

---

## Sesja 1 — Broń (`game_config_weapons`)

**Pytania:**

1. Czy `finesse` ma zmieniać sposób liczenia modyfikatora obrażeń (np. max(STR, DEX)) zamiast samego `linked_stat`?
2. Czy `two_handed` wymaga drugiej ręki / blokuje tarczę / zmienia sloty w ekwipunku?
3. Jak `weapon_type` (melee / ranged / spell) łączy się z testami ataku (`melee_attack` vs `ranged_attack` vs `spell_attack` w `dice.py`)?
4. Czy `range_m` ma wejść do przyszłych rzutów zasięgu, czy zostaje opisem dla LLM?
5. Które pola są **must-implement** w następnej fazie kodu, a które **flavor**?

**Wyjście:** Tabela decyzji per kolumna w `04_decisions_log.md`.

---

## Sesja 2 — Przedmioty (`game_config_items`)

**Pytania:**

1. Jaka jest rola `effect_json` vs zestawu `effect_type` / `effect_dice` / `effect_bonus` / `effect_target`?
2. Czy planujemy **jeden schemat JSON** (np. bonus do testu, raz na scenę, aktywacja) + walidację przy zapisie?
3. `ac_bonus` — czy ma kiedykolwiek wpływać na automatyczny AC w silniku, czy tylko na tekst katalogu / narrację?
4. `allowed_classes` — kiedy jest egzekwowane (tworzenie postaci, noszenie, użycie)?

---

## Sesja 3 — Statystyki (`game_config_stats`)

**Pytania:**

1. Czy lista statów w DB jest **jedynym** dozwolonym zestawem kluczy w arkuszu?
2. Dodanie nowego statu — obowiązkowa aktualizacja `dice.py` / arkusza / UI?

---

## Sesja 4 — Umiejętności (`game_config_skills`) vs `dice.py`

**Pytania:**

1. Czy `linked_stat` w DB ma być **źródłem prawdy**, a `SKILL_STAT_MAP` generowany / walidowany przy buildzie?
2. Czy `rank_ceiling` z DB musi być egzekwowany przy awansie (API postaci)?
3. Nowa umiejętność — procedura (klucz w DB + wpis w mapie + test)?

**Uwaga:** To jest **główka architektoniczna** — rezerwuj więcej czasu.

---

## Sesja 5 — DC (`game_config_dc`)

**Pytania:**

1. Czy progi DC są wyłącznie **słownikiem nazw** (łatwe/trudne) dla LLM i gracza?
2. Czy silnik ma **kiedykolwiek** wybierać DC z tabeli automatycznie (np. na podstawie poziomu trudności sceny)? Jeśli tak — w jakim module?

---

## Sesja 6 — Warunki i konsumable

**Pytania:**

1. `game_config_conditions.effect_json` — wspólny format z przedmiotami?
2. Konsumable w `game_config_consumables` vs `game_config_items` — docelowy **jeden** katalog?

---

## Sesja 7 — Eksport / import konfiguracji

**Cel:** Ustalić, które tabele w bundle muszą mieć ten sam kontrakt co runtime, żeby nie wdrażać „martwych” pól.

**Materiał:** [`backend/app/services/admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py).

---

## Sesja 8 — Zamknięcie fazy

1. Przejrzeć `02_code_usage_matrix.md` — czy nie ma otwartych „nie znaleziono” dla krytycznych pól?
2. Uzupełnić `04_decisions_log.md`.
3. Zaktualizować [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md) — rozdziały muszą odzwierciedlać **tylko** uchwały (nie przyszłe marzenia).

---

## Checklista przed następną fazą implementacji

- [ ] Broń: finesse / 2h / typ / zasięg — decyzja zapisana.
- [ ] Przedmioty: `effect_json` — decyzja zapisana.
- [ ] Skills: DB vs `dice.py` — decyzja zapisana.
- [ ] DC — rola tabeli — decyzja zapisana.
- [ ] Player rulebook outline — spójny z logiem decyzji.
