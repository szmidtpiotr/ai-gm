<!-- last_updated: 2026-04-30 12:00 CEST | rev: 2 -->

# Polityka backupów DB

> **Weryfikacja 2026-04-30:** treść merytoryczna (incydent, ścieżki, przywracanie) **nadal poprawna**. Zaktualizowano sekcję „status wdrożenia” względem aktualnych skryptów w repo.

---

## Incydent 2026-04-27

Podczas deployu `c954c47` (8E-3) nastąpiła korupcja `data/ai_gm.db`.
Przywócono backup z `2026-04-24 12:27` — utrata danych ~3 dni.

**Wniosek: snapshot DB przed każdym deployem jest obowiązkowy.**

---

## Istniejący mechanizm

| Mechanizm | Opis |
|-----------|------|
| **`scripts/deploy_prod.sh`** | Przed `git pull` kopiuje **`data/ai_gm.db`** → **`backups/ai_gm_pre_deploy_<timestamp>.db`** (krok **[2/5]**). To jest **automatyczny** snapshot przed deployem PROD, o ile deploy idzie tym skryptem z `main`. |
| **`scripts/backup.sh`** | Jednorazowa kopia ręczna: `backups/ai_gm_<timestamp>.db`. |
| **`scripts/db-autosync.sh`** | **To nie jest backup archiwalny** — synchronizuje kopię DB na host observability (Grafana „Campaign Story Reader”). Domyślnie co **300 s** w trybie `--loop`; opcjonalnie cron (`--install-cron`, domyślnie `*/5 * * * *`). |

---

## Rekomendacje (nadal warto rozważyć)

### 1. Snapshot przed deployem

**Stan:** spełnione dla ścieżki **`./scripts/deploy_prod.sh`** (backup przed pull).

Jeśli ktoś deployuje **bez** tego skryptu (ręczny `git pull` + restart), nadal obowiązuje ręczny snapshot wg wzoru:

```bash
DATE=$(date +%Y%m%d_%H%M%S)
COMMIT=$(git rev-parse --short HEAD)
cp data/ai_gm.db "backups/ai_gm_predeploy_${DATE}_${COMMIT}.db"
```

### 2. Rotacja backupów (zapobieganie zapychaniu dysku)

**Stan:** **nie** ma jej w `scripts/backup.sh` — nadal opcjonalnie dodać (np. zachować ostatnie N plików w `backups/`).

### 3. Weryfikacja integralności DB po restarcie

**Stan:** przykładowy `PRAGMA integrity_check` w dokumencie **nie jest** wdrożony w `backend/app/main.py` — nadal **zalecane** przy kolejnej zmianie lifecycle aplikacji.

### 4. Przywrócenie (procedura)

Bez zmian — nadal aktualna:

```bash
# 1. Zatrzymaj backend
docker compose stop backend

# 2. Zabezpiecz uszkodzoną kopię
DATE=$(date +%Y%m%d_%H%M%S)
cp data/ai_gm.db "data/ai_gm.db.corrupt_${DATE}"

# 3. Znajdź najnowszy backup
ls -lt backups/ai_gm_*.db | head -5

# 4. Przywróć wybrany backup
cp backups/ai_gm_WYBRANY.db data/ai_gm.db

# 5. Sprawdź integralność
sqlite3 data/ai_gm.db "PRAGMA integrity_check;"

# 6. Restart i healthcheck PROD (na hoście z compose PROD)
docker compose start backend
curl -sf http://127.0.0.1:8000/api/healthz
```

*(Port **8000** = backend PROD na hoście; DEV używa **8100** — nie mylić przy sprawdzaniu.)*

---

## Status wdrożenia (rev 2)

| Rekomendacja | Status |
|---|---|
| Snapshot przed deployem | ✅ w **`scripts/deploy_prod.sh`** (przed pull z `main`) |
| Rotacja backupów w `backup.sh` | 🔴 brak w repo — nadal opcjonalnie |
| `integrity_check` na starcie backendu | 🔴 nie wdrożone w kodzie |
| Procedura przywrócenia (udokumentowana) | ✅ powyżej |
