# Książka zasad dla graczy — szkic (WFRP-inspired)

**Status:** outline zsynchronizowany z zamknięciem fazy 9B (**[S8]** w [`../04_decisions_log.md`](../04_decisions_log.md)). Pełny tekst narracyjny i tabele — w kolejnej fazie redakcyjnej / po wdrożeniu kodu tam, gdzie uchwały wymagają zmian w silniku.

**Cel:** Jedna spójna książka w stylu *Warhammer Fantasy Roleplay*: konkretne procedury („najpierw X, potem Y”), przykłady, minimalny żargon developerski. Gracz nie musi znać nazw tabel SQLite ani plików backendu.

---

## Zasady redakcyjne (tylko to, co jest uchwalone)

1. **Źródło prawdy:** Każdy rozdział mechaniczny mapuje na [`../04_decisions_log.md`](../04_decisions_log.md) i na [`../02_code_usage_matrix.md`](../02_code_usage_matrix.md). Definicja „używane w grze”: **[S0]** + [`../00_brief.md`](../00_brief.md). Nie obiecujemy mechanik sprzed wdrożenia w kodzie — tam gdzie uchwała wyprzedza kod (np. **[S4b]**, **[S5]**), tekst może mówić „w zasadach tak ma być” lub „po wdrożeniu”, bez udawania że silnik już tak liczy.
2. **Druga osoba:** „Wykonujesz rzut…”, „Twoja postać może…”.
3. **Terminologia:** Jak w interfejsie / konfiguracji (np. klucze umiejętności, etykiety DC) — nie nazewnictwo kolumn SQL.
4. **DC ([S5]):** Mistrz Gry może mówić „łatwy / trudny test”; **konkretna liczba** DC pochodzi z **jednej tabeli** konfiguracji (`game_config_dc`). Poziomy DC stosujecie **tylko gdy jest rzut** — nie przy samej narracji bez testu.
5. **Broń ([S1], [S1b], [S1c]):** STR/DEX wg typu broni; dwuręczność jako umiejętność; typ broni zgodny z rodzajem ataku; zasięg „czy doleciało”; konfrontacje dwurzędowe z **remisem na korzyść obrońcy**. Nie obiecujemy jeszcze w tekście gracza pełnej taktyki finesse w kodzie — dopóki `combat_service` nie implementuje **[S1]** w szczegółach, opisuj to jako **kierunek zasad** lub skrót z [`draft_formulas_and_examples.md`](draft_formulas_and_examples.md).
6. **Przedmioty ([S2]):** Docelowo jeden schemat JSON; pancerz w liczeniu obrony (najpierw uproszczenie AC); klasy i magia przy użyciu przedmiotów — jak w uchwale.
7. **Statystyki ([S3]):** Zamknięta lista cech z konfiguracji; nowa statystyka = nowa wersja zasad.
8. **Umiejętności i XP ([S4], [S4b], [S5a], [S10a], [S10b], [S10c]):** Sufit rangi 5, **pula XP** (bez LVL), kara za deklarację bez umiejętności, pierwszy wykup +1; **widełki** przyznawania XP i kosztów rang — w szkicu [`draft_formulas_and_examples.md`](draft_formulas_and_examples.md) §0g; **cecha do rzutu** z bazy (`linked_stat`); opisy w katalogu dla gracza i dla kontekstu LLM.
9. **Warunki i konsumable ([S6]):** Wspólna rodzina JSON dla stanów i przedmiotów (różne kategorie efektów); jeden katalog przedmiotów dla zużywalnych; jeden `key` przedmiotu wszędzie; stany złożone — zasada parametryzacji (§2 **[S6]**).
10. **Konfiguracja a świat ([S7], [S7a]):** Pełny katalog treści — snapshot import/export; LLM zapisuje przez **API**; backup i retencja — po wdrożeniu; jedna baza.

---

## Proponowany spis treści (mapowanie na uchwały)

| # | Rozdział | Uchwały / uwagi |
|---|----------|-----------------|
| 1 | **Wstęp** — gra, Mistrz Gry (AI), fair play | **[S0]** |
| 2 | **Tworzenie postaci** — archetypy, start | archetypy + **[S3]**, **[S4]** |
| 3 | **Statystyki** — znaczenie cech, modyfikatory | **[S3]** |
| 4 | **Umiejętności** — rangi, sufit 5, kara, pierwszy wykup, powiązanie z cechą | **[S4]**, **[S4b]**, **[S5a]** |
| 5 | **Rzuty i testy** — k20, kiedy test; konfrontacje; remis | **[S1b]**, **[S1c]**, **[S5]** (kiedy DC), **[S4b]** (docelowo odczyt z bazy) |
| 6 | **Poziomy trudności (DC)** — etykiety i liczby z jednej tabeli | **[S5]** |
| 7 | **Walka** — trafienie, obrażenia STR/DEX, broń, zasięg (kierunek), dwuręczność jako skill | **[S1]**, **[S1b]**; szczegóły taktyczne gdy kod dogoni **[S1]** |
| 8 | **Ekwipunek i przedmioty** — typy, pancerz, konsumable, JSON | **[S2]**, **[S6]** |
| 9 | **Magia i zdolności specjalne** — na bazie broni `spell` / przedmiotów; brak osobnej tabeli czarów na razie | **[S1]**, **[S2]**, **[AUDIT]** / [`../06_schema_gaps.md`](../06_schema_gaps.md) |
| 10 | **Stany i warunki** — JSON, przykłady złożonych stanów | **[S6]** |
| 11 | **Załączniki** — komendy, glosariusz; opcjonalnie **eksport katalogu** (dla organizatorów, nie dla gracza końcowego) | **[S7]** |

**Otwarte (nie obiecywać w książce jako gotowca):** **[S5b]** — wrogowie jak karta gracza / generator; dopóki nie ma osobnej uchwały wdrożeniowej.

---

## Ton i przykład (fragment ilustracyjny)

> **Rzut testu umiejętności**  
> Gdy scena wymaga testu, wykonujesz rzut k20 i dodajesz modyfikatory (cecha z karty, ranga umiejętności, ewentualnie inne bonusy opisane w podsumowaniu). Mistrz Gry ustala **poziom trudności** słowami (np. trudny); **liczba**, którą musisz pokonać, pochodzi z **tej samej tabeli**, którą mają organizatorzy w konfiguracji — tak nie powstają „losowe” progi z powietrza (**[S5]**).

---

## Szkic przykładów liczb

[`draft_formulas_and_examples.md`](draft_formulas_and_examples.md) — spójny z [`../04_decisions_log.md`](../04_decisions_log.md) (**[S1]–[S7]**).

---

## Mapowanie na dokumenty projektowe

| Obszar | Źródło |
|--------|--------|
| Staty, umiejętności, DC | `game_config_*`, **[S3]–[S5]**, **[S4b]** |
| Walka, broń | `combat_service`, **[S1]** |
| Przedmioty, stany | **[S2]**, **[S6]**, JSON |
| Import / LLM / backup | **[S7]**, **[S7a]** |
| Luki schematu vs kod | [`../06_schema_gaps.md`](../06_schema_gaps.md), **[AUDIT]** |

---

## Następne kroki (poza zamknięciem fazy 9B docs)

1. **Implementacja** zgodnie z [`../06_schema_gaps.md`](../06_schema_gaps.md) i uchwałami (m.in. `dice.py` + **[S4b]**, pipeline DC + **[S5]**, backup + **[S7a]**).
2. Redakcja pełnych rozdziałów 3–11 z liczbami z `draft_formulas` po stabilizacji balansu.
3. Review czytelności przez osobę bez kontekstu backendu.
