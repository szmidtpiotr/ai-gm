# Testy wizualne — FAZA BL „Bestie i Łupy 2.0" (milestone #26)

Wszystko na DEV: **https://aigm-dev.studio-colorbox.com/**
Gra (ŻAR): zaloguj jako **demo / demo** → bohater **Drundor** (krasnolud-uczony) → przycisk **Graj**.
Admin: **/admin/** (dev-login).

Drundor jest przygotowany: ma złoto (~124 gp), komponenty w plecaku, odkrytą jedną ukrytą recepturę, naostrzony kostur i **założone 2 z 3 części setu wilczego**. Stoi w dziczy — do testów rzemiosła/gildii trzeba dojść do osady (najlepiej **Brzezino** — jest tam i zielarka, i faktor gildii).

---

## T1 — Karta pojawienia wroga + wskaźnik zagrożenia (#1344)

**Gdzie:** ŻAR, ekran gry.

1. W polu akcji napisz coś zaczepnego w dziczy, np. *„Idę dalej przez las, nie kryjąc się"* — powtarzaj tury wędrówki, aż wywiąże się walka (zwykle 1–4 tury).
2. W momencie startu walki ma pojawić się **karta pojawienia wroga**: obrazek/wizual wroga, nazwa po polsku i **kolorowy wskaźnik zagrożenia**: 🟢 (łatwy) / 🟡 (wyrównany) / 🔴 (groźny) / 💀 (śmiertelny).

**Efekt zamierzony:** karta pokazuje się **raz** na początku walki (nie wraca po odświeżeniu strony — możesz sprawdzić F5 w środku walki). Wskaźnik ma odpowiadać zdrowemu rozsądkowi: wilk dla Drundora ≈ 🟢/🟡, niedźwiedź/kilku wrogów ≈ 🔴.

## T2 — Zróżnicowane spotkania + rangi wrogów (#1328, #1331, #1332)

**Gdzie:** ŻAR, kolejne walki w podróży.

1. Stocz (albo ucieknij z) 3–4 walki w różnych terenach (las, potem np. w stronę gór/bagien — patrz mapa).
2. Patrz na skład przeciwników w kolejnych walkach.

**Efekt zamierzony:**
- **Nie zawsze wilk albo bandyta** — różne bestie zależnie od terenu (las: wilki/bandyci/gobliny; bagno: nieumarli; góry: niedźwiedzie/koboldy).
- Różne układy: pojedynczy silny wróg / **wataha** (2–4 takie same) / **herszt + poplecznicy**.
- Czasem wróg z przedrostkiem rangi w nazwie: **„Weteran: …"** lub **„Elitarny: …"** — to celowo rzadkie; jak zobaczysz choć raz na kilka walk, działa.

## T3 — Łupy: komponenty, zwierzęta bez złota (#1333–#1335)

**Gdzie:** ŻAR, modal łupów po wygranej walce.

1. Zabij **wilka** (albo inne zwierzę).
2. Obejrzyj okno łupów po walce.

**Efekt zamierzony:**
- Ze zwierzęcia wypadają **komponenty** (kieł wilczy, skóra), oznaczone plakietką **🧩**.
- **Zero złota** ze zwierząt (złoto sypią humanoidy — bandyci itd.).
- Otwórz **Ekwipunek** (dolny pasek) → widok Lista → na dole sekcja **„🧩 Komponenty"** — tam lądują wszystkie części rzemieślnicze.

## T4 — Zbieranie ziół w podróży (#1337)

**Gdzie:** ŻAR, pole akcji, poza osadą.

1. Napisz: *„Zbieram zioła"*.
2. Powinien pojawić się **test PRZETRWANIE** z popupem kości (klikasz rzut). Trudność zależy od terenu: las/bagno łatwiej (DC 8), góry/pustkowia trudno (DC 16).
3. Po sukcesie: narracja zbioru + **1–3 zioła** w ekwipunku (sekcja Komponenty). Przy krytycznym sukcesie (20) — dodatkowo rzadkie zioło. Przy krytycznej porażce (1) — trująca pomyłka, **−1 HP**.
4. **Napisz „zbieram zioła" drugi raz w tym samym miejscu** tego samego dnia.

**Efekt zamierzony kroku 4:** GM odmawia — komunikat w stylu *„to miejsce już ogołocone"*, **bez testu**. Cooldown = 1 raz na heks na dobę gry.

## T5 — Rzemiosło u rzemieślnika (#1336, #1338)

**Gdzie:** ŻAR — wejdź do osady z rzemieślnikiem (Brzezino: zielarka Agata).

1. Po wejściu do osady w podpowiedziach akcji (chipy nad polem tekstu) ma być chip **„Rzemiosło" 🔨**. Kliknij.
2. Otwiera się okno rzemiosła z listą przepisów jako karty:
   - przepis, na który **masz wszystkie składniki**, jest **podświetlony na zielono** z plakietką **„Starczy"**;
   - na każdej karcie chipy składników 🧩 z licznikiem **masz/potrzeba** (zielony = masz, czerwony = brakuje);
   - widoczna opłata za usługę.
3. Wytwórz **Miksturę leczniczą (z ziół)** (2× zioło lecznicze + korzeń zmornika — jak brakuje, najpierw T4).

**Efekt zamierzony:** toast potwierdzenia z dopiskiem o **zniżce krasnoluda** (płacisz 4 zamiast 5 gp), złoto i liczniki składników odświeżają się **od razu**, mikstura pojawia się w ekwipunku.

4. (U kowala — np. Strzegwacht) analogicznie **Ostrzenie broni (+1 obrażeń)**: wybierasz broń, po usłudze przy kosturze/broni widnieje ulepszenie. Spróbuj naostrzyć **drugi raz tę samą broń** → ma być **blokada** (nie kumuluje się). *Uwaga: kostur Drundora jest już naostrzony — drugi raz powinno od razu odmówić.*

## T6 — Eksperymenty: fuszerka + odkrycie (#1341)

**Gdzie:** to samo okno rzemiosła (u zielarki), zakładka **„Eksperyment"**.

1. Wybierz w pickerze **2 przypadkowe komponenty** (np. kieł wilczy + ruda żelaza). Opłata 10 gp za próbę. Kliknij eksperyment.
2. **Efekt zamierzony (fuszerka):** dramatyczna karta wyniku z rzutem 🎲 — strata składników, czasem coś gorszego (żużel / 1d4 obrażeń / przeklęty stop). Składniki znikają z ekwipunku, złoto −10.
3. Teraz poprawna kombinacja: **skóra wilcza + sadło niedźwiedzie**. To ukryta receptura maści.
4. **Efekt zamierzony (odkrycie):** karta **„Odkrycie"** z wynikiem rzutu vs DC, przedmiot (maść) w ekwipunku i wpis w sekcji **„Odkryte receptury"** na dole okna. *Uwaga: Drundor już odkrył tę recepturę w smoke — powinna widnieć na liście od razu; do świeżego odkrycia użyj innego bohatera albo pozostałych dwóch ukrytych receptur (te są trudniejsze).*
5. Bonus (#1191): w karczmie plotki potrafią **zdradzić składniki** nieodkrytej ukrytej receptury — zapytaj karczmarza o plotki.

## T7 — Gildia kupiecka (#1342)

**Gdzie:** ŻAR — osada z faktorem gildii: **Brzezino** (Kunegunda Rączka), Volhynia (Radomir Waga) lub Strzegwacht (Bruno Miech).

1. Zagadaj/podejdź do faktora gildii → otwórz jego **sklep**.
2. **Efekt zamierzony:**
   - u góry **baner reguł**: „Gildia Kupiecka — Komponenty" + zasady (sprzedaż 150% / skup 40% / rotacja co dzień gry / rzadkie tylko z farmienia);
   - lista **8 komponentów** z plakietką 🧩;
   - ceny **wyraźnie zawyżone** (150% wartości) przy kupnie, **zaniżone** (40%) przy skupie — kupno i odsprzedanie tego samego = strata;
   - **rzadkich komponentów** (krew wilkołaka, esencje) **nie ma w ofercie** — są „związane ze zdobyczą";
   - następnego **dnia gry** asortyment się zmienia (rotacja); w ramach jednego dnia jest stały nawet po odświeżeniu.

## T8 — Sety ekwipunku: „Strój Wilczego Łowcy" (#1340 + #1347)

**Gdzie:** ŻAR → dolny pasek → **Postać** oraz **Ekwipunek**.

1. Otwórz **Postać** i zjedź do sekcji **„Komplet ekwipunku"**.
2. **Efekt zamierzony (stan startowy Drundora):** widnieje **Strój Wilczego Łowcy 2/3** — progi ●●○, aktywny próg 2 z bonusem **+1 Zręczność**. Zręczność na karcie: **14** (13 bazy + 1 z setu).
3. W **Ekwipunku**: założone „Płaszcz z wilczej skóry" (plecy) i „Totem wilczej watahy" (amulet); w plecaku niezałożony „Sztylet z wilczego kła".
4. **Załóż sztylet** → sekcja Komplet ma przeskoczyć na **3/3**: +1 ZR, +1 Przetrwanie, +1 pancerz. Zdejmij jedną część → wraca 2/3; zdejmij dwie → sekcja znika/bonus gaśnie.
5. **Zdobywalność (sedno #1347):** zabij kilka **wilków** — z wilka ma czasem wypaść płaszcz (12%) lub totem (8%). Wszystkie 3 części da się też **wykuć u kowala** z komponentów wilczych.
6. **Bonus w walce:** rozpocznij walkę mając 2/3 — inicjatywa i testy zręcznościowe liczą ZR 14. (Widać pośrednio: modyfikator +2 zamiast +1 przy rzutach opartych na ZR.)

## T9 — Księga Zasad, rozdział XIV „Rzemiosło" (#1339)

**Gdzie:** **/rules/** (Księga Zasad) → spis treści → **XIV. Rzemiosło**.

**Efekt zamierzony:** rozdział z ilustracją (warsztat), prozą o pętli łup → komponenty → rzemieślnik, kartą testu zbierania ziół (DC 8/12/16 wg terenu), tabelą przepisów startowych z cenami, zniżką krasnoluda 15%, podrozdziałami o **setach**, **eksperymentach** i **gildii** (kotwice #r14-sety, #r14-eksperymenty, #r14-gildia). Najechanie na podkreślone terminy (komponent, przepis…) pokazuje dymki.

## T10 — Admin: Zawartość (sety, przepisy, tabele łupów, Smart Entry)

**Gdzie:** **/admin/** → **Zawartość**.

1. Zakładka **Sety**: tabela z 1 rekordem `wolf_hunter`; kliknij — modal z częściami (pieces) i bonusami progów 2/3. Spróbuj zapisać próg „1" → walidacja ma odrzucić (progi ≥2).
2. Zakładka **Przepisy**: tabela ~9 przepisów (3 jawne + 3 ukryte + 3 na części setu). Edycja inline/modal działa, `inputs_json` jako pole tekstowe.
3. Zakładka **Tabele łupów**: tabele tierowe `loot_tier_weak/standard/elite/boss` + per-wróg; wpisy z plakietką typu (item/consumable/weapon); klik na wagę/min/max = edycja inline. W `loot_wolf` mają być części setu (cloak 12, totem 8).
4. **🤖 Kreator AI** (Smart Entry) na przedmiotach: pola **is_component / component_type** widoczne w formularzu.

## T11 — Admin: kolumna Źródło + Power Score (#1330, #1331)

**Gdzie:** **/admin/**.

1. **Świat → Oczekujące**: tabela ma kolumnę **„Źródło"** z plakietką skąd rekord pochodzi (seed / AI / kampania…). Sortowanie po niej działa.
2. **Kampanie** → otwórz kartę kampanii Drundora („Pierwsza podróż z mury twierdzy") → w przeglądzie wiersz **Power Score** (⚡ miara siły postaci: poziom + broń + pancerz + czary). Dla Drundora ok. **4–5**. To liczba **tylko dla admina** — gracz jej nigdzie nie widzi (sprawdź, że w ŻAR nie ma ⚡).

## T12 — Sanity całej pętli (10 minut, opcjonalnie)

Jedna sesja od zera na świeżym bohaterze: podróż → walka (karta wroga 🟢) → łup 🧩 → „zbieram zioła" → osada → craft mikstury → eksperyment (choćby fuszerka) → gildia (kup brakujący komponent) → poluj na wilki aż wypadną 2 części setu → załóż → Postać pokazuje 2/3 i +1 ZR. Jeśli to przejdzie bez zgrzytu — cała faza BL jest wizualnie potwierdzona.

---

## Po testach

- Issue z labelem `review`, który przeszedł: zdejmij label / zamknij (#1327–#1342, #1344, #1347).
- Coś nie gra → napisz mi który test (T1–T12) i co zobaczyłeś zamiast oczekiwanego efektu.
- Umbrella #1343 zamykamy, gdy zero otwartych P0/P1 (obecnie czeka tylko na Twoje `review` + decyzję o #1346 — bestiariusz 6–10, zadanie contentowe).
