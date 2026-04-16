from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm_service import get_runtime_config, set_runtime_config

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
