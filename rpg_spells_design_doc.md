# Propozycje Nowych Czarów — AI GM RPG

> Dokument projektowy: lista proponowanych czarów do tekstowego RPG inspirowanego WFRP i D&D.  
> Język: polski | System statystyk: STR / DEX / CON / INT / WIS / CHA  
> DC poziomów: easy=8, medium=12, hard=16, extreme=20, legendary=24  
> DC rzucania czarów: Tier 1–2 = DC 10 | Tier 3–4 = DC 14 | Tier 5–6 = DC 18

---

## Zasady testowania czarów (podsumowanie)

- Test rzucania: **INT** (Uczony) lub rzadko **CHA** (Wojownik z magią)
- **Sukces** — czar działa normalnie
- **Sukces krytyczny** (o 5+ powyżej DC) — wzmocniony efekt (+1 kostka, dodatkowy cel, wydłużony czas itp.)
- **Porażka** — czar nie działa (fizzle), mana nadal wydana
- **Krytyczna porażka** (o 5+ poniżej DC) — niepożądany efekt lub obrażenia dla rzucającego

---

## 1. Ataki żywiołowe (Ogień, Lód, Błyskawice, Kwas) — Tier 1–5

| Klucz | Nazwa | Szkoła | Tier | Koszt many | Obrażenia | Leczenie | Strefa | Opis działania | Test rzucania |
|---|---|---|---|---|---|---|---|---|---|
| fire_bolt | Ognisty Pocisk | attack | 1 | 2 | 1d8 | — | any | Rzucający miotuje skupioną kulę ognia w wybrany cel. Cel może zapalić się i otrzymać 1 obrażenie na początku następnej tury (GM decyduje). | INT, DC 10. Sukces: cel traci 1d8 HP. Krit: 2d8 i cel płonie. Porażka: fizzle. Krit. porażka: ogień wybucha przy rzucającym — 1d4 obrażeń dla siebie. |
| frost_bolt | Mroźna Strzała | attack | 1 | 2 | 1d8 | — | any | Wir lodowatego powietrza przyjmuje kształt bełtu i uderza w cel. Cel odczuwa przeszywający chłód i może być **slowed** na 1 turę. | INT, DC 10. Sukces: 1d8 obrażeń, szansa na **slowed** (WIS celu ≥ 10 by uniknąć). Krit: 2d8 + **slowed** automatycznie. Krit. porażka: rzucający ślizga się — traci ruch w tej turze. |
| acid_splash | Plusk Kwasu | attack | 1 | 1 | 1d6 | — | nearby | Rzucający wyrzuca falę parzącej cieczy w stronę pobliskiego celu. Kwas żre zbroję, zmniejszając wartość ochronną o 1 do końca sceny. | INT, DC 10. Sukces: 1d6 obrażeń + obniżenie zbroi. Krit: 2d6 + obniżenie trwałe (do naprawy). Krit. porażka: kwas chlapie na samego rzucającego — 1d4 obrażeń. |
| lightning_arrow | Piorunowy Grot | attack | 2 | 3 | 2d6 | — | any | Rzucający formuje naładowany elektrycznie pocisk i ciska go w wybrany cel. Przy trafieniu energia łukiem przeskakuje do pobliskiej osoby za 1d4 obrażeń. | INT, DC 10. Sukces: 2d6 obrażeń + 1d4 rykoszetem. Krit: 3d6 + rykoszet na 2 dodatkowe cele. Krit. porażka: błyskawica odbija się do rzucającego — 1d6 obrażeń. |
| ice_lance | Lodowa Lanca | attack | 2 | 3 | 2d8 | — | any | Ciężka kolumna lodu wystrzelona z dłoni rzucającego przeszywa cel z siłą tarana. Trafiony wróg jest odpychany o 1 strefę i może dostać **slowed**. | INT, DC 10. Sukces: 2d8 obrażeń + odpychanie. Krit: 3d8 + **frozen** na 1 turę. Krit. porażka: lanca eksploduje — rzucający i wszyscy w zwarciu 1d6 obrażeń. |
| acid_cloud | Kwasowa Chmura | attack_aoe | 3 | 4 | 2d6 | — | aoe_nearby | Rzucający przywołuje dryfującą chmurę żrącej mgły, która ogarnia wszystkich w zasięgu. Kwas niszczy wyposażenie i gryzący dym utrudnia widzenie (**blinded** 1 tura). | INT, DC 14. Sukces: 2d6 dla wszystkich w aoe_nearby + **blinded**. Krit: 3d6 + **blinded** 2 tury. Porażka: chmura nie pojawia się. Krit. porażka: chmura wybucha przy rzucającym — 2d4 dla siebie. |
| inferno_strike | Uderzenie Inferno | attack | 3 | 4 | 3d6 | — | any | Rzucający skupia żar piekielnego ognia w jednym punkcie i wyzwala go z impetem. Ognisty wybuch może podpalić otoczenie i pozostawić żarzące się zgliszcza. | INT, DC 14. Sukces: 3d6 obrażeń. Krit: 4d6 + obszar płonie (1d4 dla wchodzących). Krit. porażka: ognisty rozbłysk — rzucający i sojusznicy w zwarciu 1d6 obrażeń. |
| blizzard_cone | Lodowa Wichura | attack_aoe | 4 | 5 | 2d8 | — | aoe_nearby | Rzucający wymiata stożkiem siarczystego mrozu, uderzając we wszystkich przed sobą. Lód osiada na pancerzach, spowalniając ruchy dotkniętych wrogów. | INT, DC 14. Sukces: 2d8 dla wszystkich w stożku + **slowed** (1 tura). Krit: 3d8 + **frozen** (1 tura). Krit. porażka: mróz ogarnia rzucającego — **slowed** na 2 tury, 1d6 obrażeń. |
| acid_rain | Deszcz Kwasu | attack_aoe | 4 | 5 | 2d6 | — | aoe_nearby | Rzucający wzywa chmurę wylewającą toksyczny deszcz na całe pole bitwy. Kwas sypie się przez 2 tury, zadając obrażenia każdemu kto pozostaje w zasięgu. | INT, DC 14. Sukces: 2d6/turę przez 2 tury dla wszystkich w aoe_nearby. Krit: 3d6/turę przez 2 tury. Krit. porażka: deszcz spada natychmiast na rzucającego — 2d6 obrażeń. |
| storm_call | Wezwanie Burzy | attack_aoe | 5 | 7 | 3d8 | — | any | Rzucający przywołuje burzową chmurę nad polem bitwy, zsyłając pioruny na wielu wrogów. Każdy cel w zasięgu wzroku zostaje uderzony osobnym wyładowaniem. | INT, DC 18. Sukces: 3d8 obrażeń dla maksymalnie 3 celów. Krit: 4d8 dla 4 celów + **stunned** (1 tura). Krit. porażka: piorun trafia rzucającego — 2d8 obrażeń i **stunned**. |

---

## 2. Czary obronne i wzmocnienia — Tier 1–5

| Klucz | Nazwa | Szkoła | Tier | Koszt many | Obrażenia | Leczenie | Strefa | Opis działania | Test rzucania |
|---|---|---|---|---|---|---|---|---|---|
| ward_of_iron | Żelazna Straż | defense | 1 | 2 | — | — | self | Rzucający otacza się niewidocznym polem ochronnym, które pochłania następne trafienie. Tarcza utrzymuje się do końca sceny lub do pierwszego uderzenia. | INT, DC 10. Sukces: absorpcja 1d6+INT obrażeń z następnego trafienia. Krit: absorpcja 2d6+INT. Krit. porażka: tarcza destabilizuje — rzucający ma -2 do testów obronnych przez 1 turę. |
| mirror_image | Zwodnicze Kopie | defense | 2 | 3 | — | — | self | Rzucający tworzy 1d4 złudnych kopii siebie poruszających się wokół niego. Każde trafienie we wroga jest skierowane najpierw na kopię — znikają po trafieniu. | INT, DC 10. Sukces: 1d4 kopie (każda znika po trafieniu). Krit: 1d4+1 kopie. Krit. porażka: kopie wywołują zamieszanie — rzucający ma -2 do ataków przez 1 turę. |
| mage_armor | Zbroja Maga | defense | 2 | 3 | — | — | self | Rzucający oplata swe ciało warstwą zmaterializowanej energii magicznej. Zbroja zwiększa DEF o 3 i nie ogranicza rzucania czarów, lecz znika po otrzymaniu 10 obrażeń. | INT, DC 10. Sukces: +3 DEF, absorpcja 10 pkt. Krit: +4 DEF, absorpcja 15 pkt. Krit. porażka: zbroja eksploduje — 1d6 obrażeń dla rzucającego. |
| blink | Błysk Przestrzeni | defense | 3 | 3 | — | — | self | Gdy rzucający jest atakowany, może natychmiast teleportować się o kilka kroków, omijając cios. Czar działa jako reakcja i jest aktywny przez 1 turę. | INT, DC 14. Sukces: teleport jako reakcja raz w tej turze, automatyczny unik. Krit: 2 użycia. Krit. porażka: teleport nie działa — +1d4 obrażeń z ataku wroga (dezorientacja). |
| stoneskin_ally | Pancerz Sojusznika | defense | 3 | 4 | — | — | nearby | Rzucający pokrywa skórę pobliskiego sojusznika kamienną łuską, znacznie zwiększając jego wytrzymałość. Efekt trwa do końca sceny lub do otrzymania 15+ obrażeń. | INT, DC 14. Sukces: cel otrzymuje +4 DEF przez 3 tury. Krit: +5 DEF przez 4 tury. Krit. porażka: łuska pojawia się na samym rzucającym zamiast sojuszniku (fizzle efekt). |
| globe_invulnerability | Sfera Nietykalności | defense | 4 | 5 | — | — | self | Rzucający otacza się magiczną bańką blokującą wszelkie czary tier 1–3. Fizyczne ataki nadal działają. Sfera trwa 3 tury. | INT, DC 14. Sukces: blokada czarów tier 1–3 przez 3 tury. Krit: blokada czarów tier 1–4 przez 3 tury. Krit. porażka: sfera odbija czary na rzucającego — 1d8 obrażeń magicznych. |
| haste | Pośpiech | defense | 3 | 3 | — | — | nearby | Rzucający nasyca ciało wybranego sojusznika magiczną energią przyspieszającą reflexy. Cel zyskuje dodatkową akcję ataku i podwójny ruch w tej turze. | INT, DC 14. Sukces: cel zyskuje +1 akcję ataku i podwójny ruch przez 2 tury. Krit: efekt przez 3 tury + +2 do testów zręczności. Krit. porażka: cel staje się **exhausted** po wygaśnięciu przyspieszenia. |
| power_word_shield | Słowo Mocy: Tarcza | defense | 5 | 6 | — | — | any | Rzucający wypowiada pradawne słowo, które owija wybrany cel niezniszczalną sferą ochronną na jedną turę. W tym czasie cel jest odporny na wszelkie obrażenia. | INT, DC 18. Sukces: cel odporny na obrażenia przez 1 turę. Krit: 2 tury. Porażka: fizzle. Krit. porażka: słowo mocy odwraca się — cel traci odporności i otrzymuje +2d6 obrażeń od następnego ataku. |

---

## 3. Czary leczące i wsparcia — Tier 1–4

| Klucz | Nazwa | Szkoła | Tier | Koszt many | Obrażenia | Leczenie | Strefa | Opis działania | Test rzucania |
|---|---|---|---|---|---|---|---|---|---|
| minor_heal | Leczniczy Dotyk | heal | 1 | 1 | — | 1d6 | engaged | Rzucający kładzie dłoń na rannym i przepuszcza przez nią strumiień kojącej energii. Prosty, szybki czar na polu walki — niezawodny, choć ograniczony mocą. | INT, DC 10. Sukces: cel odzyskuje 1d6 HP. Krit: 2d6 HP + usunięcie kondycji **poisoned**. Krit. porażka: energia zwraca się — rzucający traci 1d4 HP. |
| purify | Oczyszczenie | heal | 1 | 2 | — | — | nearby | Rzucający rozprasza negatywne energie gnębiące cel, usuwając trucizny i choroby niskiego szczebla. Nieoceniony w lochach pełnych zatrowanych pułapek. | INT, DC 10. Sukces: usuwa **poisoned**, **cursed** (tier ≤2). Krit: usuwa wszystkie kondycje negatywne tier ≤3. Krit. porażka: rzucający przejmuje kondycję celu na 1 turę. |
| group_heal | Uzdrowienie Grupowe | heal | 2 | 4 | — | 1d6 | aoe_nearby | Rzucający rozlewa falę uzdrowieńczej energii na wszystkich sojuszników w pobliżu. Każdy wyleczyć może inną ilość, zależną od stanu rany. | INT, DC 10. Sukces: wszyscy sojusznicy w aoe_nearby odzyskują 1d6 HP. Krit: 2d6 HP. Krit. porażka: energia fizzle, nikt nie zostaje uleczony, mana stracona. |
| revitalize | Witalność | heal | 2 | 3 | — | — | nearby | Rzucający napełnia cel energią życiową, usuwając **exhausted** i przywracając mu zdolność do dalszej walki. Czar nie leczy obrażeń, lecz przywraca energię. | INT, DC 10. Sukces: usuwa **exhausted**, cel zyskuje +1 do testów przez 2 tury. Krit: usuwa **exhausted** i **slowed**, +2 do testów przez 3 tury. Krit. porażka: fizzle — mana stracona. |
| mass_restoration | Masowe Przywrócenie | heal | 3 | 5 | — | 2d8 | aoe_nearby | Potężna fala uzdrowieńczej energii emanuje z rzucającego, obejmując wszystkich pobliskich sojuszników. Czar leczy obrażenia i usuwa negatywne kondycje niższego rzędu. | INT, DC 14. Sukces: 2d8 HP + usuwa **poisoned**, **slowed** dla wszystkich sojuszników w zasięgu. Krit: 3d8 HP + usuwa wszystkie kondycje tier ≤3. Krit. porażka: fala wytraca się — 1d6 dla rzucającego. |
| regenerate | Regeneracja | heal | 3 | 4 | — | 1d6/tura | nearby | Rzucający nakłada na cel tkankę uzdrowieńczą, która regeneruje obrażenia przez kilka tur. Efekt trwa 3 tury, dając po 1d6 HP na początku każdej tury celu. | INT, DC 14. Sukces: cel odzyskuje 1d6 HP na początku każdej z 3 tur. Krit: 2d6/turę przez 3 tury + usuwa **poisoned**. Krit. porażka: efekt się odwraca — cel traci 1d4 HP przez 2 tury. |
| divine_shield_ally | Ochronna Aura | heal | 4 | 5 | — | 2d6 | any | Rzucający otacza odległy cel sferą ochronnej energii, która jednocześnie leczy rany i zmniejsza kolejne obrażenia o 2 na czas trwania. Trwa do końca sceny. | INT, DC 14. Sukces: 2d6 natychmiastowego leczenia + -2 do otrzymywanych obrażeń przez 3 tury. Krit: 3d6 + -3 do obrażeń przez 4 tury. Krit. porażka: aura błędnie kieruje energie — rzucający obrywa 1d8. |

---

## 4. Efekty i kondycje — Tier 1–5

| Klucz | Nazwa | Szkoła | Tier | Koszt many | Obrażenia | Leczenie | Strefa | Opis działania | Test rzucania |
|---|---|---|---|---|---|---|---|---|---|
| frost_grip | Mroźny Uchwyt | effect | 1 | 2 | — | — | any | Rzucający sprowadza na cel przenikliwy mróz, który krępuje ruchy i zwalnia reflexy. Cel dostaje **slowed** na 2 tury, zmniejszając swoją akcję ruchu o połowę. | INT, DC 10. Sukces: cel **slowed** na 2 tury. Krit: **frozen** na 1 turę. Porażka: fizzle. Krit. porażka: mróz dociera do rzucającego — **slowed** na 1 turę. |
| hex | Klątwa | effect | 2 | 2 | — | — | any | Rzucający rzuca mroczną klątwę na cel, osłabiając jego ducha i powodząc pecha. Cel otrzymuje kondycję **cursed** i ma -2 do wszystkich testów przez czas trwania. | INT, DC 10. Sukces: cel **cursed** na 3 tury (-2 do testów). Krit: **cursed** na 5 tur (-3 do testów). Krit. porażka: klątwa odbija się — rzucający ma **cursed** na 1 turę. |
| charm_person | Urok Osoby | effect | 2 | 3 | — | — | nearby | Rzucający wplata w umysł celu czarującą sugestię, skłaniając go do postrzegania rzucającego jako przyjaciela. Cel z kondycją **charmed** nie atakuje rzucającego. | CHA, DC 10. Sukces: cel **charmed** na scenę (nie atakuje rzucającego). Krit: cel staje się tymczasowym sojusznikiem na 2 tury. Krit. porażka: cel zdaje sobie sprawę z próby i staje się wrogi. |
| poison_touch | Trujący Dotyk | effect | 2 | 2 | 1d4 | — | engaged | Rzucający powleka dłoń magiczną trucizną, a następnie dotyka wroga. Obrażenia są skromne, lecz cel staje się **poisoned** — traci 1d4 HP na początku każdej tury przez 3 tury. | INT, DC 10. Sukces: 1d4 + **poisoned** (1d4/tura przez 3 tury). Krit: 2d4 + **poisoned** (2d4/tura przez 3 tury). Krit. porażka: trucizna przesiąka przez dłoń — rzucający **poisoned** na 1 turę. |
| confusion | Zamęt | effect | 3 | 3 | — | — | any | Rzucający bombarduje umysł celu chaotycznymi obrazami, powodując dezorientację i niezdolność do skupienia. Cel z kondycją **confused** wykonuje w każdej turze losową akcję. | INT, DC 14. Sukces: cel **confused** na 2 tury (losowe akcje). Krit: **confused** na 3 tury + ma -3 do testów przez ten czas. Krit. porażka: chaos wraca — rzucający **confused** na 1 turę. |
| berserk_curse | Klątwa Szału | effect | 3 | 4 | — | — | any | Rzucający wyzwala w celu prymitywną wściekłość, zmuszając go do atakowania najbliższej istoty bez rozróżnienia sojusznik/wróg. Trwa 2 tury lub do rozproszenia. | INT, DC 14. Sukces: cel **berserk** na 2 tury. Krit: **berserk** na 3 tury, niemożność ucieczki. Krit. porażka: wściekłość skupia się na rzucającym — cel atakuje wyłącznie rzucającego przez 1 turę. |
| blind | Oślepienie | effect | 2 | 3 | — | — | any | Rzucający ciska w oczy celu falę oślepiającego światła lub magicznej ciemności. Cel z kondycją **blinded** ma -4 do ataków i testów wymagających wzroku. | INT, DC 10. Sukces: cel **blinded** na 2 tury. Krit: **blinded** na 3 tury + **slowed**. Krit. porażka: blask razi rzucającego — **blinded** na 1 turę. |
| mass_fear | Masowy Strach | effect | 4 | 5 | — | — | aoe_nearby | Rzucający emanuje falą paraliżującego terroru, ogarniaąc wrogów wokół panicznym strachem. Cele z niskim MOrale uciekają, pozostałe mają -2 do testów i ataków. | CHA, DC 14. Sukces: wszyscy wrogowie w aoe_nearby **slowed** i -2 do ataków przez 2 tury. Krit: uciekają przez 2 tury. Krit. porażka: strach ogarnia sojuszników zamiast wrogów. |
| stun_bolt | Piorun Ogłuszenia | effect | 4 | 4 | 1d6 | — | any | Rzucający wystrzeliwuje skondensowaną kulę energii w cel, która przy trafieniu ogłusza zmysły. Cel dostaje kondycję **stunned** i traci następną akcję. | INT, DC 14. Sukces: 1d6 + **stunned** (1 tura, traci akcję). Krit: 2d6 + **stunned** 2 tury. Krit. porażka: energia wstrząsa rzucającym — **stunned** na 1 turę. |
| mass_stun | Ogłuszenie Zbiorowe | effect | 5 | 6 | — | — | aoe_nearby | Rzucający wyzwala pulsacyjną falę magicznego wstrząsu, ogłuszając wszystkich wrogów w pobliżu jednocześnie. Efekt jest krótki, lecz daje sojusznikom cenną chwilę przewagi. | INT, DC 18. Sukces: wszyscy wrogowie w aoe_nearby **stunned** na 1 turę. Krit: **stunned** na 2 tury. Krit. porażka: fala ogłusza wszystkich wokół, w tym sojuszników, na 1 turę. |

---

## 5. Czary użytkowe i narracyjne — Tier 1–5

| Klucz | Nazwa | Szkoła | Tier | Koszt many | Obrażenia | Leczenie | Strefa | Opis działania | Test rzucania |
|---|---|---|---|---|---|---|---|---|---|
| detect_magic | Wykrycie Magii | narrative | 1 | 1 | — | — | self | Rzucający otwiera trzecie oko na prądy magii, widząc przez krótki czas aurę magiczną wokół przedmiotów, miejsc i istot. Użyteczny przy badaniu zaczarowanych artefaktów. | INT, DC 10. Sukces: rzucający wykrywa aurę magiczną w zasięgu wzroku przez 10 minut. Krit: poznaje też typ szkoły i tier. Krit. porażka: aury magii są widoczne przez 1 turę — przytłaczają wizję. |
| silent_step | Cichy Krok | utility | 1 | 1 | — | — | self | Rzucający otacza swoje kroki warstwą tłumiącą dźwięk, przez chwilę poruszając się bez szmeru. Przydatny w skradaniu się i unikaniu czujnych strażników. | INT, DC 10. Sukces: +3 do testów skradania przez 1 scenę. Krit: +5 do testów skradania + cisza wokół przez 2 tury. Krit. porażka: zamiast ciszy, hałas — -2 do testów skradania przez 1 turę. |
| levitate | Lewitacja | utility | 2 | 2 | — | — | self | Rzucający unosi się nad ziemią na kilka chwil, ignorując pułapki na podłodze i umożliwiając dotarcie do wyższych półek lub pokonanie przeszkód. | INT, DC 10. Sukces: lewitacja przez 2 tury (niemożność ataku, swobodny ruch pionowy). Krit: lewitacja przez 4 tury z możliwością powolnego lotu. Krit. porażka: niestabilność — rzucający spada z 2m, 1d4 obrażeń. |
| phantom_image | Fantomowy Obraz | utility | 2 | 2 | — | — | nearby | Rzucający kreuje przekonującą iluzję wizualną — postać, przedmiot lub scenerię — w pobliżu. Iluzja nie wydaje dźwięku, lecz może być mylona ze wsprawdziwym obiektem. | INT, DC 10. Sukces: iluzja wizualna utrzymuje się przez 3 tury; wrogowie z INT≥12 mogą ją przejrzeć. Krit: iluzja wydaje też dźwięki, trwa 5 tur. Krit. porażka: iluzja jest oczywista i wyśmieje rzucającego. |
| arcane_lock | Magiczna Zasuwka | utility | 2 | 2 | — | — | nearby | Rzucający pieczętuje drzwi, skrzytyrzynkę lub furtkę magiczną zasuwą nie do sforsowania bez odpowiedniego zaklęcia lub DC 20 STR. Trwała do rozproszenia. | INT, DC 10. Sukces: obiekt zapieczętowany do rozproszenia (STR DC 20 lub Dispel). Krit: +5 do DC sforsowania. Krit. porażka: magiczna zasuwka zaciska się na dłoni rzucającego — **slowed** na 1 turę. |
| scrying | Dalekowidztwo | narrative | 3 | 3 | — | — | self | Rzucający przywołuje mistyczne oko, które może podróżować w myśl po dowolnym miejscu, które rzucający zna. Przydatne do zbierania informacji i zwiadów. | INT, DC 14. Sukces: rzucający widzi wybraną lokację przez 5 minut (bez ingerencji). Krit: może też słyszeć i trwa 10 minut. Krit. porażka: mistyczne oko przyciąga wzrok wroga — rzucający jest namierzony. |
| teleport_short | Blink Step | utility | 3 | 3 | — | — | any | Rzucający znika w iskrze energii i natychmiast pojawia się w wybranym miejscu w zasięgu wzroku. Użyteczny do omijania przeszkód i zmiany pozycji w walce. | INT, DC 14. Sukces: teleport do dowolnego miejsca w zasięgu wzroku. Krit: może zabrać ze sobą jednego sojusznika. Krit. porażka: teleport się rozdziela — rzucający pojawia się 1d6 metrów od celu w losowym kierunku. |
| mind_read | Czytanie Myśli | narrative | 3 | 3 | — | — | engaged | Rzucający wnika delikatnie w myśli pobliskiej istoty, odczytując jej intencje i aktualne myśli. Ofiara zazwyczaj nie jest świadoma ingerencji przy sukcesie. | INT vs WIS celu, DC 14. Sukces: rzucający poznaje aktualne myśli celu (intencje w tej scenie). Krit: rzucający może zadać 1 pytanie "tak/nie". Krit. porażka: cel wyczuwa włamanie — staje się wrogi. |
| dispel_magic | Rozproszenie Magii | utility | 4 | 4 | — | — | any | Rzucający wysyła falę antymaginiczną, która niszczy aktywne zaklęcia na celu lub obszarze. Skuteczność zależy od tieru zwalczanego czaru. | INT, DC 14+tier czaru. Sukces: niszczy jeden aktywny czar tier ≤4. Krit: niszczy wszystkie aktywne czary celu tier ≤4. Krit. porażka: fala antymagnii uderza w rzucającego — traci aktywne czary. |
| major_illusion | Wielka Iluzja | utility | 4 | 5 | — | — | aoe_nearby | Rzucający tworzy rozbudowaną wielozmysłową iluzję obejmującą cały obszar — fałszywe ściany, stwory, tereny. Trwa 10 minut lub do rozproszenia przez INT DC 16. | INT, DC 14. Sukces: wielozmysłowa iluzja trwa 10 min (INT DC 16 by przejrzeć). Krit: trwa 30 min, DC 18 by przejrzeć. Krit. porażka: iluzja obraca się — własna drużyna ją widzi. |

---

## 6. Czary przywołania — Tier 3–6

| Klucz | Nazwa | Szkoła | Tier | Koszt many | Obrażenia | Leczenie | Strefa | Opis działania | Test rzucania |
|---|---|---|---|---|---|---|---|---|---|
| summon_familiar | Przywołanie Zwiadowcy | summon | 3 | 3 | — | — | self | Rzucający przywołuje magiczne stworzenie - raven, szczura lub kota - które służy jako zwiadowca i pomocnik. Znajomy widzi, słyszy i przekazuje informacje przez magiczną więź. | INT, DC 14. Sukces: znajomy przywołany na 1 scenę (może zwiadować). Krit: znajomy pojawia się na 2 sceny + może atakować za 1d4. Krit. porażka: stworzenie jest wrogie — ucieka lub atakuje. |
| summon_elemental | Przywołanie Elementala | summon | 4 | 6 | 2d8 | — | nearby | Rzucający rozdziera zasłonę między planami, wzywając elementala żywiołu (ogień/woda/ziemia/powietrze). Elemental walczy u boku rzucającego przez 3 tury. | INT, DC 14. Sukces: elemental (HP 20, Atak 2d8) na 3 tury. Krit: elemental (HP 30, Atak 3d8) na 4 tury + ma specjalną zdolność żywiołu. Krit. porażka: elemental przywołany, lecz niezwiązany — atakuje losowe cele w tym rzucającego. |
| animate_dead | Ożywienie Martwego | summon | 4 | 5 | — | — | engaged | Rzucający tchnął mrocze nekromantyczne zaklęcie, wzbudzając do życia leżące zwłoki. Ożywieniec działa przez 1 scenę, atakując wrogów wskazanych przez rzucającego (1d6). | INT, DC 14. Sukces: szkielet/zombie (HP 15, Atak 1d6) na 1 scenę. Krit: 2 ożywieńce lub jeden o wzmocnionych statystykach. Krit. porażka: ożywieniec powstaje, lecz nieposłuszny — atakuje najbliższą żywą istotę. |
| shadow_clone | Cień Bliźniak | summon | 4 | 5 | 1d8 | — | self | Rzucający materializuje własny cień jako walczącego sobowtóra, który odzwierciedla jego ruchy bojowe. Sobowtór ma połowę HP rzucającego i atak 1d8, trwa 2 tury. | INT, DC 14. Sukces: sobowtór (HP = połowa max rzucającego, Atak 1d8) na 2 tury. Krit: Atak 2d8, na 3 tury + absorbuje 1 trafienie za rzucającego. Krit. porażka: cień staje się autonomiczny i atakuje rzucającego. |
| greater_elemental | Wielki Elemental | summon | 5 | 7 | 3d8 | — | nearby | Rzucający przywołuje potężnego elementala najwyższego rzędu, zdolnego do obalenia nawet silnych przeciwników. Istota walczy przez 3 tury, a jej obecność zmienia bieg bitwy. | INT, DC 18. Sukces: Wielki Elemental (HP 50, Atak 3d8, Specjalna: AoE 2d6 raz/scenę) na 3 tury. Krit: HP 70, Atak 4d8, 2 użycia AoE. Krit. porażka: istota wymyka się kontroli — niszczy losowe cele przez 2 tury. |
| planar_ally | Posłaniec Planu | summon | 6 | 8 | 4d8 | — | nearby | Rzucający otwiera bramę do odległego planu egzystencji, przywołując potężnego wojownika lub anioła. Istota ta posiada boskie zdolności i walczy przez całą scenę, lecz żąda przysługi. | INT, DC 18. Sukces: Posłaniec (HP 80, Atak 4d8, Leczenie: 3d6 raz, Odporność: magia tier ≤4) na 1 scenę. Krit: istota jest wolna, bez żądania. Krit. porażka: brama otwiera się na złą stronę — demon/widmo (HP 60, wrogie) pojawia się zamiast. |

---

## Podsumowanie — statystyki bilansu czarów

| Tier | Liczba czarów | Szkoły |
|---|---|---|
| 1 | 7 | attack ×3, effect ×1, heal ×1, narrative ×1, utility ×1 |
| 2 | 12 | attack ×2, attack_aoe ×1, defense ×2, effect ×3, heal ×2, utility ×2 |
| 3 | 12 | attack ×1, attack_aoe ×1, defense ×2, effect ×1, heal ×2, narrative ×2, summon ×1, utility ×2 |
| 4 | 11 | attack_aoe ×2, defense ×2, effect ×2, heal ×1, summon ×3, utility ×1 |
| 5 | 7 | attack ×1, attack_aoe ×2, defense ×1, effect ×2, summon ×1, utility ×1 |
| 6 | 1 | summon ×1 |
| **Łącznie** | **50** | |

---

*Dokument wygenerowany dla projektu AI GM | Faza: system czarów | Wersja 1.0*
