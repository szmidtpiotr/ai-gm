# Od Figmy do działającej gry — workflow dla osoby bez doświadczenia w Figmie

**Kolejność prac (ustalone 2026-05-01):** Ten dokument służy **nauce** i jest **gotów**, gdy zdecydujecie się na nowy front — **nie** musicie go wdrażać od razu. Uchwała **[S16]** w `04_decisions_log.md` przewiduje start implementacji **na końcu** bieżącego planu; do tego czasu zostajecie przy obecnym kliencie.

**Po co ten dokument:** Wyjaśnia **prostym językiem**, jak wizualny projekt z Figmy trafia do Waszego repo (**backend już jest**), bez zakładania, że znasz Figmę od środka. Spójne z uchwałą **[S16]** (nowy front, Figma = źródło komponentów).

---

## 1. Najważniejsze — czym Figma **nie jest**

| Mit | Prawda |
|-----|--------|
| „Figma wyeksportuje mi gotową grę” | **Nie.** Figma to **projekt wizualny** (jak layout w Photoshopie/InDesignie), nie działający program. |
| „Muszę użyć tego samego frameworku co Figma” | **Nie.** Sam produkt „aplikacja Figma” w przeglądarce jest zbudowany osobno — **nie przenosisz go do swojego repo**. Ty budujesz **swój** front (np. React), **według** projektu z Figmy. |
| „Figma Make załatwi implementację” | **Często nie.** Make jest wygodny do prototypów; **pełna gra** z Waszym API, stanem sesji i narracją — **normalnie** robi się w kodzie, a Figura jest **wzorcem**. Dwie nieudane próby Make nie są „porażką”; to typowy kierunek. |

**Czym Figma **jest** dla Was:** jedno **źródło prawdy wizualnej**: kolory, odstępy, czcionki, układ ekranu, zestaw **komponentów** (przyciski, karty, listy), żeby developer nie zgadywał z pamięci.

---

## 2. Końcowy obraz całego łańcucha (pięć bloków)

```
[Figma: makietowanie] → [tokeny + komponenty w Figmie]
       → [komponenty + style w kodzie, np. React] → [podłączenie do API backendu] → [deploy]
```

**Backend** (FastAPI, SQLite, narracja LLM) **zostaje** — zmieniacie **to, co gracz widzi w przeglądarce** (nowy front wg **[S16]**).

---

## 3. Krok po kroku — co robić na kolejnych etapach

### Etap A — W Figmie (projektant lub Ty z szablonem)

1. **Załóż plik** (projekt) w Figmie — jeden na „grę gracza” (czat, karty, walka), osobno można później admin (u Was admin może zostać stary na razie).
2. **Zdefiniuj zmienne (Variables)** — to są **tokeny**: np. `color/bg-primary`, `spacing/md`, `font/body`.  
   - Dzięki temu zmiana „głównego niebieskiego” **raz** w Figmie ma odpowiednik w kodzie (CSS lub theme).
3. **Buduj z komponentów** — przycisk, ramka czatu, karta rzutu: **jedna definicja**, potem **warianty** (np. stan „disabled”).  
   - To jest dokładnie to, co **[S16]** nazywa „Figma = źródło komponentów”.
4. **Auto Layout** — ramki układają się jak elastyczny układ (podobna idea do flexbox w CSS). Ułatwia **1:1** zrozumienie odstępów przez developera.
5. **Tryb dla developerów (Dev Mode)** — pokazuje **odległości, rozmiary, kolory** — developer **przepisuje** je do CSS/theme albo porównuje z tokenami.

**Tu się kończy „projektowanie wizualne”.** Nie ma jeszcze Waszej gry — jest **specyfikacja wyglądu**.

---

### Etap B — Z Figmy do kodu (developer — tu nie ma jednego magicznego „Eksportuj grę”)

Masz **dwie ścieżki** (można je łączyć):

| Ścieżka | Opis | Kiedy |
|---------|------|--------|
| **Ręcznie / półautomat** | Developer zakłada projekt **React** (lub inny stack z **[S16]**), tworzy komponenty **nazwane tak jak w Figmie**, kopiuje wartości z Dev Mode / tokenów do pliku theme (np. `theme.ts`, `tokens.css`). | Zawsze działa; najmniej zależności. |
| **Code Connect** (opcjonalnie) | Oficjalna integracja: **powiązanie** komponentu Figmy z **plikiem kodu** (np. `Button.tsx`), żeby w Figmie widać było „ten komponent = ten kod”. **Nie** generuje całej aplikacji sama z siebie — **utrzymuje spójność**. | Gdy macie już bibliotekę komponentów w repo i chcecie długofalową synchronizację. |

**React** pojawia się tu dlatego, że w ekosystemie Figma → kod **najczęściej** spotykasz przykłady pod React; to **nie** jest „framework Figmy”, tylko **wygodny standard** pod **[S16]**.

---

### Etap C — Logika gry w kodzie (to nie robi Figma)

1. **Komponenty React** tylko **wyświetlają** dane i **wywołują** Wasze API (`fetch` / klient HTTP).
2. **Stan gry** (sesja, turę, tekst narracji, rzuty) — **odpowiedzi z backendu**, tak jak dziś stary front; nowy front **zmienia wygląd i strukturę JSX**, nie zastępuje API.
3. **Umowa API:** dla pierwszego wdrożenia można **zamrozić** zestaw endpointów (**[S16]**); nowe pola dodajecie **wersją / rozszerzeniem**, żeby nie psuć już działającego klienta.

---

### Etap D — Import / wdrożenie do „systemu”

| Co | Gdzie |
|----|--------|
| **Kod frontu** | Repo (np. folder `frontend/` lub osobny pakiet w monorepo — decyzja przy starcie). |
| **Build** | `npm run build` → statyczne pliki (`dist/`) lub serwowanie przez ten sam serwer co dziś. |
| **Konfiguracja treści gry** (bronie, przedmioty) | Nadal **panel admin + API** / import snapshotów (**[S7]**); **to nie jest eksport z Figmy**. Figura dotyczy **wyglądu klienta gry**, nie treści z `game_config_*`. |
| **Deploy** | Jak teraz: wrzucacie nowy build frontu na serwer / CDN; backend jak był. |

---

## 4. Kolejność prac (żeby się nie zagubić)

1. **Ustal MVP ekranów gracza** (np. czat + lista tur + miejsce na karty rzutów) — **bez** doskonałej grafiki na start.
2. **Tokeny w Figmie** + **jeden** ekran dopracowany jako **wzór komponentów**.
3. **Repo frontu** (React + Vite to popularny start) + **jeden** komponent podłączony do **prawdziwego API** (np. odczyt narracji).
4. **Dopięcie kolejnych ekranów** według makiet.
5. **Admin** zostaje stary do czasu osobnej fali (**[S16]**).

**Kiedy zacząć Etap C:** gdy **wiadomo**, jakie endpointy obsłużą czat i sesję w pierwszej wersji (**nie trzeba** czekać na „wszystkie funkcje z backlogu”).

---

## 5. Gdzie szukać pomocy bez zostawania ekspertem od Figmy

- **Zmienne (Variables)** w Figmie — słowo kluczowe do tutoriali: „Figma variables design tokens”.
- **Dev Mode** — „Figma dev mode inspect spacing”.
- **Code Connect** — dokumentacja Figmy pod hasłem „Code Connect”; instalacja **na etapie**, gdy macie pierwsze komponenty w repo.

---

## 6. Powiązania z Waszą dokumentacją

- Uchwała produktowa: **[S16]** w [`04_decisions_log.md`](04_decisions_log.md).
- Skrót techniczny: [`07_extended_design_spec.md`](07_extended_design_spec.md) §11.

---

## 7. Jedno zdanie na koniec

**Figma = przepis kulinarny na wygląd; React (lub inny front) = gotowanie w Waszej kuchni; backend = magazyn i lodówka, które już macie.** Żadna z tych rzeczy nie „eksportuje się” jako druga zamiast trzeciej — **łączycie je świadomie w kodzie**.
