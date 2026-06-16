"""Generate Polish room descriptions for dungeon tiles via admin API.

Run on the Claude VM (not inside container) — calls the DEV API endpoint.

Usage:
  python3 generate_tile_descriptions.py [--category krypta] [--tile-ids 6,7,8]

Calls POST /api/admin/dungeon-tiles/{id}/generate-description for each tile.
Skips tiles that already have a room_description unless --force is set.
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "https://aigm-dev.studio-colorbox.com"
ADMIN_USER = "demo"
ADMIN_PASS = "demo"


def get_token() -> str:
    data = json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/admin/dev-login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def list_tiles(token: str, category: str | None, needs_description: bool) -> list[dict]:
    params = ""
    if category:
        params += f"?category={category}"
    if needs_description:
        params += ("&" if params else "?") + "needs_description=1"
    req = urllib.request.Request(
        f"{BASE_URL}/api/admin/dungeon-tiles{params}",
        headers=_auth_headers(token),
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return data.get("tiles", data) if isinstance(data, dict) else data


def generate_description(token: str, tile_id: int) -> str:
    headers = {**_auth_headers(token), "Content-Type": "application/json"}
    req = urllib.request.Request(
        f"{BASE_URL}/api/admin/dungeon-tiles/{tile_id}/generate-description",
        data=b"",
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read()).get("room_description", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="krypta")
    parser.add_argument("--tile-ids", help="Comma-separated ids, overrides --category")
    parser.add_argument("--force", action="store_true", help="Regenerate even if description exists")
    args = parser.parse_args()

    print("Getting admin token...")
    token = get_token()
    print("Token OK.")

    if args.tile_ids:
        tile_ids = [int(x.strip()) for x in args.tile_ids.split(",")]
        tiles = [{"id": tid, "label": f"tile_{tid}", "room_description": None} for tid in tile_ids]
    else:
        print(f"Listing tiles for category '{args.category}'...")
        tiles = list_tiles(token, args.category, needs_description=not args.force)
        print(f"Found {len(tiles)} tiles needing descriptions.")

    ok = 0
    skip = 0
    fail = 0
    for tile in tiles:
        tid = tile["id"]
        label = tile.get("label", tile.get("tile_name", str(tid)))
        existing = tile.get("room_description") or ""
        if existing.strip() and not args.force:
            print(f"[SKIP] id={tid} '{label}' — already has description")
            skip += 1
            continue

        print(f"[GEN]  id={tid} '{label}'...", end=" ", flush=True)
        try:
            desc = generate_description(token, tid)
            print(f"OK ({len(desc)} chars)")
            ok += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            print(f"FAIL {e.code}: {body}")
            fail += 1
        except Exception as exc:
            print(f"FAIL: {exc}")
            fail += 1

        time.sleep(0.5)

    print(f"\nDone: {ok} generated, {skip} skipped, {fail} failed.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
