# Auto-sync fix_list.md ↔ kolumna TO DO (ClaudeCodeUI Issues Board)

Board to kanban pluginu ClaudeCodeUI liczony z LABELI issue (nie GitHub Projects).
Reguła kolumn (z `github-issues.service.js`):
- **To Do**       = issue `open` BEZ labeli `in-progress` / `review` / `blocked`
- **In Progress** = `open` + label `in-progress`
- **In Review**   = `open` + label `review`
- **Blocked**     = `open` + label `blocked`
- **Done**        = `closed`

Czyli kolumnę TO DO odtwarza zwykły `gh issue list` — wystarcza scope `repo`.
Żaden token / `read:project` / Projects API NIE jest potrzebny.

## Użycie
```
bash scripts/sync_fix_list_from_board.sh
```
Wypełnia blok `<!-- BOARD-TODO -->` w fix_list.md aktualną kolumną TO DO (idempotentne).

Uruchamiaj na żądanie (albo poproś agenta o „zsynchronizuj fix_list"). Przeniesienie issue
do innej kolumny = zmiana labela (`gh issue edit #N --add-label in-progress` itd.).
