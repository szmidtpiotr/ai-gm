# Phase 0 — Prod/Dev Environment

## Idea rozdzielenia środowisk

Na maszynie `.61` działają dwa niezależne stacki Dockera:

| Środowisko | Branch | Frontend | Backend | Baza danych | Docker Compose |
|---|---|---|---|---|---|
| **Produkcja** | `main` | `:3001` | `:8000` | `data/ai_gm.db` | `docker-compose.yml` |
| **Development** | `develop` | `:3002` | `:8100` | `data-dev/ai_gm_dev.db` | `docker-compose.dev.yml` |

Stacki są od siebie izolowane:
- osobne sieci Docker (`ai-gm` vs `ai-gm-dev`)
- osobne bazy danych (baza dev to kopia prod z momentu inicjalizacji — nie synchronizuje się automatycznie)
- osobne nazwy projektów Docker (`ai-gm` vs `ai-gm-dev`)

## Kiedy używać jakiego środowiska

**Dev (`:3002`):**
- pisanie nowych funkcji
- testowanie zmian przed wdrożeniem
- eksperymenty z konfiguracją LLM
- wszystko, co może się zepsuć

**Prod (`:3001`):**
- tylko kod z gałęzi `main`
- tylko po przejściu testów na dev
- deploy wyłącznie przez `scripts/deploy_prod.sh`

## Struktura plików

```
ai-gm/
├── docker-compose.yml          ← PROD (nie ruszamy bez potrzeby)
├── docker-compose.dev.yml      ← DEV
├── data/
│   └── ai_gm.db                ← baza PROD
├── data-dev/
│   └── ai_gm_dev.db            ← baza DEV (kopia prod)
└── scripts/
    ├── deploy_prod.sh          ← deploy na PROD z healthcheckiem
    └── deploy_dev.sh           ← deploy na DEV
```

## Szybki start po sklonowaniu

```bash
# Uruchom DEV
./scripts/deploy_dev.sh

# Uruchom PROD (tylko na maszynie produkcyjnej, branch main)
./scripts/deploy_prod.sh
```

## Dokumentacja procedury awansu

Szczegółowa procedura przeniesienia kodu z dev na prod znajduje się w:
→ [`DEPLOYMENT_PROCEDURE.md`](./DEPLOYMENT_PROCEDURE.md)
