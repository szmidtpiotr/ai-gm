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
    get_content_llm_profile,
    save_llm_preset,
    set_content_llm_profile,
)
from app.services.llm_service import (
    content_llm_enabled,
    get_default_config,
    resolve_content_llm_config,
)
from app.services.summary_settings_service import read_summary_settings, upsert_summary_settings
from app.services.ui_panel_settings import get_ui_panels_merged, merge_ui_panels_patch
from app.services.user_llm_settings import (
    get_user_llm_settings_full,
    get_user_llm_settings_masked,
    upsert_user_llm_settings,
)
from app.services.quick_chips_settings import (
    get_quick_chips_settings,
    set_quick_chips_settings,
)
from app.services.user_preferences import get_all_preferences, set_preference

router = APIRouter()
DB_PATH = resolve_db_path()


def _require_admin_token(authorization: str | None = Header(default=None)) -> None:
    """#1155: guard admina dla endpointów debugowych zwracających api_key w plaintext."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if not verify_admin_token(authorization.removeprefix("Bearer ").strip()):
        raise HTTPException(status_code=401, detail="Invalid admin token")


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
    l3_enabled_gotowa: bool | None = None  # U8: Gotowa Kampania L3 default


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


# ── Content/offline LLM profile (#919, H4b) ─────────────────────────────────
class ContentLlmPatchReq(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    # null/blank = keep existing key
    api_key: str | None = None


def _content_llm_view() -> dict:
    """Effective content-gen LLM profile for the admin panel: what generation will
    actually use (DB > env > default) + whether the toggle is on + whether a row is stored."""
    eff = resolve_content_llm_config()
    stored = get_content_llm_profile()  # masked, or None
    api_key = str(eff.get("api_key") or "")
    masked = (f"{api_key[:6]}..." if len(api_key) > 6 else f"{api_key}...") if api_key else ""
    return {
        "enabled": content_llm_enabled(),
        "provider": eff["provider"],
        "base_url": eff["base_url"],
        "model": eff["model"],
        "api_key": masked,
        "api_key_set": bool(api_key),
        "stored": stored is not None,
    }


@router.get("/settings/content-llm")
def get_content_llm_settings(_: None = Depends(_require_admin_bearer)):
    return {"ok": True, "data": _content_llm_view()}


@router.patch("/settings/content-llm")
def patch_content_llm_settings(
    req: ContentLlmPatchReq, _: None = Depends(_require_admin_bearer)
):
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    set_content_llm_profile(**patch)
    return {"ok": True, "data": _content_llm_view()}


# ── #1215 Szybkie akcje — flaga globalna + tuning liczby chipów LLM ───────────

class QuickChipsPatchReq(BaseModel):
    enabled: bool | None = None
    max: int | None = Field(default=None, ge=0, le=5)


@router.get("/settings/quick-chips")
def get_quick_chips(_: None = Depends(_require_admin_bearer)):
    return {"ok": True, "data": get_quick_chips_settings()}


@router.patch("/settings/quick-chips")
def patch_quick_chips(req: QuickChipsPatchReq, _: None = Depends(_require_admin_bearer)):
    data = set_quick_chips_settings(enabled=req.enabled, max_n=req.max)
    return {"ok": True, "data": data}


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


# ── #1215 Preferencje gracza (per-user toggle chipów LLM) ─────────────────────

class QuickChipsPrefReq(BaseModel):
    enabled: bool


@router.get("/users/{user_id}/preferences")
def get_user_preferences(user_id: int):
    """Preferencje gracza (klucz/wartość). quick_chips: '1'/'0' — chipy LLM."""
    prefs = get_all_preferences(user_id)
    return {"ok": True, "preferences": prefs, "quick_chips": prefs.get("quick_chips", "1") != "0"}


@router.put("/users/{user_id}/preferences/quick-chips")
def put_user_quick_chips_pref(user_id: int, req: QuickChipsPrefReq):
    """Włącz/wyłącz chipy szybkich akcji GENEROWANE PRZEZ LLM dla tego gracza.
    Nie wpływa na chipy regułowe (podróż/odpoczynek/usługi)."""
    set_preference(user_id, "quick_chips", "1" if req.enabled else "0")
    return {"ok": True, "quick_chips": req.enabled}


@router.get("/users/{user_id}/llm-settings/internal",
            dependencies=[Depends(_require_admin_token)])
def get_user_llm_settings_internal(user_id: int):
    """
    Internal endpoint for server-side debugging only.
    Not used by the UI; returns api_key. #1155: wymaga tokena admina.
    """
    return get_user_llm_settings_full(user_id=user_id)
