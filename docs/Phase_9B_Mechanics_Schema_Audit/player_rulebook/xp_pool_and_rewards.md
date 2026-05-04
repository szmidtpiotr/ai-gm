# Pula XP i nagrody — dla gracza

**Status:** rozdział roboczy (**T13**), zgodny z **[S10a]**, **[S10b]**, **[S10c]**, **[S10d]** oraz **[S10e]** w [`../04_decisions_log.md`](../04_decisions_log.md). Nie opisuje szczegółów panelu administracyjnego ani konkretnych ekranów — tylko zasady, które mają być **spójne** z działaniem silnika.

---

## 1. O czym mowa

- Postać **nie ma poziomu (LVL)** w stylu klasycznego RPG: nie awansujesz „na poziom”, tylko dysponujesz **pulą punktów doświadczenia (XP)** i ją **wydajesz** zgodnie z zasadami (np. na wyższą rangę umiejętności).
- **Kolejność wydatków nie jest narzucona** — o ile stać cię na koszt i limity (np. sufit rangi umiejętności), możesz najpierw podnieść jedną umiejętność, potem inną itd. (**[S10a]**).

---

## 2. Skąd bierze się XP

1. **Walka** — po pokonaniu przeciwnika liczba XP pochodzi z **ustalonej konfiguracji świata**: zwykle jest wpisana przy danym wrogu; jeśli nie, system może skorzystać z **domyślnej nagrody dla poziomu zagrożenia** (słaby, typowy, elita, boss). Ty widzisz **wynik** (np. przyrost puli), nie musisz znać tabel organizatora (**[S10b]**, **[S10e]**).
2. **Decyzja Mistrza Gry (fabularna)** — MG może uzasadnić dodatkowe XP za odkrycie, odwagę, domknięcie celu sceny itd. **Liczba**, która trafia na twoją kartę, musi być **zapisana w grze** — sam opis modelu językowego **nie** zwiększa puli (**[S10d]**).
3. **Technicznie (w tej implementacji)** operacje zapisu nagród z punktu 2 są powiązane z **właścicielem kampanii** (konto, które zakładało kampanię). To **nie** zmienia zasady fabularnej: narracyjnie nadal rozdaje **MG** — po prostu w narzędziu jest jedno miejsce decyzji zgodne z kontem (**[S10d]**).

---

## 3. „Sesja” a granty od MG

- **Oknem nie jest** „od zalogowania do wylogowania”.
- Przy **grantach MG** (poza walką) liczy się **odcinek gry**: fragment fabuły między wyraźnymi zwrotami (np. dłuższy wypoczynek, zmiana lokacji, koniec starcia i przejście do innego tonu). Szczegół sensu **„odcinka”**: **[S10c]**.
- Przy grze **bardzo rozłożonej w czasie** sensowne jest traktowanie **tygodnia kalendarzowego** jako praktycznego limitu zamiast granic odcinka — tak jak w uchwale o widełkach (**[S10b]**, **[S10c]**).
- **Widełki orientacyjne** (nie są losowane przez model z powietrza — służą kalibracji; dokładne stałe żyją w konfiguracji):

| Sytuacja (skrót) | Rząd wielkości XP |
|------------------|-------------------|
| Słabe zagrożenie / tło | kilka punktów |
| Typowy napastnik | średnie jednocyfrowe / niskie dwucyfrowe |
| Elita / mały boss | wyższe dwucyfrowe |
| Duży boss | dużo wyżej — rzadko |
| Drobny bonus fabularny od MG | kilka punktów |
| Wyraźny postęp / mini-cel sceny | średnio |
| Duży przełom fabularny | wyżej; zwykle **nie więcej niż jedna** taka nagroda **na odcinek** |
| Nadzwyczajny sukces | jeszcze wyżej — rzadko |

Łącznie z **samych grantów MG** (bez walki) na jeden odcinek (lub tydzień w grze asynchronicznej) sensowny **sufit** to rząd **ok. 60–100 XP**; więcej tylko z mocnym uzasadnieniem. **XP z walki liczy się osobno** — nie „zjada” tego limitu (**[S10b]**).

---

## 4. Na co wydajesz XP

- **Rangi umiejętności** — każdy kolejny stopień ma **koszt w XP** ustawiony w konfiguracji (typowo rośnie mocno przy najwyższych rangach). Sufit rangi i zasady kary za test bez umiejętności — jak w rozdziale o umiejętnościach (**[S4]**, **[S4b]**); liczby przykładowe: [`draft_formulas_and_examples.md`](draft_formulas_and_examples.md) §0b.
- **Podnoszenie cech za XP** — **tylko jeśli** w danej wersji zasad i w konfiguracji świata jest to włączone; nie zakładamy tego domyślnie w tekście dla gracza (**[S10a]**, **[S3]**).

---

## 5. Co jest „źródłem prawdy”

- **Nie** liczby wypowiedziane przez model w samej narracji, dopóki nie zostaną **zatwierdzone** zapisem w systemie (**[S10d]**).
- **Konfiguracja** (organizatorzy): koszty rang, nagrody za typ zdarzenia / tier wroga, ewentualnie osobne wpisy nagród — to jest kanał **twardej** wartości (**[S10e]**).

---

## Powiązane dokumenty

- Uchwały: **[S10a]**–**[S10e]** w [`../04_decisions_log.md`](../04_decisions_log.md).
- Szkic liczb i przykładów: [`draft_formulas_and_examples.md`](draft_formulas_and_examples.md) §0g.
- Outline książki: [`00_outline_and_tone.md`](00_outline_and_tone.md).
