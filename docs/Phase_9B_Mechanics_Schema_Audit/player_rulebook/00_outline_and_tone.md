# Książka zasad dla graczy — szkic (WFRP-inspired)

**Status:** outline only. Pełny tekst powstanie po zamknięciu uchwał w [`../04_decisions_log.md`](../04_decisions_log.md).

**Cel:** Jedna spójna książka w stylu *Warhammer Fantasy Roleplay*: konkretne procedury („najpierw X, potem Y”), przykłady, tabele trudności, minimalny żargon developerski. Gracz nie musi znać nazw tabel SQLite ani plików backendu.

---

## Zasady redakcyjne

1. **Zgodność z ustaleniami:** Każdy rozdział mechaniczny musi mapować na to, co jest **uchwalone** w `04_decisions_log.md` i spójne z macierzą [`02_code_usage_matrix.md`](../02_code_usage_matrix.md). Przedmioty i broń w narracji gracza odnoszą się do **katalogu w bazie** (klucze, statystyki), zgodnie z definicją „używane w grze” w [`00_brief.md`](../00_brief.md) — bez obiecywania rzeczy, których nie ma w konfiguracji ani w twardym kontekście dla LLM.
2. **Druga osoba:** „Wykonujesz rzut…”, „Twoja postać może…”.
3. **Terminologia:** Używaj kluczy umiejętności/statów z gry (np. Stealth, STR) tak, jak w interfejsie — nie „kolumna w DB”.
4. **DC i opisy:** Progi trudności opisz jako etykiety (łatwe, średnie…) z **wartościami liczbowymi** z konfiguracji, ale zaznacz, że w sesji rzut może użyć konkretnego DC podanego przez sytuację (zgodnie z uchwałą o roli `game_config_dc`).
5. **Broń:** Dopóki nie ma uchwały o finesse / dwuręczności — w rozdziale o walce opisz **tylko** to, co macierz potwierdza (np. kość obrażeń + modyfikator z atrybutu powiązanego z bronią w silniku), bez obietnic stylu D&D.

---

## Proponowany spis treści

1. **Wstęp** — czym jest gra, rola Mistrza Gry (AI), fair play, bezpieczeństwo przy stole.
2. **Tworzenie postaci** — archetypy, statystyki, umiejętności, ekwipunek startowy (zgodnie z `game_config_archetypes` / uchwałami).
3. **Statystyki** — co oznaczają, jak liczyć modyfikator z wartości (standardowo (wartość−10)/2 jeśli taka jest uchwała).
4. **Umiejętności** — rangi, sufit rangi (po uchwale o `rank_ceiling`), powiązanie z cechami.
5. **Rzuty i testy** — k20, modyfikatory, przewaga/wada (jeśli obowiązują), **rzuty obronne** vs **testy umiejętności** (zgodnie z `dice.py` i uchwałami).
6. **Poziomy trudności (DC)** — tabela nazw i liczb z konfiguracji; jak czytać sukces/porażkę.
7. **Walka** — inicjatywa, atak, trafienie, obrażenia, śmierć wrogów, zasady **tylko** potwierdzone w kodzie (np. dodge jeśli używany).
8. **Ekwipunek i przedmioty** — typy przedmiotów, pancerz, konsumable, **bez** obiecywania złożonych efektów z `effect_json` dopóki brak uchwały o schemacie.
9. **Magia i zdolności specjalne** — na razie ramy narracyjne + odesłanie do tego, co silnik faktycznie liczy (np. `spell_attack` jeśli uchwalone).
10. **Stan i warunki** — jeśli warunki mają wejść do gry: dopiero po uchwale o `game_config_conditions`.
11. **Załączniki** — skrótówka komend, glosariusz.

---

## Ton i przykład (fragment ilustracyjny — do przepisania po uchwałach)

> **Rzut testu umiejętności**  
> Gdy scena wymaga testu, wykonujesz rzut k20 i dodajesz modyfikatory opisane w podsumowaniu rzutu. Mistrz Gry ustala **DC** (trudność) dla sytuacji — liczba, którą musisz osiągnąć lub przekroczyć, aby odnieść sukces.

_(Powyższe zdanie o DC jest poprawne tylko wtedy, gdy uchwała potwierdzi, że gracz widzi DC w wyniku rzutu — sprawdź aktualny UX i `04_decisions_log.md` przed publikacją.)_

---

## Mapowanie na dokumenty projektowe

| Rozdział książki | Źródło prawdy technicznej |
|------------------|---------------------------|
| Staty / umiejętności / DC | `game_config_*` + `config_service` + `04_decisions_log` |
| Walka | `combat_service`, `dice` (ataki), uchwały o broni |
| Przedmioty | `game_config_items`, loot, uchwała o `effect_json` |
| Magia | Uchwały + `SKILL_STAT_MAP` / bronie `weapon_type` |

---

## Następne kroki (redakcyjne, poza fazą 9B)

1. Po zamknięciu `04_decisions_log.md` — przepisać rozdziały 3–8 z konkretnymi liczbami i przykładami.
2. Dodać ilustracje / tabele (opcjonalnie) i spis komend z [`/mechanics/slash-commands`](../../backend/app/api/mechanics.py).
3. Review przez osobę, która nie pisała backendu — test czytelności.
