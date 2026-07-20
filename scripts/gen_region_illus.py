#!/usr/bin/env python3
"""SG-LORE (#1481) — atmospheric illustrations for region sections.

Two targets, two conventions (both already established in this repo):

  showcase/*  → FLUX schnell, 16:9, GRIMOIRE style, darkened, WEBP+PNG
                into frontend/showcase/assets/img/  (as generate_showcase_art.py)
  rules/*     → Juggernaut-XL v9, 1024x600 PNG
                into frontend/rules/img/            (as gen_rzemioslo_illus.py)

Run from repo root:
  python3 scripts/gen_region_illus.py
  python3 scripts/gen_region_illus.py --only illus-granie-grod,podroz-lodowiec
"""
import argparse
import base64
import hashlib
import json
import urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
FLUX = "flux1-schnell-Q5_K_S.gguf"
SDXL = "SDXL/Juggernaut-XL_v9.safetensors"

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / "temp-img"
SHOWCASE_OUT = ROOT / "frontend" / "showcase" / "assets" / "img"
RULES_OUT = ROOT / "frontend" / "rules" / "img"
TEMP.mkdir(parents=True, exist_ok=True)

# Same style anchor as the rest of the showcase art — keeps the gallery coherent.
GRIMOIRE = (
    "dark fantasy illustration, grimoire aesthetic, aged tome page, deep near-black "
    "background, antique gold accents, sepia and ink wash, drifting mist, heroic-dark mood, "
    "painterly oil-on-parchment, weathered, atmospheric, cinematic, highly detailed, "
    "no text, no UI, no borders, no watermark"
)
# FLUX schnell runs at cfg=1.0, so it ignores a negative prompt — anti-text has to be
# stated positively in the prompt itself. Appended only to jobs that came back with
# garbled signage or a fake artist signature on the first pass.
NO_LETTERING = (
    ", absolutely no lettering anywhere in the image, no signboards, no written words, "
    "no letters, no numbers, no signature, no artist mark, no watermark, no logo, "
    "clean unsigned painting"
)
WIDE = (1152, 648)

JOBS = {
    # ── Siwe Granie — wizytówka ────────────────────────────────────────────────
    "illus-granie-grod": {
        "target": "showcase", "size": WIDE, "darken": 0.20,
        "prompt": (
            "a dwarven mountain fortress-city carved into a granite cliff face, a single "
            "narrow stone bridge-gate spanning a black bottomless chasm to its iron doors, "
            "tiered halls and forge chimneys venting orange glow into falling snow, snow-capped "
            "peaks looming behind, tiny lantern-lit figures crossing the bridge, "
        ),
    },
    "illus-granie-wyrobisko": {
        "target": "showcase", "size": WIDE, "darken": 0.24,
        "prompt": (
            "deep inside a dwarven silver mine tunnel, timber-braced shaft receding into "
            "darkness, a broad band of white crystalline salt set into the rock wall marking a "
            "forbidden boundary line, oil lanterns casting warm pools of light, pickaxes and "
            "ore carts, veins of silver glinting in the stone, oppressive weight of rock above, "
        ),
        "no_lettering": True,
        "trim_bottom": 0.07,
    },
    "illus-granie-siarka": {
        "target": "showcase", "size": WIDE, "darken": 0.22,
        "prompt": (
            "a barren sulphur field of cracked yellow crust and steaming fumaroles at the foot "
            "of a black volcanic cone, thick pale vapour drifting low across the ground, "
            "hooded gatherers with cloth-wrapped faces working with baskets and iron tools, "
            "no vegetation, poisoned air, sickly ochre light, "
        ),
    },
    "illus-granie-sanktuarium": {
        "target": "showcase", "size": WIDE, "darken": 0.26,
        "prompt": (
            "an abandoned stone shrine standing alone high on a vast glacier, a procession of "
            "robed pilgrims frozen solid in the clear blue ice around it, all facing uphill "
            "toward the summit, snow blowing across the ice field, the shrine's threshold "
            "swept clear of snow, one small hooded hermit figure in the doorway, utter silence, "
        ),
    },
    "illus-granie-cmentarz": {
        "target": "showcase", "size": WIDE, "darken": 0.28,
        "prompt": (
            "a field of hundreds of dwarven war hammers driven head-down into a frozen "
            "snowfield as grave markers, their hafts leaning at angles, rime and icicles on the "
            "iron, dark mountains behind under a low grey sky, blowing snow, a memorial to the "
            "dead of an exodus, mournful and vast, "
        ),
    },
    # ── Kresy — backfill dla spójności ────────────────────────────────────────
    "illus-kresy-strzegwacht": {
        "target": "showcase", "size": WIDE, "darken": 0.22,
        "prompt": (
            "a stone border fortress on a wide open borderland plain, square watchtower and "
            "curtain walls, banners of a fading empire, a rutted trade road running past the "
            "gate, soldiers on the wall looking east into gathering dusk, campfire smoke, "
            "cold damp air, two centuries of weathering on the stone, "
        ),
    },
    "illus-kresy-bor": {
        "target": "showcase", "size": WIDE, "darken": 0.30,
        "prompt": (
            "a dense old forest of dark crowded trees at dusk, a woodcutter's abandoned axe "
            "left in a half-cut trunk, sawdust and wood chips, mist pooling between the trunks, "
            "the path ahead swallowed by blackness, something unseen watching from between the "
            "trees, birch and spruce, dread creeping in, "
        ),
    },
    "illus-kresy-gospoda": {
        "target": "showcase", "size": WIDE, "darken": 0.18,
        "prompt": (
            "the warm interior of a small wooden roadside inn at night, a stout innkeeper woman "
            "pouring ale behind a plank counter, travellers hunched at heavy tables, a hearth "
            "fire, hanging lanterns, tankards and a bowl of stew, muddy boots by the door, "
            "the last safe place before the road, welcoming amber light against the dark, "
            "bare plank walls with no signage of any kind, "
        ),
        "no_lettering": True,
        "trim_bottom": 0.07,
    },
    # ── Księga Zasad, rozdział XI ─────────────────────────────────────────────
    "podroz-lodowiec": {
        "target": "rules",
        "prompt": (
            "a roped party of three travellers crossing a vast crevassed glacier in a whiteout, "
            "leaning into the wind, ice axes and heavy furs, a deep blue crevasse yawning across "
            "their path, no road, no shelter anywhere, towering ice seracs, hostile scale, "
        ),
    },
    "podroz-siarka": {
        "target": "rules",
        "prompt": (
            "travellers hurrying across a steaming sulphur flat with cloth tied over their "
            "faces, yellow crust cracking underfoot, vents of pale gas rising around them, a "
            "black volcanic cone behind, dead ground with no water and no cover, sickly haze, "
        ),
    },
}


def job_seed(name: str, offset: int) -> int:
    """Stable per-job seed — same job re-runs identically, --seed-offset rerolls it.

    The service defaults to a FIXED seed when the field is omitted (only its web UI
    randomises), so re-running a tweaked prompt without this returns the same image.
    """
    base = int(hashlib.sha1(name.encode()).hexdigest()[:8], 16)
    return (base + offset * 7919) % 4294967295


def gen(prompt: str, size, steps: int, model: str, seed: int, negative: str | None = None,
        cfg: float | None = None) -> bytes:
    w, h = size
    body = {"prompt": prompt, "width": w, "height": h, "steps": steps,
            "model": model, "seed": seed}
    if negative:
        body["negative"] = negative
    if cfg:
        body["cfg"] = cfg
    req = urllib.request.Request(
        GEN_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = json.loads(resp.read())
    if "b64" not in data:
        raise RuntimeError(f"no b64 in response: {data.get('error', data)}")
    return base64.b64decode(data["b64"])


def save_showcase(raw: bytes, name: str, darken: float, trim_bottom: float = 0.0) -> None:
    from PIL import Image, ImageEnhance

    tmp = TEMP / f"{name}.raw.png"
    tmp.write_bytes(raw)
    img = Image.open(tmp).convert("RGB")
    if trim_bottom:
        # FLUX likes to sign its work — a fake artist/watermark scrawl in the bottom
        # corner survives every "no watermark" phrasing. Cropping the strip off and
        # rescaling is deterministic; rerolling the seed is not.
        w, h = img.size
        img = img.crop((0, 0, w, int(h * (1 - trim_bottom)))).resize((w, h), Image.LANCZOS)
    if darken:
        img = ImageEnhance.Brightness(img).enhance(1.0 - darken)
        img = ImageEnhance.Contrast(img).enhance(1.05)
    png_out = SHOWCASE_OUT / f"{name}.png"
    webp_out = SHOWCASE_OUT / f"{name}.webp"
    img.save(png_out, "PNG", optimize=True)
    img.save(webp_out, "WEBP", quality=82, method=6)
    print(f"   -> {webp_out.name} ({webp_out.stat().st_size//1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma list of job keys")
    ap.add_argument("--seed-offset", type=int, default=0,
                    help="reroll the composition (0 = canonical seed of each job)")
    args = ap.parse_args()

    jobs = JOBS
    if args.only:
        want = {k.strip() for k in args.only.split(",")}
        jobs = {k: v for k, v in JOBS.items() if k in want}

    for i, (name, job) in enumerate(jobs.items(), 1):
        print(f"[{i}/{len(jobs)}] {name} ({job['target']}) …", flush=True)
        try:
            prompt = job["prompt"] + GRIMOIRE
            if job.get("no_lettering"):
                prompt += NO_LETTERING
            seed = job_seed(name, args.seed_offset)
            if job["target"] == "showcase":
                raw = gen(prompt, job["size"], 9, FLUX, seed)
                save_showcase(raw, name, job.get("darken", 0.22),
                              job.get("trim_bottom", 0.0))
            else:
                raw = gen(
                    prompt, (1024, 600), 26, SDXL, seed,
                    negative="text, watermark, signature, ui, frame, blurry, "
                             "deformed hands, extra fingers",
                    cfg=6.5,
                )
                out = RULES_OUT / f"{name}.png"
                out.write_bytes(raw)
                print(f"   -> {out.name} ({out.stat().st_size//1024} KB)")
        except Exception as exc:  # noqa: BLE001 — one bad job must not kill the batch
            print(f"   !! FAILED: {exc}", flush=True)


if __name__ == "__main__":
    main()
