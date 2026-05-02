# API_INTEGRATION_ASSUMPTIONS

## Base

- API prefix: `/api`
- Auth login: `POST /api/auth/login`
- Turns list: `GET /api/campaigns/{campaign_id}/turns`
- Turns stream: `POST /api/campaigns/{campaign_id}/turns/stream` (SSE)

## Campaigns

- `GET /api/campaigns`
- `POST /api/campaigns`
- `POST /api/campaigns/{campaign_id}/reset`
- `DELETE /api/campaigns/{campaign_id}`

## Characters

- `GET /api/campaigns/{campaign_id}/characters`
- `POST /api/campaigns/{campaign_id}/characters`
- `GET /api/characters/{character_id}/sheet`
- `POST /api/characters/{character_id}/generate-identity`
- `POST /api/characters/{character_id}/finalize-sheet`

## Combat

- `POST /api/campaigns/{campaign_id}/combat/start`
- `GET /api/campaigns/{campaign_id}/combat`
- `GET /api/campaigns/{campaign_id}/combat/turns`
- `POST /api/campaigns/{campaign_id}/combat/resolve-attack`
- `POST /api/campaigns/{campaign_id}/combat/enemy-turn`
- `POST /api/campaigns/{campaign_id}/combat/flee`

## History / Memory / Help

- `POST /api/campaigns/{campaign_id}/history/summary`
- `POST /api/campaigns/{campaign_id}/history/summary/ensure`
- `GET /api/campaigns/{campaign_id}/history/summary`
- `POST /api/campaigns/{campaign_id}/memory/ask`
- `POST /api/campaigns/{campaign_id}/helpme`

## Settings / Models / Health

- `GET /api/models`
- `GET /api/health`
- `POST /api/settings/llm`
- `GET /api/settings/llm`
- `GET /api/users/{user_id}/llm-settings`
- `PUT /api/users/{user_id}/llm-settings`

## UX Contract Notes

- Front musi utrzymac obsluge SSE i markerow route.
- Kampania `410` oznacza stan zakonczony (death flow).
- Front oczekuje JSON detail przy bledach.
