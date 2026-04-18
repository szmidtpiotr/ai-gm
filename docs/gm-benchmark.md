# Benchmark GM — LLMAPI (Node.js CLI)

Narzędzie uruchamia ten sam zestaw promptów RPG (po polsku) na wielu modelach, zapisuje surowe odpowiedzi i generuje raporty JSON / CSV / Markdown.

## Wymagania

- **Node.js 18+** (wbudowany `fetch`)
- Klucz **LLMAPI** w zmiennej środowiskowej `LLMAPI_API_KEY`

## Konfiguracja

| Plik | Opis |
|------|------|
| `config/models.json` | Lista modeli: `label`, `model` (ID z panelu LLMAPI), `enabled` |
| `config/tests.json` | `defaults` (system prompt, `temperature`, `max_tokens`) + tablica `tests` (T01–T08) |

## Uruchomienie

Z katalogu głównego repozytorium (`ai-gm/`):

```bash
export LLMAPI_API_KEY="sk-..."
npm run benchmark
```

Tryb gadatliwy (log każdego testu w konsoli):

```bash
npm run benchmark:verbose
```

## Wyniki

| Ścieżka | Zawartość |
|---------|-----------|
| `output/raw/` | Pełna odpowiedź API (JSON) na plik: `{model}__{test_id}.json` |
| `output/results/benchmark-results.json` | Metadane + tablica wyników (latency, znaki, słowa, tekst) |
| `output/results/benchmark-results.csv` | Tabela do arkusza |
| `output/results/benchmark-results.md` | Tabela zbiorcza + sekcje per model i per test |
| `output/results/manual-score-sheet.csv` | Szablon ocen ręcznych (polish, gm_style, …) |
| `output/results/errors.log` | Błędy i nieudane próby (retry) |

## Lista modeli z API

Publiczna lista (bez klucza): modeli jest wiele i zmienia się w czasie.

```bash
curl -sS "https://api.llmapi.ai/v1/models?exclude_deprecated=true" | node -e "JSON.parse(require('fs').readFileSync(0,'utf8')).data.forEach(m=>console.log(m.id))"
```

Albo w tym repo:

```bash
node scripts/list-llmapi-models.js
node scripts/list-llmapi-models.js --text-only
```

Uwaga: **dostępność przy Twoim kluczu** (darmowe modele, weryfikacja e-mail, limity) może być węższa niż sama lista endpointu.

## Typowe błędy LLMAPI

- **HTTP 403 — „email verification required to use free models”** — konto musi mieć **potwierdzony adres e-mail** w panelu LLMAPI, zanim zadziałają darmowe modele. Retry skryptu tego nie naprawi.

- **HTTP 401** — sprawdź `LLMAPI_API_KEY`.

## API

- **Base URL:** `https://api.llmapi.ai`
- **Endpoint:** `POST /v1/chat/completions` (format OpenAI)
- **Timeout:** 60 s na request
- **Retry:** do 3 prób (1 + 2 ponowienia) przy błędzie

## Dostosowanie

- Wyłącz model: `"enabled": false` w `config/models.json`
- Zmiana temperatury / limitu tokenów: sekcja `defaults` w `config/tests.json`
- Dodanie testu: nowy obiekt w `tests` z polami `id`, `name`, `user_prompt`

Przed pierwszym uruchomieniem **uzupełnij prawdziwe identyfikatory modeli** w `config/models.json` (z dokumentacji / panelu LLMAPI) zamiast wartości `REPLACE_ME_*`.
