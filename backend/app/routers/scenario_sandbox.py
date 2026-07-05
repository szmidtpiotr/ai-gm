"""Scenario Sandbox router (#1211) — admin/agent API over scenario_service.

POST /api/admin/scenario/prepare      — build an isolated test session
GET  /api/admin/scenario/list         — active scenario campaigns
GET  /api/admin/scenario/{cid}/state  — side mechanics log (per-turn trace)

Auth: /api/admin namespace guard (#1187). Deterministic — no LLM, no GitHub
calls; the agent (Claude) reads the issue and maps it onto the setup payload.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.services import scenario_service as scn

router = APIRouter(prefix="/admin/scenario", tags=["scenario-sandbox"])


@router.post("/prepare")
def prepare(payload: dict = Body(...)) -> dict[str, Any]:
    """Body = setup dict (see scenario_service.prepare_scenario docstring)."""
    try:
        return scn.prepare_scenario(payload)
    except scn.ScenarioError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/list")
def list_scenarios() -> dict[str, Any]:
    return {"scenarios": scn.list_scenarios()}


@router.get("/{campaign_id}/state")
def state(campaign_id: int, since_turn: int = 0) -> dict[str, Any]:
    try:
        return scn.get_scenario_state(campaign_id, since_turn=since_turn)
    except scn.ScenarioError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
