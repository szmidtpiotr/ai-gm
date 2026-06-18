#!/usr/bin/env bash
# Renumber the task lines in the "## KOLEJNOŚĆ IMPLEMENTACJI" region of fix_list.md
# with a stable global index (1..n) in document order, e.g.:
#   - [ ] 1. #767 — ...
#   - [x] 2. #743 — ...
# Indices are stable across [x]/[ ] state (checked tasks still consume a number) so
# that "/mass-implement fix_list.md N-M" ranges don't shift as work gets done.
#
# Only the KOLEJNOŚĆ region is touched — the auto-generated BOARD-TODO block and the
# Log zmian section are left as-is. Idempotent: re-stamps existing numbers.
#
# Usage: renumber_fix_list.sh [path-to-fix_list.md]   (default: repo-root/fix_list.md)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX_LIST="${1:-$HERE/fix_list.md}"
[ -f "$FIX_LIST" ] || { echo "FATAL: brak $FIX_LIST" >&2; exit 2; }

tmp="$(mktemp)"
awk '
  /^## KOLEJNOŚĆ/                  { reg=1 }
  reg && /^## / && !/KOLEJNOŚĆ/    { reg=0 }
  {
    if (reg && $0 ~ /^- \[[ xX]\] /) {
      n++
      cb   = substr($0, 1, 6)          # "- [ ] " / "- [x] "
      rest = substr($0, 7)
      sub(/^[0-9]+\. +/, "", rest)      # strip any existing index
      print cb n ". " rest
      next
    }
    print
  }
' "$FIX_LIST" > "$tmp"

cat "$tmp" > "$FIX_LIST" && rm -f "$tmp"   # cat (not mv) — sshfs uid mismatch breaks mv ownership
chmod 664 "$FIX_LIST" 2>/dev/null || true
echo "Renumbered KOLEJNOŚĆ region in $FIX_LIST" >&2
