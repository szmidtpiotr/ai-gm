# Poprawki tekstów — AI-GM Showcase

> **Format pliku dla agenta edycyjnego:**
> Każda poprawka zawiera:
> - **SEKCJA** — gdzie na stronie się znajduje
> - **ORYGINAŁ** — dokładny cytat z kodu źródłowego strony (znajdź po tym tekście)
> - **ZAMIEŃ NA** — nowa wersja
> - **POWÓD** — krótkie wyjaśnienie zmiany
>
> Agent powinien znaleźć tekst ORYGINAŁ w plikach HTML/JS strony i zastąpić go tekstem ZAMIEŃ NA.

---

## POPRAWKA 01
**SEKCJA:** Section 2 — Spis treści (Table of Contents)

**ORYGINAŁ:**
```
III — Księga Zasad — Żywy dokument mechanik: rzuty, walka strefowa, magia uczonego, warunki i DC.
```

**ZAMIEŃ NA:**
```
III — Księga Zasad — Wszystkie zasady gry w jednym miejscu: jak rzucać kośćmi, jak działa walka, czary i trudność zadań.
```

**POWÓD:** „Walka strefowa", „magia uczonego", „DC" to nazwy wewnętrzne systemu. Nowy gracz nie wie, co znaczą przed wejściem do gry. Opis powinien mówić *co znajdę*, nie *jak to się technicznie nazywa*.

---

## POPRAWKA 02
**SEKCJA:** Section 3 — Jak się gra / Step 2

**ORYGINAŁ:**
```
Silnik rzuca k20 + cechy + biegłości przeciw DC. Nat 20 i Nat 1 zmieniają los. Żadnego zmyślania wy…
```

**ZAMIEŃ NA:**
```
Gra rzuca kością i dodaje cechy twojego bohatera do wyniku — im wyższy rzut, tym lepiej. Najwyższy możliwy wynik (20) i najniższy (1) mają szczególne konsekwencje. Wszystko rozstrzyga matematyka, nie kaprysy AI.
```

**POWÓD:** „k20", „cechy + biegłości przeciw DC", „Nat 20 i Nat 1" — terminologia rodem z D&D, całkowicie nieczytelna dla kogoś, kto nigdy nie grał w RPG. Mechanika jest prosta — wystarczy opisać ją prostym językiem.

---

## POPRAWKA 03
**SEKCJA:** Section 3 — Jak się gra / Step 3

**ORYGINAŁ:**
```
AI opisuje skutek zgodnie z rzutem i stanem świata — po polsku, klimatycznie, spójnie z tym, co był…
```

**ZAMIEŃ NA:**
```
AI opisuje, co się stało — po polsku, klimatycznie i spójnie z całą dotychczasową historią twojej postaci.
```

**POWÓD:** „Stan świata" to wewnętrzna nazwa technicznego systemu (World State). Dla gracza nie ma znaczenia — liczy się to, że AI pamięta i jest spójne. Warto to powiedzieć wprost.

---

## POPRAWKA 04
**SEKCJA:** Section 3 — Jak się gra / Step 4

**ORYGINAŁ:**
```
Walka strefowa, łup, punkty doświadczenia, awanse, czary. Świat i twój bohater realnie się zmieniaj…
```

**ZAMIEŃ NA:**
```
Zdobywasz łupy, doświadczenie i nowe umiejętności. Twój bohater się zmienia — i świat razem z nim.
```

**POWÓD:** „Walka strefowa" znowu pojawia się jako termin bez wyjaśnienia. Na etapie „jak się gra" (krok 4.) gracz chce wiedzieć, że będzie postęp — nie jakie systemy za tym stoją.

---

## POPRAWKA 05
**SEKCJA:** Section 4 — Tabela porównawcza (AI-GM — gra z systemami)

**ORYGINAŁ:**
```
Maszyna Stanu Świata pilnuje prawdy — koniec halucynacji
```

**ZAMIEŃ NA:**
```
Gra pamięta wszystko, co zrobiłeś — AI nie zmyśla faktów z powietrza
```

**POWÓD:** „Maszyna Stanu Świata" to wewnętrzna nazwa architektury systemu. „Halucynacje" to termin z inżynierii LLM — brzmi niepokojąco dla kogoś niezaznajomionego. Korzyść dla gracza jest prosta: AI nie kłamie i nie zapomina.

---

## POPRAWKA 06
**SEKCJA:** Section 4 — Tabela porównawcza (AI-GM — gra z systemami)

**ORYGINAŁ:**
```
Walka strefowa, pancerz, mana, miscast, loot, XP
```

**ZAMIEŃ NA:**
```
Prawdziwa walka z pancerzem i obrażeniami, magia z ryzykiem, łupy i punkty doświadczenia
```

**POWÓD:** „Miscast", „loot", „XP" — mieszanka angielskich skrótów i terminu z gier karcianych, nieczytelna dla ogółu. „Walka strefowa" znowu bez wyjaśnienia.

---

## POPRAWKA 07
**SEKCJA:** Section 4 — Tabela porównawcza (AI-GM — gra z systemami)

**ORYGINAŁ:**
```
Lochy kafelkowe, solo i wspólne sesje multiplayer
```

**ZAMIEŃ NA:**
```
Eksploracja lochów na mapie, gra solo lub z przyjaciółmi
```

**POWÓD:** „Lochy kafelkowe" to nazwa wewnętrzna systemu (Dungeon Mode z kafelkową mapą). „Multiplayer" nie jest złym słowem, ale w połączeniu z „lochami kafelkowymi" brzmi technicznie. Lepiej opisać *co gracz robi*, nie *jak to działa*.

---

## POPRAWKA 08
**SEKCJA:** Section 6 — Księga Zasad (karta: Rzut d20)

**ORYGINAŁ:**
```
d20 + cecha + biegłość ≥ DC. Nat 20 i Nat 1 zmieniają los.
```

**ZAMIEŃ NA:**
```
Rzucasz dwudziestościenną kością i dodajesz cechy bohatera. Im wyższy wynik, tym większa szansa sukcesu. Wynik 20 to wielki triumf — wynik 1 to spektakularna porażka.
```

**POWÓD:** Ta karta jest na stronie-wizytówce skierowanej do nowych graczy. „DC", „Nat 20", „Nat 1", wzór matematyczny z „≥" — wszystko to wymaga znajomości konwencji RPG. Opis korzyści jest znacznie lepszy.

---

## POPRAWKA 09
**SEKCJA:** Section 6 — Księga Zasad (karta: Walka strefowa)

**ORYGINAŁ:**
```
Zwarcie i dystans, jeden test obrony, pancerz redukuje obrażenia.
```

**ZAMIEŃ NA:**
```
Walczysz w zwarciu lub z dystansu. Jeden rzut decyduje, czy cios trafia — pancerz zmniejsza otrzymane obrażenia.
```

**POWÓD:** „Jeden test obrony" — techniczna nazwa mechaniki (przeprojektowanej w historii jako duży krok). Dla gracza liczy się to, że jest prosto i uczciwie.

---

## POPRAWKA 10
**SEKCJA:** Section 6 — Księga Zasad (karta: Magia uczonego)

**ORYGINAŁ:**
```
Mana, rangi zaklęć i ryzyko miscastu — czerpiesz z Rdzenia.
```

**ZAMIEŃ NA:**
```
Czary kosztują manę i mają różne poziomy mocy. Każde zaklęcie niesie ryzyko — im potężniejsze, tym niebezpieczniejsze w użyciu.
```

**POWÓD:** „Rangi zaklęć", „miscast", „czerpiesz z Rdzenia" — dwa pierwsze terminy są techniczne lub angielskie, trzeci to lore-reference bez kontekstu. Na wizytówce gracz powinien poczuć klimat i zrozumieć zasadę.

---

## POPRAWKA 11
**SEKCJA:** Section 6 — Księga Zasad (karta: Cechy i warunki)

**ORYGINAŁ:**
```
Siedem cech, stany, DC od Łatwego po Legendarne.
```

**ZAMIEŃ NA:**
```
Twój bohater ma siedem cech określających, w czym jest dobry. Każde zadanie ma swoją trudność — od banalnego po legendarny wyczyn.
```

**POWÓD:** „Stany" (status effects) i „DC" to terminy wewnętrzne. Gracz powinien wiedzieć, *po co* cechy istnieją i jak działa trudność.

---

## POPRAWKA 12
**SEKCJA:** Section 7 — FAQ (pytanie: Czy muszę mieć własny klucz do AI?)

**ORYGINAŁ:**
```
Możesz grać na własnym kluczu LLM (pełna kontrola i prywatność) albo skorzystać z hostowanej wersji…
```

**ZAMIEŃ NA:**
```
Możesz grać korzystając z własnego konta u dostawcy AI (wtedy ty kontrolujesz koszty i dane) albo skorzystać z gotowej, hostowanej wersji gry — bez konfiguracji.
```

**POWÓD:** „Własny klucz LLM" — dla zwykłego gracza kompletnie niezrozumiałe. Nawet jeśli ta opcja istnieje, trzeba ją opisać skutkami dla gracza (kontrola, prywatność, koszt), nie terminologią techniczną.

---

## POPRAWKA 13
**SEKCJA:** Section 7 — FAQ (pytanie: Czy moje wybory naprawdę coś zmieniają?)

**ORYGINAŁ:**
```
Tak. Maszyna Stanu Świata pilnuje spójności — to, co zrobisz, zostaje zapamiętane i wpływa na świat…
```

**ZAMIEŃ NA:**
```
Tak. Gra zapamiętuje każdą twoją decyzję — postacie, które spotkałeś, miejsca, które odwiedziłeś, i skutki twoich wyborów. Świat reaguje na to, co zrobiłeś.
```

**POWÓD:** „Maszyna Stanu Świata" — po raz kolejny techniczna nazwa wewnętrzna. Odpowiedź na FAQ powinna dawać konkretne przykłady, nie ujawniać architektury systemu.

---

## POPRAWKA 14
**SEKCJA:** Section 7 — Roadmapa (W toku)

**ORYGINAŁ:**
```
Balans klas i strojenie liczb w Sandboxie
```

**ZAMIEŃ NA:**
```
Balansowanie klas i dopracowywanie liczb
```

**POWÓD:** „Strojenie liczb w Sandboxie" — „strojenie" (tuning) to żargon deweloperski, „Sandbox" to wewnętrzna nazwa środowiska testowego. Gracz nie musi wiedzieć, gdzie to się odbywa.

---

## POPRAWKA 15
**SEKCJA:** Section 7 — Roadmapa (W toku)

**ORYGINAŁ:**
```
Refaktor i porządkowanie silnika
```

**ZAMIEŃ NA:**
```
Porządkowanie i optymalizacja silnika gry
```

**POWÓD:** „Refaktor" to slang programistyczny (refactoring). Dla gracza bardziej zrozumiałe jest „porządkowanie i optymalizacja" — daje poczucie, że gra będzie działać lepiej.

---

## POPRAWKA 16
**SEKCJA:** Section 7 — Roadmapa (Planowane)

**ORYGINAŁ:**
```
Głos postaci i lektor (TTS) oraz generacja obrazów offline
```

**ZAMIEŃ NA:**
```
Głos postaci i lektor oraz generowanie ilustracji do przygód
```

**POWÓD:** „TTS" (Text-to-Speech) to skrót techniczny. „Offline" sugeruje problemy z połączeniem, a nie jest to intencja — chodzi o generację lokalną/prywatną. Lepiej opisać funkcję z perspektywy gracza.

---

## POPRAWKA 17
**SEKCJA:** Section 8 — Historia / „Kość, która naprawdę pada"

**ORYGINAŁ:**
```
Kluczowa zmiana w podejściu była taka: wynik liczy kod, nie model. Model dostaje gotowy rezultat („…
```

**ZAMIEŃ NA:**
```
Kluczowa zmiana była prosta: wynik rzutu oblicza gra — nie AI. AI dostaje gotowy rezultat i tylko opisuje, co się stało. Nie może go zmienić ani podkolorować.
```

**POWÓD:** „Wynik liczy kod, nie model" — zdanie z perspektywy dewelopera, nie gracza. Warto powiedzieć, *co to znaczy dla gracza*: że AI nie może oszukiwać wyniku.

---

## POPRAWKA 18
**SEKCJA:** Section 8 — Historia / „Maszyna stanu świata — koniec zmyślania"

**ORYGINAŁ:**
```
Punktowe łatki na halucynacje („wstrzyknij przypomnienie do promptu") przestały wystarczać.
```

**ZAMIEŃ NA:**
```
Drobne poprawki — dodawanie przypomnień do każdej wiadomości do AI — przestały wystarczać.
```

**POWÓD:** „Halucynacje" i „wstrzyknij przypomnienie do promptu" — żargon inżynierii LLM. Czytelnik-gracz nie będzie wiedział, o czym mowa.

---

## POPRAWKA 19
**SEKCJA:** Section 8 — Historia / „Maszyna stanu świata — koniec zmyślania"

**ORYGINAŁ:**
```
Zmieniła się filozofia współpracy z modelem. Wcześniej AI było autorem rzeczywistości; teraz stało…
```

**ZAMIEŃ NA:**
```
Zmieniła się filozofia całego projektu. Wcześniej AI decydowało o tym, co jest prawdą w świecie gry. Teraz to gra — jej mechaniki i historia — są źródłem prawdy, a AI tylko opowiada to, co wynika z zasad.
```

**POWÓD:** „Współpraca z modelem" — żargon ML. Zdanie urywa się. Warto dokończyć myśl w sposób zrozumiały dla gracza: co to znaczy w praktyce.

---

## POPRAWKA 20
**SEKCJA:** Section 8 — Historia / „Refaktor panelu, czyli sprzątanie po sobie"

**ORYGINAŁ:**
```
Stara wersja była monolitem…
```
*(oraz w dalszej narracji)*
```
Lekcja z tego etapu wracała potem regularnie: kod, którego nie da się czysto rozwijać, jest długiem…
```

**ZAMIEŃ NA:**
```
Stara wersja była jednym wielkim, splątanym blokiem kodu…
```
*(oraz)*
```
Lekcja z tego etapu wracała potem regularnie: funkcje, których nie da się rozwijać bez psucia reszty, to dług, który kiedyś trzeba spłacić.
```

**POWÓD:** „Monolit" i „dług techniczny" to terminy z inżynierii oprogramowania. Historia jest pisana do graczy — można je zastąpić obrazowymi opisami, które przekazują to samo znaczenie.

---

## POPRAWKA 21
**SEKCJA:** Section 8 — Historia / „Świat zaczyna mieć ceny"

**ORYGINAŁ:**
```
Pojawił się system afiksów — typowane „obiekty efektów" nałożone na przedmioty.
```

**ZAMIEŃ NA:**
```
Pojawił się system modyfikatorów — specjalne właściwości nakładane na przedmioty, które zmieniają ich działanie.
```

**POWÓD:** „System afiksów" i „typowane obiekty efektów" to terminologia deweloperska/wewnętrzna. Gracz zrozumie „modyfikatory" lub „specjalne właściwości".

---

## POPRAWKA 22
**SEKCJA:** Section 8 — Historia / „Świat zaczyna mieć ceny"

**ORYGINAŁ:**
```
Kluczowe było słowo „zbalansować". Powstał analityczny model ekonomii i telemetria złota — żeby decyzje…
```

**ZAMIEŃ NA:**
```
Kluczowe było słowo „zbalansować". Powstały narzędzia do śledzenia przepływu złota w grze — żeby decyzje o cenach i nagrodach były oparte na danych, nie intuicji.
```

**POWÓD:** „Telemetria złota" — termin z inżynierii oprogramowania / observability. „Analityczny model ekonomii" brzmi jak raport finansowy. Warto opisać cel: *po co* to zbudowano.

---

## POPRAWKA 23
**SEKCJA:** Section 8 — Historia / „Lochy kafelkowe — gra w grze"

**ORYGINAŁ:**
```
Loch to graf połączonych komnat — trzeba…
```

**ZAMIEŃ NA:**
```
Loch to sieć połączonych komnat — każda z inną zawartością i wyjściami do sąsiednich pomieszczeń.
```

**POWÓD:** „Graf" to termin z teorii grafów / informatyki. „Sieć połączonych komnat" mówi to samo i jest zrozumiała dla każdego.

---

## POPRAWKA 24
**SEKCJA:** Section 8 — Historia / „Lochy kafelkowe — gra w grze"

**ORYGINAŁ:**
```
Lochom towarzyszyła Faza obserwowalności: zbudowaliśmy zapis zdarzeń gry i wywołań modelu oraz inte…
```

**ZAMIEŃ NA:**
```
Przy okazji dodaliśmy też narzędzia diagnostyczne: zapis zdarzeń w grze i podgląd tego, co AI robi za kulisami — żeby łatwiej wyłapywać błędy.
```

**POWÓD:** „Faza obserwowalności", „wywołań modelu", „integracja" — żargon DevOps i inżynierski. Można opisać to z perspektywy gracza/dewelopera bez technikaliów.

---

## POPRAWKA 25
**SEKCJA:** Section 8 — Historia / „Silnik umiejętności, stanów i Inspektor Bohatera"

**ORYGINAŁ:**
```
Faza S dała silnik umiejętności i stanów — buffy, debuffy, efekty trwałe i chwilowe.
```

**ZAMIEŃ NA:**
```
Powstał system umiejętności i stanów — wzmocnienia, osłabienia, efekty tymczasowe i trwałe.
```

**POWÓD:** „Faza S" to wewnętrzna nazwa etapu deweloperskiego. „Buffy i debuffy" to żargon gier, ale niekoniecznie znany każdemu — warto użyć polskich odpowiedników.

---

## POPRAWKA 26
**SEKCJA:** Section 8 — Historia / „Silnik umiejętności, stanów i Inspektor Bohatera"

**ORYGINAŁ:**
```
Migracja bazy danych przeprowadzona w złym momencie…
```

**ZAMIEŃ NA:**
```
Aktualizacja struktury bazy danych przeprowadzona w złym momencie…
```

**POWÓD:** „Migracja bazy danych" — termin techniczny. „Aktualizacja struktury" jest bliższe temu, co laik zrozumie.

---

## POPRAWKA 27
**SEKCJA:** Section 8 — Historia / „Jeden rzut obrony — koniec podwójnej kary"

**ORYGINAŁ:**
```
świadomie przeprojektowaliśmy zablokowaną, „świętą" mechanikę
```

**ZAMIEŃ NA:**
```
świadomie zmieniliśmy mechanikę, która wydawała się nie do ruszenia
```

**POWÓD:** „Zablokowaną, świętą mechanikę" — żargon game-design. Lepiej oddać sens: że zmienili coś, co wszyscy traktowali jako nienaruszalne.

---

## POPRAWKA 28
**SEKCJA:** Section 8 — Historia / „Jeden rzut obrony — koniec podwójnej kary"

**ORYGINAŁ:**
```
Nowy model jest prostszy i uczciwszy: jeden test obronny na trafienie, koniec. Pancerz przestał być…
```

**ZAMIEŃ NA:**
```
Nowy system jest prostszy i uczciwszy: jeden rzut decyduje o trafieniu. Pancerz nie blokuje ataków — zmniejsza obrażenia. Koniec podwójnej kary.
```

**POWÓD:** „Test obronny" — wewnętrzna terminologia. Warto dokończyć zdanie i wyjaśnić, co zmieniono (pancerz).

---

## POPRAWKA 29
**SEKCJA:** Section 8 — Historia / „Magia z Rdzenia i wspólne sesje"

**ORYGINAŁ:**
```
Multiplayer wymusił też dojrzałe myślenie o bezpieczeństwie — pojawiła się ochrona przed próbami „p…
```

**ZAMIEŃ NA:**
```
Multiplayer wymusił też myślenie o bezpieczeństwie — pojawiła się ochrona przed graczami próbującymi manipulować AI, żeby obejść zasady gry.
```

**POWÓD:** Zdanie urwane. „Próbami p…" — kontekst wyraźnie sugeruje „prompt injection" (atak polegający na wstrzykiwaniu poleceń do AI). Warto opisać to prostym językiem, nie technicznym terminem.

---

## POPRAWKA 30
**SEKCJA:** Section 8 — Historia / „Żywa Księga, kanon świata i sprzątanie monolitów"

**ORYGINAŁ:**
```
Najświeższy etap to wielkie porządki w kodzie (Faza R): rozbicie potężnych, splątanych plików na cz…
```

**ZAMIEŃ NA:**
```
Najświeższy etap to wielkie porządki w kodzie: rozbicie rozrośniętych plików na mniejsze, wyspecjalizowane moduły — żeby każdy fragment systemu robił jedną rzecz dobrze.
```

**POWÓD:** „Faza R" to wewnętrzne oznaczenie etapu. Wystarczy opisać co i po co — bez etykiety wewnętrznej.

---

## PODSUMOWANIE WZORCOWE

Wzorzec dla agenta edycyjnego:

```
Znajdź w plikach HTML/JS/JSON strony dokładny ciąg znaków z pola ORYGINAŁ.
Zastąp go ciągiem z pola ZAMIEŃ NA.
Jeśli ORYGINAŁ jest urwany (kończy się na „…"), wyszukaj unikalny fragment bez „…".
Nie zmieniaj niczego poza wskazanym fragmentem.
Po każdej zamianie sprawdź, czy strona renderuje się poprawnie.
```
