# KOMENDY — ściąga (co odpalić, kiedy)

> Jednostronicowa ściąga dla Piotra. Nie musisz pamiętać ~50 skilli — to jest lista realnie używanych.
> Decyzje z sesji 2026-06-19 (przegląd narzędzi).

---

## 🔁 Rytm sesji — jedno issue, trzy warstwy obrony

Każde issue przechodzi przez 3 warstwy. Każda łapie co innego:
**test** = złamana logika · **code-review** = bug obok · **playwright** = zepsuty wygląd.

```
1. /tdd #NNN              → test + fix (pytest + Playwright + kryteria akceptacji)
2. /code-review (diff)    → polowanie na bugi; 🔴 napraw (wróć do /tdd), 🔵 pomiń
3. /playwright-test-report → przejście jako gracz + zrzuty (lub /game-screen — szybki podgląd)
4. commit + push (Claude sam, develop) · issue → review + needs-testing
5. TY oglądasz na DEV → zamykasz issue
```

Plus rama sesji: **start** „stan?" (Claude czyta STATUS.md) · **koniec** Claude aktualizuje STATUS.md + raport po polsku → STOP. Jedno zadanie = jedna sesja.

### 📋 Prompt do wklejenia na start (podmień numer)

```
Przeczytaj STATUS.md. Robimy #743 przez /tdd.
Przed commitem odpal /code-review na diffie — realne bugi napraw, kosmetykę pomiń.
Na końcu pokaż wynik przez /playwright-test-report + raport po polsku.
```

Warianty:
- **Siedzisz, chcesz checkpointy:** dopisz na końcu „Zatrzymaj się po RED żebym potwierdził."
- **Wychodzisz, mam lecieć sam:** dopisz „Auto, leć bez pytań."
- **Nie wiesz który numer:** „Przeczytaj STATUS, co następne?" → Claude poda pierwszy z kolejki priorytetów.

---

## 🎯 6 poleceń podstawowych

| Komenda | Kiedy |
|---|---|
| „stan?" / `STATUS.md` | start sesji — gdzie jesteśmy |
| `/github-task` | co robić / przesuń task / status |
| `tdd #NNN` | wdróż jedno zadanie (twój workhorse kodowania) |
| `/mass-implement` | wychodzisz, Claude robi listę zadań sam |
| `/playwright-test-report` | sprawdź UI + zgłoś bugi (twój workhorse testowy) |
| `/game-screen` | szybki podgląd ekranu |

---

## 🧪 Testowanie — który kiedy (zawężone)

**Reguła:** *bug widać na ekranie?* → `/playwright-test-report`. *bug to liczby w bazie przez wiele tur (złoto/XP/quest)?* → `/game-test-player-screenshot`. *cały tryb grywalny?* → `/game-smoke[-dungeon]`.

| Skill | Kiedy NAJLEPSZY | Status |
|---|---|---|
| **`/playwright-test-report`** | bug wizualny/UI, regresja, „przetestuj ekran" — łapie najwięcej, zakłada issue | ✅ główny |
| **`/game-smoke`** | „czy tryb gra się end-to-end" — szeroka pokrywa mechanik | ✅ |
| **`/game-smoke-dungeon`** | to samo dla lochu kafelkowego (FAZA L) | ✅ |
| **`/game-screen`** | „pokaż jak wygląda ekran X" (1 zrzut) | ✅ |
| **`/game-test-player-screenshot #NNN`** | bug logiczny (DB) konkretnego issue + dowód wizualny, flow narracyjny przez wiele tur | sytuacyjnie |
| **`/mobile-game-test`** | tylko realny bug na telefonie (Android/dotyk) | rzadko |
| `/game-test`, `/game-test-player` (bez zrzutów), `/verify`, `/webapp-testing` | — | ❌ pomijasz (redundantne) |

---

## 🛠 Kodowanie / jakość

| Skill | Co robi | Status |
|---|---|---|
| **`tdd #NNN`** | pełny cykl: test→kod→sprzątanie + Playwright + GitHub + update notes/game_mechanics + narracja PL | ✅ główny |
| **`/code-review`** | szuka **bugów** w diffie + jakość. `--comment` (PR), `--fix` (napraw). `ultra` = głęboki w chmurze | 🔜 testujesz |
| **`/simplify`** | tylko jakość (mniej powtórzeń) — **NIE szuka bugów** | ⚠️ tylko w klatce |
| **`/cleanup`** | kasuje martwy kod, partiami, zgoda na każdą + kwarantanna | ⚠️ tylko w klatce |
| `ai-gm-tdd` | cienka nakładka, tylko pytest lokalnie bez SSH | ❌ pomijasz (`tdd` lepszy) |
| `verify` | generyczne odpalenie apki | ❌ pomijasz (`game-*` lepsze) |

**Klatka bezpieczeństwa dla `/simplify` i `/cleanup`** (twój strach o ukrytą regresję — słuszny):
- tylko świeży **mały** diff, nigdy „posprzątaj cały kod"
- **osobny commit** „cleanup" → regresja = jeden `git revert`
- po nich obowiązkowo `tdd` test + `/playwright-test-report`

---

## 📐 System pracy (raz na projekt/fazę)

| Skill | Co robi |
|---|---|
| **`/workflow-loop`** | buduje system „jeden prompt = jedno zadanie": dokument zadań + checklista + prompt startowy. Odpalasz RAZ na nowy projekt/fazę. |
| **`/mass-implement`** | automat: leci checklistę zadanie po zadaniu sam, każde w osobnej sesji, STOP na bramce. ⚠️ wymaga dobrze ustrukturyzowanego pliku + osobnego promptu — **do dopracowania** (zob. niżej). |

---

## ✍️ Dokumentacja

| Skill | Kiedy |
|---|---|
| **`/document`** | „wytłumacz jak działa X prostym językiem" → docsy typu `game_flow.md` (non-tech, bloki „Dlaczego?"). **NIE** pisze jak `game_mechanics.md` (to spec, robi go `tdd`). |
| `/fetch-telegram` | przegląd wiadomości testerów → bugi → issues. **Wrócimy później.** |

---

## 🧠 Myślenie / decyzje (znasz, używasz — żeby nie zapomnieć)

| Skill | Kiedy |
|---|---|
| `/brainstorming` | przed nowym ficzerem — drążenie czego naprawdę chcesz |
| `/llm-council` | nie możesz wybrać A/B — 5 doradców + werdykt |
| `/deep-research` | głęboki research wielu źródeł z weryfikacją |
| `/game-design` | ocena pojedynczej mechaniki (czy się opłaca, czemu źle się czuje) |

## 🎨 Design / wizualia (twój teren)

| Skill | Kiedy |
|---|---|
| `/frontend-design`, `/ui-ux-pro-max`, `/interface-design` | projekt UI |
| `/canvas-design`, `/algorithmic-art` | grafika, plakaty, sztuka |
| `/creating-mermaid-diagrams`, `/excalidraw-diagram` | diagramy (architektura, flow) |

---

## 🔧 Do dopracowania (notatka)
- **`mass-implement`** — Piotr lubi, ale: (1) psuje się gdy plik źle ustrukturyzowany, (2) wymaga osobnego, poprawnego pliku-promptu. Cel: bardziej odporny na zły input + uniwersalny między projektami.

## ⚙️ Automaty (zero akcji od ciebie)
- **caveman** — zwięzła komunikacja (oszczędza tokeny). `/caveman lite|full|ultra`.
- **RTK** — kompresja komend serwera.
- **ponytail** (opcjonalnie) — mniej kodu.
