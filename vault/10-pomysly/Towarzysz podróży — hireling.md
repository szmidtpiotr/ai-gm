---
typ: pomysl
status: szkic
zrodlo: "#1192"
---

# Towarzysz podróży — hireling / zwierzę

## Co gracz dostaje
W osadzie można nająć towarzysza podróży: najemnika, tropiciela albo psa. Towarzysz walczy u boku gracza, daje pasywne bonusy w podróży — i może zginąć na dobre. Solo play robi się mniej samotne.

## Jak to działa
- Towarzysz ma uproszczoną kartę: HP, 1–2 akcje bojowe, koszt dzienny w złocie (potrącany przy odpoczynku / upływie dnia z systemu podróży).
- **W walce**: działa jak drugi kombatant po stronie gracza — prosty AI-turn po turze gracza (priorytet: atak najsłabszego wroga w swojej strefie); silnik multiplayer rounds już umie obsłużyć wielu uczestników po jednej stronie.
- **Poza walką**: pasywny bonus — tropiciel obniża koszt podróży przez las, pies ostrzega przed zasadzką (obniża wagę encounterów zaskoczenia), najemnik nosi dodatkowy ekwipunek.
- Towarzysz **może zginąć** — i to boli; brak wskrzeszania, najwyżej nowy najem.
- Technicznie: katalog `game_config_companions` (typ, HP, atak, koszt dzienny, pasywy, dostępność per region) + `character_companions` (stan najmu). Pasywy czytane w kalkulacji kosztu terenu i wag encounterów (FAZA PT); kod bojowy pisany zgodnie z `multiplayer_round_service`.

## Zarządzanie (admin)
- Katalog towarzyszy w panelu Świat — jak wrogowie, tylko friendly: statystyki, koszt dzienny, bonusy, dostępność per region/osada.
- Smart Entry generuje towarzyszy jak wrogów; monitor kampanii pokazuje, kogo gracz prowadzi i w jakim stanie.
- Sandbox powinien umieć dodać towarzysza do setupu (tuning wartości).

## Dlaczego pasuje do gry
Strategicznie: wykorzystuje i **testuje kod multiplayera zanim FAZA G ruszy** — towarzysz to poligon dla multi-kombatantów po stronie graczy. Do tego gold sink dla ekonomii (koszt dzienny).

## Liczby startowe
- Limit: **1 towarzysz naraz**
- Koszty dzienne, HP, siła ataku, wartości pasywów — startowe, tuning w Sandboxie.

## Zależności i powiązania
- FAZA PT (day-tick, koszty terenu) — jest.
- Synergia z FAZĄ G/5 (multiplayer) — towarzysz NIE czeka na nią.
- Kolejny stały gold sink obok [[Dom bohatera — kwatera w osadzie]] — razem adresują problem „złoto nie ma na co schodzić".
- Najdroższy feature z listy — wdrażać po tańszych (patrz uwaga w [[Nemezis — wróg, który pamięta]]).

## Out of scope
- Rozwój/levelowanie towarzysza — v2.
- Relacje/lojalność towarzysza — v2.
- Więcej niż 1 towarzysz naraz.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1192
