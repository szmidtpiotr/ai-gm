#!/usr/bin/env python3
"""#1543 — export two real map fragments (Czarnobór + Kresy) for the Mapa 2.0
makieta comparison page (frontend/makieta.html).

Output: frontend/makieta_data.json
  { "<region>": {label, window:{qmin,qmax,rmin,rmax}, hexes:[[q,r,type],...],
                 counts:{type:n}} }

Czarnobór window is fixed on the trakt (road ~q75) + Szept Koron belt.
Kresy window is auto-picked: the WxH window with the most distinct terrain types
(so the makieta shows coast/sea/town variety, not a monoculture).
"""
import json
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ROOT / "data" / "regions"
OUT = ROOT / "frontend" / "makieta_data.json"

WIN_W, WIN_H = 22, 20  # cols (q) x rows (r) — ~ a screenful fragment


def load(region):
    d = json.load(open(REGIONS / f"region_{region}.json"))
    return d["label"], d["hexes"]


def slice_window(hexes, qmin, qmax, rmin, rmax):
    out = []
    for h in hexes:
        q, r = h["q"], h["r"]
        if qmin <= q <= qmax and rmin <= r <= rmax:
            out.append([q, r, h["hex_type"]])
    counts = collections.Counter(t for _, _, t in out)
    return out, dict(counts.most_common())


def best_window(hexes):
    """Pick the WIN_W x WIN_H window maximizing distinct terrain types."""
    qs = [h["q"] for h in hexes]
    rs = [h["r"] for h in hexes]
    q0, q1, r0, r1 = min(qs), max(qs), min(rs), max(rs)
    grid = {(h["q"], h["r"]): h["hex_type"] for h in hexes}
    best = None
    for qa in range(q0, q1 - WIN_W + 2, 2):
        for ra in range(r0, r1 - WIN_H + 2, 2):
            types = set()
            n = 0
            for q in range(qa, qa + WIN_W):
                for r in range(ra, ra + WIN_H):
                    t = grid.get((q, r))
                    if t:
                        types.add(t); n += 1
            # prefer variety, then density
            score = (len(types), n)
            if best is None or score > best[0]:
                best = (score, qa, ra)
    _, qa, ra = best
    return qa, qa + WIN_W - 1, ra, ra + WIN_H - 1


def main():
    data = {}

    # Czarnobór — fixed on the trakt + hub belt
    label, hexes = load("czarnobor")
    win = (66, 87, -14, 5)
    cells, counts = slice_window(hexes, *win)
    data["czarnobor"] = {
        "label": label, "raster": "/showcase/assets/img/kraina-czarnobor.png",
        "window": dict(zip(("qmin", "qmax", "rmin", "rmax"), win)),
        "hexes": cells, "counts": counts,
    }
    print("czarnobor", win, len(cells), counts)

    # Kresy — auto-pick most varied window
    label, hexes = load("kresy")
    win = best_window(hexes)
    cells, counts = slice_window(hexes, *win)
    data["kresy"] = {
        "label": label, "raster": "/showcase/assets/img/kraina-kresy.png",
        "window": dict(zip(("qmin", "qmax", "rmin", "rmax"), win)),
        "hexes": cells, "counts": counts,
    }
    print("kresy", win, len(cells), counts)

    OUT.write_text(json.dumps(data, ensure_ascii=False))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
