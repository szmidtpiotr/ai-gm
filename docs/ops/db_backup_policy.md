# Polityka backupów DB

## Zakres

Projekt używa jednej bazy SQLite: `data/ai_gm.db`.

Są teraz dwie uzupełniające się ścieżki backupu:

1. Ręczna / operatorska:
   - `./scripts/backup.sh`
   - `./scripts/restore.sh <plik.db>`
2. Automatyczna przed importem konfiguracji z panelu admin / API:
   - `POST /api/admin/config/import`
   - `POST /api/admin/config/catalog-snapshot/import`

## Backup automatyczny przed importem

Przed **realnym** importem (`dry_run=false`) backend tworzy kopię bazy **zanim** zacznie podmieniać rekordy konfiguracyjne.

- Domyślna ścieżka w kontenerze: `/backups/imports`
- Na hoście: `./backups/imports` (bind mount Dockera)
- Format nazwy:
  - `ai_gm_pre_import_config_<timestamp>.db`
  - `ai_gm_pre_import_catalog_snapshot_<timestamp>.db`

`dry_run=true` nie tworzy backupu.

## Retencja

Retencja działa automatycznie po utworzeniu nowego backupu importowego.

Zasady:

- zachowaj wszystkie backupy młodsze niż `30 dni`
- jeśli starsze backupy przekraczają ten próg, zostaw zawsze co najmniej `3` najnowsze
- niezależnie od wieku nie trzymaj więcej niż `10` backupów importowych łącznie

To daje praktyczny kompromis:

- świeże importy są łatwe do cofnięcia
- bardzo stare kopie nie zapychają dysku
- nawet przy długim przestoju zostają minimum `3` ostatnie snapshoty importowe

## Restore

Automatyczne backupy importowe są zwykłymi plikami `.db`, więc można je przywrócić standardową ścieżką:

```bash
./scripts/restore.sh backups/imports/<nazwa_pliku>.db
docker compose restart backend
```

## Uwagi operacyjne

- To nie zastępuje backupu przed deployem ani ręcznego snapshotu przed większą operacją administracyjną.
- Import przez API nadal powinien zaczynać się od `dry_run=true`.
- Źródłem prawdy dla pełnego katalogu treści pozostaje `catalog-snapshot`, a nie wąski `import_config`.
