import sqlite3
from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.llm_service import generate_chat
from app.services.location_integrity_config import get_effective_flag

DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover
    fuzz = None


@dataclass
class ValidationResult:
    allowed: bool
    resolved_location_id: int | None
    is_new_location: bool
    block_reason: str | None


@dataclass
class _Loc:
    id: int
    key: str
    label: str
    parent_id: int | None
    location_type: str


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _score(a: str, b: str) -> int:
    if not a or not b:
        return 0
    if fuzz is None:
        return 100 if a.strip().lower() == b.strip().lower() else 0
    return int(fuzz.ratio(a.strip().lower(), b.strip().lower()))


def _ask_same_location(a: str, b: str, llm_config: dict[str, str] | None = None) -> bool:
    out = generate_chat(
        messages=[
            {"role": "system", "content": "Odpowiedz wyłącznie: TAK albo NIE."},
            {"role": "user", "content": f"Czy '{a}' to ta sama lokalizacja co '{b}'? TAK/NIE"},
        ],
        llm_config=llm_config,
    )
    return (out or "").strip().upper().startswith("TAK")


def _load_locations(conn: sqlite3.Connection) -> list[_Loc]:
    rows = conn.execute(
        """
        SELECT id, key, label, parent_id, location_type
        FROM game_locations
        WHERE is_active = 1
        """
    ).fetchall()
    return [
        _Loc(
            id=int(r["id"]),
            key=str(r["key"]),
            label=str(r["label"]),
            parent_id=r["parent_id"],
            location_type=str(r["location_type"] or "macro"),
        )
        for r in rows
    ]


def _get_current_location(conn: sqlite3.Connection, campaign_id: int) -> _Loc | None:
    row = conn.execute(
        """
        SELECT gl.id, gl.key, gl.label, gl.parent_id, gl.location_type
        FROM campaigns c
        LEFT JOIN game_locations gl ON gl.id = c.current_location_id
        WHERE c.id = ?
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    if not row or row["id"] is None:
        return None
    return _Loc(
        id=int(row["id"]),
        key=str(row["key"]),
        label=str(row["label"]),
        parent_id=row["parent_id"],
        location_type=str(row["location_type"] or "macro"),
    )


def validate_move(
    campaign_id: int,
    intent,
    llm_config: dict[str, str] | None = None,
) -> ValidationResult:
    with _conn() as conn:
        current = _get_current_location(conn, campaign_id)
        locations = _load_locations(conn)

    if not intent or not str(getattr(intent, "target_label", "")).strip():
        logger.info("location_integrity_validate_rejected_empty_target", campaign_id=campaign_id)
        return ValidationResult(False, None, False, "empty_target")

    target_label = str(intent.target_label).strip()
    action = str(getattr(intent, "action", "") or "").strip().lower()

    best: _Loc | None = None
    best_score = -1
    for loc in locations:
        s = _score(target_label, loc.label)
        if s > best_score:
            best = loc
            best_score = s

    matched = best is not None and best_score >= 80
    if not matched and best is not None and best_score > 0:
        try:
            matched = _ask_same_location(target_label, best.label, llm_config=llm_config)
        except Exception:
            matched = False

    if matched and best is not None:
        if not get_effective_flag("location_integrity_enabled", campaign_id):
            logger.info(
                "location_integrity_validate_bypass_flag_disabled",
                campaign_id=campaign_id,
                target_label=target_label,
                resolved_key=best.key,
                best_score=int(best_score),
            )
            return ValidationResult(True, best.id, False, None)
        # Sub -> sub same parent always allowed.
        if current and current.location_type == "sub" and best.location_type == "sub":
            if current.parent_id == best.parent_id:
                logger.info(
                    "location_integrity_validate_allowed_sub_same_parent",
                    campaign_id=campaign_id,
                    current_key=current.key,
                    target_key=best.key,
                    best_score=int(best_score),
                )
                return ValidationResult(True, best.id, False, None)

        # Macro/sub -> other macro = soft block.
        if current and current.location_type in {"sub", "macro"} and best.location_type == "macro":
            if current.id != best.id:
                logger.info(
                    "location_integrity_validate_blocked_travel_required",
                    campaign_id=campaign_id,
                    current_key=current.key,
                    target_key=best.key,
                    best_score=int(best_score),
                )
                return ValidationResult(False, best.id, False, "travel_required")
        logger.info(
            "location_integrity_validate_allowed_match",
            campaign_id=campaign_id,
            target_key=best.key,
            best_score=int(best_score),
        )
        return ValidationResult(True, best.id, False, None)

    if action == "create":
        logger.info(
            "location_integrity_validate_allowed_create",
            campaign_id=campaign_id,
            target_label=target_label,
            best_score=int(best_score),
        )
        return ValidationResult(True, None, True, None)
    logger.info(
        "location_integrity_validate_blocked_unknown_location",
        campaign_id=campaign_id,
        target_label=target_label,
        best_score=int(best_score),
    )
    return ValidationResult(False, None, True, "unknown_location_without_create")
