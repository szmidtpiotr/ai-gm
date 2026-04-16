# Perplexity Access Tutorial (Logs)

This guide shows how to let Perplexity analyze AI-GM logs safely.

## Goal

Give Perplexity **read-only** access to log data from Loki/Grafana without exposing admin credentials.

## Recommended architecture

- Observability VM: `192.168.1.19`
- Grafana UI: `http://192.168.1.19:3000`
- Loki API: `http://192.168.1.19:3100`
- AI-GM host ships logs via Promtail to Loki

## Public endpoints (Nginx Proxy Manager)

Use these public URLs for external access:

- Grafana: `https://aigm-grafana.studio-colorbox.com/`
- Loki: `https://aigm-loki.studio-colorbox.com/`

## Security baseline (required)

1. Create a dedicated Grafana **Viewer** user for external AI tools.
2. Do **not** share admin password.
3. Restrict network access (VPN/Tailscale preferred).
4. Keep token redaction enabled in Promtail pipeline.

## Option A (easy): Share filtered log exports

Use Grafana Explore/Loki query, export recent lines, paste to Perplexity.

### Useful queries

- All backend request logs:
  - `{service="backend"} |= "request_complete"`
- Backend 5xx:
  - `{service="backend"} | json | status_code=~"5.."`
- LLM failures:
  - `{service="backend", error_type=~"llm_.*"}`

This is the safest option because you only share selected snippets.

## Option B (direct read-only API): service account token

If Perplexity environment can call HTTP endpoints, provide a read-only Grafana token.

### Steps

1. In Grafana:
   - `Administration -> Users and access -> Service Accounts`
   - Create `perplexity-readonly`
   - Role: `Viewer`
   - Generate token

2. Use token with Grafana/Loki queries:

```bash
TOKEN="<service-account-token>"

# Find datasource ID for Loki
curl -s -H "Authorization: Bearer $TOKEN" \
  https://aigm-grafana.studio-colorbox.com/api/datasources \
  | jq '.[] | select(.type=="loki") | {id,uid,name,url}'
```

```bash
TOKEN="<service-account-token>"

# Query through Grafana proxy (recommended with auth)
curl -G -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://aigm-grafana.studio-colorbox.com/api/datasources/proxy/uid/loki/loki/api/v1/query_range" \
  --data-urlencode 'query={service="backend"} |= "request_complete"' \
  --data-urlencode "start=$(date -u -d '15 minutes ago' +%s)000000000" \
  --data-urlencode "end=$(date -u +%s)000000000" \
  --data-urlencode "limit=200" \
  | jq .
```

## Tailscale / VPN recommendation

If Perplexity side supports remote fetch:

1. Install Tailscale on observability VM.
2. Disable direct public exposure of Grafana/Loki ports.
3. Allow access only from Tailscale IP range.

## Suggested Perplexity prompt template

```text
Analyze these AI-GM backend logs and identify:
1) root cause of latest failure,
2) top repeating error signatures,
3) exact remediation steps.

Context:
- backend service logs are JSON
- fields include request_id, route, status_code, error_type, llm_provider, llm_model
```

## Troubleshooting

- Empty results:
  - Check promtail on game host is up.
  - Check Loki endpoint is reachable: `https://aigm-loki.studio-colorbox.com/`.
- No `request_id`:
  - Ensure backend runs latest middleware-enabled build.
- Unauthorized:
  - Recreate service account token, verify Viewer role.
- Grafana loads error page ("failed to load application files"):
  - Usually reverse proxy path/header issue.
  - If served under subpath, set Grafana `root_url` + `serve_from_sub_path=true`.
  - If served on plain domain root (recommended), keep NPM forwarding directly to `:3000` without subpath rewrites.
