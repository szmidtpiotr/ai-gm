---
name: test-inreview
description: >-
  Use when the user types /test-inreview or asks to "uruchom testy review", "przetestuj
  in-review", "zacznij testy". Scans all GitHub issues with label `review`, groups them into
  7 test runs, executes Playwright + pytest via subprocess claude sessions, auto-closes passing
  issues, comments (Polish) on ambiguous ones, files new bugs to FIX milestone. Do NOT use for
  testing a single issue — use /game-test-player-screenshot for that.
---

# test-inreview — masowy test wszystkich issue in-review

Cel: przetestować WSZYSTKIE otwarte issue z labelką `review` w minimalnej liczbie przebiegów,
zamknąć pewne, skomentować nierozstrzygalne, zalogować nowe bugi.

## ⛔ KONTRAKT — TRYB TEST, NIE NAPRAWA

**Podczas testów NIE naprawiasz błędów.** Znaleziony bug → zaloguj issue → jedź dalej.

Wyjątek: szybka naprawa (< 5 min, 1-2 linie) która **blokuje dalsze testowanie tej grupy**.
Wtedy napraw, zacommituj jedną linią, kontynuuj. Nie rozwijaj.

Reguła prosta: jeśli zastanawiasz się czy naprawić — nie naprawiaj. Zaloguj i jedź dalej.

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

## Krok 0.5 — ZAPYTAJ o zakres i konfigurację agentów (OBOWIĄZKOWE)

Przed jakimkolwiek testem użyj `AskUserQuestion` z **trzema pytaniami naraz**:

**Pytanie 1 — Milestony** (multiSelect):
Pokaż listę milestonów z liczbą issue `review` w każdym. Domyślnie odznacz wykluczone
(Admin Mobile / Faza R / Faza 6), ale i tak je pokaż.

**Pytanie 2 — Model subprocesów** (singleSelect):
| Opcja | Kiedy |
|---|---|
| `haiku` (szybki, tani) | proste Playwright checks, triage read-only |
| `sonnet` (domyślny) | standardowe testy gry, game-smoke |
| `opus` (najsilniejszy) | złożone scenariusze MP, niejednoznaczne przypadki |

**Pytanie 3 — Effort subprocesów** (singleSelect):
| Opcja | Kiedy |
|---|---|
| `low` | triage, read-only checks |
| `medium` (domyślny) | standardowe testy |
| `high` | trudne scenariusze (MP, G-tasks, skomplikowane bugi) |

Zapamiętaj wybrany model i effort — użyj ich w każdym subprocess `claude --print`.
Po wyborze: odejmij niewybrane milestony, podziel resztę na grupy (patrz niżej).
Jeśli lista różni się od poprzedniej sesji — zaktualizuj grupy przed startem.

## Model wykonania — subprocess `claude --print` per przebieg

**Każdy przebieg = osobny subprocess `claude --print`, NIE `Agent` tool.**

**Dlaczego nie `Agent` tool:** duże prompty z instrukcjami grupy powodują dialog uprawnień
w claudecodeui którego nie można zatwierdzić. CLI subprocess (`claude --print`) omija UI
i działa zawsze — nowa sesja, czysty kontekst, pełne narzędzia.

### Workflow per grupa (sekwencyjny — czekaj na koniec przed następną)

```
1. Przygotuj self-contained prompt dla grupy → zapisz do /tmp/aigm-test-grupaN.md
2. Uruchom subprocess w tle:
   claude --model MODEL --print < /tmp/aigm-test-grupaN.md > /tmp/aigm-out-grupaN.md 2>&1
3. Monitoruj zakończenie (plik output nie jest pusty i proc skończył)
4. Przeczytaj /tmp/aigm-out-grupaN.md → zaktualizuj TEST_RAPORT.md
5. Skasuj pliki temp → przejdź do następnej grupy
```

### Komenda subprocess

Podmień `MODEL` na wybrany model (np. `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`):

```bash
# Uruchom w tle (Bash run_in_background: true)
claude --model MODEL --dangerouslySkipPermissions \
  --print < /tmp/aigm-test-grupaN.md > /tmp/aigm-out-grupaN.md 2>&1
```

Użyj `run_in_background: true` w Bash tool — potem czekaj na notyfikację zakończenia.
Nie monitoruj aktywnie co 30s — background Bash notyfikuje gdy proc skończy.

### Mapping modelu do model-id

| Wybrany model | Flag `--model` |
|---|---|
| haiku | `claude-haiku-4-5-20251001` |
| sonnet | `claude-sonnet-4-6` |
| opus | `claude-opus-4-8` |

### Effort w prompcie subprocesu

`--print` nie ma flagi effort. Zamiast tego dopisz na początku promptu dla grupy:
```
EFFORT: medium  (lub low/high — wpływa na głębokość analizy)
```
Subprocess przeczyta i dostosuje dokładność.

### Sekwencyjność (krytyczne)

Grupy grające (1–4, 6, 7) dzielą konto Demo (user_id=1) + DB DEV.
**Nie odpalaj dwóch grajacych grup równolegle — kolizja stanu kampanii.**
Grupa 5 (Admin Playwright, read-mostly) może iść równolegle z inną, jeśli nie modyfikuje kampanii Demo.

## Szablon self-contained promptu dla grupy

Każdy plik `/tmp/aigm-test-grupaN.md` musi być **w pełni autonomiczny** — subprocess
nie ma dostępu do bieżącej sesji. Użyj poniższego szablonu (podmień CAPS):

```markdown
# AI-GM Test Runner — Grupa NAZWA (ZAKRES ISSUE)

EFFORT: MEDIUM

## Kontekst środowiska
- DEV backend: ssh claude@192.168.1.61
- Repo na DEV: /home/piotrszmidt/ai-gm
- DEV URL: https://aigm-dev.studio-colorbox.com/
- Konto testowe: Demo (user_id=1), NIE user_id=1013 (Mizel — tylko read)
- Git: sudo -u piotrszmidt git ... (na .61)

## Twoja rola
Jesteś subprocesem testowym. Testuj poniższe issue, zamykaj pewne, komentuj nierozstrzygalne,
loguj nowe bugi. NIE naprawiaj — wyjątek: <5 min fix blokujący dalsze testowanie.

## Kontrakt
- Triage STRICT: TESTABLE = backend+UI+DB wpięte end-to-end. Spec-only → SKIP.
- Zamykaj: gh issue close NR --repo szmidtpiotr/ai-gm --comment "✅ Zweryfikowano [data]. [opis]. Zamykam."
- Komentuj (nie zamykaj): gh issue comment NR --repo szmidtpiotr/ai-gm --body "🔍 Testowano [data]. [opis problemu]. [co trzeba żeby zamknąć]."
- Nowe bugi: gh issue create --repo szmidtpiotr/ai-gm --milestone "Bugi i poprawki (FIX)" --label bug --title "[BUG] OPIS" --body "TREŚĆ"
- Komentarze po polsku, dla gracza nie technicznie.

## Issue do przetestowania

LISTA_ISSUE_Z_TYTULAMI_I_OPISAMI

## Przebieg testowy

SCENARIUSZ_TESTOWY (np. Zagraj 10-15 tur jako Łotrzyk na kampanii Demo, sprawdź...)

## Zwróć na końcu

Po zakończeniu wszystkich testów zwróć JSON:
{
  "grupa": "NAZWA",
  "wyniki": [
    {"nr": 747, "wynik": "PASS|FAIL|SKIP|KOMENTARZ", "notatka": "krótko po polsku"},
    ...
  ],
  "nowe_bugi": [{"nr": 960, "tytul": "[BUG] ..."}],
  "czas_testu_min": 25
}
```

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
2. Przygotuj prompt grupy → /tmp/aigm-test-grupaN.md (self-contained)
3. Uruchom subprocess: claude --model MODEL --dangerouslySkipPermissions --print < prompt > output &
4. Czekaj na zakończenie (run_in_background: true + notyfikacja)
5. Przeczytaj output → zamknij/skomentuj/zaloguj buga na GitHub
6. Zaktualizuj TEST_RAPORT.md
7. Przejdź do następnej grupy
```

## Skróty

- Pojedynczy issue → `/game-test-player-screenshot #NNN`
- Loch pełny run → `/game-smoke-dungeon`
- Nowa/gotowa kampania → `/game-smoke nowa-kampania` lub `/game-smoke gotowa-kampania`
- Playwright report → `/playwright-test-report CO_PRZETESTOWAĆ`
