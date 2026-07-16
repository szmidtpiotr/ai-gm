---
typ: pomysl
status: szkic
zrodlo: "#1195"
---

# Nemezis — wróg, który pamięta

## Co gracz dostaje
Czasem pokonany (ale nie dobity) albo uciekający wróg przeżywa i staje się nemezis — wrogiem osobistym bohatera. Wraca silniejszy, z blizną po poprzednim starciu, działa w tle i może ścigać bohatera nawet w kolejnej kampanii. Finał to konfrontacja z osobistym wrogiem z historią, nie kolejnym goblinem z puli.

## Jak to działa
- Nemezis wraca **+1 tier** silniejszy, z blizną/cechą z poprzedniego starcia („herszt z wypaloną twarzą — pamiątka po twojej pochodni"); wariant generuje LLM (opis) + mechaniczny buff.
- Działa w tle: wyznacza nagrodę za głowę bohatera (silniejsze encountery z łowcami), wysyła zbirów, sabotuje reputację w regionie.
- Pojawia się w narracji i plotkach („podobno ktoś o ciebie wypytywał…").
- Może wrócić **w kolejnej kampanii tego samego bohatera** — wpis w Kronice Bohatera (#1096) niesie go między przygodami.
- Dobicie nemezis = bonus XP + trofeum + wpis do kroniki.
- Zasady bezpieczeństwa designu: max **1 aktywny nemezis** na bohatera; narodziny to **mała szansa** przy ucieczce wroga / niedobiciu humanoidalnego przeciwnika — nie każda walka.
- Technicznie: tabela `character_nemeses` (wróg źródłowy, geneza, tekst blizny, poziom eskalacji, stan dormant/active/dead, UNIQUE aktywny per character); `nemesis_service` z maszyną eskalacji (dormant → zbiry → łowcy nagród → konfrontacja) napędzaną day-tickiem podróży; hook narodzin w `combat_service`.

## Zarządzanie (admin)
- Monitor kampanii → karta „Nemezis": kto jest nemezis, historia starć, aktualny poziom eskalacji.
- Przyciski: „uśmierć" (zabij wątek), „eskaluj teraz" (wymuś następny ruch), „edytuj opis".
- Szansa narodzin i tempo eskalacji tuningowalne w configu.

## Dlaczego pasuje do gry
Robi z systemu walki **generator fabuły** — gra zaczyna „pamiętać" gracza. Konsumenci już istnieją: Kronika Bohatera, plotki, encountery z podróży (FAZA PT), reputacja (#1099), trofea. Najciekawszy efekt „ta gra mnie zna" z całej listy Features.

## Liczby startowe
- Szansa narodzin: **20%** przy ucieczce wroga-humanoida
- Tempo eskalacji: co N dni podróży; buff **+1 tier** — startowe, tuning po obserwacji realnych kampanii.

## Zależności i powiązania
- Kronika Bohatera #1096 i FAZA PT day-tick — są.
- Mocna synergia (żadna nie blokuje): [[System plotek w karczmach]] (nemezis jako źródło plotek), [[Klątwy i trofea z krytyków]] (trofeum za dobicie), reputacja #1099 (sabotaż −rep przy wysokiej eskalacji).
- Najdroższy feature z listy po [[Towarzysz podróży — hireling]] — wdrażać po tańszych.

## Out of scope
- Wielu nemezis naraz / nemezis frakcyjny — v2.
- Nemezis w multiplayerze — po FAZIE G.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1195
