# Mapa architektury — instrukcja obsługi (pilot: Combat)

Prostym językiem: **co to jest, jak otworzyć, i co musisz robić żeby mapa była aktualna.**

---

## 1. Co to w ogóle jest

To **jeden plik HTML** (`architecture-map.html`), który rysuje twój kod jako mapę:
pudełka (węzły) połączone strzałkami (przepływy). Otwierasz go w przeglądarce — bez
instalacji, bez serwera, bez internetu. Każde pudełko to prawdziwy plik albo funkcja
z projektu, z prawdziwym numerem linii.

Pilot pokazuje **tylko podsystem walki** (combat) — 27 węzłów. To celowo mały wycinek,
żebyś zobaczył format zanim zmapujemy całość.

Mapa ma dwie warstwy:

| Warstwa | Co pokazuje | Skąd się bierze |
|---|---|---|
| **Szkielet** | pudełka, strzałki, role, opisy „po ludzku", ścieżka krytyczna, martwy kod | wpisane ręcznie w HTML (agent czytał pliki) |
| **Nakładka** | czerwone/zielone kółka (bugi/zadania z GitHub), grubość ramki = ruch na żywo | plik `overlay/map-overlay.json`, generowany skryptem |

Szkielet zmienia się rzadko (gdy dodasz/usuniesz plik). Nakładka odświeża się sama.

---

## 2. Jak otworzyć mapę

**Najprościej** — kliknij dwa razy `architecture-map.html`. Otworzy się w przeglądarce.

> ⚠️ Jeden haczyk: gdy otwierasz plik bezpośrednio (`file://`), przeglądarka czasem
> blokuje wczytanie nakładki `overlay/map-overlay.json` (zasady bezpieczeństwa).
> Wtedy zobaczysz mapę bez kółek bugów. Jeśli chcesz kółka — odpal mały serwer:

```bash
cd tools/archmap
python3 -m http.server 4747
# potem w przeglądarce: http://localhost:4747/architecture-map.html
```

W prawym górnym rogu mapy jest plakietka `overlay: …` — mówi czy nakładka się wczytała
(`12 fixów · 0 bugów · …`) czy nie (`brak (statyczna mapa)`).

---

## 3. Jak czytać mapę (klikanie)

- **Najedź myszą na pudełko** → podświetla jego sąsiadów, reszta przygasa. Z prawej
  pojawia się opis: co to robi (technicznie), co to robi (po ludzku), numery linii,
  co go woła, co on woła, jakie ma bugi/zadania.
- **Kliknij pudełko** → przypina opis (zostaje gdy ruszysz myszą). Kliknij drugi raz
  albo w puste tło → odpina.
- **Kółko myszy** → przybliż/oddal. **Przeciągnij tło** → przesuń. Przyciski `⤢ + −`
  w prawym górnym rogu: dopasuj / przybliż / oddal.
- **Chipy u góry** (Overview, Ścieżka krytyczna, Atak, Strefy, Loot/XP, Martwy kod,
  Heat-map, …) → filtrują mapę do jednego tematu. „Wszystkie kable" pokazuje wszystko.

**Pierwszy ekran z prawej** (gdy nic nie klikniesz) to „Notable findings" — najważniejsze
wnioski: gdzie jest martwy kod, który plik jest przeładowany, gdzie wpina się
observability. To czyta się najpierw.

Czerwona gruba ramka = **ścieżka krytyczna** (kręgosłup walki: od kliknięcia „Atakuj"
do zadania obrażeń i nagrody). Przerywana ramka = **martwy kod** (nikt nie woła).

---

## 4. Co MUSISZ robić, żeby mapa była aktualna

Trzy sytuacje. Większość czasu **nie robisz nic**.

### A) Codziennie — bugi i zadania → NIC nie robisz

Skrypt `overlay/refresh.sh` (odpalany z crona, jak nocny backup) sam:
1. pobiera otwarte issues z GitHub,
2. czyta z każdego sekcję `## Files changed`,
3. dopasowuje pliki do pudełek i maluje kółka:
   - **czerwone** = otwarty bug na tym pliku,
   - **zielone** = zaplanowane zadanie/feature na tym pliku.

Rano mapa pokazuje aktualne bugi i zadania. **Zero klikania z twojej strony.**
Warunek: trzymasz szablon issue z obowiązkową sekcją `## Files changed` (i tak go macie).

> Chcesz odświeżyć ręcznie zamiast czekać na cron:
> ```bash
> cd tools/archmap/overlay && ./refresh.sh
> ```

### B) Dodałeś / usunąłeś plik lub serwis → JEDNO ZDANIE do mnie

Skrypt-strażnik (`drift_check.py`, też w `refresh.sh`) zauważy nowy plik bez pudełka:

```
NEW (1) — files in scope with no node on the map:
  + backend/app/services/raid_service.py
  -> tell the agent: "zaktualizuj mapę — przyrost"
```

Twoja cała robota: napisz mi **„zaktualizuj mapę — przyrost"**. Ja czytam nowy plik,
dorysowuję pudełko, reszta mapy nietknięta. To samo gdy plik znika („GONE …").

### C) Skończyłeś dużą fazę (przebudowa) → JEDNO ZDANIE do mnie

Napisz **„przegeneruj mapę combat"** (albo inny podsystem). Ja przerysowuję ten jeden
kawałek od zera. Nie całość.

### Podsumowanie — tabela

| Sytuacja | Twoja akcja |
|---|---|
| Bug otwarty/zamknięty, nowe zadanie | **nic** (cron sam) |
| Nowy / usunięty plik | napisz: „zaktualizuj mapę — przyrost" |
| Duża faza skończona | napisz: „przegeneruj mapę X" |
| Chcę popatrzeć na mapę | otwórz `architecture-map.html` |

---

## 5. Skrypty w `overlay/` — co robi który

| Plik | Co robi | Kiedy odpalany |
|---|---|---|
| `refresh.sh` | odpala 3 poniższe po kolei | cron / ręcznie |
| `update_overlay.py` | GitHub issues → kółka bugów/zadań | codziennie |
| `update_heat.py` | dane z bazy → grubość ramki = ruch na żywo | codziennie (pełne po Phase 11) |
| `drift_check.py` | porównuje pliki na dysku z mapą, krzyczy gdy rozjazd | codziennie |
| `node-map.json` | tabela „ścieżka pliku → które pudełko" | edytujesz gdy dochodzi pudełko |
| `heat-source.json` | tabela „typ zdarzenia → które pudełko" (dla ruchu) | edytujesz przy Phase 11 |
| `map-overlay.json` | **wynik** — to czyta mapa. Nie edytuj ręcznie. | nadpisywany automatem |

Uruchamiać na hoście, który ma `gh` (GitHub CLI) i dostęp do repo. Skrypt bazy
(`update_heat.py`) łączy się przez SSH do `.61` i czyta bazę **tylko do odczytu przez
docker** — nigdy bezpośrednio przez sshfs (to psuje SQLite).

---

## 6. Chip „Heat-map (live)" — ruch na żywo

To połączenie z **fazą observability** (Phase 11). Gdy klikniesz ten chip, ramki pudełek
robią się grubsze tam, gdzie jest dużo ruchu, i czerwone tam, gdzie są błędy.

- **Teraz** działa częściowo: czyta tabelę `combat_turns` (już istnieje) — pokazuje, że
  węzeł `resolve-attack` / `log-event` jest „gorący".
- **Po Phase 11** (tabele `game_events`, `llm_call_log`) pokaże pełny obraz: ile razy
  gracze ginęli, jak wolne są wywołania LLM, gdzie są błędy — wszystko per pudełko.
  Wystarczy włączyć źródła `_phase11` w `heat-source.json`, bez zmiany kodu.

Dlatego mapa i observability to **jedna faza** — dzielą te same tabele i ten sam cron.

---

## 7. Najczęstsze problemy

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| Brak czerwonych/zielonych kółek | otwarte przez `file://`, przeglądarka blokuje nakładkę | odpal `python3 -m http.server 4747` |
| Plakietka „overlay: brak" | `map-overlay.json` nie wczytany | jw. albo odpal `refresh.sh` |
| Kółek za mało | issue nie ma sekcji `## Files changed` | uzupełnij issue wg szablonu |
| Heat-map pusta | brak danych w bazie / Phase 11 jeszcze nie ma | normalne przed observability |
| „NEW … no node" w drift | doszedł plik | napisz mi „zaktualizuj mapę — przyrost" |

---

## 8. Na przyszłość — to ma być osobne repo

Cały folder `tools/archmap/` jest pisany tak, żeby dało się go wyjąć do osobnego repo
(`archmap`) i wrzucić do dowolnego innego projektu. Generyczne są: skill (instrukcja dla
agenta jak budować mapę), skrypty overlay, format `node-map.json`. Jedyne co jest
specyficzne dla AI-GM to zawartość `architecture-map.html` i ścieżki w `node-map.json` —
w nowym projekcie agent generuje je od nowa. Patrz `README.md`.
