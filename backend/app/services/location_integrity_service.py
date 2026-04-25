import sqlite3

from app.core.logging import get_logger

DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_campaign_location(campaign_id: int, location_id: int) -> dict:
    with _conn() as conn:
        camp = conn.execute("SELECT id FROM campaigns WHERE id = ? LIMIT 1", (campaign_id,)).fetchone()
        if not camp:
            raise LookupError("campaign_not_found")
        loc = conn.execute(
            "SELECT id, key, label FROM game_locations WHERE id = ? AND is_active = 1 LIMIT 1",
            (location_id,),
        ).fetchone()
        if not loc:
            raise LookupError("location_not_found")
        conn.execute(
            "UPDATE campaigns SET current_location_id = ? WHERE id = ?",
            (int(loc["id"]), campaign_id),
        )
        conn.commit()
        logger.info(
            "location_integrity_campaign_location_updated",
            campaign_id=campaign_id,
            location_id=int(loc["id"]),
            location_key=str(loc["key"]),
        )
        return {
            "campaign_id": campaign_id,
            "current_location_id": int(loc["id"]),
            "location_key": str(loc["key"]),
            "location_label": str(loc["label"]),
        }


def update_campaign_location_by_key(campaign_id: int, location_key: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (location_key,),
        ).fetchone()
    if not row:
        raise LookupError("location_not_found")
    return update_campaign_location(campaign_id, int(row["id"]))


def log_integrity_violation(
    campaign_id: int,
    character_id: int | None,
    attempted_move: str,
    current_location_key: str | None,
    reason_blocked: str | None,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO location_integrity_log
            (campaign_id, character_id, attempted_move, current_location_key, reason_blocked)
            VALUES (?, ?, ?, ?, ?)
            """,
            (campaign_id, character_id, attempted_move, current_location_key, reason_blocked),
        )
        conn.commit()
        logger.info(
            "location_integrity_violation_logged",
            campaign_id=campaign_id,
            character_id=character_id,
            attempted_move=attempted_move,
            current_location_key=current_location_key or "",
            reason_blocked=reason_blocked or "",
        )
