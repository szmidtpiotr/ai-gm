# Campaign Story Reader (Grafana + SQLite)

This is the SQL for reading full campaign story content from the canonical DB.

## Stale vs live play (important)

Grafana uses a **SQLite file on the observability VM** (`/var/lib/ai-gm-db/ai_gm.db` in `sqlite-story.yml`). That file is **not** the live database inside `ai-gm-backend` unless you copy it there.

- **Auto-refresh** in Grafana only re-queries the **same file** on disk. It does **not** stream new turns from the running game.
- After new turns in the app, run `observability/sync_story_db_to_observability.sh` (or `docker cp …` + `scp` to the VM) so the snapshot matches reality, then refresh the dashboard.

Use **Loki / logs** for near-real-time traces; use this SQL dashboard for **batch inspection** of a copied DB.

## Live-ish story via Loki (structured logs)

The backend emits **one JSON log line per narrative turn** (after the turn is saved) with `event: narrative_turn`, `campaign_id`, `turn_id`, `turn_number`, `user_text`, and `assistant_text`. Promtail ships Docker logs to Loki, so Grafana Explore can show current play **without** copying SQLite.

- Disable: env `NARRATIVE_STORY_LOG=0`
- Optional cap on text size per field: `NARRATIVE_LOG_MAX_CHARS` (e.g. `8000`; `0` = no cap)

Example LogQL (adjust label selectors to your stack):

```logql
{container="ai-gm-backend-1"} | json | event="narrative_turn" | campaign_id="3"
```

Then use **Logs** panel or **Table** with extracted fields — not the SQLite datasource.

Datasource:
- `AI-GM Story DB` (`uid: ai_gm_sqlite_story`)

## Variable query (`campaign_id`)

Create a dashboard variable:

```sql
SELECT id AS __value, title AS __text
FROM campaigns
ORDER BY id DESC;
```

## Story table query

Use this panel query (Table panel):

```sql
SELECT
  t.turn_number,
  c.title AS campaign_title,
  ch.name AS character_name,
  t.route,
  t.created_at,
  t.user_text,
  t.assistant_text
FROM campaign_turns t
LEFT JOIN campaigns c ON c.id = t.campaign_id
LEFT JOIN characters ch ON ch.id = t.character_id
WHERE t.campaign_id = ${campaign_id}
ORDER BY t.turn_number ASC;
```

## Optional compact query (GM narrative only)

```sql
SELECT
  t.turn_number,
  t.created_at,
  t.assistant_text
FROM campaign_turns t
WHERE t.campaign_id = ${campaign_id}
  AND t.route = 'narrative'
  AND COALESCE(TRIM(t.assistant_text), '') <> ''
ORDER BY t.turn_number ASC;
```

## Retencja: Loki vs kanon rozgrywki vs „historia” (AI)

| Źródło | Rola | Retencja |
|--------|------|----------|
| **SQLite** `campaign_turns` | Kanoniczna treść tur (gracz + MG); źródło dla podsumowań i eksportów | Trwała wraz z DB (backup VM/volume). To jest **jedyne wymagane** miejsce na treść pod funkcje produktowe. |
| **Loki** | Podgląd operacyjny „na żywo”, korelacja z błędami | Możesz ustawić krótką retencję (np. 7–30 dni) — **nie** polegaj na Loki jako jedynym archiwum narracji. |
| **Tabela** `campaign_ai_summaries` | Zapisane podsumowania z endpointu `POST /api/campaigns/{id}/history/summary` | Osobno od logów; przetrwa skrócenie retencji Loki. |

**Zasada:** funkcja **historia** (podsumowanie przez LLM) czyta wyłącznie tury z **SQLite** (`route = narrative`), a reguły stylu podsumowania są w pliku `backend/prompts/history_summary_prompt.txt` (override: `HISTORY_SUMMARY_PROMPT_PATH`).

### API (backend)

- `POST /api/campaigns/{campaign_id}/history/summary?user_id=<owner>&max_turns=200&persist=true` — generuje podsumowanie; `user_id` musi być **ownerem** kampanii.
- `GET /api/campaigns/{campaign_id}/history/summary` — ostatnio zapisane podsumowanie (jeśli był POST z `persist=true`).

### Grafana

- Dashboard **AI GM - Campaign narrative (Loki, near-live)** (`grafana/provisioning/dashboards/json/campaign-narrative-loki.json`) — logi `narrative_turn`.
- Dashboard SQL (snapshot pliku) — `campaign-story-reader.json` po sync DB na VM.
