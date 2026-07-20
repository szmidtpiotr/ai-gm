#!/usr/bin/env python3
"""SG-5c — raport asortymentu WSZYSTKICH kupców w grze (stary vs nowy dobór).

Nie zmienia danych. Dla każdego aktywnego sklepu liczy listę towaru, którą
zobaczy gracz, i pokazuje: profil roli, tier lokacji, liczbę pozycji oraz
zakres cen. Z flagą --diff dokłada wynik STAREGO algorytmu (najtańsze wg roli),
żeby było widać, co się realnie zmieniło.

    docker cp scripts/report_shop_stock.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/report_shop_stock.py --diff
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _old_stock(conn: sqlite3.Connection, npc: sqlite3.Row) -> list[dict]:
    """Algorytm sprzed SG-5c: N NAJTAŃSZYCH pozycji wg roli (do porównania)."""
    from app.services.shop_service import _HEALER_KEYWORDS

    def cheapest(kind: str, limit: int) -> list[str]:
        return [
            r[0] for r in conn.execute(
                "SELECT key FROM game_items WHERE kind = ? AND is_active = 1 "
                "AND COALESCE(price_gp,0) > 0 ORDER BY price_gp ASC, key ASC LIMIT ?",
                (kind, limit),
            ).fetchall()
        ]

    key, label = str(npc["key"] or "").lower(), str(npc["label"] or "").lower()
    if int(npc["is_crafter"] or 0) == 1:
        out = [{"type": "weapon", "key": k} for k in cheapest("weapon", 4)]
        out += [{"type": "armor", "key": k} for k in cheapest("armor", 3)]
        return out
    if any(w in key or w in label for w in _HEALER_KEYWORDS):
        return [{"type": "consumable", "key": k} for k in cheapest("consumable", 6)]
    out = [{"type": "consumable", "key": k} for k in cheapest("consumable", 3)]
    out += [{"type": "item", "key": k} for k in cheapest("item", 3)]
    out += [{"type": "weapon", "key": k} for k in cheapest("weapon", 1)]
    return out


def _span(conn: sqlite3.Connection, entries: list[dict]) -> str:
    prices = []
    for e in entries:
        row = conn.execute("SELECT price_gp FROM game_items WHERE key = ?", (e["key"],)).fetchone()
        if row and row[0]:
            prices.append(int(row[0]))
    return f"{min(prices)}–{max(prices)} gp" if prices else "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    ap.add_argument("--diff", action="store_true")
    a = ap.parse_args()

    from app.services import shop_service

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, key, label, npc_type, is_crafter, crafter_type, shop_inventory_json "
        "FROM npcs WHERE is_shop = 1 AND is_active = 1 ORDER BY key"
    ).fetchall()

    explicit = dynamic = empty = 0
    print(f"{'kupiec':34s} {'profil':8s} {'tier':4s} {'poz':>3s}  zakres cen        źródło")
    print("-" * 100)
    for npc in rows:
        has_explicit = bool(json.loads(npc["shop_inventory_json"] or "[]"))
        entries = shop_service._effective_shop_entries(conn, npc)
        profile = shop_service._shop_profile_for_npc(npc)
        tier = shop_service._npc_home_tier(conn, npc)
        src = "jawny" if has_explicit else "domyślny"
        explicit += has_explicit
        dynamic += not has_explicit
        if not entries:
            empty += 1
        print(f"{(npc['label'] or npc['key'])[:33]:34s} {profile:8s} {tier:^4d} "
              f"{len(entries):3d}  {_span(conn, entries):17s} {src}")
        if a.diff and not has_explicit:
            old = _old_stock(conn, npc)
            print(f"{'':34s} {'':8s} {'':4s} {len(old):3d}  {_span(conn, old):17s} "
                  f"(przed SG-5c)")

    print("-" * 100)
    print(f"sklepów: {len(rows)} | jawny asortyment: {explicit} | "
          f"dobierany automatycznie: {dynamic} | PUSTYCH: {empty}")
    conn.close()
    return 1 if empty else 0


if __name__ == "__main__":
    sys.exit(main())
