#!/usr/bin/env python3
"""
E19 — LLM Vision: dungeon tile image → Polish room description.

Runs on machine .170 (has llava:7b via Ollama + network access to DEV API).

Usage:
  python3 scripts/vision_describe_tiles.py
  python3 scripts/vision_describe_tiles.py --tile-id 3
  python3 scripts/vision_describe_tiles.py --all --force
  python3 scripts/vision_describe_tiles.py --dry-run

Options:
  --tile-id N     Process single tile by ID
  --all           Process all tiles with images (skips tiles already described)
  --force         Re-describe even if room_description is already filled
  --dry-run       Print what would be done, don't update DB
  --model M       Ollama model to use (default: llava:7b)
  --ollama-url U  Ollama base URL (default: http://localhost:11434)
  --api-url U     AI-GM DEV API base URL (default: https://aigm-dev.studio-colorbox.com)
"""
import argparse
import base64
import json
import sys
import urllib.request
import urllib.error


# ─── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_API_URL = "https://aigm-dev.studio-colorbox.com"
DEFAULT_MODEL = "llava:7b"
ADMIN_USER = "demo"
ADMIN_PASS = "demo"


# ─── Auth ─────────────────────────────────────────────────────────────────────

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


# ─── Tile list ────────────────────────────────────────────────────────────────

def fetch_tiles(api_url: str, token: str, needs_description: bool = True) -> list[dict]:
    """Fetch dungeon tiles from admin API."""
    url = f"{api_url}/api/admin/dungeon-tiles"
    if needs_description:
        url += "?needs_description=1"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("tiles", [])


def fetch_all_tiles(api_url: str, token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{api_url}/api/admin/dungeon-tiles",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("tiles", [])


# ─── Image download ───────────────────────────────────────────────────────────

def download_image(image_path: str, api_url: str) -> bytes:
    """Download tile image by its relative path (/images/tiles/...)."""
    if image_path.startswith("http"):
        url = image_path
    else:
        url = api_url.rstrip("/") + image_path
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


# ─── Vision ───────────────────────────────────────────────────────────────────

def build_vision_prompt(tile: dict) -> str:
    label = tile.get("label") or "Nieznane pomieszczenie"
    category = tile.get("category_key") or "dungeon"
    return (
        f"Jesteś asystentem GM do gry RPG fantasy. Opisz to pomieszczenie po polsku.\n"
        f"Kafelek: {label} (kategoria: {category})\n\n"
        "Wygeneruj zwięzły opis atmosfery tego wnętrza (2-4 zdania). Opisz:\n"
        "- Co widać w pomieszczeniu (meble, przedmioty, materiały, stan)\n"
        "- Atmosferę i klimat (światło, zapachy, odgłosy)\n"
        "- Czy widoczne są wyjścia/przejścia i gdzie\n\n"
        "Odpowiedz TYLKO opisem, bez nagłówków i wstępu."
    )


def describe_tile(image_bytes: bytes, ollama_url: str, model: str = DEFAULT_MODEL) -> str:
    """Send image to Ollama vision model, return Polish description."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = json.dumps({
        "model": model,
        "prompt": (
            "Opisz po polsku to pomieszczenie w lochu RPG. "
            "Podaj 2-4 zdania o atmosferze, wyglądzie, oświetleniu i klimacie. "
            "Odpowiedz TYLKO opisem, bez wstępu."
        ),
        "images": [image_b64],
        "stream": False,
    }).encode("utf-8")
    url = ollama_url.rstrip("/") + "/api/generate"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result.get("response", "").strip()


# ─── Update ───────────────────────────────────────────────────────────────────

def update_tile_description(tile_id: int, description: str, api_url: str, token: str) -> None:
    payload = json.dumps({"room_description": description}).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url}/api/admin/dungeon-tiles/{tile_id}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        raise RuntimeError(f"PATCH tile {tile_id} failed: {result}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def process_tile(tile: dict, ollama_url: str, model: str, api_url: str, token: str, dry_run: bool) -> bool:
    tile_id = tile["id"]
    label = tile.get("label", f"tile_{tile_id}")
    image_url = tile.get("image_url_raw") or tile.get("image_url") or ""

    if not image_url:
        print(f"  [SKIP] tile {tile_id} ({label}) — no image_url")
        return False

    print(f"  [→] tile {tile_id} ({label}) image: {image_url}")

    if dry_run:
        print(f"  [DRY] would call Ollama vision on {image_url}")
        return True

    try:
        image_bytes = download_image(image_url, api_url)
    except Exception as e:
        print(f"  [ERR] download failed: {e}")
        return False

    try:
        description = describe_tile(image_bytes, ollama_url, model)
    except Exception as e:
        print(f"  [ERR] vision failed: {e}")
        return False

    if not description:
        print(f"  [ERR] empty description returned")
        return False

    try:
        update_tile_description(tile_id, description, api_url, token)
    except Exception as e:
        print(f"  [ERR] update failed: {e}")
        return False

    print(f"  [OK] saved: {description[:80]}...")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="E19 — Dungeon tile vision describer")
    parser.add_argument("--tile-id", type=int, help="Process single tile by ID")
    parser.add_argument("--all", action="store_true", help="Process all tiles with images")
    parser.add_argument("--force", action="store_true", help="Re-describe even if description exists")
    parser.add_argument("--dry-run", action="store_true", help="Don't update DB")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args()

    print(f"E19 Vision Describer — model={args.model} ollama={args.ollama_url}")
    print(f"DEV API: {args.api_url}")

    token = get_admin_token(args.api_url)
    print("Authenticated as admin.")

    if args.tile_id:
        # Single tile mode
        all_tiles = fetch_all_tiles(args.api_url, token)
        tiles = [t for t in all_tiles if t["id"] == args.tile_id]
        if not tiles:
            print(f"Tile {args.tile_id} not found.")
            sys.exit(1)
    elif args.force:
        tiles = fetch_all_tiles(args.api_url, token)
    else:
        # Default: only tiles missing description
        tiles = fetch_tiles(args.api_url, token, needs_description=True)

    # Filter to only tiles with images
    tiles_with_images = [t for t in tiles if t.get("image_url") or t.get("image_url_raw")]
    print(f"Found {len(tiles_with_images)} tile(s) to process.")

    ok = err = skip = 0
    for tile in tiles_with_images:
        result = process_tile(tile, args.ollama_url, args.model, args.api_url, token, args.dry_run)
        if result:
            ok += 1
        else:
            skip += 1 if not tile.get("image_url") else 0
            err += 1 if tile.get("image_url") else 0

    print(f"\nDone. OK={ok}  errors={err}  skipped={skip}")


if __name__ == "__main__":
    main()
