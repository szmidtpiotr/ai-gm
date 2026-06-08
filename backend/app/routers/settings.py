import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.db_runtime import resolve_db_path
from app.services.admin_auth import verify_admin_token
from app.services.llm_admin_service import (
    activate_llm_preset,
    apply_global_llm_settings,
    clear_global_llm_override,
    delete_llm_preset,
    get_admin_llm_settings_snapshot,
    save_llm_preset,
)
from app.services.llm_service import get_default_config
from app.services.summary_settings_service import read_summary_settings, upsert_summary_settings
from app.services.ui_panel_settings import get_ui_panels_merged, merge_ui_panels_patch
from app.services.user_llm_settings import (
    get_user_llm_settings_full,
    get_user_llm_settings_masked,
    upsert_user_llm_settings,
)

router = APIRouter()
DB_PATH = resolve_db_path()


def _require_admin_bearer(
    authorization: str | None = Header(default=None),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/settings/ui")
def get_ui_settings():
    """Public read-only defaults for player sheet fold sections (8E-2)."""
    panels = get_ui_panels_merged()
    return {"ok": True, "data": {"panels": panels}}


class UiPanelsPatchReq(BaseModel):
    panels: dict[str, str] = Field(default_factory=dict)


@router.patch("/settings/ui")
def patch_ui_settings(req: UiPanelsPatchReq, _: None = Depends(_require_admin_bearer)):
    """Admin-only — merge panel defaults into game_config_meta (ui_panel_defaults)."""
    merged = merge_ui_panels_patch(req.panels or {})
    return {"ok": True, "data": {"panels": merged}}


class SummarySettingsPatchReq(BaseModel):
    summary_rollup_cooldown_turns: int | None = Field(default=None, ge=1, le=500)
    dual_summary_preview_mode: Literal["owner", "owner_admin", "off"] | None = None


@router.get("/settings/summary")
def get_summary_settings():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return {"ok": True, "data": read_summary_settings(conn)}
    finally:
        conn.close()


@router.patch("/settings/summary")
def patch_summary_settings(
    req: SummarySettingsPatchReq, _: None = Depends(_require_admin_bearer)
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        data = upsert_summary_settings(
            conn,
            summary_rollup_cooldown_turns=req.summary_rollup_cooldown_turns,
            dual_summary_preview_mode=req.dual_summary_preview_mode,
        )
        return {"ok": True, "data": data}
    finally:
        conn.close()


# E9 (#424) — Story Gravity thresholds, configurable from the Admin Panel.
class StoryGravityPatchReq(BaseModel):
    enabled: bool | None = None
    turns_l1: int | None = Field(default=None, ge=1, le=200)
    turns_l2: int | None = Field(default=None, ge=1, le=200)
    turns_l3: int | None = Field(default=None, ge=1, le=200)
    l3_enabled: bool | None = None


@router.get("/settings/story-gravity")
def get_story_gravity_settings():
    from app.services.story_gravity_service import get_story_gravity_config
    return {"ok": True, "data": get_story_gravity_config()}


@router.patch("/settings/story-gravity")
def patch_story_gravity_settings(
    req: StoryGravityPatchReq, _: None = Depends(_require_admin_bearer)
):
    from app.services.story_gravity_service import set_story_gravity_config
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    return {"ok": True, "data": set_story_gravity_config(**patch)}


class LlmSettingsReq(BaseModel):
    provider: str
    base_url: str
    model: str
    # null/omit = keep existing runtime API key (do not clear on save with empty field)
    api_key: str | None = None


@router.post("/settings/llm")
def set_llm_settings(req: LlmSettingsReq, _: None = Depends(_require_admin_bearer)):
    return {
        "ok": True,
        "settings": apply_global_llm_settings(
            provider=req.provider,
            base_url=req.base_url,
            model=req.model,
            api_key=req.api_key,
        ),
    }


@router.get("/settings/llm")
def get_llm_settings():
    return get_default_config(mask_api_key=True)


@router.get("/settings/llm/admin")
def get_admin_llm_settings(_: None = Depends(_require_admin_bearer)):
    return {"ok": True, **get_admin_llm_settings_snapshot()}


class LlmPresetReq(BaseModel):
    label: str
    provider: str
    base_url: str
    model: str
    api_key: str | None = None
    preset_id: int | None = None
    activate: bool = False


@router.post("/settings/llm/presets")
def post_llm_preset(req: LlmPresetReq, _: None = Depends(_require_admin_bearer)):
    try:
        preset = save_llm_preset(
            preset_id=req.preset_id,
            label=req.label,
            provider=req.provider,
            base_url=req.base_url,
            model=req.model,
            api_key=req.api_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc
    except ValueError as exc:
        detail = str(exc)
        if detail == "preset_label_exists":
            raise HTTPException(status_code=409, detail="Preset label already exists") from exc
        raise HTTPException(status_code=400, detail="Preset payload is invalid") from exc
    if req.activate:
        preset = activate_llm_preset(int(preset["id"]))
    return {
        "ok": True,
        "preset": preset,
        **get_admin_llm_settings_snapshot(),
    }


@router.post("/settings/llm/presets/{preset_id}/activate")
def post_activate_llm_preset(preset_id: int, _: None = Depends(_require_admin_bearer)):
    try:
        preset = activate_llm_preset(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc
    return {
        "ok": True,
        "preset": preset,
        **get_admin_llm_settings_snapshot(),
    }


@router.delete("/settings/llm/presets/{preset_id}")
def delete_llm_preset_route(preset_id: int, _: None = Depends(_require_admin_bearer)):
    try:
        delete_llm_preset(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Active preset cannot be deleted") from exc
    return {"ok": True, **get_admin_llm_settings_snapshot()}


@router.post("/settings/llm/use-env")
def post_use_env_llm_settings(_: None = Depends(_require_admin_bearer)):
    return {
        "ok": True,
        "settings": clear_global_llm_override(),
        **get_admin_llm_settings_snapshot(),
    }


class UserLlmSettingsReq(BaseModel):
    mode: Literal["default", "custom"] = "custom"
    provider: str = ""
    base_url: str = ""
    model: str = ""
    # null/omit = keep existing stored api_key
    api_key: str | None = None


@router.get("/users/{user_id}/llm-settings")
def get_user_llm_settings(user_id: int):
    """
    Safe per-user LLM settings for UI.
    Does not expose api_key.
    """
    return get_user_llm_settings_masked(user_id=user_id)


@router.put("/users/{user_id}/llm-settings")
def put_user_llm_settings(user_id: int, req: UserLlmSettingsReq):
    """
    Stores per-user LLM settings (including api_key on the server side).
    """
    upsert_user_llm_settings(
        user_id=user_id,
        mode=req.mode,
        provider=req.provider,
        base_url=req.base_url,
        model=req.model,
        api_key=req.api_key,
    )
    return {
        "ok": True,
        "settings": get_user_llm_settings_masked(user_id=user_id),
    }


@router.get("/users/{user_id}/llm-settings/internal")
def get_user_llm_settings_internal(user_id: int):
    """
    Internal endpoint for server-side debugging only.
    Not used by the UI; returns api_key.
    """
    return get_user_llm_settings_full(user_id=user_id)
