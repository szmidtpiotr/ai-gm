#!/usr/bin/env python3
"""#1543 — Wariant D „tło biomów": large per-FAMILY backdrop images.

Idea (Piotr): don't texture each hex separately (repetitive, unreadable) —
generate ONE large image of a whole biome area and lay it under a CLUSTER of
contiguous same-terrain hexes, clipped to the hex boundary of the blob.

These are big (1024²), varied, painterly area-views (NOT seamless tiles) so a
blob spanning many hexes shows one continuous scene instead of a repeated tile.
2 variants per family → neighbouring blobs sample different images.

Writes to frontend/images/biomes/<family>_v{n}.png. Idempotent.
"""
import argparse, base64, json, time, urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
MODEL = "flux1-schnell-Q5_K_S.gguf"
SIZE = 1024
STEPS = 8
TIMEOUT = 600

STYLE = ("painterly fantasy world-map art, high-altitude top-down aerial view of "
         "a large landscape region, continuous varied terrain, soft natural "
         "lighting, muted moody palette, 2D game map, high detail, NO grid, "
         "NO hexes, no text, no UI, no borders, no frame, no characters")

FAMILIES = {
    "lasy": [
        "a vast expanse of dark old-growth forest, many treetops with clearings, "
        "a winding stream, scattered rocky outcrops, mist in the hollows",
        "a large ancient woodland, mixed pine and black-bark trees, a few glades "
        "and fallen giants, a faint trail, damp green gloom",
    ],
    "bagna": [
        "a vast murky swamp wetland, black stagnant pools between mossy hummocks, "
        "reed beds, rotting logs, patches of grey mud, low drifting mist",
        "a large fen of dark peat water and sedge, tangled dead trees, scattered "
        "bright green mosses, sickly damp haze",
    ],
    "stepy": [
        "a vast open grassland steppe, rolling green and tan grass, scattered "
        "wildflower patches, lone bushes, faint braided trails",
        "a wide windswept heath and plain, coarse pale grass and purple heather, "
        "bare peaty patches, a few grey standing stones",
    ],
    "gory": [
        "a large rugged mountain range, grey rocky ridges and scree slopes, snow "
        "in the shadowed crevices, deep dark gullies, sparse pines below",
        "steep stony highlands and crags, folded grey rock, patchy snow, loose "
        "boulders and cliffs, cold thin light",
    ],
    "woda": [
        "a large lake and river system, deep blue-green water, gravel and reed "
        "banks, small islands, ripples and eddies",
        "broad dark waters meeting a shoreline, calm surface with faint currents, "
        "reed fringes and wet mud flats",
    ],
}


def generate(prompt, steps, size):
    payload = json.dumps({"prompt": prompt, "width": size, "height": size,
                          "steps": steps, "model": MODEL}).encode()
    req = urllib.request.Request(GEN_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read())
    if "b64" not in data:
        raise RuntimeError(f"no b64: {str(data)[:200]}")
    return base64.b64decode(data["b64"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frontend/images/biomes")
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    for fam, prompts in FAMILIES.items():
        if args.only and fam != args.only:
            continue
        for i, p in enumerate(prompts, 1):
            dest = out / f"{fam}_v{i}.png"
            if dest.exists() and not args.force:
                print(f"[skip] {dest}", flush=True); continue
            t0 = time.time()
            try:
                dest.write_bytes(generate(f"{p}, {STYLE}", args.steps, args.size))
                print(f"[ok] {dest} ({time.time()-t0:.0f}s)", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[FAIL] {fam} v{i}: {exc}", flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
