# Szablon Uniwersalnego Promptu dla Cursora

> **Przeznaczenie:** Użyj tego szablonu przy każdym nowym zadaniu dla Cursora.
> Skopiuj plik, wypełnij sekcje i przekaż Perplexity do wygenerowania właściwego promptu.
> Perplexity generuje REV 1, potem REV 2 po Twoich odpowiedziach.

---

## Jak używać tego szablonu

1. **Skopiuj ten plik** do folderu odpowiedniej Phase, nadaj nazwę: `PROMPT N — Nazwa.md`
2. **Wypełnij sekcje** `[DO UZUPEŁNIENIA]` poniżej
3. **Wklej do Perplexity** — poproś o wygenerowanie promptu dla Cursora
4. Perplexity generuje **REV 1** z pytaniami blokującymi
5. Wklej REV 1 do Cursora → **skopiuj odpowiedzi** z powrotem do Perplexity
6. Perplexity generuje **REV 2** (właściwy prompt implementacyjny)
7. Wklej REV 2 do Cursora → Cursor **implementuje**
8. Cursor uzupełnia sekcję `## Co zostało zrobione`
9. Wklej raport Cursora do Perplexity → **Perplexity dopisuje notatki** i oznacza plik `DONE`

---

## Prompt dla Perplexity (wklej to do nowej rozmowy)

```
Jestem właścicielem projektu ai-gm (RPG z AI-GM, repo: szmidtpiotr/ai-gm).
Chcę żebyś przygotował prompt dla Cursora (Agent Mode) zgodnie z naszym workflow.

Zadanie do zaimplementowania:
[OPISZ CO MA ZOSTAĆ ZROBIONE]

Kontekst:
- Obecna faza projektu: [np. Phase 8A — Combat System]
- Pliki których dotyczy zadanie: [np. backend/app/services/, docker-compose.yml]
- Czego NIE wolno ruszać: [np. docker-compose.yml prod, baza data/ai_gm.db]
- Zależności: [np. wymaga wcześniejszej migracji DB z PROMPT 1]

Proszę:
1. Wygeneruj PROMPT REV 1 z pytaniami blokującymi dla Cursora
2. Pamiętaj żeby Cursor przed implementacją sprawdził czy nic nie zepsuje
3. Na końcu promptu zostaw sekcje: ## Odpowiedzi Cursora, ## Co zostało zrobione, ## Notatki po implementacji
4. Zapisz plik w docs/[Phase folder]/PROMPT N — Nazwa.md
```

---

## Struktura pliku promptu (generowana przez Perplexity)

```markdown
<!-- STATUS: PENDING | IN_PROGRESS | DONE -->
<!-- REV: 1 | DATE: YYYY-MM-DD -->

# PROMPT N — [Nazwa zadania]

> Workflow tego pliku: [standardowy opis]

## Cel
[Co ma zostać zrobione i dlaczego]

## Kontekst techniczny
[Pliki, zależności, ograniczenia]

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące
[Lista pytań do Cursora — odpowiada zanim implementuje]

## Implementacja (REV 1 — do zatwierdzenia)
[Kroki implementacji — Cursor NIE wykonuje zanim nie zatwierdzi Perplexity]

## Odpowiedzi Cursora (REV 1)
[Miejsce na wklejenie odpowiedzi Cursora]

## Co zostało zrobione *(uzupełnia Cursor)*
[Miejsce na raport Cursora po implementacji]

## Notatki po implementacji *(uzupełnia Perplexity)*
[Miejsce na notatki Perplexity]
```

---

## Reguły workflow — dla pamięci

| Krok | Kto | Co robi |
|---|---|---|
| 1 | Perplexity | Generuje PROMPT REV 1 z pytaniami blokującymi, zapisuje na GitHub |
| 2 | Cursor | Odpowiada na pytania blokujące (NIE implementuje) |
| 3 | Ty | Wklejasz odpowiedzi Cursora do Perplexity |
| 4 | Perplexity | Analizuje odpowiedzi, generuje PROMPT REV 2 lub zgłasza blokery |
| 5 | Cursor | Implementuje wg REV 2 |
| 6 | Cursor | Uzupełnia `## Co zostało zrobione` w pliku |
| 7 | Ty | Wklejasz raport Cursora do Perplexity |
| 8 | Perplexity | Dopisuje `## Notatki po implementacji`, zmienia STATUS na DONE |
| 9 | Ty (opcjonalnie) | Zmieniasz nazwę pliku dodając sufiks `_DONE` |

---

## Flagi statusu

```
<!-- STATUS: PENDING -->      ← prompt wygenerowany, czeka na odpowiedzi
<!-- STATUS: IN_PROGRESS -->  ← Cursor implementuje
<!-- STATUS: DONE -->         ← implementacja zakończona, notatki dopisane
```

---

## Przykładowe pytania blokujące (Perplexity zawsze generuje podobne)

- Czy plik X już istnieje? (`ls -la X`)
- Czy port Y jest wolny? (`ss -tlnp | grep Y`)
- Czy jesteś na właściwym branchu? (`git branch --show-current`)
- Czy są niezacommitowane zmiany? (`git status`)
- Czy zależność Z jest zainstalowana? (`which Z` / `pip show Z`)
- Czy baza danych jest w dobrym stanie? (`ls -lh data/ai_gm.db`)
