# Campaign Story Reader (Grafana + SQLite)

This is the SQL for reading full campaign story content from the canonical DB.

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
