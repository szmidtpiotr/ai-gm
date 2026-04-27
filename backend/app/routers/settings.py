from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.admin_auth import verify_admin_token
from app.services.llm_service import get_runtime_config, set_runtime_config
from app.services.ui_panel_settings import get_ui_panels_merged, merge_ui_panels_patch
from app.services.user_llm_settings import (
    get_user_llm_settings_full,
    get_user_llm_settings_masked,
    upsert_user_llm_settings,
)

router = APIRouter()


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


class LlmSettingsReq(BaseModel):
    provider: str
    base_url: str
    model: str
    # null/omit = keep existing runtime API key (do not clear on save with empty field)
    api_key: str | None = None


@router.post("/settings/llm")
def set_llm_settings(req: LlmSettingsReq):
    current = get_runtime_config(mask_api_key=False)
    resolved_key = req.api_key if req.api_key is not None else str(current.get("api_key") or "")
    set_runtime_config(
        provider=req.provider,
        base_url=req.base_url,
        model=req.model,
        api_key=resolved_key,
    )
    return {
        "ok": True,
        "settings": get_runtime_config(mask_api_key=True),
    }


@router.get("/settings/llm")
def get_llm_settings():
    return get_runtime_config(mask_api_key=True)


class UserLlmSettingsReq(BaseModel):
    provider: str
    base_url: str
    model: str
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
