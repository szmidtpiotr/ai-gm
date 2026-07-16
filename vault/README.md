# Vault AI-GM — notatnik projektowy Piotra

Ten folder to vault Obsidiana. Leży w repo (`ai-gm/vault/`), więc:
- **Piotr** edytuje go w Obsidianie na desktopie (przez mount `~/remout_mount/ai-gm/vault`)
- **Claude (agent)** czyta i pisze te same pliki w każdej sesji
- wszystko jest wersjonowane w git razem z projektem

## Struktura

| Folder | Do czego |
|---|---|
| `00-inbox/` | Szybkie wrzutki — pomysł w biegu, jedno zdanie wystarczy. Agent regularnie przegląda i porządkuje. |
| `10-pomysly/` | Dopracowane pomysły na funkcje / zmiany w grze |
| `20-mechaniki/` | Szkice mechanik (walka, skille, ekonomia...) — projektowanie PRZED wdrożeniem |
| `30-lore/` | Szkice świata Kresów — lokacje, frakcje, NPC, historia |
| `40-canvas/` | Tablice wizualne Obsidiana (.canvas) — planowanie faz, mapy powiązań |
| `90-archiwum/` | Notatki przetworzone / wdrożone — przenoszone tu po zakończeniu |
| `_szablony/` | Szablony notatek (Obsidian → Templates) |

## Konwencja statusów (umowa Piotr ↔ agent)

Każda notatka ma nagłówek (frontmatter) ze statusem:

```
---
typ: pomysl
status: szkic
---
```

| Status | Znaczenie |
|---|---|
| `szkic` | Piotr jeszcze myśli — agent NIE rusza |
| `do-omowienia` | Piotr chce przegadać z agentem w sesji |
| `do-wdrozenia` | Zielone światło — agent może wziąć do implementacji (utworzy issue na GitHubie) |
| `wdrozone` | Zrobione — agent dopisuje link do issue/commita i przenosi do archiwum |

## Czego tu NIE trzymamy

- **Zadań/tasków** — źródłem prawdy pozostaje GitHub Issues
- **Kanonu mechanik** — to `game_mechanics.md` + `backend/prompts/system_prompt.txt` (vault to szkicownik, nie kanon)
- **Kanonu lore** — to `docs/world/LORE_v1_KANON.md`

Notatka w vaulcie → dyskusja → wdrożenie → aktualizacja dokumentów kanonicznych przez agenta.

## Dokumenty kanoniczne (poza vaultem, w repo wyżej)

- [Mechaniki gry](../game_mechanics.md)
- [Pomysły / backlog historyczny](../to_do_ideas.md)
- [Design frontendu](../frontend_design.md)
- [Status projektu](../STATUS.md)
