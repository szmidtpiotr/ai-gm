import os
import time
import sqlite3
from typing import Any

import httpx
from fastmcp import FastMCP

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
STORY_DB_PATH = os.getenv("STORY_DB_PATH", "/var/lib/ai-gm-db/ai_gm.db")
PORT = int(os.getenv("PORT", "8001"))

mcp = FastMCP("ai-gm-debug-platform")


def _now_ns() -> int:
    return int(time.time() * 1_000_000_000)


def _loki_query_range(query: str, start_ns: int, end_ns: int, limit: int) -> dict[str, Any]:
    url = f"{LOKI_URL}/loki/api/v1/query_range"
    # step is required by Loki; for log search it can be coarse.
    params = {
        "query": query,
        "start": str(start_ns),
        "end": str(end_ns),
        "step": "1s",
        "limit": str(limit),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, params=params)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Loki query failed: {payload}")
    return payload["data"]


@mcp.tool()
def loki_query(query: str, since_minutes: int = 60, limit: int = 200) -> dict[str, Any]:
    """
    Query Loki logs using a raw Loki `query` expression (example: {service="backend"} |= "request_complete").

    Returns parsed streams with `stream` labels and `values` (timestamp_ns, line).
    Read-only tool intended for external log analysis via Perplexity MCP connectors.
    """
    if since_minutes < 1:
        since_minutes = 1
    end_ns = _now_ns()
    start_ns = end_ns - int(since_minutes * 60 * 1_000_000_000)
    data = _loki_query_range(query=query, start_ns=start_ns, end_ns=end_ns, limit=limit)

    streams = []
    for stream in data.get("result", []):
        labels = stream.get("stream", {})
        values = []
        for ts_str, line in stream.get("values", []) or []:
            try:
                ts_ns = int(float(ts_str))
            except Exception:
                ts_ns = None
            values.append({"timestamp_ns": ts_ns, "line": line})
        streams.append({"stream": labels, "values": values})

    return {"streams": streams, "query": query, "since_minutes": since_minutes}


@mcp.tool()
def campaign_story(campaign_id: int, limit_turns: int = 50) -> dict[str, Any]:
    """
    Return a slice of the campaign story (turns) from the game's SQLite DB snapshot.
    Read-only tool intended for external log analysis via Perplexity MCP connectors.
    """
    if limit_turns < 1:
        limit_turns = 1

    conn = sqlite3.connect(STORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, title, system_id, model_id, language, mode, status, created_at
            FROM campaigns
            WHERE id = ?
            """,
            (campaign_id,),
        ).fetchone()
        if not row:
            return {"campaign": None, "turns": []}

        turns = conn.execute(
            """
            SELECT
              t.turn_number,
              t.route,
              t.user_text,
              t.assistant_text,
              ch.name AS character_name,
              t.created_at
            FROM campaign_turns t
            LEFT JOIN characters ch ON ch.id = t.character_id
            WHERE t.campaign_id = ?
            ORDER BY t.turn_number ASC
            LIMIT ?
            """,
            (campaign_id, limit_turns),
        ).fetchall()

        return {
            "campaign": dict(row),
            "turns": [dict(t) for t in turns],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    # Expose MCP over Streamable HTTP for Perplexity "Custom connector" Remote MCP.
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)

