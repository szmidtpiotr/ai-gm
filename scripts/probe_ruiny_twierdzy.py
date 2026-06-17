#!/usr/bin/env python3
"""L17 probe — 5 mixed-flavor trial tiles for the 'ruiny twierdzy' category.

Calls FLUX (.170:8765/generate) directly with 5 candidate base_prompts, saves raw
PNGs to temp-img/ for visual review. Does NOT touch the DB — pure style probe.

Run on .61:
  python3 scripts/probe_ruiny_twierdzy.py
"""
import base64
import json
import time
import urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
MODEL = "flux1-schnell-Q5_K_S.gguf"
STEPS = 8
SIZE = 768
OUT = Path(__file__).resolve().parent.parent / "temp-img"
OUT.mkdir(parents=True, exist_ok=True)

# Shared top-down battlemap suffix (matches the approved dir2_camp discipline)
SUFFIX = (
    "painted tabletop RPG battlemap art style, high detail, "
    "strict top-down orthographic overhead view, square map tile, 2D game art, "
    "NO perspective, NO side view, flat overhead, no text, no UI"
)

PROBES = {
    "01_opuszczona": (
        "ruined stone fortress chamber seen from directly straight above, a crumbling "
        "great hall of an abandoned human keep, thick weathered stone-block walls form the "
        "boundary of the room with collapsed sections, cracked flagstone floor overgrown with "
        "moss, ivy and weeds creeping through, toppled stone columns and rubble piles, "
        "2-3 broken archway openings leading off the edges as passages, faded torn banners, "
        "cold grey daylight filtering through a broken ceiling, "
    ),
    "02_poprzezarze": (
        "ruined stone fortress chamber seen from directly straight above, a fire-scorched "
        "siege-damaged keep hall, soot-blackened stone walls with catapult breaches and rubble, "
        "burnt timber beams collapsed across a cracked stone floor, scattered ash and charred "
        "debris, broken weapons and shattered shields strewn about, 2-3 jagged wall breaches "
        "leading off the edges as passages, smoldering embers and warm orange firelight, "
    ),
    "03_nawiedzone": (
        "ruined stone fortress chamber seen from directly straight above, a haunted crypt-hall "
        "overtaken by undead, ancient mossy stone walls form the boundary, cracked floor with "
        "open stone sarcophagi and scattered bones and skulls, cobweb-draped broken pillars, "
        "eerie greenish necromantic mist drifting low, faintly glowing runes carved into the "
        "flagstones, 2-3 dark archway openings leading off the edges as passages, cold haunted "
        "blue-green lighting, "
    ),
    "04_zatopione": (
        "ruined stone fortress chamber seen from directly straight above, a flooded sunken keep "
        "hall, weathered stone walls form the boundary with water stains, shallow murky water "
        "covering half the cracked flagstone floor with reflections, fallen mossy columns half "
        "submerged, slime and algae creeping up the walls, dripping broken ceiling, 2-3 archway "
        "openings leading off the edges as passages, dim cold damp lighting, "
    ),
    "05_zarosniete": (
        "ruined stone fortress chamber seen from directly straight above, an old keep hall "
        "reclaimed by wild nature, crumbling stone walls form the boundary cracked open by "
        "tree roots, flagstone floor split by grass, roots and small bushes, a young tree "
        "growing through the collapsed ceiling, vines draping toppled columns, scattered rubble "
        "and bird nests, 2-3 broken archway openings leading off the edges as passages, "
        "dappled green daylight, "
    ),
}


def gen(prompt: str) -> bytes:
    payload = json.dumps(
        {"prompt": prompt, "width": SIZE, "height": SIZE, "steps": STEPS, "model": MODEL}
    ).encode()
    req = urllib.request.Request(
        GEN_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    if "b64" not in data:
        raise RuntimeError(f"no b64 in response: {data.get('error', data)}")
    return base64.b64decode(data["b64"])


def main() -> None:
    for name, flavor in PROBES.items():
        prompt = flavor + SUFFIX
        print(f"[GEN] {name} ...", flush=True)
        t0 = time.time()
        try:
            png = gen(prompt)
        except Exception as exc:
            print(f"      FAILED: {exc}", flush=True)
            continue
        path = OUT / f"ruiny_probe_{name}.png"
        path.write_bytes(png)
        print(f"      ✓ {path.name}  ({len(png)//1024} KB, {time.time()-t0:.1f}s)", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
