# Procedura: Wdrożenie z Dev na Produkcję

Aktualizacja modelu środowisk:

- `192.168.1.61` = **DEV only**
- `192.168.1.63` = **PROD only**
- aktualny preferowany deploy PROD jest **manualny przez skrypt na `.63`**
- workflow GitHub Actions w repo jest obecnie wyłączony celowo, żeby nie wdrożyć niczego na stary host przez pomyłkę

> ⚠️ Przeczytaj całość przed pierwszym wdrożeniem.

---

## Checklist przed wdrożeniem

- [ ] Feature działa poprawnie na dev (`http://IP:3002`)
- [ ] Brak nieskończonych błędów w logach dev: `docker compose -f docker-compose.dev.yml logs --tail=30`
- [ ] Masz dostęp SSH do maszyny DEV `.61`
- [ ] Masz dostęp SSH do maszyny PROD `.63`
- [ ] Baza prod jest w dobrym stanie: `ls -lh data/ai_gm.db`
- [ ] Nie ma niezacommitowanych zmian na dev: `git status`

---

## Krok 1 — Merge `develop` → `main`

### Opcja A: przez Pull Request (zalecana)

1. GitHub → Pull Requests → New Pull Request
2. `base: main`, `compare: develop`
3. Przejrzyj diff, zatwierdź
4. Merge (Squash and Merge jeśli feature branch, Merge commit jeśli chcesz zachować historię)

### Opcja B: lokalnie (solo, bez code review)

```bash
git checkout main
git pull origin main
git merge develop --no-ff -m "chore: promote develop to main — [opis zmian]"
git push origin main
```

---

## Krok 2 — Deploy na produkcję

```bash
ssh <user>@192.168.1.63
cd /ścieżka/do/ai-gm
./scripts/deploy_prod.sh
```

Skrypt automatycznie:

1. Sprawdza, czy jesteś na gałęzi `main` (odmawia jeśli nie)
2. Tworzy backup bazy przed wdrożeniem → `backups/ai_gm_pre_deploy_DATA.db`
3. Pobiera najnowszy kod z `main`
4. Restartuje kontenery prod (`docker-compose.yml`) na dedykowanym hoście `.63`
5. Czeka na healthcheck backendu (max 120 sekund)

---

## Pierwszy bootstrap nowej maszyny PROD

Na świeżej maszynie `.63` zrób najpierw bootstrap repo i stosu:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/szmidtpiotr/ai-gm.git
cd ai-gm
chmod +x install.sh
GRAFANA_ADMIN_PASSWORD='strong-password' ./install.sh --with-observability --no-ollama
```

`--no-ollama` jest zalecane, jeśli finalny custom provider / URL / API key / model ustawisz później w panelu admina.

Po pierwszym bootstrapie kolejne release idą już przez:

```bash
./scripts/deploy_prod.sh
```

---

## Status GitHub Actions

Workflow:

- Plik: `.github/workflows/deploy-production.yml`
- Status: **wyłączony celowo**
- Powód: stary workflow był związany z dawnym mieszanym hostem DEV/PROD; aktualny model wymaga manualnego deployu na dedykowanym `.63`

---

## Krok 3 — Weryfikacja po wdrożeniu

- [ ] Otwórz `http://IP:3001` — czy gra działa?
- [ ] Otwórz obserwowalność na `.63` (`:3000`, `:3100`, `:8001`) i potwierdź, że stack działa
- [ ] Sprawdź logi: `docker compose logs backend --tail=20`
- [ ] Sprawdź, czy dev stack nadal chodzi niezależnie: `docker compose -f docker-compose.dev.yml ps`

---

## Rollback (jeśli coś pójdzie nie tak)

### Rollback kodu

```bash
# Preferuj bezpieczny rollback przez revert / nowy commit na main
# zamiast force-pusha historii.

# Przykład: odwrócenie ostatniego commita i nowy deploy
git checkout main
git pull --ff-only origin main
git revert <commit-hash>
git push origin main
./scripts/deploy_prod.sh
```

### Rollback bazy danych

```bash
# Znajdź backup (format: ai_gm_pre_deploy_YYYYMMDD_HHMMSS.db)
ls -lt backups/ | head -5

# Zatrzymaj kontenery
docker compose stop

# Przywróć bazę
cp backups/ai_gm_pre_deploy_XXXXXXXX_XXXXXX.db data/ai_gm.db

# Uruchom ponownie
docker compose up -d
```

> Backup jest tworzony automatycznie przez `deploy_prod.sh` przed każdym wdrożeniem.
> Jeśli chcesz zrobić ręczny backup w dowolnym momencie: `./scripts/backup.sh`

---

## Diagram przepływu

```text
[Praca na develop]
       ↓
[Test na :3002 — czy działa?]
       ↓
[PR: develop → main] lub [git merge lokalnie]
       ↓
[SSH na 192.168.1.63]
       ↓
[./scripts/deploy_prod.sh]
       ↓
[Healthcheck: backend :8000/api/healthz]
       ↓
[Weryfikacja na :3001]
```
