---
typ: pomysl
status: szkic
zrodlo: "#1194"
---

# Klątwy i trofea z rzutów krytycznych w lochach

## Co gracz dostaje
Podbicie stawki emocjonalnej rzutów krytycznych w lochach: krytyczna porażka może przykleić długotrwałą klątwę, a Nat 20 na bossie — unikalne trofeum z historią. Nat 1 i Nat 20 przestają być ulotne, zaczynają zostawiać ślad.

## Jak to działa
**Klątwy (Nat 1, rzadko):**
- Krytyczna porażka w lochu może (mała szansa, nie każdy Nat 1) przykleić klątwę — np. „Piętno Krypty": −1 do WIS-testów, słabsza regeneracja przy odpoczynku.
- Klątwa **nie schodzi odpoczynkiem** — tylko kapłan w osadzie (koszt złota, nowy typ usługi) albo mini-quest („obmyj piętno w źródle pod Czarnstein").
- Technicznie: condition z istniejącego systemu conditions z flagą `curse=true`, ignorowaną przez zwykłe leczenie; aplikacja tylko w kontekście `session_flags.dungeon_run`.

**Trofea (Nat 20 na bossie, szansa):**
- Unikalny przedmiot z historią — „Kieł Wodza Mrocznej Sfory" — item z flagą `unique`, drobnym bonusem lub tylko wartością kolekcjonerską/sprzedażną (preferencja: istniejąca tabela items z flagą `unique+trophy` zamiast osobnej tabeli).
- Zdobycie trofeum zapisuje się do **Kroniki Bohatera** (#1096) — NPC mogą o tym wspominać w innych kampaniach.

W UI: klątwa widoczna w conditions na karcie postaci (fioletowa ramka), trofeum w ekwipunku z lore-tooltipem.

## Zarządzanie (admin)
- Pula klątw (`game_config_curses`: efekt, koszt zdjęcia, podpowiedź questa) i trofeów w tabelach configu — edycja przez Smart Entry / Kuźnię.
- Wagi wystąpienia tuningowalne w **Sandboxie** jak inne stałe walki; podgląd aktywnych klątw bohatera w monitorze kampanii.

## Dlaczego pasuje do gry
Nat 1 / Nat 20 mają dziś skutki natychmiastowe i ulotne — to daje im **konsekwencje długoterminowe**. Kronika Bohatera dostaje materiał narracyjny. Wszystko w ramach istniejących systemów: conditions, loot/items, dungeon runs.

## Liczby startowe
- Szansa klątwy przy Nat 1 w lochu: **15%**
- Szansa trofeum przy Nat 20 na bossie: **50%**
- Koszt kapłana — startowy, tuning w Sandboxie.

## Zależności i powiązania
- Dungeon runs, conditions system, Hero Chronicle #1096 — wszystkie już są.
- Mini-quest zdejmujący klątwę zyskuje na [[Tablica zleceń — bounty board]] — nie blokujące (fallback: tylko kapłan).
- Trofea eksponuje ściana trofeów w [[Dom bohatera — kwatera w osadzie]]; dobicie nemezis daje trofeum ([[Nemezis — wróg, który pamięta]]).
- Profanacja kapliczki używa tego samego systemu klątw ([[Kapliczki przydrożne i błogosławieństwa]]).

## Out of scope
- Klątwy poza lochami (z fabuły/NPC) — v2.
- Przedmioty przeklęte (cursed items w loot) — osobny, pokrewny temat.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1194
