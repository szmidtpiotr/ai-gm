#!/usr/bin/env bash
# Port GENERIC archmap changes from this AI-GM instance up to the reusable kit repo
# (github.com/szmidtpiotr/archmap). Mechanical for the engine + render shell; project
# DATA (node-map.json, heat-source.json, map-overlay.json, and the clusters/nodes/edges/
# FINDINGS arrays of architecture-map.html) is NEVER ported.
#
#   ./sync_to_kit.sh            # clone kit, copy generic parts, show git diff (no push)
#   ./sync_to_kit.sh --push     # also commit + push the kit
#
# Run on a host with `gh`/git auth to szmidtpiotr/archmap (.19 or .61).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KIT_REMOTE="https://github.com/szmidtpiotr/archmap.git"
KIT="${ARCHMAP_KIT_DIR:-/tmp/archmap-kit}"
PUSH="${1:-}"

# 1) fresh kit clone (or pull)
if [ -d "$KIT/.git" ]; then git -C "$KIT" pull -q; else rm -rf "$KIT"; git clone -q "$KIT_REMOTE" "$KIT"; fi

# 2) ENGINE (generic scripts) -> kit/engine/   (AI-GM keeps them under overlay/)
cp "$HERE/overlay/update_overlay.py" "$HERE/overlay/update_heat.py" \
   "$HERE/overlay/drift_check.py"    "$HERE/overlay/refresh.sh"      "$KIT/engine/"

# 3) RENDER SHELL -> kit/template/architecture-map.html
#    Strip THIS project's data arrays, leave the generic 3-node EDIT-ME placeholder.
python3 - "$HERE/architecture-map.html" "$KIT/template/architecture-map.html" << 'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding='utf-8').read()
def repl(s, a, b, new):
    i = s.index(a); j = s.index(b, i); return s[:i] + new + s[j:]
clusters = """const clusters = [
  // EDIT: one column box per cluster. Pick clusters that match the codebase.
  { id:'entry', label:'Entry / Routes', x:40,  y:80, w:240, h:420, color:'route' },
  { id:'core',  label:'Core / Services', x:340, y:80, w:240, h:420, color:'critical' },
  { id:'data',  label:'Data / External', x:640, y:80, w:240, h:420, color:'db' },
];

"""
nodes = """const nodes = [
  // EDIT: one node per significant file/function/table. Mark the spine critical:true,
  // surface dead code with dead:true. path+role+plain+notes+tag are required.
  N('entry-main','entry','app/main.py','entry point', 60,120,200,56,'route',{
    role:'Application entry / router wiring.',
    plain:'Where the app starts and requests come in.',
    path:'REPLACE/with/real/path.py:1',
    notes:['REPLACE with real line:note'], tag:['overview','all'], critical:true }),
  N('core-svc','core','service.py','core logic', 360,120,200,56,'critical',{
    role:'The seam — the most important code path.',
    plain:'The heart of the feature being mapped.',
    path:'REPLACE/with/real/path.py:1',
    notes:['REPLACE'], tag:['overview','all'], critical:true }),
  N('data-db','data','table / api','data sink', 660,120,200,50,'db',{
    role:'Where state is read/written or an external call goes.',
    plain:'The database or outside service the logic talks to.',
    path:'REPLACE',
    notes:['REPLACE'], tag:['overview','all'] }),
];

"""
edges = """const edges = [
  // EDIT: label every edge with what flows; kind = critical|api|db|mount|normal
  { from:'entry-main', to:'core-svc', kind:'critical', label:'1 · handle', tag:['overview','all'] },
  { from:'core-svc',   to:'data-db',  kind:'db',       label:'read/write', tag:['overview','all'] },
];

"""
findings = """const FINDINGS = [
  ['EDIT','Replace these with real findings from the codebase you mapped.'],
];

"""
h = repl(h, 'const clusters = [', 'const N = (', clusters)
h = repl(h, 'const nodes = [', 'const edges = [', nodes)
h = repl(h, 'const edges = [', '/* Overlay registries', edges)
h = repl(h, 'const FINDINGS = [', '/* ============================ RENDER', findings)
import re
h = re.sub(r'<title>.*?</title>', '<title>Architecture map — template</title>', h, count=1)
h = re.sub(r'AI-GM [^<]*Combat \(pilot\)', 'PROJECT · architecture map (template)', h)
open(dst, 'w', encoding='utf-8').write(h)
print('template render shell regenerated from AI-GM html')
PY

# 4) scrub any LAN host that slipped into copied generic files (engine has none, but be safe)
{ grep -rlE '192\.168\.[0-9.]+|claude@' "$KIT/engine" "$KIT/template" 2>/dev/null || true; } | while read -r f; do
  [ -n "$f" ] && sed -i -E 's#192\.168\.[0-9.]+#<dev-host>#g; s#claude@#<user>@#g' "$f"
done

echo "== generic changes staged into $KIT =="
git -C "$KIT" --no-pager status --short
git -C "$KIT" --no-pager diff --stat || true

if [ "$PUSH" = "--push" ]; then
  git -C "$KIT" add -A
  if git -C "$KIT" diff --cached --quiet; then echo "nothing to port."; exit 0; fi
  git -C "$KIT" -c commit.gpgsign=false commit -q -m "sync: port engine/render updates from AI-GM instance

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
  git -C "$KIT" push -q origin master
  echo "pushed to kit (master)."
else
  echo
  echo "review above. Re-run with --push to commit+push the kit."
fi
