"""Shared runtime constants.

R9 (#1249): single source of truth for the default world region. Before this,
the literal "kresy" was scattered as a fallback across ~10 services/routers, so a
future rename (or a second live region becoming the default) meant hunting every
copy. Import DEFAULT_REGION instead of hardcoding the string.

NOTE: SQL DDL defaults (e.g. `world_hexes.region TEXT NOT NULL DEFAULT 'kresy'`)
and the `world_regions` seed row keep their literal — those are schema/data, not
a Python fallback, and must stay stable across migration replay.
"""

# The starting and default world region key. Kresy is the only live region today
# (see world_regions seed); other krainy are DLC stubs (FAZA RM).
DEFAULT_REGION = "kresy"
