import sqlite3
from datetime import datetime, timedelta, UTC

ADMIN_DB = "/data/ai_gm.db"


def _conn():
    c = sqlite3.connect(ADMIN_DB)
    c.row_factory = sqlite3.Row
    return c


def _date_from(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")


# ── Overview ──────────────────────────────────────────────────────────────────

def get_overview(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        # Turns per day
        turns_rows = conn.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM campaign_turns
               WHERE date(created_at) >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()

        # New campaigns per day
        camps_rows = conn.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM campaigns
               WHERE date(created_at) >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()

        # New users per day
        users_rows = conn.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM users
               WHERE date(created_at) >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()

        # Totals
        totals = conn.execute(
            """SELECT
               (SELECT COUNT(*) FROM campaign_turns WHERE date(created_at) >= ?) AS turns,
               (SELECT COUNT(*) FROM campaigns WHERE status='active') AS active_campaigns,
               (SELECT COUNT(*) FROM campaigns WHERE date(created_at) >= ?) AS new_campaigns,
               (SELECT COUNT(*) FROM users WHERE date(created_at) >= ?) AS new_users,
               (SELECT COUNT(*) FROM active_combat WHERE date(created_at) >= ?) AS combats
            """,
            (since, since, since, since),
        ).fetchone()

        return {
            "turns_per_day": [{"day": r["day"], "count": r["count"]} for r in turns_rows],
            "campaigns_per_day": [{"day": r["day"], "count": r["count"]} for r in camps_rows],
            "users_per_day": [{"day": r["day"], "count": r["count"]} for r in users_rows],
            "totals": {
                "turns": totals["turns"],
                "active_campaigns": totals["active_campaigns"],
                "new_campaigns": totals["new_campaigns"],
                "new_users": totals["new_users"],
                "combats": totals["combats"],
            },
        }
    finally:
        conn.close()


# ── Dice ──────────────────────────────────────────────────────────────────────

def get_dice(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT roll_value, actor, COUNT(*) AS count
               FROM combat_turns
               WHERE roll_value IS NOT NULL
                 AND roll_value BETWEEN 1 AND 20
                 AND date(created_at) >= ?
               GROUP BY roll_value, actor""",
            (since,),
        ).fetchall()

        # Build distribution 1..20
        distribution = {i: {"player": 0, "enemy": 0, "total": 0} for i in range(1, 21)}
        for r in rows:
            v = r["roll_value"]
            actor = r["actor"]
            cnt = r["count"]
            if actor == "player":
                distribution[v]["player"] += cnt
            elif actor == "enemy":
                distribution[v]["enemy"] += cnt
            distribution[v]["total"] += cnt

        total_rolls = sum(d["total"] for d in distribution.values())
        crit_count = distribution[20]["total"]
        fumble_count = distribution[1]["total"]
        player_total = sum(d["player"] for d in distribution.values())
        enemy_total = sum(d["enemy"] for d in distribution.values())

        return {
            "distribution": [
                {
                    "value": i,
                    "player": distribution[i]["player"],
                    "enemy": distribution[i]["enemy"],
                    "total": distribution[i]["total"],
                }
                for i in range(1, 21)
            ],
            "total_rolls": total_rolls,
            "player_rolls": player_total,
            "enemy_rolls": enemy_total,
            "crit_count": crit_count,
            "fumble_count": fumble_count,
            "crit_rate": round(crit_count / total_rolls * 100, 1) if total_rolls else 0,
            "fumble_rate": round(fumble_count / total_rolls * 100, 1) if total_rolls else 0,
            "avg_roll": round(
                sum(i * distribution[i]["total"] for i in range(1, 21)) / total_rolls, 2
            ) if total_rolls else 0,
        }
    finally:
        conn.close()


# ── Combat ────────────────────────────────────────────────────────────────────

def get_combat(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        # Combat outcomes
        outcome_rows = conn.execute(
            """SELECT ended_reason, COUNT(*) AS count
               FROM active_combat
               WHERE date(created_at) >= ?
               GROUP BY ended_reason""",
            (since,),
        ).fetchall()

        # Avg rounds per ended combat
        avg_row = conn.execute(
            """SELECT AVG(round) AS avg_rounds, MAX(round) AS max_rounds, COUNT(*) AS total
               FROM active_combat
               WHERE status='ended' AND date(created_at) >= ?""",
            (since,),
        ).fetchone()

        # Top enemies killed (death events where actor is not 'player' = enemy died)
        enemy_rows = conn.execute(
            """SELECT target_name, COUNT(*) AS kills
               FROM combat_turns
               WHERE event_type='death' AND actor != 'player' AND target_name IS NOT NULL
                 AND date(created_at) >= ?
               GROUP BY target_name
               ORDER BY kills DESC LIMIT 10""",
            (since,),
        ).fetchall()

        # Player deaths (death events where actor is 'player')
        player_death_rows = conn.execute(
            """SELECT COALESCE(target_name, actor) AS attacker, COUNT(*) AS count
               FROM combat_turns
               WHERE event_type='death' AND actor='player'
                 AND date(created_at) >= ?
               GROUP BY attacker
               ORDER BY count DESC LIMIT 5""",
            (since,),
        ).fetchall()

        # Total damage dealt / received
        damage_rows = conn.execute(
            """SELECT actor, SUM(damage) AS total_damage, AVG(damage) AS avg_damage
               FROM combat_turns
               WHERE event_type='attack' AND hit=1 AND damage IS NOT NULL
                 AND date(created_at) >= ?
               GROUP BY actor""",
            (since,),
        ).fetchall()

        outcomes = {r["ended_reason"]: r["count"] for r in outcome_rows}
        total_combats = sum(outcomes.values())

        damage_by_actor = {}
        for r in damage_rows:
            damage_by_actor[r["actor"]] = {
                "total": r["total_damage"] or 0,
                "avg": round(r["avg_damage"] or 0, 1),
            }

        return {
            "total_combats": total_combats,
            "outcomes": {
                "victory": outcomes.get("victory", 0),
                "player_dead": outcomes.get("player_dead", 0),
                "fled": outcomes.get("fled", 0),
                "other": sum(v for k, v in outcomes.items() if k not in ("victory", "player_dead", "fled", None)),
            },
            "avg_rounds": round(avg_row["avg_rounds"] or 0, 1),
            "max_rounds": avg_row["max_rounds"] or 0,
            "top_enemies_killed": [
                {"name": r["target_name"], "kills": r["kills"]} for r in enemy_rows
            ],
            "player_killers": [
                {"name": r["attacker"] or "Unknown", "count": r["count"]} for r in player_death_rows
            ],
            "damage": damage_by_actor,
        }
    finally:
        conn.close()


# ── Economy ───────────────────────────────────────────────────────────────────

def get_economy(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        # Top items acquired
        item_rows = conn.execute(
            """SELECT item_key AS name, 'item' AS type, SUM(quantity) AS total
               FROM character_inventory
               WHERE item_key IS NOT NULL AND date(acquired_at) >= ?
               GROUP BY item_key
               UNION ALL
               SELECT weapon_key AS name, 'weapon' AS type, SUM(quantity) AS total
               FROM character_inventory
               WHERE weapon_key IS NOT NULL AND date(acquired_at) >= ?
               GROUP BY weapon_key
               UNION ALL
               SELECT consumable_key AS name, 'consumable' AS type, SUM(quantity) AS total
               FROM character_inventory
               WHERE consumable_key IS NOT NULL AND date(acquired_at) >= ?
               GROUP BY consumable_key
               ORDER BY total DESC LIMIT 15""",
            (since, since, since),
        ).fetchall()

        # Items by source
        source_rows = conn.execute(
            """SELECT COALESCE(source, 'unknown') AS src, COUNT(*) AS count
               FROM character_inventory
               WHERE date(acquired_at) >= ?
               GROUP BY src ORDER BY count DESC""",
            (since,),
        ).fetchall()

        # Total gold by campaign
        gold_rows = conn.execute(
            """SELECT c.title, ch.gold, ch.gold_gp
               FROM characters ch
               JOIN campaigns c ON c.id = ch.campaign_id
               WHERE ch.gold > 0 OR ch.gold_gp > 0
               ORDER BY (ch.gold + ch.gold_gp * 100) DESC LIMIT 10""",
        ).fetchall()

        # Totals
        totals = conn.execute(
            """SELECT
               COUNT(*) AS total_items,
               SUM(quantity) AS total_qty
               FROM character_inventory
               WHERE date(acquired_at) >= ?""",
            (since,),
        ).fetchone()

        return {
            "top_items": [
                {"name": r["name"], "type": r["type"], "total": r["total"]}
                for r in item_rows
            ],
            "by_source": [
                {"source": r["src"], "count": r["count"]} for r in source_rows
            ],
            "gold_leaders": [
                {
                    "campaign": r["title"],
                    "gold_sp": r["gold"],
                    "gold_gp": r["gold_gp"],
                }
                for r in gold_rows
            ],
            "totals": {
                "items_acquired": totals["total_items"] or 0,
                "quantity_total": totals["total_qty"] or 0,
            },
        }
    finally:
        conn.close()
