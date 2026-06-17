#!/usr/bin/env python3
"""
L16 — Batch dungeon tile description generator (Polish room descriptions via LLM).

Calls POST /admin/dungeon-tiles/{id}/generate-description for each tile in a category.
Skips tiles that already have a room_description (unless --force).

Usage:
  python3 scripts/generate_descriptions_batch.py --category jaskinie
  python3 scripts/generate_descriptions_batch.py --category jaskinie --force
  python3 scripts/generate_descriptions_batch.py --category jaskinie --limit 5 --dry-run

Options:
  --category KEY  Filter tiles by category key (required)
  --limit N       Max tiles to process (default: all)
  --force         Re-generate even if tile already has a description
  --dry-run       Print what would be done, no generation
  --api-url URL   DEV API base (default: https://aigm-dev.studio-colorbox.com)
  --delay S       Seconds to wait between tiles (default: 1.0)
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_API_URL = "https://aigm-dev.studio-colorbox.com"
ADMIN_USER = "demo"
ADMIN_PASS = "demo"
DEFAULT_DELAY = 1.0
MAX_RETRIES = 2


def get_admin_token(api_url: str) -> str:
    payload = json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode()
    req = urllib.request.Request(
        f"{api_url}/api/admin/dev-login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["token"]


def fetch_tiles(api_url: str, token: str, category: str) -> list[dict]:
    url = f"{api_url}/api/admin/dungeon-tiles?category={category}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    tiles = data.get("tiles", [])
    return [t for t in tiles if t.get("category_key") == category]


def generate_description(api_url: str, token: str, tile_id: int) -> str | None:
    url = f"{api_url}/api/admin/dungeon-tiles/{tile_id}/generate-description"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                return result.get("room_description", "")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            if attempt < MAX_RETRIES:
                print(f"         HTTP {e.code} — retry {attempt+1}/{MAX_RETRIES}")
                time.sleep(3)
            else:
                print(f"         FAIL HTTP {e.code}: {body}")
                return None
        except Exception as exc:
            if attempt < MAX_RETRIES:
                print(f"         Error {exc} — retry {attempt+1}/{MAX_RETRIES}")
                time.sleep(3)
            else:
                print(f"         FAIL: {exc}")
                return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch tile description generator")
    ap.add_argument("--category", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--api-url", default=DEFAULT_API_URL)
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    args = ap.parse_args()

    print("L16 Tile Description Batch Generator")
    print(f"  category : {args.category}")
    print(f"  limit    : {args.limit or 'all'}")
    print(f"  force    : {args.force}")
    print(f"  dry-run  : {args.dry_run}")
    print(f"  api-url  : {args.api_url}")
    print()

    token = get_admin_token(args.api_url)
    print("Authenticated as admin.")

    tiles = fetch_tiles(args.api_url, token, args.category)
    print(f"Found {len(tiles)} tile(s) in category '{args.category}'.")

    if not args.force:
        to_process = [t for t in tiles if not (t.get("room_description") or "").strip()]
    else:
        to_process = tiles

    already = len(tiles) - len(to_process)
    if args.limit:
        to_process = to_process[:args.limit]

    print(f"  {already} already have descriptions, {len(to_process)} to generate "
          f"(limit={args.limit or 'none'}, force={args.force})")
    print()

    ok = errors = skipped = 0
    for i, tile in enumerate(to_process, 1):
        tid = tile["id"]
        label = tile.get("label", f"#{tid}")
        has = bool((tile.get("room_description") or "").strip())
        tag = "[FORCE]" if has else "[NEW]"

        print(f"[{i}/{len(to_process)}]")
        print(f"  {tag} #{tid} {label}")

        if args.dry_run:
            print(f"         (dry-run, skip)")
            skipped += 1
            continue

        desc = generate_description(args.api_url, token, tid)
        if desc:
            preview = desc[:80].replace("\n", " ")
            print(f"         ✓ \"{preview}...\"")
            ok += 1
        else:
            errors += 1

        if i < len(to_process):
            time.sleep(args.delay)

    print(f"\nDone. OK={ok}  errors={errors}  skipped={skipped}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
