import json
import sqlite3

DB_PATH = "/data/ai_gm.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _to_bool(v: object, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def get_effective_flag(key: str, campaign_id: int) -> bool:
    """
    Merge logic:
    campaigns.session_flags[key] ?? game_config_meta[key]
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT session_flags FROM campaigns WHERE id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row and row["session_flags"]:
            try:
                data = json.loads(str(row["session_flags"]))
                if isinstance(data, dict) and key in data:
                    return _to_bool(data.get(key), default=False)
            except json.JSONDecodeError:
                pass

        meta = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (key,),
        ).fetchone()
        if not meta:
            return False
        return _to_bool(meta["value"], default=False)
