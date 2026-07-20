"""
Admin Test Runner API (Phase 9A-5). Active only when AI_TEST_MODE=1 (see main.py).
"""

from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.models import _curate_narration_models
from app.core.logging import get_logger
from app.services.admin_auth import verify_admin_token
from app.services.llm_service import generate_chat, get_health

logger = get_logger(__name__)

router = APIRouter(prefix="/test_runner", tags=["test_runner"])

_AI_GM_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SCENARIOS = _AI_GM_ROOT / "ai_test_agent" / "scenarios"


def _scenarios_dir() -> Path:
    raw = (os.getenv("AI_TEST_SCENARIOS_DIR") or "").strip()
    return Path(raw) if raw else _DEFAULT_SCENARIOS


def _agent_url() -> str:
    return (os.getenv("AI_TEST_AGENT_URL") or "http://127.0.0.1:4000").rstrip("/")


def _is_test_agent_unreachable(exc: BaseException) -> bool:
    s = f"{type(exc).__name__}: {exc!s}"
    if any(
        x in s
        for x in (
            "Connection refused",
            "Errno 111",
            "Name or service not known",
            "getaddrinfo failed",
        )
    ):
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (111, 99, 101, -2):
        return True
    c = exc.__cause__
    if c is not None and c is not exc:
        return _is_test_agent_unreachable(c)
    return False


def _format_test_agent_error(agent_base: str, exc: BaseException) -> str:
    base = (agent_base or "http://127.0.0.1:4000").rstrip("/")
    raw = f"{type(exc).__name__}: {exc!s}"
    if not _is_test_agent_unreachable(exc):
        return raw
    out = [
        f"{raw} — brak usługi agenta testowego (Node/Playwright) pod {base}.",
        "Docker dev (zalecane): `docker compose -f docker-compose.dev.yml up -d --build test-agent` — backend łączy się z usługą `test-agent:4000.",
        "Bez agenta w kontenerze, na hoście: `cd ai_test_agent && AGENT_PORT=4000 npm run agent:server`.",
    ]
    if "test-agent" not in base and (
        "host.docker.internal" in base
        or "127.0.0.1" in base
    ):
        out.append(
            "Prawdopodobne nadpisanie `AI_TEST_AGENT_URL` w pliku `.env` (lub w shellu). Usuń tę linię albo ustaw "
            "`AI_TEST_AGENT_URL=http://test-agent:4000` gdy używasz usługi `test-agent` z docker-compose; "
            "`http://host.docker.internal:4000` tylko gdy `npm run agent:server` jest uruchomiony na maszynie hosta."
        )
    return " ".join(out)


def require_admin_bearer_or_query(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> None:
    raw: str | None = None
    if authorization and authorization.startswith("Bearer "):
        raw = authorization.removeprefix("Bearer ").strip()
    elif token:
        raw = token.strip()
    if not raw or not verify_admin_token(raw):
        raise HTTPException(status_code=401, detail="Invalid admin token")


SCENARIO_SYSTEM_PROMPT = """Jesteś asystentem do pisania testów AI dla gry RPG.
Kiedy użytkownik opisze test, generujesz YAML w formacie:
  name, goal, persona, constraints[], success_criteria{}, max_steps, timeouts.
Najpierw zadaj pytania precyzujące (persona, agresywność, oczekiwany wynik).
Gdy masz kompletne dane, zwróć YAML w bloku ```yaml ... ``` i ustaw ready: true w JSON response.
Format odpowiedzi JSON: {"reply": str, "yaml": str|null, "ready": bool}
Odpowiedz TYLKO jednym obiektem JSON (bez markdown wokół), chyba że użytkownik prosi o wyjaśnienie — wtedy reply może być dłuższe, ale JSON musi być parsowalny na końcu."""


class LlmOverrideBody(BaseModel):
    """Opcjonalna konfiguracja LLM dla planera (nadpisuje env / runtime na czas tego requestu)."""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class GenerateScenarioReq(BaseModel):
    message: str
    history: list[dict[str, Any]] = Field(default_factory=list)
    llm: LlmOverrideBody | None = None


class TestRunnerLlmModelsReq(BaseModel):
    """Lista modeli z podanego hosta (Ollama / OpenAI-compatible) — do panelu Test Runner."""

    provider: str = Field(default="ollama")
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    show_all: bool = Field(default=False)


class AgentPlannerLlm(BaseModel):
    """Ten sam kształt co `getLlmPayloadForRequest()` — planer kroków ai_test_agent (Ollama/OpenAI)."""

    provider: str = Field(default="ollama")
    base_url: str = Field(default="")
    model: str = Field(default="")
    api_key: str | None = Field(default=None)


class AgentPlannerPingReq(BaseModel):
    agent_planner_llm: AgentPlannerLlm | None = None


class StartReq(BaseModel):
    yaml: str = Field(..., description="JSON lub YAML scenariusza testowego")
    agent_planner_llm: AgentPlannerLlm | None = Field(
        default=None,
        description="Opcjonalnie: nadpisanie LLM planera (jak w panelu); brak = env w kontenerze agenta",
    )


class SaveScenarioReq(BaseModel):
    filename: str
    content: str


_runs: dict[str, dict[str, Any]] = {}
_runs_lock = threading.Lock()


def _any_running() -> bool:
    with _runs_lock:
        for s in _runs.values():
            if s.get("status") == "RUNNING":
                return True
    return False


def _get_running_run_id() -> str | None:
    """Zwraca run_id aktualnie działającego testu lub None."""
    with _runs_lock:
        for run_id, s in _runs.items():
            if s.get("status") == "RUNNING":
                return run_id
    return None


def _set_run_cancelled(run_id: str) -> bool:
    """Oznacza run jako cancelled (wewnętrznie). Zwraca True jeśli run był RUNNING."""
    with _runs_lock:
        st = _runs.get(run_id)
        if st is None:
            return False
        if st.get("status") == "RUNNING":
            st["status"] = "CANCELLED"
            st["cancelled_at"] = time.time()
            return True
        return False


def _parse_scenario_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="empty scenario")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Niepoprawny JSON/YAML: {e}") from e
    if not isinstance(loaded, dict):
        raise HTTPException(status_code=400, detail="Scenariusz musi być obiektem (JSON/YAML map)")
    return loaded


def _normalize_agent_runner_base_url(raw: str, provider: str) -> str:
    """Jak normalizeLlmBaseUrlInput w admin test_runner.js — baza przed /v1/chat/completions."""
    value = (raw or "").strip().rstrip("/")
    pl = (provider or "ollama").strip().lower()
    low = value.lower()
    if pl == "openai":
        for suffix in ("/v1/chat/completions", "/chat/completions", "/v1/models", "/v1"):
            if low.endswith(suffix):
                value = value[: -len(suffix)].rstrip("/")
                low = value.lower()
                break
    else:
        for suffix in ("/api/chat", "/api/tags", "/api"):
            if low.endswith(suffix):
                value = value[: -len(suffix)].rstrip("/")
                low = value.lower()
                break
    return value.rstrip("/")


def _agent_planner_llm_to_internal(req: AgentPlannerLlm | None) -> dict[str, Any] | None:
    """
    JSON dla Node: llm_api_url (OpenAI-compat), model, opcjonalnie klucz.
    None = agent używa wyłącznie LLM_* z env kontenera (np. LLM_API_URL do zewn. API produkcyjnego).
    """
    if req is None:
        return None
    provider = (req.provider or "ollama").strip().lower()
    base = _normalize_agent_runner_base_url(req.base_url or "", provider)
    if not base:
        base = "http://127.0.0.1:11434" if provider == "ollama" else ""
    if not base:
        return None
    chat_url = f"{base}/v1/chat/completions"
    model = (req.model or "").strip() or "gemma4:e4b"
    out: dict[str, Any] = {"llm_api_url": chat_url, "llm_model": model}
    if req.api_key is not None:
        out["llm_api_key"] = str(req.api_key)
    return out


def _extract_json_object(text: str) -> dict[str, Any]:
    s = (text or "").strip()
    start = s.find("{")
    if start < 0:
        raise ValueError("brak poprawnego JSON w odpowiedzi LLM")
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(s, start)
    except json.JSONDecodeError as e:
        raise ValueError("brak poprawnego JSON w odpowiedzi LLM") from e
    if not isinstance(obj, dict):
        raise ValueError("odpowiedź LLM musi być obiektem JSON")
    return obj


def _stub_scenario_response(
    message: str, history: list, *, reply_prefix: str = ""
) -> dict[str, Any]:
    n_user = sum(1 for h in history if h.get("role") == "user")
    if n_user < 1:
        return {
            "reply": f'{reply_prefix}Opisz proszę cel testu, oczekiwany wynik oraz ograniczenia (persona, maks. kroki).',
            "yaml": None,
            "ready": False,
        }
    yaml_blob = "\n".join(
        [
            'name: "admin_stub_scenario"',
            'goal: "Weryfikacja ścieżki użytkownika"',
            "max_steps: 8",
            "total_timeout_ms: 120000",
        ]
    )
    return {
        "reply": f'{reply_prefix}Oto szkic scenariusza w YAML — możesz go edytować przed uruchomieniem.',
        "yaml": yaml_blob,
        "ready": True,
    }


def _llm_dict_from_body(llm: LlmOverrideBody | None) -> dict[str, str] | None:
    if llm is None:
        return None
    d: dict[str, str] = {}
    for key in ("provider", "base_url", "model", "api_key"):
        v = getattr(llm, key, None)
        if v is not None and str(v).strip() != "":
            d[key] = str(v).strip()
    return d if d else None


def _is_llm_network_error(exc: BaseException) -> bool:
    """Brak Ollamy / zły host / timeout połączenia z LLM."""
    msg = f"{type(exc).__name__}: {exc!s}"
    needles = (
        "Connection refused",
        "Errno 111",
        "Name or service not known",
        "ConnectError",
        "ReadTimeout",
        "ConnectTimeout",
        "timed out",
        "Connection reset",
        "Temporary failure in name resolution",
    )
    if any(n in msg for n in needles):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 111:
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)):
        return True
    c = exc.__cause__
    if c is not None and c is not exc:
        return _is_llm_network_error(c)
    return False


@router.post("/generate_scenario", dependencies=[Depends(require_admin_bearer_or_query)])
def post_generate_scenario(req: GenerateScenarioReq) -> dict[str, Any]:
    if os.getenv("AI_TEST_STUB_SCENARIO") == "1":
        return _stub_scenario_response(req.message, req.history)
    llm_cfg = _llm_dict_from_body(req.llm)
    # Szkic (env) — chyba że klient poda własne `llm` w body (Ollama / OpenAI w panelu).
    if llm_cfg is None and os.getenv("AI_TEST_STUB_LLM") == "1":
        return _stub_scenario_response(req.message, req.history)

    messages: list[dict] = [{"role": "system", "content": SCENARIO_SYSTEM_PROMPT}]
    for h in req.history:
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": req.message})

    try:
        raw = generate_chat(messages, model=None, llm_config=llm_cfg)
    except Exception as e:
        if _is_llm_network_error(e):
            logger.warning("test_runner_generate_llm_unavailable", error=str(e))
            return _stub_scenario_response(
                req.message,
                req.history,
                reply_prefix="[Ollama/LLM niedostępna — tryb szkicu] ",
            )
        logger.error("test_runner_generate_failed", error=str(e))
        raise HTTPException(
            status_code=502, detail=f"LLM: {e!s}"[:2000]
        ) from e

    try:
        out = _extract_json_object(raw)
    except ValueError:
        return {"reply": raw, "yaml": None, "ready": False}

    return {
        "reply": str(out.get("reply", "")),
        "yaml": out.get("yaml") if "yaml" in out else None,
        "ready": bool(out.get("ready", False)),
    }


@router.post("/llm_models", dependencies=[Depends(require_admin_bearer_or_query)])
def post_llm_models(req: TestRunnerLlmModelsReq) -> dict[str, Any]:
    provider = (req.provider or "ollama").strip().lower() or "ollama"
    cfg: dict[str, str] = {"provider": provider}
    b = (req.base_url or "").strip()
    if b:
        cfg["base_url"] = b
    a = (req.api_key or "").strip()
    if a:
        cfg["api_key"] = a
    h = get_health(cfg)
    models: list[str] = list(h.get("models") or [])
    if provider == "openai" and not req.show_all:
        models = _curate_narration_models("openai", models)
    return {
        "reachable": bool(h.get("reachable")),
        "models": models,
        "error": h.get("error"),
        "provider": h.get("provider", provider),
        "base_url": h.get("base_url"),
    }


def _httpx_serve_agent_stream(
    run_id: str,
    scenario: dict[str, Any],
    q: "queue.Queue[Any]",
    agent: str,
    planner_internal: dict[str, Any] | None,
) -> None:
    status_set = "DONE"
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=15.0, read=None, write=30.0, pool=5.0)) as client:
            body: dict[str, Any] = {"scenario": scenario, "headed": False, "run_id": run_id}
            if planner_internal is not None:
                body["planner_llm"] = planner_internal
            with client.stream("POST", f"{agent}/agent/run", json=body) as resp:
                if resp.status_code != 200:
                    try:
                        body = (resp.read() or b"")[:2000]
                    except Exception:
                        body = b""
                    err_text = body.decode("utf-8", errors="replace")
                    q.put(
                        {
                            "done": True,
                            "success": False,
                            "reason": "agent_http",
                            "error": f"HTTP {resp.status_code}: {err_text}",
                        }
                    )
                    status_set = "ERROR"
                    return
                for line in resp.iter_lines():
                    if line is None:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    try:
                        obj: Any = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    q.put(obj)
                    if isinstance(obj, dict) and obj.get("done"):
                        with _runs_lock:
                            st = _runs.get(run_id)
                            if st is not None:
                                st["result"] = obj
    except Exception as e:
        logger.error("test_runner_agent_stream_error", run_id=run_id, error=str(e))
        q.put(
            {
                "done": True,
                "success": False,
                "reason": "error",
                "error": _format_test_agent_error(agent, e),
            }
        )
        status_set = "ERROR"
    finally:
        with _runs_lock:
            st = _runs.get(run_id)
            if st is not None and st.get("status") == "RUNNING":
                st["status"] = status_set
        q.put(None)


@router.get("/agent_health", dependencies=[Depends(require_admin_bearer_or_query)])
def get_agent_health() -> dict[str, Any]:
    """Czy HTTP agent testowy (Node) odpowiada pod AI_TEST_AGENT_URL — przed Uruchom ▶."""
    agent = _agent_url()
    try:
        with httpx.Client(timeout=httpx.Timeout(3.0, connect=2.0)) as client:
            r = client.get(f"{agent}/agent/scenarios")
    except Exception as e:
        return {
            "agent_url": agent,
            "reachable": False,
            "error": _format_test_agent_error(agent, e),
        }
    if r.status_code != 200:
        text = (r.text or "")[:400].strip()
        return {
            "agent_url": agent,
            "reachable": False,
            "error": f"Agent HTTP {r.status_code}: {text or 'brak treści'}",
        }
    try:
        data = r.json()
    except Exception:
        data = {}
    scenarios = data.get("scenarios") if isinstance(data, dict) else None
    n = len(scenarios) if isinstance(scenarios, list) else None
    return {"agent_url": agent, "reachable": True, "scenario_count": n}


@router.post("/agent_planner_ping", dependencies=[Depends(require_admin_bearer_or_query)])
def post_agent_planner_ping(req_body: AgentPlannerPingReq) -> dict[str, Any]:
    """
    Sprawdza dostępność LLM planera (GET /api/tags Ollama lub /v1/models OpenAI-compat) z perspektywy agenta.
    Body opcjonalnie z tymi samymi polami co przy starcie testu (jak sekcja LLM w panelu).
    """
    agent = _agent_url()
    internal = _agent_planner_llm_to_internal(req_body.agent_planner_llm)
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0)) as client:
            r = client.post(f"{agent}/agent/planner_ping", json={"planner_llm": internal})
    except Exception as e:
        return {
            "agent_url": agent,
            "reachable": False,
            "error": _format_test_agent_error(agent, e),
            "planner": None,
        }
    if r.status_code != 200:
        text = (r.text or "")[:500].strip()
        return {
            "agent_url": agent,
            "reachable": True,
            "planner": {"reachable": False, "error": f"HTTP {r.status_code}: {text or 'planner_ping'}"},
        }
    try:
        return {
            "agent_url": agent,
            "reachable": True,
            "planner": r.json(),
        }
    except Exception:
        return {"agent_url": agent, "reachable": True, "planner": {"reachable": False, "error": r.text[:300]}}


@router.post("/start", dependencies=[Depends(require_admin_bearer_or_query)])
def post_start(req: StartReq) -> dict[str, str]:
    if _any_running():
        raise HTTPException(status_code=409, detail="Test już trwa (jedna sesja agenta).")

    scenario = _parse_scenario_text(req.yaml)
    run_id = str(uuid.uuid4())
    q: queue.Queue[Any] = queue.Queue()
    with _runs_lock:
        _runs[run_id] = {
            "status": "RUNNING",
            "queue": q,
            "started_at": time.time(),
            "scenario_name": scenario.get("name", "unnamed"),
        }

    planner_internal = _agent_planner_llm_to_internal(req.agent_planner_llm)
    agent = _agent_url()
    t = threading.Thread(
        target=_httpx_serve_agent_stream,
        args=(run_id, scenario, q, agent, planner_internal),
        name=f"test-runner-{run_id[:8]}",
        daemon=True,
    )
    t.start()
    logger.info("test_runner_started", run_id=run_id, scenario_name=scenario.get("name"))
    return {"run_id": run_id}


@router.post("/stop/{run_id}", dependencies=[Depends(require_admin_bearer_or_query)])
def post_stop(run_id: str) -> dict[str, Any]:
    """
    Zatrzymaj działający test. Wysyja sygnał stop do agenta i oznacza run jako CANCELLED.
    """
    with _runs_lock:
        st = _runs.get(run_id)
    if not st:
        raise HTTPException(status_code=404, detail="Nieznany run_id")

    if st.get("status") != "RUNNING":
        return {"run_id": run_id, "status": st.get("status"), "message": "Test nie jest aktywny"}

    # Wyslij sygnał stop do agenta (best effort)
    agent = _agent_url()
    try:
        with httpx.Client(timeout=httpx.Timeout(3.0)) as client:
            client.post(f"{agent}/agent/stop", json={"run_id": run_id})
    except Exception as e:
        logger.warning("test_runner_stop_agent_error", run_id=run_id, error=str(e))

    # Oznacz jako cancelled lokalnie
    was_running = _set_run_cancelled(run_id)
    q = st.get("queue")
    if isinstance(q, queue.Queue):
        q.put({"done": True, "success": False, "reason": "cancelled", "error": "Test zatrzymany przez użytkownika"})

    logger.info("test_runner_stopped", run_id=run_id, was_running=was_running)
    return {"run_id": run_id, "status": "CANCELLED", "message": "Test zatrzymany"}


@router.get("/status/{run_id}", dependencies=[Depends(require_admin_bearer_or_query)])
def get_status(run_id: str) -> dict[str, Any]:
    with _runs_lock:
        st = _runs.get(run_id)
    if not st:
        raise HTTPException(status_code=404, detail="Nieznany run_id")
    return {"status": st.get("status", "UNKNOWN"), "result": st.get("result")}


@router.get("/stream/{run_id}", dependencies=[Depends(require_admin_bearer_or_query)])
def get_stream(run_id: str) -> StreamingResponse:
    with _runs_lock:
        st = _runs.get(run_id)
    if not st:
        raise HTTPException(status_code=404, detail="Nieznany run_id")
    q = st.get("queue")
    if not isinstance(q, queue.Queue):
        raise HTTPException(status_code=500, detail="internal queue error")

    def event_gen():
        while True:
            try:
                item: Any = q.get(timeout=600.0)
            except queue.Empty:
                yield f"data: {json.dumps({'done': True, 'error': 'timeout waiting for agent'})}\n\n"
                break
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream; charset=utf-8",
    )


@router.get("/screenshot/{run_id}", dependencies=[Depends(require_admin_bearer_or_query)])
def get_screenshot_proxy(run_id: str) -> dict[str, str]:
    with _runs_lock:
        st = _runs.get(run_id)
    if not st or st.get("status") != "RUNNING":
        raise HTTPException(status_code=404, detail="Brak aktywnego testu dla tego run_id")
    try:
        r = httpx.get(
            f"{_agent_url()}/agent/screenshot",
            timeout=10.0,
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Agent: {e!s}") from e
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Agent: brak aktywnej sesji przeglądarki")
    if r.status_code != 200:
        raise HTTPException(
            status_code=502, detail=(r.text or f"HTTP {r.status_code}")[:2000]
        )
    return r.json()


@router.post("/save_scenario", dependencies=[Depends(require_admin_bearer_or_query)])
def post_save_scenario(req: SaveScenarioReq) -> dict[str, Any]:
    if not re.match(r"^[a-zA-Z0-9._-]+\.json$", req.filename):
        raise HTTPException(
            status_code=400, detail="Dozwolone tylko pliki .json, nazwa: litery, cyfry, ._-"
        )
    sdir = _scenarios_dir()
    sdir.mkdir(parents=True, exist_ok=True)
    path = (sdir / req.filename).resolve()
    if not str(path).startswith(str(sdir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    # Validate that content is JSON object
    _parse_scenario_text(req.content)
    path.write_text(req.content.strip() + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path)}


@router.get("/scenarios", dependencies=[Depends(require_admin_bearer_or_query)])
def get_scenarios() -> dict[str, Any]:
    sdir = _scenarios_dir()
    if not sdir.is_dir():
        return {"scenarios": []}
    files = sorted([f for f in sdir.iterdir() if f.suffix == ".json" and f.is_file()])
    return {"scenarios": [f.name for f in files]}


@router.get("/scenario/{filename}", dependencies=[Depends(require_admin_bearer_or_query)])
def get_scenario_file(filename: str) -> dict[str, str]:
    if not re.match(r"^[a-zA-Z0-9._-]+\.json$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    sdir = _scenarios_dir().resolve()
    path = (sdir / filename).resolve()
    if not str(path).startswith(str(sdir)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return {"content": path.read_text(encoding="utf-8")}


def _load_ai_test_config_file() -> dict[str, Any]:
    """
    Same path semantics as refresh_test_env (`AI_TEST_CONFIG_PATH` or `/data/ai_test_config.json`).
    Used so the admin panel can apply Test Runner LLM overrides to `player_id` from seed.
    """
    path_str = (os.getenv("AI_TEST_CONFIG_PATH") or "/data/ai_test_config.json").strip()
    if not path_str:
        raise HTTPException(status_code=404, detail="Brak ścieżki AI_TEST_CONFIG_PATH.")
    path = Path(path_str)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Brak pliku ai_test_config: {path_str} — uruchom seed_ai_test_env lub ustaw AI_TEST_CONFIG_PATH.",
        )
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"ai_test_config: niepoprawny JSON ({path_str}): {exc}",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="ai_test_config: oczekiwano obiektu JSON")
    return {"config_path": path_str, **data}


class PlaywrightRunReq(BaseModel):
    spec: str | None = Field(default=None, description="filename, np. issue_392_hp_no_death.spec.js; null = uruchom wszystkie")
    target: str = Field(default="live", description="'sandbox' = izolowany stack e2e, 'live' = żywy DEV")


def _sandbox_urls() -> tuple[str, str]:
    """Adresy izolowanego stacku e2e widziane z kontenera test-agenta (#1488)."""
    host = os.getenv("AI_SANDBOX_HOST", "host.docker.internal")
    return (
        os.getenv("AI_SANDBOX_BASE_URL", f"http://{host}:{os.getenv('E2E_FRONTEND_PORT', '13002')}"),
        os.getenv("AI_SANDBOX_BACKEND_URL", f"http://{host}:{os.getenv('E2E_BACKEND_PORT', '18100')}"),
    )


def _sandbox_ready(backend_url: str) -> bool:
    try:
        with httpx.Client(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
            return client.get(f"{backend_url}/api/healthz").status_code == 200
    except Exception:
        return False


@router.get("/playwright-specs", dependencies=[Depends(require_admin_bearer_or_query)])
def list_playwright_specs() -> dict[str, Any]:
    """Lista spec files z playwright/ux/regression/ (przez agenta Node)."""
    agent = _agent_url()
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            r = client.get(f"{agent}/playwright/specs")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        if _is_test_agent_unreachable(e):
            return {"specs": [], "error": _format_test_agent_error(agent, e)}
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/cleanup", dependencies=[Depends(require_admin_bearer_or_query)])
def cleanup_test_leftovers() -> dict[str, Any]:
    """Ręczne sprzątanie śmieci testowych w bieżącej bazie (#1488).

    Bez zdjęcia „przed" kasuje wszystko, co pasuje do wzorca testowego — używane
    z panelu, gdy ktoś chce posprzątać zaległości bez wchodzenia na serwer.
    """
    from app.services import test_cleanup_service as tcs

    removed = tcs.cleanup_since({t: set() for t in tcs.WATCHED})
    return {"removed": removed, "summary": tcs.summarize(removed)}


@router.post("/playwright-run", dependencies=[Depends(require_admin_bearer_or_query)])
def run_playwright(body: PlaywrightRunReq) -> StreamingResponse:
    """Uruchom Playwright spec(s) — SSE stream z logami i wynikiem.

    #1488: specy klikają ŻYWY DEV, więc przed startem robimy zdjęcie bazy, a po
    zakończeniu kasujemy to, co przebieg dołożył i co wygląda na testowe. Dzięki temu
    baza nie rośnie po każdym uruchomieniu Test Runnera.
    """
    agent = _agent_url()

    from app.services import test_cleanup_service as tcs

    sandbox = body.target == "sandbox"
    base_url, backend_url = _sandbox_urls() if sandbox else (None, None)
    if sandbox and not _sandbox_ready(backend_url):
        # Bez cichego przełączenia na żywy DEV — to właśnie było źródłem śmieci.
        raise HTTPException(
            status_code=409,
            detail=(
                f"Sandbox nie odpowiada ({backend_url}). Podnieś go: "
                "./scripts/sandbox_up.sh — albo wybierz cel „żywy DEV”."
            ),
        )

    # Na sandboxie baza jest osobna i jednorazowa — nie ma czego sprzątać.
    before = None
    if not sandbox:
        try:
            before = tcs.snapshot()
        except Exception:                  # sprzątanie nie może wywrócić przebiegu
            before = None

    def gen():
        # Czytamy stream agenta w wątku → kolejka. Główna pętla emituje heartbeat (komentarz SSE)
        # podczas ciszy, by proxy (NPM idle ~60s) nie zerwało połączenia. Group run odpala ~114
        # testów i Playwright milczy ~90s na starcie (zbieranie + launch) → bez heartbeatu proxy
        # zrywało SSE i frontend pokazywał "Błąd: network error".
        import queue as _queue
        import threading

        q: "_queue.Queue[tuple[str, str | None]]" = _queue.Queue()

        def _reader() -> None:
            try:
                with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=5.0)) as client:
                    payload: dict[str, Any] = {"spec": body.spec}
                    if base_url:
                        payload |= {"baseUrl": base_url, "backendUrl": backend_url}
                    with client.stream("POST", f"{agent}/playwright/run", json=payload) as resp:
                        if resp.status_code != 200:
                            err_txt = resp.read()[:2000].decode("utf-8", errors="replace")
                            q.put(("data", json.dumps({'type': 'done', 'success': False, 'error': f'HTTP {resp.status_code}: {err_txt}'})))
                            return
                        for line in resp.iter_lines():
                            if line is None:
                                continue
                            line = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                            line = line.strip()
                            if line.startswith("data: "):
                                q.put(("raw", line))
            except Exception as e:
                q.put(("data", json.dumps({'type': 'done', 'success': False, 'error': _format_test_agent_error(agent, e)})))
            finally:
                q.put(("eof", None))

        threading.Thread(target=_reader, daemon=True).start()

        # Natychmiastowy hello: klient widzi feedback od razu, a proxy dostaje dane zanim
        # Playwright (po ~90s ciszy) wyśle pierwszą linię.
        yield f"data: {json.dumps({'type': 'log', 'line': 'Uruchamianie testów (start Playwright potrafi potrwać ~90s)…'})}\n\n"

        _HEARTBEAT_S = 15  # < proxy idle timeout (NPM ~60s)
        cleaned = False

        def _cleanup_line() -> str:
            """Posprzątaj po przebiegu i zwróć linię do logu (#1488)."""
            try:
                removed = tcs.cleanup_since(before)
                return f"🧹 Sprzątanie po testach: {tcs.summarize(removed)}"
            except Exception as e:                       # nigdy nie psuj raportu z testów
                return f"🧹 Sprzątanie po testach nie powiodło się: {e}"

        while True:
            try:
                kind, val = q.get(timeout=_HEARTBEAT_S)
            except _queue.Empty:
                yield ": keepalive\n\n"  # komentarz SSE — utrzymuje połączenie podczas ciszy startu
                continue
            if kind == "eof":
                break
            if val is None:
                continue
            # Sprzątamy PRZED zdarzeniem 'done' — po nim frontend zamyka stream
            # i nasza linia by nie dotarła.
            if before is not None and not cleaned and '"done"' in val:
                cleaned = True
                yield f"data: {json.dumps({'type': 'log', 'line': _cleanup_line()})}\n\n"
            yield f"{val}\n\n" if kind == "raw" else f"data: {val}\n\n"

        if before is not None and not cleaned:
            yield f"data: {json.dumps({'type': 'log', 'line': _cleanup_line()})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/ai_test_config", dependencies=[Depends(require_admin_bearer_or_query)])
def get_ai_test_config() -> dict[str, Any]:
    """
    Exposes seeded test env ids (especially `player_id`) so the UI can PUT the same LLM settings
    the game iframe uses (`/api/health?user_id=…`, `user_llm_settings`).
    """
    out = _load_ai_test_config_file()
    if out.get("player_id") is None:
        raise HTTPException(status_code=500, detail="ai_test_config: brak pola player_id")
    return out
