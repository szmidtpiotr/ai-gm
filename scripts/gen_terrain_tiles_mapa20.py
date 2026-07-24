#!/usr/bin/env python3
"""Mapa 2.0 (#1543 M-2b) — generate the terrain tiles still missing for the
Czarnobór + Kresy makieta comparison.

Same FLUX.1-schnell service + style as scripts/gen_terrain_tiles.py (SG-1), so
the new tiles sit visually next to czarny_las/step/trzesawisko/las_iglasty/etc.

Writes ONE variant per type straight into frontend/images/terrain/ (the dir the
map renderer already reads via TERRAIN_TILE_KEYS). Idempotent: skips a type
whose <type>.png already exists.

Usage:
  python3 scripts/gen_terrain_tiles_mapa20.py                 # all missing
  python3 scripts/gen_terrain_tiles_mapa20.py --only forest   # one type
  python3 scripts/gen_terrain_tiles_mapa20.py --out temp-img/mapa20  # elsewhere
"""
import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
MODEL = "flux1-schnell-Q5_K_S.gguf"
SIZE = 768
STEPS = 8
TIMEOUT = 600

STYLE = (
    "painted tabletop RPG battlemap art style, strict top-down orthographic "
    "overhead view, flat overhead, square map tile, seamless natural terrain "
    "filling the entire tile, 2D game art, high detail, dark moody palette, "
    "NO perspective, NO side view, NO walls, NO doors, no characters, "
    "no text, no UI, no borders, no frame"
)

# One prompt per missing terrain type. Chosen to read instantly at hex scale
# and to match the muted, moody palette of the existing SG-1 tiles.
TERRAINS = {
    # — Czarnobór-critical (forest is 47% of the region) —
    "forest": "dense mixed deciduous and pine forest seen from directly above, "
              "layered dark and mid green treetops, a few small clearings, a "
              "faint dirt path winding through, fallen mossy logs",
    "swamp": "murky lowland swamp from directly above, dark stagnant black-green "
             "water between mossy hummocks, clumps of reeds, rotting half-sunk "
             "logs, patches of grey mud, sickly damp palette",
    "heath": "windswept heathland from directly above, low purple-brown heather "
             "scrub, tufts of coarse pale grass, bare peaty dark patches, "
             "scattered grey lichen-covered stones",
    "road": "packed dirt travel road seen from directly above, a broad earthen "
            "track with cart wheel ruts running straight through the tile, "
            "trampled grass verges on both sides, loose small stones and puddles",
    "water": "still dark lake water seen from directly above, deep blue-black "
             "surface with faint concentric ripples, a fringe of reeds at one "
             "edge, muted cold light",
    # — Kresy-additional —
    "plains": "open grassy plains seen from directly above, rolling green and "
              "tan grassland, scattered small wildflowers, faint braided animal "
              "trails, a few lone bushes",
    "river": "a river seen from directly above, a band of flowing blue-green "
             "water crossing the tile diagonally, pale gravel banks, ripples "
             "and eddies, reeds along the shore",
    "snow": "smooth snow field seen from directly above, wind-drifted white snow "
            "with soft blue shadow hollows, sparse dark rocks poking through, "
            "cold pale daylight",
    "sea": "open sea water seen from directly above, deep blue ocean surface, "
           "gentle scattered whitecaps, darker cold depths, faint foam streaks",
    "hills": "rolling green hills seen from directly above, grassy rounded "
             "slopes and hillocks, exposed grey rock outcrops, sheep trails "
             "and shadowed folds",
    "coast": "a coastline seen from directly above, pale sandy beach meeting "
             "blue sea, a strip of wet tidal sand, scattered dark rocks and "
             "clumps of seaweed",
    "mountain": "rugged mountain peaks seen from directly above, grey rocky "
                "ridges and loose scree slopes, snow packed into shadowed "
                "crevices, deep dark gullies",
    "tundra": "cold tundra seen from directly above, mottled brown-grey lichen "
              "and moss, patches of thin lingering snow, permafrost polygon "
              "cracks, low sparse shrubs",
}


def generate(prompt: str, steps: int, size: int) -> bytes:
    payload = json.dumps({
        "prompt": prompt, "width": size, "height": size,
        "steps": steps, "model": MODEL,
    }).encode()
    req = urllib.request.Request(
        GEN_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read())
    if "b64" not in data:
        raise RuntimeError(f"no b64 in response: {str(data)[:200]}")
    return base64.b64decode(data["b64"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frontend/images/terrain")
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for terrain, prompt in TERRAINS.items():
        if args.only and terrain != args.only:
            continue
        dest = out / f"{terrain}.png"
        if dest.exists() and not args.force:
            print(f"[skip] {dest}", flush=True)
            continue
        t0 = time.time()
        try:
            dest.write_bytes(generate(f"{prompt}, {STYLE}", args.steps, args.size))
            print(f"[ok] {dest}  ({time.time() - t0:.0f}s)", flush=True)
        except Exception as exc:  # noqa: BLE001 — batch tool, keep going
            print(f"[FAIL] {terrain}: {exc}", flush=True)
    print("[done]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
