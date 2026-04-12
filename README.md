# 🎲 AI Game Master 🇵🇱

Lokalny AI Mistrz Gry RPG uruchamiany przez Docker Compose, z backendem FastAPI, frontendem na Nginx oraz lokalnym Ollama z obsługą GPU NVIDIA. Projekt działa lokalnie, udostępnia API pod `/api`, dokumentację Swagger pod `/docs` i zapisuje kampanie, postacie oraz tury w SQLite.[web:95]

## Opis

AI Game Master to polskojęzyczny silnik narracyjny do prowadzenia kampanii RPG lokalnie, bez zależności od zewnętrznych usług LLM. Aktualna architektura wykorzystuje kontenery `backend`, `frontend` i `ollama`, a stan gry jest trwale przechowywany w wolumenie Dockera pod `/data`, dzięki czemu kampanie i historia tur przetrwają restart usług.[web:95]

Backend udostępnia endpointy kampanii, postaci, modeli, komend i tur, a frontend jest serwowany na porcie 3000. Narracja działa przez Ollama, a po ostatnich zmianach numeracja tur jest prowadzona niezależnie per kampania przez pole `turn_number`, zamiast opierać się na globalnym identyfikatorze rekordu.[cite:1]

## Funkcje

- Lokalny AI GM uruchamiany przez FastAPI i Ollama.[web:95]
- Frontend dostępny pod `http://localhost:3000`.[cite:1]
- Swagger UI pod `http://localhost:8000/docs`.[cite:1]
- API pod `http://localhost:8000/api`.[cite:1]
- Ollama pod `http://localhost:11434`.[cite:1]
- Obsługa kampanii, postaci i tur narracyjnych.[cite:1]
- Numeracja `turn_number` liczona per kampania, poprawnie rosnąca niezależnie od `id` w tabeli.[cite:1]
- Trwała baza SQLite w wolumenie Dockera `ai_gm_data`.[cite:1]
- Dev mode z bind mountem backendu i `uvicorn --reload` przez `docker-compose.override.yml`.[cite:1]
- Możliwość użycia modeli Ollama takich jak `gemma3:4b`, po wcześniejszym pobraniu ich do kontenera Ollama.[web:79][web:93]

## Architektura

| Usługa | Rola | Port | Uwagi |
|---|---|---:|---|
| `frontend` | statyczny UI przez Nginx | 3000 | serwuje pliki z `./frontend` przez bind mount.[cite:1] |
| `backend` | API FastAPI | 8000 | udostępnia `/api/*`, `/docs` i korzysta z SQLite oraz Ollama.[cite:1] |
| `ollama` | lokalny serwer modeli | 11434 | uruchamiany w Dockerze, z konfiguracją GPU NVIDIA.[cite:1] |
| `ai_gm_data` | trwałe dane | — | przechowuje plik bazy SQLite pod `/data/ai_gm.db`.[cite:1] |

## Endpointy

Na podstawie aktualnego OpenAPI backend wystawia między innymi poniższe ścieżki.[cite:1]

- `GET /api/health`
- `GET /api/models`
- `GET /api/campaigns`
- `POST /api/campaigns`
- `GET /api/campaigns/{campaign_id}`
- `DELETE /api/campaigns/{campaign_id}`
- `GET /api/campaigns/{campaign_id}/characters`
- `POST /api/campaigns/{campaign_id}/characters`
- `GET /api/campaigns/{campaign_id}/turns`
- `POST /api/campaigns/{campaign_id}/turns`
- `POST /api/commands/execute`

## Quick start

### 1. Uruchomienie

```bash
git clone <your-repo>
cd ai-gm
docker compose up -d --build
```

Po uruchomieniu aplikacja jest dostępna pod poniższymi adresami.[cite:1]

- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API: `http://localhost:8000/api`
- Ollama: `http://localhost:11434`

### 2. Pobranie modelu do Ollama

Jeżeli kampania ma ustawiony model `gemma3:4b`, ten model musi być dostępny w kontenerze `ollama`, a nie tylko na zewnętrznym hoście. W praktyce oznacza to konieczność wykonania `ollama pull` wewnątrz usługi Dockerowej, bo backend domyślnie komunikuje się z `http://ollama:11434` przez sieć Compose.[web:95][cite:1]

```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama list | grep gemma3
```

### 3. Szybki test API

```bash
curl -s http://localhost:8000/api/campaigns | jq
```

## Przykładowy workflow

### Utworzenie kampanii

```bash
curl -s -X POST http://localhost:8000/api/campaigns \
  -H 'Content-Type: application/json' \
  -d '{
    "title":"Test Campaign",
    "system_id":"fantasy",
    "model_id":"gemma3:4b",
    "owner_user_id":1,
    "language":"pl"
  }' | jq
```

### Utworzenie postaci

```bash
curl -s -X POST http://localhost:8000/api/campaigns/16/characters \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"Test Character",
    "user_id":1,
    "system_id":"fantasy"
  }' | jq
```

### Wysłanie tury narracyjnej

```bash
curl -s -X POST http://localhost:8000/api/campaigns/16/turns \
  -H 'Content-Type: application/json' \
  -d '{"character_id":17,"text":"Patrzę wokół pokoju"}' | jq
```

### Odczyt historii kampanii

```bash
curl -s http://localhost:8000/api/campaigns/16/turns | jq
```

## Turn numbering

Projekt używa numeracji tur niezależnej od technicznego klucza głównego tabeli. Pole `turn_number` jest liczone osobno dla każdej kampanii, a endpoint listujący tury zwraca dane posortowane po `t.turn_number DESC`, dzięki czemu historia kampanii zachowuje logiczną kolejność nawet wtedy, gdy globalne `id` rekordów rośnie w całej bazie.[cite:1]

Praktyczny przykład potwierdzony podczas testów wyglądał tak: kampania 16 miała tury z `turn_number` równymi 1, 2, 3 i 4, podczas gdy odpowiadające im rekordy miały `id` 82, 85, 86 i 87. To potwierdza, że numeracja kampanii została skutecznie oddzielona od identyfikatorów SQLite.[cite:1]

## Tryb developerski

W trybie developerskim backend działa z bind mountem `./backend:/app` oraz z `uvicorn --reload`, dzięki czemu zmiany w kodzie są widoczne bez przebudowy obrazu. Zostało to zweryfikowane przez poprawne przeładowania WatchFiles po zmianach w `app/main.py` i `app/api/turns.py`.[cite:1]

Przykładowy `docker-compose.override.yml`:

```yaml
services:
  backend:
    volumes:
      - ./backend:/app
      - ai_gm_data:/data
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      WATCHFILES_FORCE_POLLING: "true"
```

Uruchomienie w dev mode:

```bash
docker compose up -d --build
docker compose logs -f backend
```

## Konfiguracja

Domyślna konfiguracja backendu korzysta z następujących zmiennych środowiskowych zdefiniowanych w Compose lub `.env`.[cite:1]

| Zmienna | Domyślna wartość | Opis |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | adres Ollama używany przez backend.[cite:1] |
| `OLLAMA_TIMEOUT` | `60` | timeout połączenia do modelu.[cite:1] |
| `DEFAULT_CAMPAIGN_LANGUAGE` | `pl` | domyślny język kampanii.[cite:1] |
| `GAME_LANG` | `pl-PL` | ustawienie języka gry.[cite:1] |
| `DATABASE_URL` | `sqlite:////data/ai_gm.db` | ścieżka do bazy SQLite.[cite:1] |

Jeżeli chcesz używać zewnętrznego hosta Ollama zamiast kontenera Compose, ustaw `OLLAMA_BASE_URL` w `.env` na adres zewnętrzny i zrestartuj backend. Bez tego backend używa wewnętrznej nazwy sieciowej `ollama` i wymaga pobrania modeli do kontenera `ollama`.[cite:1]

```env
OLLAMA_BASE_URL=http://your-external-host:11434
```

## Stack

- Python 3.12 + FastAPI + Pydantic.[cite:1]
- SQLite jako lokalna baza danych kampanii, postaci i tur.[cite:1]
- Ollama jako lokalny runner modeli LLM.[web:95]
- Docker Compose jako warstwa orkiestracji.[web:22]
- Nginx jako prosty serwer frontendu.[cite:1]

## Znane uwagi

Aktualnie w logach może pojawiać się ostrzeżenie Pydantic dotyczące pola `model_id` i przestrzeni nazw `model_`. To ostrzeżenie nie blokuje działania aplikacji, ale warto je później uporządkować w modelu `CampaignCreateRequest` przez konfigurację `protected_namespaces` albo zmianę nazwy pola po stronie modelu danych.[cite:1]

W OpenAPI była też widoczna dodatkowa ścieżka `/campaigns/campaigns/{campaign_id}/turns`, co wskazuje na tymczasowy problem z podwójnym prefiksem routera. Główna ścieżka robocza pozostaje jednak poprawna i dostępna pod `/api/campaigns/{campaign_id}/turns`.[cite:1]

## Roadmap

- uporządkowanie prefixów routerów i usunięcie duplikatu ścieżki,
- dopracowanie frontendu pod pełen gameplay loop,
- lepsza obsługa wielu modeli Ollama i wyboru modelu w UI,
- eksport i import kampanii,
- rozbudowa sheetów postaci i komend systemowych.

## Repozytorium

Aby zaktualizować README w repozytorium GitHub, skopiuj zawartość tego pliku do `README.md` w katalogu głównym projektu, a następnie wykonaj standardowy commit i push:[cite:1]

```bash
git add README.md docker-compose.override.yml backend/app/main.py backend/app/api/turns.py
git commit -m "docs: expand README with setup, API, dev mode and turn numbering"
git push
```
