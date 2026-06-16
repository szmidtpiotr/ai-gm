#!/usr/bin/env python3
"""
L15 — Batch dungeon tile image generator.

Calls POST /admin/dungeon-tiles/{id}/generate-image for each tile in a category.
Skips tiles that already have an image_url (unless --force).

Run from repo root on any machine with network access to DEV API.

Usage:
  python3 scripts/generate_tiles_batch.py --category krypta --limit 5
  python3 scripts/generate_tiles_batch.py --category krypta --dry-run
  python3 scripts/generate_tiles_batch.py --category krypta --force --steps 8
  python3 scripts/generate_tiles_batch.py --category krypta --limit 20 --steps 8

Options:
  --category KEY  Filter tiles by category key (required)
  --limit N       Max tiles to process (default: all)
  --steps N       FLUX generation steps (default: 8; higher = more detail, slower)
  --size N        Image size in pixels, square (default: 768)
  --force         Re-generate even if tile already has an image
  --dry-run       Print what would be done, no generation
  --api-url URL   DEV API base (default: https://aigm-dev.studio-colorbox.com)
  --delay S       Seconds to wait between tiles (default: 2.0)
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
DEFAULT_STEPS = 8
DEFAULT_SIZE = 768
DEFAULT_DELAY = 2.0
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


def generate_image(tile_id: int, api_url: str, token: str,
                   steps: int, size: int) -> dict:
    payload = json.dumps({"steps": steps, "width": size, "height": size}).encode()
    req = urllib.request.Request(
        f"{api_url}/api/admin/dungeon-tiles/{tile_id}/generate-image",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def process_tile(tile: dict, api_url: str, token: str,
                 steps: int, size: int, force: bool, dry_run: bool) -> bool:
    tile_id = tile["id"]
    label = tile.get("label", f"tile_{tile_id}")
    has_image = bool(tile.get("image_url"))

    if has_image and not force:
        print(f"  [SKIP] #{tile_id} {label} — already has image (use --force to regenerate)")
        return False

    status = "FORCE" if has_image else "NEW"
    print(f"  [{status}] #{tile_id} {label}")
    if dry_run:
        print(f"         DRY-RUN: would call generate-image (steps={steps}, size={size})")
        return True

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            result = generate_image(tile_id, api_url, token, steps, size)
            if result.get("ok"):
                print(f"         ✓ {result.get('image_url', '?')}")
                return True
            else:
                print(f"         ✗ API returned not-ok: {result}")
                return False
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"         HTTP {e.code}: {body}")
            if attempt <= MAX_RETRIES:
                print(f"         retry {attempt}/{MAX_RETRIES}...")
                time.sleep(5)
            else:
                return False
        except Exception as e:
            print(f"         error: {e}")
            if attempt <= MAX_RETRIES:
                print(f"         retry {attempt}/{MAX_RETRIES}...")
                time.sleep(5)
            else:
                return False
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="L15 — Batch tile image generator")
    parser.add_argument("--category", required=True, help="Tile category key")
    parser.add_argument("--limit", type=int, default=None, help="Max tiles to process")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="FLUX steps")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Image size px (square)")
    parser.add_argument("--force", action="store_true", help="Regenerate tiles with existing images")
    parser.add_argument("--dry-run", action="store_true", help="No generation, just show plan")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="DEV API base URL")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="Seconds between tiles (default 2.0)")
    args = parser.parse_args()

    print(f"L15 Tile Batch Generator")
    print(f"  category : {args.category}")
    print(f"  steps    : {args.steps}")
    print(f"  size     : {args.size}px")
    print(f"  limit    : {args.limit or 'all'}")
    print(f"  force    : {args.force}")
    print(f"  dry-run  : {args.dry_run}")
    print(f"  api-url  : {args.api_url}")
    print()

    token = get_admin_token(args.api_url)
    print("Authenticated as admin.")

    tiles = fetch_tiles(args.api_url, token, args.category)
    print(f"Found {len(tiles)} tile(s) in category '{args.category}'.")

    to_process = [t for t in tiles if args.force or not t.get("image_url")]
    if args.limit:
        to_process = to_process[:args.limit]

    already = len(tiles) - len([t for t in tiles if not t.get("image_url")])
    print(f"  {already} already have images, {len(to_process)} to generate "
          f"(limit={args.limit or 'none'}, force={args.force})")
    print()

    ok = err = skip = 0
    for i, tile in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}]")
        result = process_tile(tile, args.api_url, token,
                              args.steps, args.size, args.force, args.dry_run)
        if result:
            ok += 1
        else:
            has_image = bool(tile.get("image_url"))
            if has_image and not args.force:
                skip += 1
            else:
                err += 1

        if i < len(to_process) and not args.dry_run:
            time.sleep(args.delay)

    print()
    print(f"Done. OK={ok}  errors={err}  skipped={skip}")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
