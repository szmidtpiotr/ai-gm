"""F21 (#481) — World State snapshot diff utility.

compute_snapshot_diff(snap_a, snap_b) compares two snapshot JSON dicts.
Snapshots have shape: {"section_name": {"entry_key": {...value...}, ...}, ...}

Returns {"added": [...], "removed": [...], "changed": [...]}
Each entry: {"key": "section.entry_key", "before": ..., "after": ...}
"""
from __future__ import annotations


def flatten_snapshot(snap: dict) -> dict[str, object]:
    """Convert nested snapshot dict to flat 'section.key' → value map.

    Only processes sections that are dicts of dicts. Scalar sections are included
    as-is under their top-level key.
    """
    flat: dict[str, object] = {}
    if not isinstance(snap, dict):
        return flat
    for section, content in snap.items():
        if isinstance(content, dict):
            for key, value in content.items():
                flat[f"{section}.{key}"] = value
        else:
            flat[section] = content
    return flat


def compute_snapshot_diff(snap_a: dict, snap_b: dict) -> dict:
    """Return diff between two world state snapshots.

    Returns dict with:
      added   — keys in B not in A
      removed — keys in A not in B
      changed — keys in both where value differs (with before/after)
    """
    flat_a = flatten_snapshot(snap_a or {})
    flat_b = flatten_snapshot(snap_b or {})

    keys_a = set(flat_a.keys())
    keys_b = set(flat_b.keys())

    added = [
        {"key": k, "after": flat_b[k]}
        for k in sorted(keys_b - keys_a)
    ]
    removed = [
        {"key": k, "before": flat_a[k]}
        for k in sorted(keys_a - keys_b)
    ]
    changed = []
    for k in sorted(keys_a & keys_b):
        val_a = flat_a[k]
        val_b = flat_b[k]
        if val_a != val_b:
            changed.append({"key": k, "before": val_a, "after": val_b})

    return {"added": added, "removed": removed, "changed": changed}
