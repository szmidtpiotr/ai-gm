---
name: test-inreview
description: >-
  Use when the user types /test-inreview or asks to "uruchom testy review", "przetestuj
  in-review", "zacznij testy". Scans all GitHub issues with label `review`, groups them into
  7 test runs, executes Playwright + pytest, auto-closes passing issues, comments (Polish) on
  ambiguous ones, files new bugs to FIX milestone. Do NOT use for testing a single issue —
  use /game-test-player-screenshot for that.
---

# test-inreview — masowy test wszystkich issue in-review

Cel: przetestować WSZYSTKIE otwarte issue z labelką `review` w minimalnej liczbie przebiegów,
zamknąć pewne, skomentować nierozstrzygalne, zalogować nowe bugi.

## ⛔ KONTRAKT

- **Zawsze rób świeży skan** labelki `review` przed startem — lista zmienia się między sesjami.
- **Wykluczone milestony:** Admin Panel Mobile · Refaktor monolitów (Faza R) · Głos/obrazy (Faza 6).
- **Strict triage:** TESTABLE tylko gdy backend + UI + DB wpięte end-to-end. Spec-only/partial → SKIP.
- **Zamykaj samodzielnie** jeśli test definitywnie potwierdza działanie.
- **Nie zamykaj** na podstawie samego odczytu kodu — tylko po realnym teście.
- **Komentarz po polsku** dla nierozstrzygalnych (nie po angielsku, nie technicznie).
- Nowe bugi → issue w milestone `Bugi i poprawki (FIX)` + label `bug`.
- Testuj zawsze na koncie Demo (user_id=1). Nigdy na user_id=1013 (Mizel).
- Aktualizuj `TEST_RAPORT.md` po każdym przebiegu.

## Krok 0 — Świeży skan (ZAWSZE PIERWSZY)

```bash
gh issue list --repo szmidtpiotr/ai-gm --label review --state open --limit 300 \
  --json number,title,milestone,labels \
  --jq '.[] | "#\(.number) [\(.milestone.title // "brak")] \(.title)"' | sort -t'#' -k2 -n
```

Pogrupuj wynik wg milestone, policz issue per milestone.

## Krok 0.5 — ZAPYTAJ które milestony testować (OBOWIĄZKOWE)

Przed jakimkolwiek testem użyj `AskUserQuestion` (multiSelect) — pokaż listę milestonów
z liczbą issue `review` w każdym. Domyślnie odznacz wykluczone (Admin Mobile / Faza R / Faza 6),
ale i tak je pokaż. User wybiera zakres tej sesji.

Po wyborze: odejmij niewybrane, podziel resztę na grupy (patrz niżej).
Jeśli lista różni się od poprzedniej sesji — zaktualizuj grupy przed startem.

## Model wykonania — osobna sesja per przebieg

**Każdy przebieg = osobny subagent (Agent tool).** Powód: czysty kontekst, jeden
przebieg zamyka wiele issue, minimum przejść przez grę.

- **Sekwencyjnie** dla przebiegów grających (1–4, 6, 7) — dzielą konto Demo (user_id=1)
  + DB DEV. Równoległe granie = kolizja stanu kampanii. Lecisz jeden po drugim.
- **Równolegle** dozwolone tylko dla read-only (przebieg 5 Admin Playwright), jeśli w zakresie.
- Każdy subagent: triage swojej grupy → test → zamknij/skomentuj/zaloguj buga → zwróć podsumowanie.
- Main wątek scala podsumowania → aktualizuje `TEST_RAPORT.md` po każdym przebiegu.

## 7 Grup testowych

Jedna sesja → wiele zamkniętych issue. Kolejność: 1→7.

| Grupa | Silnik | Pokrywa |
|---|---|---|
| 1 — Nowa Kampania | `game-smoke nowa-kampania` + Playwright | kreator, narracja, lokacja, quest, walka, sklep, odpoczynek, kostki, World State |
| 2 — Klasy bojowe | `game-test-player` (Wojownik/Łucznik) | dual-wield, amunicja, short rest, paski akcji walki |
| 3 — Mag + specjalne | `game-test-player` (Scholar) | czary ally/summon/reakcja/CHA, grapple, zaskoczenie, konsumable |
| 4 — Loch | `game-smoke-dungeon` | wszystkie L-taski + bugi zagadek/lochu z FIX |
| 5 — Admin panel | Playwright `/admin/` | Sandbox, tabele Czary/Rzuty, zakładki kampanii, dice configurator |
| 6 — MP frontend | Playwright (dual context) | GF1–GF7, bugi HTTP 500/migracje/model_id |
| 7 — G-tasks triage | grep + Playwright dual | triage G1–G31: które wpięte end-to-end → testuj; reszta → SKIP + komentarz |

## Triage (Krok 1 każdej grupy)

Przed testem sprawdź czy feature faktycznie istnieje:

```bash
# Backend — czy endpoint istnieje?
ssh claude@192.168.1.61 'grep -r "SŁOWO_KLUCZOWE" /home/piotrszmidt/ai-gm/backend/app/ --include="*.py" -l'

# Frontend — czy UI istnieje?
grep -r "SŁOWO_KLUCZOWE" /home/claude/projects/DEV_AIGM/frontend/ --include="*.js" -l
```

**TESTABLE** = backend + UI + DB path widoczne. **SKIP** = brak → komentarz na issue po polsku:
> "Mechanika jeszcze niezaimplementowana — feature istnieje jako spec w tym tickecie, ale kod nie jest gotowy. Ticket pozostaje w review."

## Zamykanie issue

**Zamknij** gdy: test przeszedł, feature działa zgodnie z opisem, brak regresji.
```bash
gh issue close NR --repo szmidtpiotr/ai-gm \
  --comment "✅ Zweryfikowano [DATA]. [Opis co przetestowano i jaki wynik]. Zamykam."
```

**Komentarz (nie zamykaj)** gdy: nie można rozstrzygnąć (zależność od innego ticketu, dane LLM niedeterministyczne, feature częściowo działa):
```bash
gh issue comment NR --repo szmidtpiotr/ai-gm \
  --body "🔍 Testowano [DATA]. [Opis problemu po ludzku]. [Co trzeba żeby zamknąć / od czego zależy]."
```

## Nowe bugi

```bash
gh issue create --repo szmidtpiotr/ai-gm \
  --milestone "Bugi i poprawki (FIX)" \
  --label bug \
  --title "[BUG] OPIS" \
  --body "TREŚĆ"
```

## TEST_RAPORT.md (aktualizuj po każdej grupie)

Plik: `TEST_RAPORT.md` w root repo. Struktura:

```markdown
# Raport testów — issue in-review
Aktualizacja: DATA | Łącznie: X/TOTAL (PASS ✅ / FAIL ❌ / SKIP ⏭ / KOMENTARZ 💬)

## Dashboard
| Milestone | Łącznie | ✅ | ❌ | ⏭ | 💬 |
...

## Wyniki per issue
| # | Tytuł | Wynik | Notatka |
...

## Nowe bugi (znalezione podczas testów)
| # | Tytuł |
...

## Nierozstrzygalne (czekają na decyzję)
| # | Tytuł | Powód |
...
```

## Workflow per grupa

```
1. Świeży skan (gh issue list)
2. Triage grupy (grep/read)
3. Uruchom test (odpowiedni silnik)
4. Per issue: zamknij / skomentuj / zaloguj buga
5. Aktualizuj TEST_RAPORT.md
6. Przejdź do następnej grupy
```

## Skróty

- Pojedynczy issue → `/game-test-player-screenshot #NNN`
- Loch pełny run → `/game-smoke-dungeon`
- Nowa/gotowa kampania → `/game-smoke nowa-kampania` lub `/game-smoke gotowa-kampania`
- Playwright report → `/playwright-test-report CO_PRZETESTOWAĆ`
