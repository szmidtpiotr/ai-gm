#!/usr/bin/env python3
"""L17 runoff — po pozarze (02) vs nawiedzone (03), 3 varied chambers each.

Generates 3 different room types per flavor so we can judge how the style holds
across a real batch (not 3 identical prompts). Saves to temp-img/, no DB writes.

Run on .61:
  python3 scripts/probe_ruiny_dogrywka.py
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

SUFFIX = (
    "painted tabletop RPG battlemap art style, high detail, "
    "strict top-down orthographic overhead view, square map tile, 2D game art, "
    "NO perspective, NO side view, flat overhead, no text, no UI"
)

# Flavor 02 — fire-scorched / siege-damaged keep
FIRE = (
    "fire-scorched siege-damaged ruined stone fortress, soot-blackened stone-block walls "
    "with catapult breaches, burnt collapsed timber beams, scattered ash and charred debris, "
    "smoldering embers and warm orange firelight, "
)
# Flavor 03 — haunted undead-overtaken keep
HAUNT = (
    "haunted undead-overtaken ruined stone fortress, ancient mossy stone-block walls, "
    "scattered bones and skulls, cobwebs, eerie greenish necromantic mist drifting low, "
    "faintly glowing runes carved into the cracked flagstones, cold haunted blue-green lighting, "
)

PROBES = {
    # po pozarze across 3 room types
    "fire_a_hall": FIRE + (
        "a great hall chamber seen from directly straight above, broken stone columns, "
        "cracked flagstone floor, toppled long table and shattered shields, "
        "2-3 jagged wall breaches leading off the edges as passages, "
    ),
    "fire_b_zbrojownia": FIRE + (
        "an armory guardroom seen from directly straight above, burnt weapon racks, "
        "scattered scorched swords and spears, melted armor stands, cracked stone floor, "
        "2-3 broken archway openings leading off the edges as passages, "
    ),
    "fire_c_schody": FIRE + (
        "a collapsed stairwell chamber seen from directly straight above, a broken stone "
        "staircase choked with rubble, fallen ceiling blocks on a cracked floor, "
        "2-3 jagged wall breaches leading off the edges as passages, "
    ),
    # nawiedzone across 3 room types
    "haunt_a_krypta": HAUNT + (
        "a crypt hall seen from directly straight above, open stone sarcophagi, "
        "scattered bones across the cracked flagstone floor, cobweb-draped broken pillars, "
        "2-3 dark archway openings leading off the edges as passages, "
    ),
    "haunt_b_rytual": HAUNT + (
        "a ritual chamber seen from directly straight above, a large summoning circle of "
        "glowing runes on the floor, candle stubs and bone fetishes, cracked stone altar, "
        "2-3 dark archway openings leading off the edges as passages, "
    ),
    "haunt_c_tron": HAUNT + (
        "a ruined throne room seen from directly straight above, a cracked stone throne, "
        "tattered rotting banners, scattered bones and a fallen crown on the flagstone floor, "
        "2-3 dark archway openings leading off the edges as passages, "
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
    for name, prompt in PROBES.items():
        print(f"[GEN] {name} ...", flush=True)
        t0 = time.time()
        try:
            png = gen(prompt + SUFFIX)
        except Exception as exc:
            print(f"      FAILED: {exc}", flush=True)
            continue
        path = OUT / f"ruiny_run_{name}.png"
        path.write_bytes(png)
        print(f"      ✓ {path.name}  ({len(png)//1024} KB, {time.time()-t0:.1f}s)", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
