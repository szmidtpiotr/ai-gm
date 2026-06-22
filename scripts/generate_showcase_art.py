#!/usr/bin/env python3
"""W7 (#908) — Showcase ART generator (GRIMOIRE style).

Generates atmospheric art for the AI-GM public showcase site:
  - hero background (wide, darkened)
  - parchment/tome texture (subtle panel background)
  - 6 land illustrations (per LORE_v1_KANON 6 krain)

Talks DIRECTLY to the local FLUX/ComfyUI service on .170:8765/generate
(same JSON contract as scripts/probe_ruiny_twierdzy.py — confirmed http 200).
Response: {"b64": "<base64 png>"}.

Saves raw PNGs to temp-img/ (working previews) and optimized WEBP + PNG to
frontend/showcase/assets/img/.

Run from repo root:
  python3 scripts/generate_showcase_art.py
  python3 scripts/generate_showcase_art.py --only hero,parchment
  python3 scripts/generate_showcase_art.py --steps 10
"""
import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
MODEL = "flux1-schnell-Q5_K_S.gguf"
DEFAULT_STEPS = 9
MAX_RETRIES = 3

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / "temp-img"
OUT = ROOT / "frontend" / "showcase" / "assets" / "img"
TEMP.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

# GRIMOIRE palette / style anchor — dark fantasy, gold/sepia, old-tome, heroic-dark.
STYLE = (
    "dark fantasy illustration, grimoire aesthetic, aged tome page, deep near-black "
    "background #0a0908, antique gold #c9a54a accents, sepia and ink wash, candlelit glow, "
    "drifting mist, heroic-dark mood, painterly oil-on-parchment, weathered, atmospheric, "
    "cinematic, highly detailed, no text, no UI, no borders, no watermark"
)

# Wide landscape size for hero + lands; texture is squarer.
WIDE = (1344, 768)
HERO = (1344, 768)
TEXTURE = (1024, 1024)

JOBS = {
    "hero-bg": {
        "size": HERO,
        "prompt": (
            "an ancient dark altar of knowledge in a forgotten sanctum, a massive open "
            "grimoire on a stone lectern, golden runic light rising from its pages, scattered "
            "old scrolls and a guttering candle, heavy mist coiling through shadow, towering "
            "ruined arches fading into blackness, a single shaft of warm gold light, vast and "
            "solemn, lots of dark empty space at the top for overlaid title text, vignette, "
        ),
        "darken": 0.42,  # extra darkening multiplier for text legibility
    },
    "parchment": {
        "size": TEXTURE,
        "prompt": (
            "a plain seamless dark brown leather texture swatch filling the entire frame, "
            "macro photograph of worn aged leather grain, very dark desaturated near-black "
            "brown, uniform fine pebbled grain edge to edge, completely flat and even, "
            "no center, no frame, no border, no ornament, no corners, no gold, no pattern, "
            "no decoration, no symbol, no object, no text, no glow, no lighting gradient, "
            "just raw material surface texture, "
        ),
        "darken": 0.25,
    },
    "kraina-koronne-niziny": {
        "size": WIDE,
        "prompt": (
            "a wide heroic-dark fantasy landscape of a grand walled capital city of Vilnograd "
            "on golden lowland plains, royal palace and cathedral spires catching warm gold "
            "evening light, banners and a distant crown silhouette, rich and orderly on the "
            "surface yet uneasy, faint shadows of intrigue, sepia haze, opulent but cold, "
        ),
        "darken": 0.18,
    },
    "kraina-kresy": {
        "size": WIDE,
        "prompt": (
            "a wide heroic-dark fantasy landscape of a bleak borderland frontier, a lone stone "
            "border fortress Strazyn on a foggy ridge, scattered poor wooden villages, thick "
            "grey mist rolling over fields, dim watchfires, a sense of dread at the edge of the "
            "world, muted sepia and ash tones, lonely and tense, "
        ),
        "darken": 0.2,
    },
    "kraina-czarnobor": {
        "size": WIDE,
        "prompt": (
            "a wide heroic-dark fantasy landscape of a haunted black forest and swamp, pitch-"
            "black tree trunks like soot, drowned bog and stagnant water, eerie greenish "
            "necromantic mist, pale undead shapes and bones half-sunk in mire, faint hidden "
            "elven shapes among the trees, cold and oppressive, deep shadow, "
        ),
        "darken": 0.22,
    },
    "kraina-siwe-granie": {
        "size": WIDE,
        "prompt": (
            "a wide heroic-dark fantasy landscape of frozen grey mountains, abandoned dwarven "
            "mine entrances carved into icy cliffs, glaciers and a volcanic sulphur vent "
            "belching ash in the distance, ice and brimstone, a ruined fortress-forge, harsh "
            "cold blue and ashen tones with faint gold light on the peaks, desolate, "
        ),
        "darken": 0.2,
    },
    "kraina-wybrzeze-lez": {
        "size": WIDE,
        "prompt": (
            "a wide heroic-dark fantasy landscape of a storm-lashed coast, a lawless pirate "
            "port of black timber clinging to cliffs, towering grey waves and wrecked ships on "
            "rocks, lightning behind heavy clouds, a vast dark shape looming beneath the surf, "
            "salt spray and gloom, cold sea tones with sickly gold lantern light, ominous, "
        ),
        "darken": 0.2,
    },
    "kraina-martwe-pustkowia": {
        "size": WIDE,
        "prompt": (
            "a wide heroic-dark fantasy landscape of a vast white salt flat wasteland under a "
            "bruised sky, scattered ancient alien ruins of the Pradawni half-buried in salt, a "
            "great cracked glowing fissure in the ground leaking dim arcane light from a broken "
            "Core deep below, bleached bones, dead silence, eerie and primordial, "
            "pale sepia and bone-white tones with an ominous gold-violet glow from the crack, "
        ),
        "darken": 0.22,
    },
    # --- NEW section backgrounds (#908, second batch) ---
    "hero-bg-2": {
        "size": HERO,
        "prompt": (
            "an epic open glowing grimoire on a stone altar of knowledge in vast ancient ruins, "
            "brilliant golden runic light and sparks rising and swirling from its pages into the "
            "dark, broken cathedral arches and toppled columns around it, warm gold radiance "
            "pushing back drifting silver mist, a magnificent solemn shaft of light from above, "
            "awe and wonder, grander and a touch brighter than a tomb, but the upper third and "
            "center kept in deep shadow and empty dark space for overlaid title text, vignette, "
        ),
        # lighter than hero-bg (0.42) so the 'wow' reads, but top still drops to black via prompt
        "darken": 0.28,
    },
    "bg-tavern": {
        "size": WIDE,
        "prompt": (
            "the warm dim interior of a dark fantasy tavern called Pod Zlamanym Rogiem, heavy "
            "old timber beams and worn wooden tables, flickering candlelight and a low hearth "
            "fire glow, pewter tankards and a broken drinking horn on the bar, deep shadowy "
            "corners, smoke and dust in the air, cozy yet faintly menacing, a few hooded "
            "patrons in silhouette, amber and gold firelight against near-black shadow, "
        ),
        "darken": 0.3,
    },
    "bg-battle": {
        "size": WIDE,
        "prompt": (
            "a dramatic dark fantasy battle scene, a lone armored warrior with raised sword "
            "facing a towering shadowy undead figure, sparks and embers flying, clashing steel "
            "and a burst of cold light between them, dust and mist swirling, dynamic tense "
            "composition, deep blacks with fierce gold and pale-blue highlights on the figures, "
            "ominous and cinematic, lots of dark atmosphere around the edges, "
        ),
        "darken": 0.3,
    },
    "bg-arcane": {
        "size": WIDE,
        "prompt": (
            "the dim arcane study of a Scholar mage, towering shelves of ancient leather books "
            "and scrolls, glowing blue-gold runes hovering and carved into a stone wall, a "
            "jagged glowing fissure of the broken Core leaking arcane light, an open spellbook "
            "and burning candles on a cluttered desk, dust motes in shafts of light, mysterious "
            "and scholarly, deep shadow with cold blue and warm gold magical glow, "
        ),
        "darken": 0.3,
    },
    "bg-divider": {
        "size": WIDE,
        "prompt": (
            "a wide sweeping panorama of heroic-dark fantasy wilderness at dusk, rolling misty "
            "hills layered into the distance, a far-off ruined fortress silhouette on a ridge "
            "catching faint gold light, low fog filling the valleys, a vast moody overcast sky, "
            "lonely and atmospheric, muted sepia and ash tones with a thin band of gold horizon "
            "light, calm but foreboding, empty and panoramic, "
        ),
        "darken": 0.32,
    },
}

# Convenience set: the second-batch section backgrounds (--only new).
NEW_BATCH = (
    "hero-bg-2",
    "bg-tavern",
    "bg-battle",
    "bg-arcane",
    "bg-divider",
)


def gen(prompt: str, size, steps: int) -> bytes:
    w, h = size
    payload = json.dumps(
        {"prompt": prompt, "width": w, "height": h, "steps": steps, "model": MODEL}
    ).encode()
    req = urllib.request.Request(
        GEN_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    if "b64" not in data:
        raise RuntimeError(f"no b64 in response: {data.get('error', data)}")
    return base64.b64decode(data["b64"])


def post_process(png_path: Path, name: str, darken: float) -> None:
    """Save optimized WEBP (and a darkened PNG variant) into OUT."""
    from PIL import Image, ImageEnhance

    img = Image.open(png_path).convert("RGB")

    if darken and darken > 0:
        img = ImageEnhance.Brightness(img).enhance(1.0 - darken)
        # gentle contrast lift so it doesn't go muddy
        img = ImageEnhance.Contrast(img).enhance(1.05)

    png_out = OUT / f"{name}.png"
    webp_out = OUT / f"{name}.webp"
    img.save(png_out, "PNG", optimize=True)
    img.save(webp_out, "WEBP", quality=82, method=6)
    print(
        f"      -> {webp_out.name} ({webp_out.stat().st_size//1024} KB), "
        f"{png_out.name} ({png_out.stat().st_size//1024} KB)"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma list of job keys")
    ap.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    args = ap.parse_args()

    jobs = JOBS
    if args.only:
        want = set()
        for k in args.only.split(","):
            k = k.strip()
            if k == "new":
                want.update(NEW_BATCH)
            else:
                want.add(k)
        jobs = {k: v for k, v in JOBS.items() if k in want}

    print(f"Showcase ART generator — {len(jobs)} job(s), steps={args.steps}")
    ok, fail = 0, 0
    for name, spec in jobs.items():
        prompt = spec["prompt"] + STYLE
        size = spec["size"]
        print(f"[GEN] {name} {size[0]}x{size[1]} ...", flush=True)
        png = None
        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.time()
            try:
                png = gen(prompt, size, args.steps)
                print(f"      generated ({len(png)//1024} KB, {time.time()-t0:.1f}s)")
                break
            except Exception as exc:
                print(f"      attempt {attempt}/{MAX_RETRIES} FAILED: {exc}", flush=True)
                if attempt < MAX_RETRIES:
                    time.sleep(5)
        if png is None:
            fail += 1
            continue
        raw_path = TEMP / f"showcase_{name}.png"
        raw_path.write_bytes(png)
        try:
            post_process(raw_path, name, spec.get("darken", 0.0))
            ok += 1
        except Exception as exc:
            print(f"      post-process FAILED: {exc}")
            fail += 1

    print(f"\nDone. OK={ok} FAIL={fail}")
    print(f"Previews: {TEMP}")
    print(f"Assets:   {OUT}")


if __name__ == "__main__":
    main()
