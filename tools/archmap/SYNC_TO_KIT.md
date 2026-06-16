# Porting AI-GM archmap changes up to the kit

When you improve archmap **functionality** here (in AI-GM) and want it in the reusable kit
(github.com/szmidtpiotr/archmap), so other projects get it too.

## The phrase to write

> **„przenieś zmiany archmap do kitu"**  (lub: *"port archmap changes to the kit"*)

That triggers this procedure. For the mechanical 90% just run the helper:

```bash
cd tools/archmap
./sync_to_kit.sh            # clone kit, copy generic parts, SHOW diff (no push)
./sync_to_kit.sh --push     # also commit + push the kit (master)
```

## What is GENERIC (gets ported) vs DATA (never)

| File | Generic? | Ported how |
|---|---|---|
| `overlay/update_overlay.py`, `update_heat.py`, `drift_check.py`, `refresh.sh` | ✅ engine | copied verbatim → kit `engine/` |
| render shell of `architecture-map.html` (SVG, pan/zoom, sidebar, filter bar, issue popup, drag, overlay loader) | ✅ render | regenerated → kit `template/architecture-map.html` (data arrays stripped to placeholder) |
| `SKILL.md` / method changes | ✅ skill | edit kit `SKILL.md` by hand |
| `architecture-map.html` **data arrays** (`clusters`/`nodes`/`edges`/`FINDINGS`) | ❌ DATA | never — project-specific |
| `overlay/node-map.json`, `heat-source.json`, `map-overlay.json` | ❌ DATA | never — project-specific |

The helper handles engine + render shell automatically. It strips AI-GM's nodes/edges and
leaves the kit's generic EDIT-ME placeholder, so no AI-GM data leaks into the public kit.
It also scrubs any LAN host (`192.168.x` / `user@`) from copied files.

## When the change is SKILL/method only

Edit `SKILL.md` in the kit directly (not auto-ported) — `sync_to_kit.sh` doesn't touch it.

## After porting

Bump a one-line note in the kit's `README.md` if it's a notable feature, so projects know a
newer shell exists (kit `UPDATING.md` Flow 2 covers pulling it back into other projects).
