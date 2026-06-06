"""Voice service reverse-proxy with a swappable backend host.

The game's UI calls ``/voice/*`` (TTS, STT WebSocket, config, voices, healthz)
over the same origin. Historically nginx proxied those straight to a fixed
``voice-service:8300`` container. To let an admin repoint the game at a different
machine (e.g. a GPU box) at runtime, nginx now forwards ``/voice/*`` to this
backend, which proxies to whichever ``voice_hosts`` row is active. Switching the
active host in the admin panel takes effect immediately — no restart.

``/voice/config`` is handled locally (stored in the game DB ``voice_config``
table) so admin-level TTS/STT toggles and speed work regardless of which TTS
engine is active. On POST the config is also forwarded to the upstream (Piper
accepts it; F5-TTS ignores it — both are fine).

``/voice/tts`` automatically injects the stored ``tts_speed`` value when the
caller does not pass an explicit ``speed`` query param.

Two routers:
  * ``public_router`` (``/voice/*``) — unauthenticated, mirrors the voice
    service surface. The player UI hits these.
  * ``admin_router`` (``/api/admin/voice/*``) — admin-token protected host CRUD.
"""

import asyncio
import json
import sqlite3

import httpx
import websockets
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from app.routers.admin import require_admin_token

DB_PATH = "/data/ai_gm.db"
DEFAULT_BASE = "http://voice-service:8300"

public_router = APIRouter(prefix="/voice", tags=["voice-proxy"])
admin_router = APIRouter(prefix="/api/admin/voice", tags=["voice-admin"])


# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _active_base() -> str:
    """Base URL of the active voice host (no trailing slash). Falls back to the
    bundled local service if the table is empty or unreadable."""
    try:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT base_url FROM voice_hosts WHERE is_active = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            return (row["base_url"].rstrip("/") if row else DEFAULT_BASE)
        finally:
            conn.close()
    except Exception:
        return DEFAULT_BASE


# ── Voice config helpers (stored in game DB, not in TTS service) ─────────────

_BOOL_KEYS = {"tts_enabled", "stt_enabled", "vad_filter"}
_INT_KEYS = {"stt_beam_size", "stt_silence_auto_stop_ms", "tts_nfe_step", "tts_seed"}
_FLOAT_KEYS = {"tts_speed", "tts_noise_scale", "tts_cfg_strength", "tts_cross_fade_duration", "tts_sway_sampling_coef"}

# F5-TTS query params → voice_config keys. All injected when not supplied by caller.
_F5_TTS_PARAMS = {
    "speed": "tts_speed",
    "nfe_step": "tts_nfe_step",
    "cfg_strength": "tts_cfg_strength",
    "cross_fade_duration": "tts_cross_fade_duration",
    "sway_sampling_coef": "tts_sway_sampling_coef",
    "seed": "tts_seed",
}


def _get_config_dict() -> dict:
    try:
        conn = _conn()
        try:
            rows = conn.execute("SELECT key, value FROM voice_config").fetchall()
        finally:
            conn.close()
        result = {}
        for row in rows:
            k, v = row["key"], row["value"]
            if k in _BOOL_KEYS:
                result[k] = v == "1"
            elif k in _INT_KEYS:
                try:
                    result[k] = int(v)
                except (ValueError, TypeError):
                    result[k] = v
            elif k in _FLOAT_KEYS:
                try:
                    result[k] = float(v)
                except (ValueError, TypeError):
                    result[k] = v
            else:
                result[k] = v
        return result
    except Exception:
        return {}


def _set_config_values(data: dict) -> None:
    conn = _conn()
    try:
        for k, v in data.items():
            if k in _BOOL_KEYS:
                str_v = "1" if v else "0"
            else:
                str_v = str(v)
            conn.execute(
                "INSERT INTO voice_config (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, str_v),
            )
        conn.commit()
    finally:
        conn.close()


def _get_config_value(key: str, default: str = "") -> str:
    try:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT value FROM voice_config WHERE key = ?", (key,)
            ).fetchone()
        finally:
            conn.close()
        return row["value"] if row else default
    except Exception:
        return default


# ── Public proxy (/voice/*) ─────────────────────────────────────────────────────

@public_router.websocket("/stt")
async def voice_stt_proxy(ws: WebSocket) -> None:
    """Bidirectional WebSocket proxy to the active host's ``/voice/stt``.

    The client streams audio frames (bytes) plus optional ``__end__`` text
    markers; the upstream replies with JSON transcripts. We relay both ways
    until either side closes."""
    await ws.accept()
    base = _active_base()
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/voice/stt"
    try:
        async with websockets.connect(ws_url, max_size=None) as upstream:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await ws.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if msg.get("bytes") is not None:
                            await upstream.send(msg["bytes"])
                        elif msg.get("text") is not None:
                            await upstream.send(msg["text"])
                except WebSocketDisconnect:
                    pass
                finally:
                    await upstream.close()

            async def upstream_to_client() -> None:
                try:
                    async for frame in upstream:
                        if isinstance(frame, bytes):
                            await ws.send_bytes(frame)
                        else:
                            await ws.send_text(frame)
                except Exception:
                    pass

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception as exc:
        try:
            await ws.send_json({"error": f"voice proxy: {exc}"})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


@public_router.get("/config")
async def voice_config_get() -> Response:
    """Return voice config from game DB. Works regardless of active TTS engine."""
    cfg = _get_config_dict()
    return Response(content=json.dumps(cfg), media_type="application/json")


@public_router.post("/config")
async def voice_config_post(request: Request) -> Response:
    """Save voice config to game DB, then forward best-effort to upstream (Piper
    needs this to reload its synthesis params; F5-TTS ignores it — both OK)."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="invalid JSON")
    _set_config_values(data)
    base = _active_base()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(f"{base}/voice/config", json=data)
    except Exception:
        pass  # best-effort; F5-TTS will 404 here which is fine
    cfg = _get_config_dict()
    return Response(content=json.dumps(cfg), media_type="application/json")


@public_router.api_route("/tts", methods=["GET", "POST"])
async def voice_tts_proxy(request: Request) -> Response:
    """Proxy TTS request to active host, injecting stored F5-TTS params when not supplied."""
    base = _active_base()
    params = dict(request.query_params)
    for param, config_key in _F5_TTS_PARAMS.items():
        if param not in params:
            val = _get_config_value(config_key)
            if val:
                params[param] = val
    body = await request.body()
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in ("content-type", "accept")
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            upstream = await client.request(
                request.method,
                f"{base}/voice/tts",
                params=params,
                content=body or None,
                headers=fwd_headers,
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"voice host unreachable: {exc}") from None
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


@public_router.api_route("/{path:path}", methods=["GET", "POST"])
async def voice_http_proxy(path: str, request: Request) -> Response:
    """Forward any non-WS /voice/* request to the active host, preserving query
    params, body, and content type (so WAV, config JSON, etc. pass through)."""
    base = _active_base()
    url = f"{base}/voice/{path}"
    body = await request.body()
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in ("content-type", "accept")
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            upstream = await client.request(
                request.method,
                url,
                params=dict(request.query_params),
                content=body or None,
                headers=fwd_headers,
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"voice host unreachable: {exc}") from None
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


# ── Admin host management (/api/admin/voice/hosts) ──────────────────────────────

class VoiceHostCreate(BaseModel):
    label: str
    base_url: str
    kind: str = "cpu"


class VoiceHostPatch(BaseModel):
    label: str | None = None
    base_url: str | None = None
    kind: str | None = None
    is_active: bool | None = None


async def _probe_health(base_url: str) -> dict:
    """Hit a host's /voice/healthz and return {online, ...payload}."""
    url = base_url.rstrip("/") + "/voice/healthz"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(url)
        if r.status_code == 200:
            data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            return {"online": True, **data}
        return {"online": False, "error": f"HTTP {r.status_code}"}
    except Exception as exc:
        return {"online": False, "error": str(exc)}


def _host_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "label": row["label"],
        "base_url": row["base_url"],
        "kind": row["kind"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


@admin_router.get("/hosts")
async def list_voice_hosts(_: None = Depends(require_admin_token)):
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM voice_hosts ORDER BY id").fetchall()
    finally:
        conn.close()
    hosts = [_host_row_to_dict(r) for r in rows]
    healths = await asyncio.gather(*[_probe_health(h["base_url"]) for h in hosts])
    for h, health in zip(hosts, healths):
        h["health"] = health
    return {"items": hosts}


@admin_router.post("/hosts")
def create_voice_host(req: VoiceHostCreate, _: None = Depends(require_admin_token)):
    base_url = req.base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="base_url must start with http:// or https://")
    conn = _conn()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO voice_hosts (label, base_url, kind, is_active) VALUES (?, ?, ?, 0)",
                (req.label.strip(), base_url, (req.kind or "cpu").strip()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Host with this base_url already exists") from None
        row = conn.execute("SELECT * FROM voice_hosts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _host_row_to_dict(row)
    finally:
        conn.close()


@admin_router.patch("/hosts/{host_id}")
def patch_voice_host(host_id: int, req: VoiceHostPatch, _: None = Depends(require_admin_token)):
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM voice_hosts WHERE id = ?", (host_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Host not found")

        updates, params = [], []
        if req.label is not None:
            updates.append("label = ?"); params.append(req.label.strip())
        if req.base_url is not None:
            bu = req.base_url.strip().rstrip("/")
            if not bu.startswith(("http://", "https://")):
                raise HTTPException(status_code=422, detail="base_url must start with http:// or https://")
            updates.append("base_url = ?"); params.append(bu)
        if req.kind is not None:
            updates.append("kind = ?"); params.append(req.kind.strip())

        if updates:
            params.append(host_id)
            try:
                conn.execute(f"UPDATE voice_hosts SET {', '.join(updates)} WHERE id = ?", params)
            except sqlite3.IntegrityError:
                raise HTTPException(status_code=409, detail="base_url already in use") from None

        # Activating one host deactivates the rest (single active host).
        if req.is_active:
            conn.execute("UPDATE voice_hosts SET is_active = 0")
            conn.execute("UPDATE voice_hosts SET is_active = 1 WHERE id = ?", (host_id,))
        conn.commit()
        updated = conn.execute("SELECT * FROM voice_hosts WHERE id = ?", (host_id,)).fetchone()
        return _host_row_to_dict(updated)
    finally:
        conn.close()


@admin_router.delete("/hosts/{host_id}")
def delete_voice_host(host_id: int, _: None = Depends(require_admin_token)):
    conn = _conn()
    try:
        row = conn.execute("SELECT is_active FROM voice_hosts WHERE id = ?", (host_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Host not found")
        if row["is_active"]:
            raise HTTPException(status_code=409, detail="Nie można usunąć aktywnego hosta — najpierw aktywuj inny.")
        conn.execute("DELETE FROM voice_hosts WHERE id = ?", (host_id,))
        conn.commit()
        return {"ok": True, "deleted_id": host_id}
    finally:
        conn.close()
