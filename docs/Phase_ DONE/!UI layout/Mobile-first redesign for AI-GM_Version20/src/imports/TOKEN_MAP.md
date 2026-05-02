# TOKEN_MAP

Mapowanie tokenow Figma na aktualne zmienne CSS.

| Figma token (proposed) | CSS variable (current) | Notes |
|---|---|---|
| `surface/app` | `--bg` | tlo calej aplikacji |
| `surface/panel` | `--panel` | glowny panel |
| `surface/panel-alt` | `--panel-2` | panel pomocniczy |
| `text/primary` | `--text` | glowny tekst |
| `text/muted` | `--muted` | opisy/pomocnicze |
| `accent/primary` | `--accent` | CTA i highlight |
| `accent/secondary` | `--accent-light` | hover/secondary |
| `status/danger` | `--danger` | delete/error |
| `status/warning` | `--warning` | warning |
| `status/success` | `--ok` | success/ok |
| `border/default` | `--border` | obrysy paneli |
| `radius/default` | `--radius` | promienie |
| `shadow/default` | `--shadow` | cienie |
| `chat/user-bg` | `--user` | dymek user |
| `chat/assistant-bg` | `--assistant` | dymek AI |
| `chat/system-bg` | `--system` | dymek system |

## Recommendation

Najpierw utrzymac obecne aliasy CSS, potem ewentualnie migrowac do nowych nazw semantycznych.
