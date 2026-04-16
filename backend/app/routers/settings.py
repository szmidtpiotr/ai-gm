from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm_service import get_runtime_config, set_runtime_config
from app.services.user_llm_settings import (
    get_user_llm_settings_full,
    get_user_llm_settings_masked,
    upsert_user_llm_settings,
)

router = APIRouter()


class LlmSettingsReq(BaseModel):
    provider: str
    base_url: str
    model: str
    api_key: str = ""


@router.post("/settings/llm")
def set_llm_settings(req: LlmSettingsReq):
    set_runtime_config(
        provider=req.provider,
        base_url=req.base_url,
        model=req.model,
        api_key=req.api_key,
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
    api_key: str = ""


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
