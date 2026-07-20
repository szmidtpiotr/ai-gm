#!/usr/bin/env python3
"""SG-1 — generate terrain tiles for the 3 new Siwe Granie hex types.

Calls the FLUX.1-schnell service on 192.168.1.170:8765 directly (no DEV API
round-trip: these are terrain illustrations, not dungeon tiles, so the
compositor / dungeon_tiles pipeline does not apply).

Style is matched to the existing dungeon tiles: painted tabletop RPG battlemap,
strict top-down orthographic, 768x768 square, high detail, no text/UI.

Usage:
  python3 scripts_tmp/sg1_gen_terrain_tiles.py --variants 3 --out temp-img/sg1
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

# Three prompt variants per terrain — same subject, different framing/detail,
# so the picker has genuinely different candidates instead of noise-only reruns.
TERRAINS = {
    "lodowiec": [
        "glacier ice field, cracked pale blue glacial ice, deep dark crevasses, "
        "wind-scoured snow ridges, frozen meltwater pools",
        "high mountain glacier surface, fractured blue-white ice slabs, "
        "wide crevasse splitting the field, drifted snow, dark rocks frozen into the ice",
        "frozen glacier plateau, rippled wind-carved ice, hairline fracture network, "
        "shallow refrozen ponds, thin snow cover, cold pale daylight",
    ],
    # Runda 2: runda 1 dała czystą LAWĘ (v2/v3 = biom `volcanic`, nie siarka).
    # Winne były "geothermal / boiling / fumarole / vent" — FLUX ciągnie je w magmę.
    # Teraz opis pozytywny: matowa skorupa mineralna, szare błoto, zimna para.
    "siarka": [
        "barren sulphur flats, dull pale yellow mineral crust over grey cracked "
        "ground, chalky ochre deposits, shallow grey mud pools, dark grey rocks, "
        "thin cold white steam drifting low, overcast desaturated light, NO lava, "
        "NO molten rock, NO glowing magma, NO fire, NO orange glow",
        "sulphur pans at the foot of black cliffs, crusted matte yellow and ochre "
        "mineral terraces, milky grey mud puddles, scattered black stone rubble, "
        "wisps of pale steam, muted washed-out palette, dead poisoned ground, "
        "NO lava, NO molten rock, NO glowing magma, NO fire, NO orange glow",
        "poisoned sulphur ground, powdery sickly yellow-green mineral crust, dry "
        "cracked grey clay, small stagnant grey-white pools with yellow rims, "
        "dark boulders, low pale haze, cold overcast daylight, dull matte colours, "
        "NO lava, NO molten rock, NO glowing magma, NO fire, NO orange glow",
    ],
    "las_iglasty": [
        "dense coniferous spruce forest seen from directly above, dark green fir "
        "treetops, narrow game trail winding through, mossy boulders",
        "northern fir forest canopy from overhead, tightly packed spruce crowns, "
        "snow dusted branches, small clearing with fallen logs, rocky ground",
        "mountain conifer woodland from above, dark spruce and pine tops, "
        "needle-covered forest floor visible in gaps, grey boulders, thin mist",
    ],
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
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--out", default="temp-img/sg1")
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for terrain, prompts in TERRAINS.items():
        if args.only and terrain != args.only:
            continue
        for i in range(args.variants):
            prompt = f"{prompts[i % len(prompts)]}, {STYLE}"
            dest = out / f"{terrain}_v{i + 1}.png"
            if dest.exists():
                print(f"[skip] {dest}", flush=True)
                continue
            t0 = time.time()
            try:
                dest.write_bytes(generate(prompt, args.steps, args.size))
                print(f"[ok] {dest}  ({time.time() - t0:.0f}s)", flush=True)
            except Exception as exc:  # noqa: BLE001 — batch tool, keep going
                print(f"[FAIL] {terrain} v{i + 1}: {exc}", flush=True)
    print("[done]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
