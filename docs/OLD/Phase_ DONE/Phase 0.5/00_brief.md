<!-- STATUS: DONE -->
<!-- PHASE: 0.5 | DATE_START: — | DATE_END: — -->

# Phase 0.5 — Środowisko PROD/DEV + Observability (DEV) · Brief archiwalny

> Folder dokumentuje rozdzielenie stacków i pierwsze kroki observability na DEV. Szczegóły proceduralne: `README.md`, `DEPLOYMENT_PROCEDURE.md`, prompty PROMPT 1–3.

---

## 1. Cel fazy (podsumowanie)

Izolacja **produkcji** i **developmentu** na osobnych portach, bazach i sieciach Docker; dokumentacja deploy oraz metryki FastAPI / stack observability po stronie DEV.

**Definicja ukończenia (DoD) — stan archiwalny:**
- [x] Opisane porty i compose: PROD vs DEV (`docker-compose.yml` vs `docker-compose.dev.yml`)
- [x] Skrypty/procedury deploy (`scripts/`, `DEPLOYMENT_PROCEDURE.md`)
- [x] Prompty observability / metrics (pliki `PROMPT *` w tym folderze — status DONE w nazwach `_DONE`)

---

## 2. Zakres (co obejmuje dokumentacja w folderze)

| # | Komponent | Opis |
|---|-----------|------|
| 1 | Prod/Dev split | Osobne bazy, sieci, projekty Docker |
| 2 | Deploy | Procedura awansu dev → prod |
| 3 | Observability DEV | Prompty pod metryki / Loki / Grafana (wg plików w folderze) |

---

## 3. Podsumowanie wdrożenia (wysoki poziom)

- Dokumentacja operacyjna dla zespołu: **gdzie** uruchamiać eksperymenty (DEV) vs stabilny ruch (PROD).
- Materiały PROMPTów jako historia decyzji przy włączaniu observability na DEV.

---

## 4. Powiązane pliki w tym folderze

- `README.md` — idea środowisk, struktura katalogów  
- `DEPLOYMENT_PROCEDURE.md` — procedura wdrożeń  
- `PROMPT 1 — Prod Dev Split_DONE.md`, `PROMPT 2 — Observability DEV_DONE.md`, `PROMPT 3 — FastAPI Metrics DEV_DONE.md`

---

## Analiza po fazie *(Perplexity — opcjonalnie)*

*Do uzupełnienia jeśli robicie retrospektywę operacyjną.*

### STATUS: DONE
