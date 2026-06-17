#!/usr/bin/env python3
"""
L20a — Batch portrait generator for enemies and NPCs.

Calls POST /api/admin/images/generate then PATCH image_url on each entity.
Skips entities that already have an image_url (unless --force).

Run from repo root on any machine with network access to DEV API.

Usage:
  python3 scripts/generate_portraits_batch.py --entity enemy
  python3 scripts/generate_portraits_batch.py --entity npc
  python3 scripts/generate_portraits_batch.py --entity enemy --keys skeleton,vampire_master
  python3 scripts/generate_portraits_batch.py --entity enemy --limit 5 --dry-run
  python3 scripts/generate_portraits_batch.py --entity enemy --force --steps 8

Options:
  --entity enemy|npc   Which table to target (required)
  --keys KEY1,KEY2     Comma-separated keys/IDs to process (default: all)
  --limit N            Max entities to process (default: all)
  --steps N            FLUX generation steps (default: 8; higher = more detail)
  --force              Re-generate even if entity already has image_url
  --dry-run            Print plan, no generation
  --api-url URL        DEV API base (default: https://aigm-dev.studio-colorbox.com)
  --delay S            Seconds between entities (default: 2.0)
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
DEFAULT_DELAY = 2.0
MAX_RETRIES = 2
PORTRAIT_WIDTH = 576
PORTRAIT_HEIGHT = 1024

BASE_PROMPT = (
    "dark fantasy portrait, bust shot facing viewer, dramatic lighting, "
    "detailed face, no text, no UI, no borders, oil painting style"
)


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


def fetch_enemies(api_url: str, token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{api_url}/api/admin/enemies",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("items", [])


def fetch_npcs(api_url: str, token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{api_url}/api/admin/npcs",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("items", [])


def generate_image(prompt: str, api_url: str, token: str, steps: int) -> dict:
    payload = json.dumps({
        "prompt": prompt,
        "steps": steps,
        "width": PORTRAIT_WIDTH,
        "height": PORTRAIT_HEIGHT,
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/api/admin/images/generate",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def patch_enemy_image(key: str, image_url: str, image_url_raw: str,
                      api_url: str, token: str) -> None:
    payload = json.dumps({
        "image_url": image_url,
        "image_url_raw": image_url_raw,
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/api/admin/enemies/{key}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def patch_npc_image(npc_id: int, image_url: str, image_url_raw: str,
                    api_url: str, token: str) -> None:
    payload = json.dumps({
        "image_url": image_url,
        "image_url_raw": image_url_raw,
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/api/admin/npcs/{npc_id}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def build_prompt(entity: dict) -> str:
    custom = entity.get("image_gen_prompt", "").strip()
    if custom:
        return custom
    label = entity.get("label", entity.get("key", "creature"))
    desc = (entity.get("description") or "").strip()
    parts = [label]
    if desc:
        parts.append(desc[:120])
    return f"{', '.join(parts)}, {BASE_PROMPT}"


def process_entity(entity: dict, entity_type: str, api_url: str, token: str,
                   steps: int, force: bool, dry_run: bool) -> bool:
    key = entity.get("key") or str(entity.get("id", "?"))
    label = entity.get("label", key)
    has_image = bool(entity.get("image_url"))

    if has_image and not force:
        print(f"  [SKIP] {key} — already has image_url (use --force to regenerate)")
        return False

    status = "FORCE" if has_image else "NEW"
    prompt = build_prompt(entity)
    print(f"  [{status}] {key} — {label}")
    print(f"         prompt: {prompt[:80]}...")

    if dry_run:
        print(f"         DRY-RUN: would generate {PORTRAIT_WIDTH}×{PORTRAIT_HEIGHT}, steps={steps}")
        return True

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            result = generate_image(prompt, api_url, token, steps)
            img_url = result.get("image_url") or result.get("url")
            img_raw = result.get("image_url_raw") or result.get("raw_url") or img_url
            if not img_url:
                print(f"         ✗ no image_url in response: {result}")
                return False
            # save back
            if entity_type == "enemy":
                patch_enemy_image(key, img_url, img_raw or img_url, api_url, token)
            else:
                patch_npc_image(int(entity["id"]), img_url, img_raw or img_url, api_url, token)
            print(f"         ✓ {img_url}")
            return True
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
    parser = argparse.ArgumentParser(description="L20a — Batch portrait generator")
    parser.add_argument("--entity", required=True, choices=["enemy", "npc"],
                        help="Entity type: enemy or npc")
    parser.add_argument("--keys", default=None,
                        help="Comma-separated keys (enemies) or IDs (NPCs) to process")
    parser.add_argument("--limit", type=int, default=None, help="Max entities to process")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="FLUX steps")
    parser.add_argument("--force", action="store_true", help="Regenerate entities with existing images")
    parser.add_argument("--dry-run", action="store_true", help="No generation, just show plan")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="DEV API base URL")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="Seconds between entities (default 2.0)")
    args = parser.parse_args()

    print(f"L20a Portrait Batch Generator")
    print(f"  entity   : {args.entity}")
    print(f"  keys     : {args.keys or 'all'}")
    print(f"  steps    : {args.steps}")
    print(f"  size     : {PORTRAIT_WIDTH}×{PORTRAIT_HEIGHT}")
    print(f"  limit    : {args.limit or 'all'}")
    print(f"  force    : {args.force}")
    print(f"  dry-run  : {args.dry_run}")
    print(f"  api-url  : {args.api_url}")
    print()

    token = get_admin_token(args.api_url)
    print("Authenticated as admin.")

    if args.entity == "enemy":
        entities = fetch_enemies(args.api_url, token)
    else:
        entities = fetch_npcs(args.api_url, token)

    print(f"Found {len(entities)} {args.entity}(ies).")

    if args.keys:
        filter_keys = {k.strip() for k in args.keys.split(",")}
        if args.entity == "enemy":
            entities = [e for e in entities if e.get("key") in filter_keys]
        else:
            entities = [e for e in entities
                        if str(e.get("id")) in filter_keys or e.get("key") in filter_keys]
        print(f"Filtered to {len(entities)} by --keys.")

    to_process = [e for e in entities if args.force or not e.get("image_url")]
    if args.limit:
        to_process = to_process[:args.limit]

    already = sum(1 for e in entities if e.get("image_url"))
    print(f"  {already} already have images, {len(to_process)} to generate "
          f"(limit={args.limit or 'none'}, force={args.force})")
    print()

    ok = err = 0
    for i, entity in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}]")
        result = process_entity(entity, args.entity, args.api_url, token,
                                args.steps, args.force, args.dry_run)
        if result:
            ok += 1
        else:
            err += 1
        if i < len(to_process) and not args.dry_run:
            time.sleep(args.delay)

    print()
    print(f"Done. OK={ok}  errors={err}")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
