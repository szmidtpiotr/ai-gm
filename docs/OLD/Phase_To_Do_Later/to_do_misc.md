# Backlog — pomysły i prace na później (`to_do_misc`)

Ten plik zbiera **wszystkie luźne pomysły** i ulepszenia, które **nie** mają jeszcze osobnej fazy ani briefu, ale powinny zostać zarejestrowane, żeby ich nie zgubić.

## Po co to jest

- **Jedno miejsce** na szybkie notatki: „warto by kiedyś zrobić X”.
- Każdy wpis ma **czytelny opis po ludzku** — co to ma robić, po co, ewentualnie dla kogo (gracz / GM / dev).
- Stąd można później **wyciągnąć temat do nowego folderu fazy** w `docs/` (np. `Phase_8K_...`) wraz z briefem — patrz [`../_PHASE_BRIEF_TEMPLATE.md`](../_PHASE_BRIEF_TEMPLATE.md) i workflow w [`../00_WORKFLOW_PERPLEXITY_CURSOR.md`](../00_WORKFLOW_PERPLEXITY_CURSOR.md) (jeśli istnieją).
- W tym samym katalogu mogą leżeć też **osobne pliki** na większe wątki (np. `8D-LOC4_...md`); `to_do_misc` jest na **krótkie, mieszane** tematy.

## Jak dodawać wpisy

1. Wpisz **nagłówek** w formacie `## [TYTUŁ]` lub `### [TYTUŁ]` (albo numer / ID jeśli wolicie, np. `### IDEA-014`).
2. Pod spodem, w zwykłym tekście:
   - **Co** zrobić (zachowanie produktu lub kodu).
   - **Dlaczego** (problem, szansa, ryzyko jeśli nie zrobimy).
   - **Uwagi** (zależności, link do issue/PR, „blokuje X”).
3. Opcjonalnie: **`→ Faza:`** — propozycja nazwy przyszłego folderu fazy, gdy temat dojrzeje.

Nie trzeba pisać specyfikacji implementacji — tylko tyle, żeby **ktokolwiek z zespołu** zrozumiał intencję za rok.

---

## Backlog (wpisy)

Szablon pojedynczego pomysłu (skopiuj i wypełnij):

```markdown
### Krótki tytuł pomysłu

**Co:** …

**Dlaczego:** …

**Uwagi:** … *(opcjonalnie)*

**→ Faza:** … *(opcjonalnie, gdy temat jest gotowy na osobny folder `docs/Phase_…`)*
```

---

<!-- Nowe wpisy dodawaj pod spodem. -->

### Punkty XP — zarabianie i wymiana na skills, stats itd.

**Co:** Ustalić model ekonomii XP (jak gracz zdobywa punkty, jak i po jakiej stawce wymienia je na umiejętności, statystyki i podobne elementy postaci).

**Dlaczego:** Bez spójnych zasad balans i UX nagród będą nieprzewidywalne; warto odłożyć na osobną dyskusję projektową, gdy będzie gotowy szerszy kontekst progresji.

**Uwagi:** Temat na później — do dyskusji, nie blokuje krótkoterminowych fixów.

---

### Komendy `/admin` nadal nie działają

**Co:** Naprawić lub dokończyć implementację komend administracyjnych (`/admin`); ustalić zakres (co dokładnie mają robić w produkcji vs. dev).

**Dlaczego:** Brak działających narzędzi admin utrudnia testy, moderację i obsługę sesji.

**Uwagi:** Do weryfikacji po aktualnym stanie backendu / Discord bota (jeśli dotyczy).

---

### Source of truth — lokalizacje, przedmioty, enemy, NPC i mechanika pobierania przez GM

**Co:** Jednoznacznie ustalić **źródło prawdy** dla danych gry (lokalizacje, przedmioty, wrogowie, NPC itd.) oraz **jak lokalny GM** ma te dane pobierać (cache, API, pliki, wersjonowanie, offline).

**Dlaczego:** Bez tego ryzykujemy rozjazdy między klientem a GM-em, duplikację definicji i trudny debugging scenariuszy.

**Uwagi:** Może wyrosnąć w osobną fazę architektoniczną (kontrakt danych + pipeline aktualizacji).

**→ Faza:** propozycja — osobny brief gdy ustalimy priorytet (np. „data layer / GM sync”).

---

### Archetypy — dodanie i poprawne wczytanie starter items

**Co:** Uzupełnić definicje archetypów o kompletne, sensowne zestawy startowe (`starter_items_json`, ewentualnie `starter_gold_gp`) oraz zapewnić **poprawne wczytanie** tych danych w całym flow: migracje/seed, panel admin (edycja, podgląd), tworzenie postaci (`grant_loot_to_character` / walidacja kluczy wobec `game_config_weapons`, `game_config_items`, `game_config_consumables`). Rozważyć walidację przy zapisie i czytelny komunikat przy złym kluczu.

**Dlaczego:** Bez spójnych danych i parsowania gracz może dostać pusty ekwipunek albo niespójny zestaw; błędy w JSON lub nieistniejących kluczach są trudne do zauważenia na pierwszy rzut oka.

**Uwagi:** Dotyczy tabeli `game_config_archetypes` i logiki tworzenia postaci (grant startowego lootu / złota). Można spiąć z wpisem „Source of truth” powyżej, jeśli katalog przedmiotów będzie centralnie wersjonowany.
