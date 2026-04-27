# Procedura: Wdrożenie z Dev na Produkcję

> ⚠️ Przeczytaj całość przed pierwszym wdrożeniem.

---

## Checklist przed wdrożeniem

- [ ] Feature działa poprawnie na dev (`http://IP:3002`)
- [ ] Brak nieskończonych błędów w logach dev:
  ```bash
  docker compose -f docker-compose.dev.yml logs --tail=30
  ```
- [ ] Masz dostęp SSH do maszyny `.61`
- [ ] Baza prod jest w dobrym stanie:
  ```bash
  ls -lh data/ai_gm.db
  ```
- [ ] Nie ma niezacommitowanych zmian na dev:
  ```bash
  git status
  ```

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
cd /ścieżka/do/ai-gm
./scripts/deploy_prod.sh
```

Skrypt automatycznie:
1. Sprawdza, czy jesteś na gałęzi `main` (odmawia jeśli nie)
2. Tworzy backup bazy przed wdrożeniem → `backups/ai_gm_pre_deploy_DATA.db`
3. Pobiera najnowszy kod z `main`
4. Restartuje kontenery prod (`docker-compose.yml`)
5. Czeka na healthcheck backendu (max 60 sekund)

---

## Krok 3 — Weryfikacja po wdrożeniu

- [ ] Otwórz `http://IP:3001` — czy gra działa?
- [ ] Sprawdź logi:
  ```bash
  docker compose logs backend --tail=20
  ```
- [ ] Sprawdź, czy dev stack nadal chodzi niezależnie:
  ```bash
  docker compose -f docker-compose.dev.yml ps
  ```

---

## Rollback (jeśli coś pójdzie nie tak)

### Rollback kodu

```bash
# Znajdź hash przed wdrożeniem
git log --oneline -10

# Wróć do poprzedniej wersji
git checkout main
git reset --hard <poprzedni-commit-hash>
git push origin main --force-with-lease
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

```
[Praca na develop]
       ↓
[Test na :3002 — czy działa?]
       ↓
[PR: develop → main] lub [git merge lokalnie]
       ↓
[./scripts/deploy_prod.sh]
       ↓
[Healthcheck: backend :8000/api/healthz]
       ↓
[Weryfikacja na :3001]
```
