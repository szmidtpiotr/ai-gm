# front-v2 — nowy frontend gracza (ŻAR)

Kierunek wizualny **ŻAR** (frontend_design.md §5–6). Stack: React 18 + Vite + TS +
Tailwind + shadcn/ui (Radix) + TanStack Query + Zustand + React Router.
Stary `frontend/front/` został usunięty 2026-07-18 (archiwum: tag
`archive/frontend-front-legacy-20260718` + tar w `/home/piotrszmidt/ai-gm-archive/` na `.61`).

## Serwowanie

- **DEV:** wspólny nginx (`frontend/nginx.conf`) serwuje zbudowane `dist/` pod **`/v2/`**
  (`location ^~ /v2/`). Zbuduj bundle do `dist/`, a mount `./frontend` udostępni go kontenerowi.
- **Prod / standalone:** multi-stage `Dockerfile` + `nginx.front-v2.conf`.

`base` (vite.config.ts) i router `basename` = `/v2` — nie zmieniać osobno.

## Build (na DEV .61, bez lokalnego node)

```bash
cd /home/piotrszmidt/ai-gm/frontend/front-v2
docker run --rm -v "$PWD":/app -w /app node:20-alpine sh -lc 'npm install && npm run build'
```

Podgląd: `https://aigm-dev.studio-colorbox.com/v2/`

## Struktura

- `src/components/ui/` — komponenty bazowe (Button, Input, Sheet, Dialog, Card, Badge,
  ProgressBar, Avatar, Toast, Tabs)
- `src/components/shell/` — Topbar, TabBar, Breadcrumb, AppShell
- `src/routes/` — router (lazy per trasa) + `pages/` (placeholdery ekranów F-NN)
- `src/store/appStore.ts` — Zustand (client-state, sekcja 8)
- `src/lib/queryClient.ts` — TanStack Query
- `src/index.css` — tokeny ŻAR (`:root`), `tailwind.config.js` mapuje je na theme
