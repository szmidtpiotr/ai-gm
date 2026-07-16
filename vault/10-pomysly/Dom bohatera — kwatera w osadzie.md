---
typ: pomysl
status: szkic
zrodlo: "#1197"
---

# Dom bohatera — kwatera w osadzie

## Co gracz dostaje
Za ciężkie złoto bohater kupuje kwaterę w osadzie — swój kawałek Kresów: skrzynię-magazyn, lepszy odpoczynek we własnym łóżku, ścianę trofeów i drzewko rozbudów. Dom należy do bohatera, nie kampanii — przeżywa koniec przygody i czeka w następnej.

## Jak to działa
- **Skrzynia** — magazyn przedmiotów ponad limit ekwipunku (bezpieczne, dostępne tylko w domu); transfer ekwipunek↔skrzynia tylko gdy bohater jest w lokacji domu.
- **Pełniejszy odpoczynek** — bonus regeneracji HP/many przy odpoczynku we własnym łóżku (hook w rest/healing service).
- **Ściana trofeów** — trofea można wyeksponować (czysta duma + wpis w narracji, gdy ktoś odwiedza).
- **Rozbudowy** (kolejne wydatki): zielnik → tańsze mikstury u zielarza / własny craft, kuźnia domowa → naprawy bez kowala, gołębnik → wiadomości/plotki docierają same.
- Model Hero-First: dom przypisany do bohatera (UNIQUE per character), limit **1 dom na bohatera**.
- Technicznie: `game_config_houses` (cennik per osada) + `game_config_house_upgrades` (drzewko z wymaganiami) + `character_houses` + `character_house_storage` (wzór z `character_inventory`).

## Zarządzanie (admin)
- Cennik domów per osada i drzewko rozbudów w tabeli configu (panel / Smart Entry).
- Monitor kampanii pokazuje dom bohatera, rozbudowy, zawartość skrzyni.
- Admin może przyznać/odebrać dom ręcznie (nagroda eventowa).

## Dlaczego pasuje do gry
Największa dziura ekonomii: po kilku lochach **złoto nie ma na co schodzić**. Dom to długoterminowy gold sink z jasną progresją. Hero-First aż się o to prosi — trwały majątek wzmacnia przywiązanie do bohatera (kluczowa pętla gry). Odbiornik dla trofeów i podpora rzemiosła.

## Liczby startowe
- Cena domu: **200 gp** mała osada / **500 gp** miasto
- Bonus odpoczynku: **+25% regeneracji**
- Pojemność skrzyni: start **bez limitu** (obserwować)
- Ceny rozbudów — do przeglądu razem z ogólnym audytem ekonomii.

## Zależności i powiązania
- Hero-First i inventory — są.
- Synergia: ściana trofeów z [[Klątwy i trofea z krytyków]]; zielnik/kuźnia domowa wspierają rzemiosło; gołębnik dostarcza [[System plotek w karczmach]].
- Drugi duży gold sink obok [[Towarzysz podróży — hireling]].
- **Rekomendacja: wdrażać razem z przeglądem ekonomii** — dom ma sens, gdy ceny/dochody są zbilansowane.

## Out of scope
- Dom jako lokacja na mapie lokalnej (FAZA ML) — v2.
- Najem/utrata domu, podatki.
- Domy w multiplayerze (wspólna kwatera drużyny) — po FAZIE G.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1197
