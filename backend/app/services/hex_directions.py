"""
Canonical flat-top hex direction table — single source of truth for PT1.

Grid: flat-top axial, 6 primary directions.
NW and SE do not exist on this grid; they are aliased to W and E respectively.
"""

# Primary 6 directions (dq, dr, canonical Polish name)
# flat-top: E/W move q, N/S move r, NE/SW move both
HEX_DIRECTIONS: list[tuple[int, int, str]] = [
    (1,   0,  "wschód"),
    (-1,  0,  "zachód"),
    (0,   1,  "południe"),
    (0,  -1,  "północ"),
    (1,  -1,  "północny-wschód"),
    (-1,  1,  "południowy-zachód"),
]

# All keyword → (dq, dr) mappings consumed by turn_pipeline and any future module.
# NW → W alias, SE → E alias (no such direction on flat-top; closest real neighbor).
DIRECTION_KEYWORDS: dict[str, tuple[int, int]] = {
    # Polish with diacritics
    "północ":            (0,  -1),
    "północny":          (0,  -1),
    "north":             (0,  -1),
    "południe":          (0,   1),
    "południowy":        (0,   1),
    "south":             (0,   1),
    "wschód":            (1,   0),
    "wschodni":          (1,   0),
    "east":              (1,   0),
    "zachód":            (-1,  0),
    "zachodni":          (-1,  0),
    "west":              (-1,  0),
    "północny-wschód":   (1,  -1),
    "północny wschód":   (1,  -1),
    "northeast":         (1,  -1),
    "południowy-zachód": (-1,  1),
    "południowy zachód": (-1,  1),
    "southwest":         (-1,  1),
    # Aliases — NW→W, SE→E (no such hex neighbor on flat-top grid)
    "północny-zachód":   (-1,  0),
    "północny zachód":   (-1,  0),
    "northwest":         (-1,  0),
    "południowy-wschód": (1,   0),
    "południowy wschód": (1,   0),
    "southeast":         (1,   0),
    # ASCII transliterations (user may type without Polish diacritics)
    "polnoc":            (0,  -1),
    "polnocny":          (0,  -1),
    "poludnie":          (0,   1),
    "poludniowy":        (0,   1),
    "wschod":            (1,   0),
    "zachod":            (-1,  0),
    "polnocny-wschod":   (1,  -1),
    "polnocny wschod":   (1,  -1),
    "poludniowy-zachod": (-1,  1),
    "poludniowy zachod": (-1,  1),
    "polnocny-zachod":   (-1,  0),
    "polnocny zachod":   (-1,  0),
    "poludniowy-wschod": (1,   0),
    "poludniowy wschod": (1,   0),
}
