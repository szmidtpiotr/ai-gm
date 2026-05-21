# 📖 Podręcznik Zasad (Rulebook)

> **Język:** Polski. Ten dokument jest dla graczy — pokazuje, jak działa mechanika gry.
> **Mechanika gry:** zablokowana — patrz `backend/prompts/system_prompt.txt` jako źródło prawdy techniczne.

---

## 🎲 Rzut na umiejętność — formuła

Każdy test umiejętności rozstrzyga jeden rzut kością dwudziestościenną (d20):

```
d20  +  modyfikator atrybutu  +  ranga umiejętności  +  premia biegłości   ≥   ST
```

- **d20** — losowa kość 20-ścienna (wynik 1–20)
- **Modyfikator atrybutu** — wynika z wartości statystyki (patrz tabela niżej)
- **Ranga umiejętności** — twój poziom wytrenowania (0–5)
- **Premia biegłości** — `+2`, **tylko gdy ranga ≥ 3**
- **ST** (Stopień Trudności) — próg, który musisz osiągnąć

---

## 🧠 Atrybuty (statystyki)

Postać ma 7 atrybutów:

| Skrót | Nazwa polska | Co opisuje |
|:---:|:---|:---|
| **STR** | Siła | Walka wręcz, dźwiganie, fizyczna moc |
| **DEX** | Zręczność | Akrobacja, skradanie, refleks |
| **CON** | Kondycja | Wytrzymałość, PŻ, opieranie się truciznom |
| **INT** | Inteligencja | Wiedza, magia, dochodzenie |
| **WIS** | Mądrość | Spostrzegawczość, intuicja, medycyna |
| **CHA** | Charyzma | Perswazja, zastraszanie, oszustwo |
| **LCK** | Szczęście | Wyłapanie szczęśliwego trafu |

### Modyfikator z wartości atrybutu

Formuła: **`floor((atrybut − 10) / 2)`**

| Atrybut | Modyfikator |
|:---:|:---:|
| 8 | −1 |
| 9 | −1 |
| 10 | 0 |
| 11 | 0 |
| **12–13** | **+1** |
| **14–15** | **+2** |
| **16–17** | **+3** |
| **18–19** | **+4** |
| **20** | **+5** (maksimum) |

> **Dlaczego „modyfikator zawsze +3" przy STR 17?**
> Modyfikator zmienia się **dopiero co dwa pełne stopnie** atrybutu. STR 16 i STR 17 dają ten sam modyfikator `+3`. Żeby przeskoczyć na `+4`, musisz mieć STR 18 (lub 19, też daje +4). Dopiero STR 20 daje `+5`.

### Maksimum atrybutu

Najwyższy możliwy poziom atrybutu to **20** (nie 30).

- Na starcie atrybuty mieszczą się w przedziale **8–18** (rzut z premiami klasowymi).
- Podczas gry można podnosić atrybuty wydając XP w panelu "Awansuj":

| Z poziomu | Na poziom | Koszt PD |
|:---:|:---:|:---:|
| 8 → 9 | 40 PD |
| 14 → 15 | 230 PD |
| 17 → 18 | 550 PD |
| 19 → **20** | **1000 PD** |

Czyli **maksymalny modyfikator wynosi +5** (STR/DEX/… na 20). Wszystko powyżej musi pochodzić z magicznych przedmiotów (planowane — paski boostu po prawej stronie wskaźnika atrybutu).

---

## 🎯 Stopnie trudności (ST)

| ST | Tier | Kiedy stosowany |
|:---:|---|---|
| **8** | Łatwe | Proste, oczywiste czynności |
| **12** | Średnie | Wymaga skupienia, ale realne dla wytrenowanego |
| **16** | Trudne | Niepewne nawet dla profesjonalisty |
| **20** | Ekstremalne | Granica możliwości |
| **24+** | Legendarne | Tylko mistrzowski wyczyn lub szczęście |

---

## ⚔️ Krytyki — natura 20 i natura 1

- **Naturalna 20** (kość pokazuje 20 niezależnie od modyfikatorów):
  - **Automatyczny sukces** — niezależnie od ST.
  - **Podwójne obrażenia** w walce.
- **Naturalny 1** (kość pokazuje 1):
  - **Automatyczna porażka.**
  - **Komplikacja** — GM dorzuca konsekwencję (broń się ślizga, drabina pęka, zwracasz uwagę strażnika).

---

## 📈 Umiejętności (Umiejka, Skill)

Każda umiejętność ma:

- **Wytrenowany atrybut** (linked stat) — który modyfikator wchodzi do rzutu (np. Atletyka = STR, Skradanie = DEX).
- **Rangę** od **0** (nietrenowany) do **5** (mistrz). Pułap to 5 — wyższy nie istnieje.
- **Wizualnie**: pięć kropek `●●●○○`. Złote = wytrenowane, puste = jeszcze nie.

### Premia biegłości

Gdy osiągasz **rangę 3** w umiejętności, dostajesz dodatkowo **+2** do każdego rzutu na nią. To największy pojedynczy skok w całej progresji — od tego momentu twoja postać jest **biegła** w tej umiejętności.

Wizualnie: zielona plakietka **`+2`** pojawia się obok kropek.

### Koszt rang umiejętności (PD)

| Z rangi | Na rangę | Koszt PD |
|:---:|:---:|:---:|
| 0 → 1 | 50 PD |
| 1 → 2 | 100 PD |
| 2 → **3** ⭐ | **200 PD** (i wpada premia biegłości!) |
| 3 → 4 | 400 PD |
| 4 → **5** | **1200 PD** (mistrzostwo) |

---

## 🏃 Przykład progresji — Atletyka przy STR 17

Wojownik ma STR **17**, czyli stały modyfikator **+3**. Patrzymy, jak rośnie premia do rzutu Atletyki na każdym poziomie wytrenowania:

| Ranga | Kropki | Formuła | Rzut | Co to znaczy |
|:---:|:---:|:---|:---:|:---|
| **0** *nietrenowany* | ○○○○○ | d20 + 3 + 0 | **d20+3** | ST 8 (Łatwe) trafiasz ok. 80% rzutów. Trudne 16 — potrzebujesz 13+ na kości. |
| **1** | ●○○○○ | d20 + 3 + 1 | **d20+4** | ST 12 (Średnie) ~65%. |
| **2** | ●●○○○ | d20 + 3 + 2 | **d20+5** | ST 12 ~70%. Trudne 16 zaczyna być realne. |
| **3** ⭐ | ●●●○○ +2 | d20 + 3 + 3 + **2** | **d20+8** | **Premia biegłości wchodzi.** ST 16 ~65%. Łatwe ST 8 automat (oprócz Nat 1). |
| **4** | ●●●●○ +2 | d20 + 3 + 4 + 2 | **d20+9** | ST 16 ~70%. ST 20 zaczyna być w zasięgu. |
| **5** | ●●●●● +2 | d20 + 3 + 5 + 2 | **d20+10** | ST 20 ~55%. Cokolwiek ≤ ST 10 — **niemożliwe do oblania** (poza Nat 1). |

### Dwa kluczowe momenty progresji

1. **Ranga 3** — skok `+2` w jednej rancie (premia biegłości). Z `d20+5` na `d20+8` z dnia na dzień. Po to istnieje zielona plakietka.
2. **Ranga 5** przy atrybucie 17 — nie da się oblać niczego do ST 10 włącznie. Tylko Nat 1 cię zatrzyma. To poziom legendarny dla tej jednej umiejętności.

### Co widzisz na karcie postaci

```
STR  17  +3   ━━━━━━━━━━━━━━━━━━━━░░░  20
   Atletyka      ●●●○○  +2          +8
   ↑ nazwa      ↑ ranga ↑ biegłość  ↑ pełna premia do rzutu
```

Liczba po prawej to **gotowa premia do rzutu** — chwytasz d20, dorzucasz to, porównujesz z ST.

---

## ❤️ Punkty Życia (PŻ) i Mana

### PŻ
```
max_HP = bazowe_PŻ_klasy + (modyfikator_CON × poziom)
```

Wojownik na 1. poziomie z CON 14 (mod +2) i bazą 10:
`max_HP = 10 + (2 × 1) = 12 PŻ`

### Mana (tylko Uczony / Scholar)
```
max_mana = 8 + (modyfikator_INT × poziom)
```

Uczony na 1. poziomie z INT 16 (mod +3):
`max_mana = 8 + (3 × 1) = 11 many`

---

## ⚡ Stany (Conditions)

Stany to czasowe efekty wpływające na postać lub wroga. Przykłady:

| Klucz | Nazwa | Efekt |
|---|---|---|
| `poisoned` | Zatruty | −2 do STR przez 3 rundy |
| `zaskoczony` | Zaskoczony | Atakujący ma `+2` do trafienia i **podwaja obrażenia pierwszego trafienia**. Znika po otrzymaniu obrażeń. |
| `frightened` | Przerażony | Trudniej działać agresywnie |

W walce ⚡ znaczek przy inicjatywie znaczy „cel zaskoczony — uderz mocno teraz".

---

## 🛌 Odpoczynek

Aby odzyskać PŻ i manę, musisz być w **bezpiecznym miejscu** (`safe_for_rest`):

- **Krótki odpoczynek** (☽): +1h zegara, regen `1d6 + CON_mod` PŻ. Max 2 razy między długimi.
- **Długi odpoczynek** (★): +8h zegara, pełne PŻ i mana, reset krótkich odpoczynków, wypłata `pending_xp → xp_available`.
- **Rozbij obóz** (🔥): tworzy tymczasowy bezpieczny obóz w dziczy, +1h, +20% szansy na encounter.

---

## 🎒 Ekwipunek

- Każda postać startuje z **klasowym zestawem** (warrior dostaje krótki miecz + tarczę + łuk + skórzaną zbroję; scholar dostaje kij + miksturkę zdrowia + maniturkę).
- **Pierwsza broń i pierwsza zbroja są automatycznie zakładane.**
- Walka wręcz wymaga broni w slocie `main_hand`. Strzelanie — broń dystansowa.

---

## 📊 Skala awansowania postaci

- Postać awansuje co `100 XP` przekraczając próg.
- **Maksymalny poziom:** 10.
- XP zdobywasz za: walkę, eksplorację (pierwsza wizyta w lokacji, rozmowa z nowym NPC, odkrycie sekretu), sukcesy umiejętności (ST 12+: 3 PD, ST 16+: 8 PD, ST 20+: 15 PD), zakończone questy, beat-y fabuły, „heroiczne" momenty (`[XP_GRANT]`).

---

## 🗺 Magia i odległość (uproszczona)

Każdy uczestnik walki jest w jednej z dwóch stref:
- **Zwarcie** (⚔) — walka wręcz, dotyk
- **Dystans** (🏹) — strzelanie z łuku, zaklęcia dalekiego zasięgu

Atak wręcz na cel w dystansie jest blokowany — najpierw musisz **„Zbliżyć się"** (akcja `zbliż się`). Magowie domyślnie startują w dystansie, wojownicy w zwarciu.

---

## 🎲 Czego d20 *nie* widzi

Nie każda interakcja wymaga rzutu. Codzienne czynności (otworzenie drzwi, kupienie chleba, pójście do karczmy) są rozstrzygane narracyjnie — d20 wchodzi dopiero, gdy stawka jest jasna i wynik niepewny.

---

*Dokument żyje razem z mechaniką. Jeśli coś tu nie pasuje do tego, co widzisz na karcie postaci — zgłoś, bo to bug.*
