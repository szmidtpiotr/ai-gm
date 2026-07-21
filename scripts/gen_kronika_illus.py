#!/usr/bin/env python3
"""Kronika Świata (#1520) — illustrations for the rebuilt swiat.html.

Same GRIMOIRE style anchor and FLUX pipeline as scripts/gen_region_illus.py, so the
new art sits in the same gallery as the existing region illustrations.

Three families, three aspect ratios:

  lud-*      2.66:1 banner  → background of a collapsed race chapter header
  rana-*     16:9  wide     → scene above each "named wound" of history
  herb-*     1:1   square   → faction emblem badge inside a codex card

Run from repo root:
  python3 scripts/gen_kronika_illus.py
  python3 scripts/gen_kronika_illus.py --only lud-krasnoludy,rana-bicie
"""
import argparse
import base64
import hashlib
import json
import urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
FLUX = "flux1-schnell-Q5_K_S.gguf"

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / "temp-img"
SHOWCASE_OUT = ROOT / "frontend" / "showcase" / "assets" / "img"
TEMP.mkdir(parents=True, exist_ok=True)

GRIMOIRE = (
    "dark fantasy illustration, grimoire aesthetic, aged tome page, deep near-black "
    "background, antique gold accents, sepia and ink wash, drifting mist, heroic-dark mood, "
    "painterly oil-on-parchment, weathered, atmospheric, cinematic, highly detailed, "
    "no text, no UI, no borders, no watermark"
)
# FLUX schnell runs at cfg=1.0 and ignores `negative`; anti-text must be positive prose.
NO_LETTERING = (
    ", absolutely no lettering anywhere in the image, no signboards, no written words, "
    "no letters, no numbers, no signature, no artist mark, no watermark, no logo, "
    "clean unsigned painting"
)
# Emblems read as icons at ~64px, so they need a flatter, higher-contrast treatment
# than the scene art — otherwise the grimoire mist eats the silhouette.
HERALDIC = (
    "heraldic emblem, single centered symbol, flat symmetrical icon design, "
    "antique gold and bone-white on deep black background, engraved medallion, "
    "high contrast, clean silhouette, no text, no lettering, no watermark, no border frame"
)

BANNER = (1152, 432)
WIDE = (1152, 648)
EMBLEM = (640, 640)

JOBS = {
    # ── Ludy — banery nagłówków rozdziałów ────────────────────────────────────
    "lud-ludzie": {
        "kind": "scene", "size": BANNER, "darken": 0.26,
        "prompt": (
            "a crowded human borderland market square at dusk under a fading empire's banners, "
            "a mounted soldier, a hooded merchant weighing coins, a priest in white, a beggar, "
            "a thief slipping through the crowd, timber and stone buildings, mud and lantern "
            "light, the whole span of human life from crown to gutter in one frame, "
        ),
    },
    "lud-krasnoludy": {
        "kind": "scene", "size": BANNER, "darken": 0.26,
        "prompt": (
            "a great dwarven hall of ancestors carved from dark granite, rows of iron war "
            "hammers mounted on the walls as clan standards, a forge glow at the far end, "
            "bearded dwarven elders in heavy furs and mail standing in council, "
            "snow drifting through a high arched opening, salt-white crystal seams in the stone, "
        ),
    },
    "lud-elfy": {
        "kind": "scene", "size": BANNER, "darken": 0.28,
        "prompt": (
            "an elven settlement built high in the crowns of colossal ancient trees, rope "
            "walkways and lantern-lit platforms among the canopy, slender hooded elven figures "
            "with longbows watching the forest below, one enormous tree in the middle distance "
            "blackened and dead among the living green, mist below, "
        ),
    },
    "lud-pietnowani": {
        "kind": "scene", "size": BANNER, "darken": 0.24,
        "prompt": (
            "a small enclave settlement of low salt-brick houses at the edge of an endless "
            "white salt flat, ash-skinned people with pale eyes in dust-wrapped robes loading "
            "salt onto a caravan, ruined alien columns on the horizon, grey ash haze, "
            "harsh sunless light, survival at the threshold of a dead land, "
        ),
    },
    "lud-wyspiarze": {
        "kind": "scene", "size": BANNER, "darken": 0.26,
        "prompt": (
            "a tar-black harbour district at night, dark-skinned islander sailors and dock "
            "workers hauling crates on a wet quay, hulls and rigging looming above, lanterns "
            "reflected in oily water, a distant wall of permanent storm on the southern "
            "horizon lit from within by lightning, crowded, loud, far from home, "
        ),
    },
    # ── Nazwane rany — sceny historyczne ──────────────────────────────────────
    "rana-schizma": {
        "kind": "scene", "size": WIDE, "darken": 0.30,
        "prompt": (
            "a forest clearing where the grass grows black, two groups of elven figures facing "
            "each other across it in the moment after a irreparable split, one side turning away "
            "into the deep forest, the others standing motionless, a great tree at the edge of "
            "the clearing half blackened as if burned from within, cold moonlight, "
        ),
    },
    "rana-wojny": {
        "kind": "scene", "size": WIDE, "darken": 0.26,
        "prompt": (
            "the weathered ramparts of an old stone border fortress at grey dawn, tired soldiers "
            "in worn mail on the wall looking east across an empty plain, a long line of ragged "
            "refugees and wagons approaching from the far horizon fleeing westward, "
            "graveyard crosses beside the road below the walls, two centuries of siege scars, "
        ),
    },
    "rana-bicie": {
        "kind": "scene", "size": WIDE, "darken": 0.32,
        "prompt": (
            "the mouth of an abandoned dwarven mine sealed with timber and iron, snow drifted "
            "against it, a broken ore cart and dropped tools left where they fell, a band of "
            "white salt crystal set into the rock across the tunnel entrance, one lantern still "
            "burning on a hook, absolute stillness, the sense of something knocking far below, "
        ),
    },
    "rana-sztorm": {
        "kind": "scene", "size": WIDE, "darken": 0.28,
        "prompt": (
            "a towering unbroken wall of black storm standing on the open sea like a cliff, "
            "lightning inside it, one battered wooden ship with torn sails running away from it "
            "toward the viewer carrying huddled refugee families on deck, mountainous waves, "
            "spray and rain, a horizon permanently closed off, "
        ),
    },

    # ── Wpisy lokacji w gazetteerze (16:9, .gaz-fig) ──────────────────────────
    "loc-birkenwald": {"kind": "scene", "size": WIDE, "darken": 0.26, "prompt": (
        "a small timber logging village at the edge of a black forest, stacked cut logs and a "
        "water-driven sawmill, smoke from low roofs, woodcutters' axes leaning by doorways, "
        "the treeline standing unnaturally close and dark behind the last house, dusk, ")},
    "loc-wolfsmark": {"kind": "scene", "size": WIDE, "darken": 0.28, "prompt": (
        "a poor mining village huddled at the foot of grey mountains, a timbered mine entrance "
        "in the hillside above the houses, ore carts and slag heaps, miners with lanterns "
        "trudging home in the snow, a small stone chapel, cold blue evening light, ")},
    "loc-most": {"kind": "scene", "size": WIDE, "darken": 0.24, "prompt": (
        "an old stone toll bridge over a wide black river, a timber gatehouse and customs post "
        "with a lowered barrier, a tax collector's lantern, wagons queuing in the mud, dark "
        "water sliding beneath the arches, mist on the river at dawn, ")},
    "loc-cieszburg": {"kind": "scene", "size": WIDE, "darken": 0.22, "prompt": (
        "a quiet farming village square with a small wooden chapel and beehives along a fence, "
        "a weekly market of a few stalls, an old dry stone well in the middle of the square, "
        "children playing near it, thatched roofs, warm late afternoon light, deceptively "
        "peaceful, ")},
    "loc-zgliszcza": {"kind": "scene", "size": WIDE, "darken": 0.30, "prompt": (
        "the burnt ruin of a village a year after the fire, blackened chimneys standing alone "
        "like teeth, makeshift plank shelters among the ash, a gutted stone church without its "
        "bell, a fresh mass grave with rows of simple wooden crosses, a few survivors around a "
        "cooking fire, grey overcast sky, ")},
    "loc-kruki": {"kind": "scene", "size": WIDE, "darken": 0.22, "prompt": (
        "a lonely two-storey roadside coaching inn at a crossroads at night, three ravens on "
        "the ridge of its roof, stables and a wagon in the yard, warm light spilling from small "
        "windows onto wet mud, a traveller dismounting, the road vanishing into darkness both "
        "ways, ")},
    "loc-pustelnia": {"kind": "scene", "size": WIDE, "darken": 0.24, "prompt": (
        "a tiny stone hermitage chapel in a forest clearing, a herb garden in neat beds beside "
        "it, a spring bubbling into a mossy stone basin, one old hooded hermit tending the "
        "plants, shafts of pale light through the trees, deep quiet, ")},
    "loc-vilnograd": {"kind": "scene", "size": WIDE, "darken": 0.24, "prompt": (
        "a vast medieval capital city seen from across its river at dusk, a royal castle on the "
        "height, a great cathedral spire, dense tiled roofs and guild towers, a busy river port "
        "with barges, bridges, thousands of window lights, smoke and haze, the largest city in "
        "the world, ")},
    "loc-volhynia": {"kind": "scene", "size": WIDE, "darken": 0.22, "prompt": (
        "a prosperous merchant town at a crossing of four highways, a huge covered market hall, "
        "loaded caravan wagons and pack mules in the square, auction crowds, weighing scales "
        "and crates of goods, banners of trading guilds, golden afternoon light, ")},
    "loc-iskry": {"kind": "scene", "size": WIDE, "darken": 0.22, "prompt": (
        "a fortified monastery of a light-worshipping faith on a hill, a cloister courtyard with "
        "an eternal flame in a bronze brazier, robed monks and healers tending the sick on cots "
        "under an arcade, scriptorium windows glowing, dawn light on pale stone, serene but "
        "watchful, ")},
    "loc-bor-zmarlych": {"kind": "scene", "size": WIDE, "darken": 0.32, "prompt": (
        "a forest of tar-black trees with no leaves and no undergrowth, trunks black as pitch, "
        "the ground bare grey ash, a wall of ordinary green forest visible far behind marking "
        "where the blackness ends, absolute silence, no birds, the blackness visibly spreading, ")},
    "loc-trzesawiska": {"kind": "scene", "size": WIDE, "darken": 0.30, "prompt": (
        "a vast misty swamp of black water and drowned trees, thick fog lying on the surface, "
        "rotten plank walkways half sunk, pale wisps of light hovering over the water, the shape "
        "of something moving just under the surface, twilight, oppressive damp, ")},
    "loc-step-wilkow": {"kind": "scene", "size": WIDE, "darken": 0.26, "prompt": (
        "an endless windswept grass steppe under an enormous grey sky, dry grass bending in "
        "waves, a wolf pack silhouetted on a low ridge watching, an ancient overgrown burial "
        "mound standing alone on the plain, no trees, no roads, no shelter, ")},
    "loc-czarnograd": {"kind": "scene", "size": WIDE, "darken": 0.26, "prompt": (
        "a tar-black harbour city at a river mouth at night, crowded docks and warehouses, dark "
        "hulled ships at anchor, a smugglers' market under awnings on the quay, lanterns "
        "reflected in oily water, rain, the second largest city in the world and the most "
        "lawless, ")},
    "loc-zatoka": {"kind": "scene", "size": WIDE, "darken": 0.28, "prompt": (
        "a pirate fortress town built on a rocky island, stone walls and cannon batteries above "
        "the surf, a crowded harbour of black-hulled ships, plundered goods piled on the quays, "
        "a great hall on the summit, storm clouds gathering over the sea, no law here, ")},
    "loc-swiatynia": {"kind": "scene", "size": WIDE, "darken": 0.32, "prompt": (
        "the interior of a colossal pre-human temple built of impossible geometry, ribbed vaults "
        "like the inside of a vast ribcage, a black fissure splitting the floor and glowing "
        "faintly from far below, dust motes in shafts of sick light, alien carvings, a scale "
        "that dwarfs human beings, ")},
    "loc-krypta": {"kind": "scene", "size": WIDE, "darken": 0.32, "prompt": (
        "an underground noble crypt of black marble, a knight's tomb with a cracked effigy, dark "
        "dried stains on the stone floor, guttering candles left by someone, cobwebbed banners "
        "of a royal house, a heavy iron door standing open into deeper darkness, ")},
    "loc-twierdza": {"kind": "scene", "size": WIDE, "darken": 0.34, "prompt": (
        "a black basalt fortress standing alone on an ash plain under a sunless sky, its gate "
        "wide open and utterly dark inside, no defenders, no bodies, no damage, a road of "
        "bones and abandoned packs leading up to the threshold, absolute stillness, ")},
    "loc-kamienny-grod": {"kind": "scene", "size": WIDE, "darken": 0.24, "prompt": (
        "a dwarven fortress city gate at the end of a single narrow stone bridge over a "
        "bottomless chasm, colossal iron doors flanked by carved ancestor statues, forge smoke "
        "and orange light from arrow slits above, snow falling, guards with hammers at the "
        "bridgehead, ")},
    "loc-linia-soli": {"kind": "scene", "size": WIDE, "darken": 0.28, "prompt": (
        "a guarded mine tunnel checkpoint deep underground, a thick band of white crystalline "
        "salt set into the rock across the passage marking a forbidden depth, timber barricade "
        "and two dwarven wardens with lanterns, the tunnel beyond the line pitch black, ")},
    "loc-czarne-skaly": {"kind": "scene", "size": WIDE, "darken": 0.28, "prompt": (
        "a black volcanic cone rising over a field of shattered obsidian and ash, red glow deep "
        "in fissures on its flank, sulphur vapour drifting, no vegetation at all, a dead "
        "landscape of glass and cinder under a bruised sky, ")},
    "loc-gorace-zrodla": {"kind": "scene", "size": WIDE, "darken": 0.20, "prompt": (
        "steaming hot springs in a snowy mountain hollow, milky blue pools rimmed with mineral "
        "crust, a timber caravanserai and stables built beside them, travellers and merchants "
        "resting in the steam, the only warm place in the mountains, lantern light in the mist, ")},

    "loc-wyrobisko": {"kind": "scene", "size": WIDE, "darken": 0.26, "prompt": (
        "an active dwarven silver mine on a snowy mountainside, timber headframe and winch over "
        "the shaft mouth, ore carts on rails, miners hauling baskets of glittering silver ore, "
        "a cluster of stone bunkhouses below, lantern light against blue dusk snow, ")},
    "loc-hutman": {"kind": "scene", "size": WIDE, "darken": 0.33, "prompt": (
        "a huge abandoned mine complex swallowed by snow on a black mountainside, collapsed "
        "winch towers and boarded galleries, a great iron door in the rock sealed with chains "
        "and salt-white crystal, no tracks in the snow leading in or out, deathly quiet, "
        "something waiting far below, ")},
    "loc-krzyz-gor": {"kind": "scene", "size": WIDE, "darken": 0.26, "prompt": (
        "colossal granite peaks crossing each other like a cross seen from a high pass, a vast "
        "white glacier tongue pouring down between them, wind-driven snow plumes off the "
        "summits, a lone tiny figure on the pass for scale, brutal and sacred, ")},
    "loc-wygnancy": {"kind": "scene", "size": WIDE, "darken": 0.28, "prompt": (
        "a small exile camp of hide tents and windbreaks on an open frozen tundra, dwarven "
        "outcasts in furs around a low fire, sledges and lashed bundles, no walls and no "
        "permanent buildings, the white wall of a glacier rising on the horizon behind them, "
        "bitter wind, ")},
    # ── Frakcje — herby ───────────────────────────────────────────────────────
    "herb-korona": {
        "kind": "emblem",
        "prompt": "an iron crown resting on a sheathed sword, austere and heavy, ",
    },
    "herb-rada": {
        "kind": "emblem",
        "prompt": (
            "four blank faceless masks arranged in a square around an empty centre, "
            "a merchant's wax seal beneath them, "
        ),
    },
    "herb-swiatlo": {
        "kind": "emblem",
        "prompt": "a radiant sunburst lantern above a pair of open hands, rays of light, ",
    },
    "herb-kulty": {
        "kind": "emblem",
        "prompt": (
            "a jagged crack splitting a stone circle open, tendrils of darkness pouring out of "
            "the fissure, an inverted ritual sigil, "
        ),
    },
    "herb-gildie": {
        "kind": "emblem",
        "prompt": "a merchant's balance scale over a coin and a rolled contract scroll, ",
    },
    "herb-zlodzieje": {
        "kind": "emblem",
        "prompt": "a signet ring and a lockpick crossed beneath a crescent moon, ",
    },
    "herb-piraci": {
        "kind": "emblem",
        "prompt": "a ship's wheel with five chairs around it, one chair empty and broken, an anchor below, ",
    },
    "herb-rody": {
        "kind": "emblem",
        "prompt": "a dwarven war hammer crossed with a miner's pick over a mountain peak and a salt crystal, ",
    },
    "herb-elfy": {
        "kind": "emblem",
        "prompt": "a great tree whose left half is in leaf and right half is bare and blackened, a longbow behind it, ",
    },
    "herb-dzicz": {
        "kind": "emblem",
        "prompt": "a snarling wolf skull with a broken orcish tusk blade behind it, bones, ",
    },
}


def job_seed(name: str, offset: int) -> int:
    h = hashlib.sha256(f"{name}:{offset}".encode()).hexdigest()[:8]
    return int(h, 16) % (2**31)


def gen(prompt: str, size, steps: int, seed: int) -> bytes:
    w, h = size
    body = {"prompt": prompt, "width": w, "height": h, "steps": steps,
            "model": FLUX, "seed": seed}
    req = urllib.request.Request(
        GEN_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = json.loads(resp.read())
    if "b64" not in data:
        raise RuntimeError(f"no b64 in response: {data.get('error', data)}")
    return base64.b64decode(data["b64"])


def save(raw: bytes, name: str, darken: float, trim_bottom: float = 0.0) -> None:
    from PIL import Image, ImageEnhance

    tmp = TEMP / f"{name}.raw.png"
    tmp.write_bytes(raw)
    img = Image.open(tmp).convert("RGB")
    if trim_bottom:
        w, h = img.size
        img = img.crop((0, 0, w, int(h * (1 - trim_bottom)))).resize((w, h), Image.LANCZOS)
    if darken:
        img = ImageEnhance.Brightness(img).enhance(1.0 - darken)
        img = ImageEnhance.Contrast(img).enhance(1.05)
    webp_out = SHOWCASE_OUT / f"{name}.webp"
    img.save(webp_out, "WEBP", quality=82, method=6)
    print(f"   -> {webp_out.name} ({webp_out.stat().st_size//1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma list of job keys")
    ap.add_argument("--seed-offset", type=int, default=0)
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if the .webp already exists")
    args = ap.parse_args()

    jobs = JOBS
    if args.only:
        want = {k.strip() for k in args.only.split(",")}
        jobs = {k: v for k, v in JOBS.items() if k in want}

    # Resumable by default: the batch is long enough that it will be interrupted, and
    # rerunning must not redo an hour of GPU work.
    if not args.force:
        jobs = {k: v for k, v in jobs.items()
                if not (SHOWCASE_OUT / f"{k}.webp").exists()}
        print(f"do zrobienia: {len(jobs)} (reszta już na dysku)", flush=True)

    for i, (name, job) in enumerate(jobs.items(), 1):
        print(f"[{i}/{len(jobs)}] {name} …", flush=True)
        try:
            seed = job_seed(name, args.seed_offset)
            if job["kind"] == "emblem":
                prompt = job["prompt"] + HERALDIC + NO_LETTERING
                raw = gen(prompt, EMBLEM, 9, seed)
                save(raw, name, 0.05, trim_bottom=0.07)
            else:
                prompt = job["prompt"] + GRIMOIRE + NO_LETTERING
                raw = gen(prompt, job["size"], 9, seed)
                save(raw, name, job.get("darken", 0.24), trim_bottom=0.07)
        except Exception as exc:  # noqa: BLE001 — one bad job must not kill the batch
            print(f"   !! FAILED: {exc}", flush=True)


if __name__ == "__main__":
    main()
