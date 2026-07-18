#!/usr/bin/env python3
"""One-shot: generate the Rzemiosło chapter illustration via Juggernaut-XL v9 on .170.
Saves to frontend/rules/img/ch-rzemioslo.png (1024x600, matches other chapter art)."""
import base64
import json
import urllib.request
from pathlib import Path

GEN_URL = "http://192.168.1.170:8765/generate"
MODEL = "SDXL/Juggernaut-XL_v9.safetensors"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "rules" / "img" / "ch-rzemioslo.png"

STYLE = (
    "dark fantasy illustration, grimoire aesthetic, painterly oil-on-parchment, deep "
    "shadows, antique gold and sepia accents, candlelit warm glow, weathered, atmospheric, "
    "cinematic, highly detailed, no text, no UI, no border, no watermark"
)
PROMPT = (
    "inside a dwarven smithy at night, a stout bearded dwarf blacksmith at a glowing anvil "
    "hammering a sword blade, a hooded adventurer handing over a handful of beast fangs and "
    "raw ore across the workbench, bundles of dried healing herbs and glass potion vials on "
    "a wooden table nearby, sparks and forge fire, coils of smoke, heroic-dark mood, "
) + STYLE

payload = json.dumps({
    "prompt": PROMPT,
    "negative": "text, watermark, signature, ui, frame, blurry, deformed hands, extra fingers",
    "width": 1024, "height": 600, "steps": 26, "cfg": 6.5, "model": MODEL,
}).encode()
req = urllib.request.Request(GEN_URL, data=payload,
                            headers={"Content-Type": "application/json"}, method="POST")
print(f"Generating via {MODEL} …")
with urllib.request.urlopen(req, timeout=600) as resp:
    data = json.loads(resp.read())
if "b64" not in data:
    raise SystemExit(f"no b64: {data.get('error', data)}")
OUT.write_bytes(base64.b64decode(data["b64"]))
print(f"Saved {OUT} ({OUT.stat().st_size // 1024} KB)")
