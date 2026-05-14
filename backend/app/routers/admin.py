import json
import os
import re
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.services.admin_accounts import (
    create_account_admin,
    list_accounts,
    reset_account_sheet,
    set_account_password,
    soft_delete_account,
    update_account,
)
from app.services.admin_campaigns import (
    advance_campaign_scene_admin,
    get_campaign_gm_plan_admin,
    list_campaigns_by_owner,
    regenerate_campaign_gm_plan_admin,
    regenerate_campaign_summary_admin,
    replace_campaign_gm_plan_admin,
)
from app.services.admin_character_recreate import (
    delete_character_admin,
    list_characters_admin,
    list_characters_by_owner,
    recreate_character_in_place,
)
from app.migrations_admin import run_admin_migrations
from app.services.admin_auth import issue_dev_admin_token, verify_admin_token
from app.services.admin_config_transfer import (
    export_catalog_snapshot,
    export_config,
    import_catalog_snapshot,
    import_config,
)
from app.services.admin_llm_assistant import (
    build_admin_assistant_messages,
    extract_admin_assistant_json,
    supported_admin_assistant_resources,
)
from app.services.llm_admin_service import (
    activate_llm_preset,
    clear_global_llm_override,
    delete_llm_preset,
    get_admin_llm_settings_snapshot,
    get_llm_preset,
    save_llm_preset,
)
from app.services.llm_service import _normalize_base_url as _llm_normalize_base_url
from app.services.admin_config import (
    create_condition,
    create_consumable,
    create_enemy,
    create_item,
    create_loot_table,
    create_skill,
    create_weapon,
    delete_condition,
    delete_consumable,
    delete_enemy,
    delete_item,
    delete_loot_entry,
    delete_loot_table,
    delete_weapon,
    delete_skill,
    list_conditions,
    list_consumables,
    list_enemies,
    list_items,
    list_loot_entries,
    list_loot_tables,
    list_weapons,
    list_dc,
    list_xp_rewards,
    list_skills,
    list_stats,
    list_archetypes,
    update_condition,
    update_enemy,
    update_item,
    update_loot_table,
    update_weapon,
    update_consumable,
    update_dc,
    update_xp_reward,
    update_skill,
    update_stat,
    update_archetype,
    upsert_loot_entry,
)
from app.services.llm_service import generate_chat
from app.services.client_ui_config import get_merged_slash_commands, set_slash_commands_ui
from app.services.loki_settings import (
    DEFAULT_LOKI_URL,
    get_display_loki_url,
    get_stored_loki_url,
    set_stored_loki_url,
)
from app.services.user_llm_settings import (
    get_user_llm_settings_full,
    get_user_llm_settings_masked,
    upsert_user_llm_settings,
)
from app.api.npcs import (
    NpcCreateReq,
    NpcPatchReq,
    create_npc as create_npc_public,
    delete_npc as delete_npc_public,
    get_npc as get_npc_public,
    list_npcs as list_npcs_public,
    patch_npc as patch_npc_public,
)

router = APIRouter()

ADMIN_SQLITE_PATH = "/data/ai_gm.db"
ADMIN_DB_RESTORE_TMP = "/data/ai_gm_restore_tmp.db"
ADMIN_DB_BAK_PATH = "/data/ai_gm.db.bak"
_SAFE_SQLITE_TABLE = re.compile(r"^[a-zA-Z0-9_]+$")

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
PROMPT_NAME_TO_FILE: dict[str, str] = {
    "system_prompt": "system_prompt.txt",
    "history_summary_prompt": "history_summary_prompt.txt",
    "memory_qa_prompt": "memory_qa_prompt.txt",
    "helpme-gm": "helpme-gm.txt",
}


class AdminAuthReq(BaseModel):
    token: str


class AdminDevLoginReq(BaseModel):
    username: str
    password: str


class StatPatchReq(BaseModel):
    label: str | None = None
    description: str | None = None
    sort_order: int | None = None
    force: bool = False


class SkillPatchReq(BaseModel):
    label: str | None = None
    linked_stat: str | None = None
    rank_ceiling: int | None = None
    sort_order: int | None = None
    description: str | None = None
    trigger_keywords: str | None = None
    force: bool = False


class SkillCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    linked_stat: str
    rank_ceiling: int = 5
    sort_order: int | None = None
    description: str | None = ""
    trigger_keywords: str | None = None

    @field_validator("sort_order", mode="before")
    @classmethod
    def _empty_sort_as_none(cls, v: object) -> object:
        """Treat omitted / null like None so client need not send sort_order."""
        if v is None or v == "":
            return None
        return v


class SkillDeleteReq(BaseModel):
    force: bool = False


class DcPatchReq(BaseModel):
    label: str | None = None
    value: int | None = None
    sort_order: int | None = None
    description: str | None = None
    force: bool = False


class XpRewardPatchReq(BaseModel):
    """[T12] Edycja wpisu game_config_xp_rewards (category/key są stałe)."""

    label: str | None = None
    description: str | None = None
    xp_amount: int | None = None
    is_active: int | None = Field(default=None, description="0 wyłącza wpis w silniku")
    sort_order: int | None = None
    force: bool = False


class AccountPatchReq(BaseModel):
    display_name: str | None = None
    is_active: int | None = None
    is_admin: int | None = Field(default=None, description="0 = player, 1 = admin")


class AccountPasswordResetReq(BaseModel):
    new_password: str = Field(..., min_length=8)


class AccountCreateReq(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    is_admin: int = 0

    @model_validator(mode="after")
    def _validate_is_admin(self) -> "AccountCreateReq":
        if self.is_admin not in (0, 1):
            raise ValueError("is_admin must be 0 or 1")
        return self


class AdminCharacterRecreateReq(BaseModel):
    """Same shape as player character create `sheet_json` (archetype, stats, skills, background, …)."""

    model_config = ConfigDict(extra="forbid")

    sheet_json: dict
    name: str | None = None
    clear_inventory: bool = True


class ConfigImportReq(BaseModel):
    config_version: str
    tables: dict
    export_kind: str | None = None
    exported_at: str | None = None
    exported_by: str | None = None
    excluded: list[str] | None = None
    notes: str | None = None


class AdminGmPlanPutReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gm_plan_json: dict


class AdminAdvanceSceneReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(default="", max_length=2000)


class SlashCommandItemReq(BaseModel):
    command: str
    description: str = Field(..., max_length=4000)
    enabled: bool


class SlashCommandsPutReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commands: list[SlashCommandItemReq]


class UserLlmSettingsReq(BaseModel):
    mode: Literal["default", "custom"] = "custom"
    provider: str = ""
    base_url: str = ""
    model: str = ""
    api_key: str | None = None


class LokiUrlSettingsReq(BaseModel):
    """Empty string clears DB row (health then uses LOKI_URL env only)."""

    loki_url: str = ""


class WeaponCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    damage_die: str
    linked_stat: str
    allowed_classes: list[str]
    description: str = ""
    weapon_type: str = "melee"
    two_handed: bool = False
    finesse: bool = False
    range_m: int | None = None
    targeting: str = "single"
    aoe_radius_m: float | None = None
    magic_school: str | None = None
    value_gp: int = 0
    weight_kg: float = 0.0
    note: str | None = None
    effect_json: str | None = None
    is_active: bool = True


class WeaponPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    damage_die: str | None = None
    linked_stat: str | None = None
    allowed_classes: list[str] | None = None
    description: str | None = None
    weapon_type: str | None = None
    two_handed: bool | None = None
    finesse: bool | None = None
    range_m: int | None = None
    targeting: str | None = None
    aoe_radius_m: float | None = None
    magic_school: str | None = None
    value_gp: int | None = None
    weight_kg: float | None = None
    note: str | None = None
    effect_json: str | None = None
    is_active: bool | None = None
    force: bool = False


class EnemyCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    hp_base: int
    ac_base: int
    attack_bonus: int
    dex_modifier: int = 0
    damage_die: str
    description: str | None = None
    tier: str = "standard"
    attacks_per_turn: int = 1
    damage_bonus: int = 0
    damage_type: str = "physical"
    xp_award: int = 0
    conditions_immune: list[str] = []
    skills_json: dict[str, int] = {}
    loot_table_key: str | None = None
    drop_chance: float = 1.0
    note: str | None = None
    is_active: bool = True


class EnemyPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    hp_base: int | None = None
    ac_base: int | None = None
    attack_bonus: int | None = None
    dex_modifier: int | None = None
    damage_die: str | None = None
    description: str | None = None
    tier: str | None = None
    attacks_per_turn: int | None = None
    damage_bonus: int | None = None
    damage_type: str | None = None
    xp_award: int | None = None
    conditions_immune: list[str] | None = None
    skills_json: dict[str, int] | None = None
    loot_table_key: str | None = None
    drop_chance: float | None = None
    note: str | None = None
    is_active: bool | None = None
    force: bool = False


class EnemyDeleteReq(BaseModel):
    force: bool = False


class ConditionCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    effect_json: str
    description: str | None = None
    stackable: bool = False
    auto_remove: str | None = None
    is_active: bool = True


class ConditionPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    effect_json: str | None = None
    description: str | None = None
    stackable: bool | None = None
    auto_remove: str | None = None
    is_active: bool | None = None
    force: bool = False


class ConditionDeleteReq(BaseModel):
    force: bool = False


class ItemCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    item_type: str = "misc"
    description: str = ""
    value_gp: int = 0
    weight_kg: float = 0.0
    allowed_classes: list[str] = []
    ac_bonus: int = 0
    effect_type: str | None = None
    effect_dice: str | None = None
    effect_bonus: int = 0
    effect_target: str = "self"
    charges: int = 1
    effect_json: str | None = None
    ai_generated: int = 0
    approved: int = 1
    note: str | None = None
    is_active: bool = True


class ItemPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    item_type: str | None = None
    description: str | None = None
    value_gp: int | None = None
    weight_kg: float | None = None
    allowed_classes: list[str] | None = None
    ac_bonus: int | None = None
    effect_type: str | None = None
    effect_dice: str | None = None
    effect_bonus: int | None = None
    effect_target: str | None = None
    charges: int | None = None
    effect_json: str | None = None
    ai_generated: int | None = None
    approved: int | None = None
    note: str | None = None
    is_active: bool | None = None
    force: bool = False


class ItemDeleteReq(BaseModel):
    force: bool = False


class LootTableCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    description: str = ""
    is_active: bool = True
    gold_min: int = 0
    gold_max: int = 0


class LootTablePatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_key: str | None = None
    label: str | None = None
    description: str | None = None
    is_active: bool | None = None
    gold_min: int | None = None
    gold_max: int | None = None
    force: bool = False


class LootTableDeleteReq(BaseModel):
    force: bool = False


class LootEntryReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_key: str | None = None
    consumable_key: str | None = None  # DEPRECATED 8H — traktowane jak item_key (katalog consumable)
    weapon_key: str | None = None
    weight: int = 10
    qty_min: int = 1
    qty_max: int = 1

    @model_validator(mode="after")
    def _xor_loot_source(self) -> "LootEntryReq":
        ik = (self.item_key or "").strip() or None
        ck = (self.consumable_key or "").strip() or None
        wk = (self.weapon_key or "").strip() or None
        if ck and not ik:
            ik = ck
            ck = None
        if sum(1 for x in (ik, wk) if x is not None) != 1:
            raise ValueError("invalid_loot_entry_source")
        self.item_key = ik
        self.consumable_key = ck
        self.weapon_key = wk
        return self


class ConsumableCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    description: str = ""
    effect_type: str = "misc"
    effect_dice: str | None = None
    effect_bonus: int = 0
    effect_target: str = "self"
    weight_kg: float = 0.0
    charges: int = 1
    value_gp: int = 0  # było base_price (8H)
    note: str | None = None
    is_active: bool = True


class ConsumablePatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_key: str | None = None
    label: str | None = None
    description: str | None = None
    effect_type: str | None = None
    effect_dice: str | None = None
    effect_bonus: int | None = None
    effect_target: str | None = None
    weight_kg: float | None = None
    charges: int | None = None
    value_gp: int | None = None  # było base_price (8H)
    note: str | None = None
    is_active: bool | None = None
    force: bool = False


class ConsumableDeleteReq(BaseModel):
    force: bool = False


class ArchetypePatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    description: str | None = None
    starter_items_json: str | None = None
    starter_gold_gp: int | None = None
    is_active: bool | None = None
    force: bool = False


class PromptPutReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    restore_from_backup: bool = False

    @model_validator(mode="after")
    def _content_or_restore(self) -> "PromptPutReq":
        if self.restore_from_backup:
            return self
        if self.content is None:
            raise ValueError("content is required unless restore_from_backup is true")
        return self


AssistantResourceLiteral = Literal[
    "skills",
    "weapons",
    "enemies",
    "conditions",
    "items",
    "consumables",
    "loot-tables",
]


class AdminAssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class AdminAssistantDraftReq(BaseModel):
    resource: AssistantResourceLiteral
    message: str = Field(..., min_length=1, max_length=8000)
    history: list[AdminAssistantChatMessage] = Field(default_factory=list)


class AdminAssistantSaveReq(BaseModel):
    resource: AssistantResourceLiteral
    payload: dict = Field(default_factory=dict)


def _assistant_resource_model(resource: AssistantResourceLiteral) -> type[BaseModel]:
    mapping: dict[AssistantResourceLiteral, type[BaseModel]] = {
        "skills": SkillCreateReq,
        "weapons": WeaponCreateReq,
        "enemies": EnemyCreateReq,
        "conditions": ConditionCreateReq,
        "items": ItemCreateReq,
        "consumables": ConsumableCreateReq,
        "loot-tables": LootTableCreateReq,
    }
    return mapping[resource]


def _assistant_resource_title(resource: AssistantResourceLiteral) -> str:
    for item in supported_admin_assistant_resources():
        if item["resource"] == resource:
            return item["title"]
    return resource


def _assistant_coerce_list_of_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _assistant_coerce_object(value: object) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _assistant_prepare_payload(resource: AssistantResourceLiteral, draft: dict) -> dict:
    payload = dict(draft or {})
    if resource in {"conditions", "items"} and isinstance(payload.get("effect_json"), (dict, list)):
        payload["effect_json"] = json.dumps(payload["effect_json"], ensure_ascii=False)
    if resource in {"weapons", "items"} and "allowed_classes" in payload:
        payload["allowed_classes"] = _assistant_coerce_list_of_strings(payload.get("allowed_classes"))
    if resource == "enemies":
        if "conditions_immune" in payload:
            payload["conditions_immune"] = _assistant_coerce_list_of_strings(payload.get("conditions_immune"))
        if "skills_json" in payload:
            payload["skills_json"] = _assistant_coerce_object(payload.get("skills_json"))
    return payload


def _assistant_validation_errors(exc: ValidationError) -> list[str]:
    out: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc") or [])
        msg = str(err.get("msg") or "invalid value")
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


def _assistant_validate_payload(resource: AssistantResourceLiteral, draft: dict) -> tuple[dict, list[str]]:
    payload = _assistant_prepare_payload(resource, draft)
    model_cls = _assistant_resource_model(resource)
    try:
        validated = model_cls.model_validate(payload)
    except ValidationError as exc:
        return payload, _assistant_validation_errors(exc)
    return validated.model_dump(exclude_none=True), []


def _assistant_save_validated_payload(resource: AssistantResourceLiteral, payload: dict) -> dict:
    if resource == "skills":
        return admin_create_skill(SkillCreateReq.model_validate(payload), None)
    if resource == "weapons":
        return admin_create_weapon(WeaponCreateReq.model_validate(payload), None)
    if resource == "enemies":
        return admin_create_enemy(EnemyCreateReq.model_validate(payload), None)
    if resource == "conditions":
        return admin_create_condition(ConditionCreateReq.model_validate(payload), None)
    if resource == "items":
        return admin_create_item(ItemCreateReq.model_validate(payload), None)
    if resource == "consumables":
        return admin_create_consumable(ConsumableCreateReq.model_validate(payload), None)
    if resource == "loot-tables":
        return admin_create_loot_table(LootTableCreateReq.model_validate(payload), None)
    raise HTTPException(status_code=404, detail="Unsupported assistant resource")


def _prompt_paths(name: str) -> tuple[Path, Path, str]:
    if name not in PROMPT_NAME_TO_FILE:
        raise HTTPException(status_code=404, detail="Unknown prompt")
    fn = PROMPT_NAME_TO_FILE[name]
    path = PROMPTS_DIR / fn
    bak = PROMPTS_DIR / (fn + ".bak")
    return path, bak, fn


def require_admin_token(
    authorization: str | None = Header(default=None),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/admin/auth")
def admin_auth(req: AdminAuthReq):
    if not verify_admin_token(req.token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return {"ok": True}


@router.post("/admin/dev-login")
def admin_dev_login(req: AdminDevLoginReq):
    try:
        token = issue_dev_admin_token(req.username.strip(), req.password)
        return {"ok": True, "token": token}
    except ValueError:
        raise HTTPException(status_code=400, detail="username and password are required") from None
    except PermissionError as e:
        if str(e) == "inactive_user":
            raise HTTPException(status_code=403, detail="User is inactive") from None
        raise HTTPException(status_code=401, detail="Invalid credentials") from None


@router.get("/admin/verify")
def admin_verify(_: None = Depends(require_admin_token)):
    return {"ok": True}


class AdminGlobalLlmPresetReq(BaseModel):
    label: str
    provider: str
    base_url: str
    model: str
    api_key: str | None = None
    preset_id: int | None = None
    activate: bool = False


class AdminLlmFetchModelsReq(BaseModel):
    provider: str
    base_url: str
    api_key: str | None = None
    preset_id: int | None = None


class CampaignDesignerGenerateReq(BaseModel):
    snippet_type: Literal["hook", "location", "npc", "encounter"]
    brief: str = Field(..., min_length=5, max_length=1000)
    preset_id: int | None = None


class CampaignDesignerSaveReq(BaseModel):
    snippet_type: Literal["hook", "location", "npc", "encounter"]
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=8000)
    tags: str | None = None


@router.get("/admin/llm/global-settings")
def admin_llm_global_settings(_: None = Depends(require_admin_token)):
    """Same payload as GET /api/settings/llm/admin — lives under /admin/* for proxies that only expose admin routes."""
    return {"ok": True, **get_admin_llm_settings_snapshot()}


@router.post("/admin/llm/presets")
def admin_llm_post_preset(req: AdminGlobalLlmPresetReq, _: None = Depends(require_admin_token)):
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


@router.post("/admin/llm/presets/{preset_id}/activate")
def admin_llm_activate_preset(preset_id: int, _: None = Depends(require_admin_token)):
    try:
        preset = activate_llm_preset(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc
    return {
        "ok": True,
        "preset": preset,
        **get_admin_llm_settings_snapshot(),
    }


@router.delete("/admin/llm/presets/{preset_id}")
def admin_llm_delete_preset(preset_id: int, _: None = Depends(require_admin_token)):
    try:
        delete_llm_preset(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Active preset cannot be deleted") from exc
    return {"ok": True, **get_admin_llm_settings_snapshot()}


@router.post("/admin/llm/use-env")
def admin_llm_use_env(_: None = Depends(require_admin_token)):
    return {
        "ok": True,
        "settings": clear_global_llm_override(),
        **get_admin_llm_settings_snapshot(),
    }


@router.post("/admin/llm/fetch-models")
async def admin_llm_fetch_models(req: AdminLlmFetchModelsReq, _: None = Depends(require_admin_token)):
    import asyncio as _asyncio
    import httpx
    import re as _re

    api_key = (req.api_key or "").strip()
    if not api_key and req.preset_id is not None:
        try:
            preset = get_llm_preset(req.preset_id, mask_api_key=False)
            api_key = (preset.get("api_key") or "").strip()
        except KeyError:
            pass

    provider = (req.provider or "").strip().lower()
    # Apply the same normalization as llm_service so "https://ollama.com/api/" → "https://ollama.com"
    base_url = _llm_normalize_base_url((req.base_url or "").strip(), provider)

    if not base_url:
        return {"ok": False, "models": [], "error": "base_url is required"}

    def _extract_azure_alias_candidates(raw_list: list[dict]) -> list[str]:
        """
        From the /openai/models catalog, extract only the short alias IDs
        (no YYYY-MM-DD date suffix, no bare trailing -N number) that support
        chat_completion. These are the candidate deployment names to probe.
        """
        _SKIP = _re.compile(
            r"(tts|whisper|embed|dall-e|image|audio|realtime|transcribe|sora|translate|rerank)",
            _re.IGNORECASE,
        )
        _DATE_SUFFIX    = _re.compile(r"-\d{4}-\d{2}-\d{2}")
        _NUMBERED_COPY  = _re.compile(r"-\d{1,2}$")

        result = []
        for m in raw_list:
            mid = m.get("id", "")
            if not m.get("capabilities", {}).get("chat_completion"):
                continue
            if _SKIP.search(mid):
                continue
            if _DATE_SUFFIX.search(mid):
                continue  # versioned name like gpt-4.1-2025-04-14
            if _NUMBERED_COPY.search(mid):
                continue  # load-balancing copy like Phi-4-5
            result.append(mid)
        return sorted(result, key=str.lower)

    async def _probe_azure_deployment(
        client: "httpx.AsyncClient",
        sem: "_asyncio.Semaphore",
        model_id: str,
        key: str,
        base: str,
    ) -> str | None:
        async with sem:
            try:
                r = await client.post(
                    f"{base}/openai/deployments/{model_id}/chat/completions",
                    headers={"api-key": key, "Content-Type": "application/json"},
                    params={"api-version": "2024-02-01"},
                    json={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    timeout=5.0,
                )
                if r.status_code == 200:
                    return model_id
            except Exception:
                pass
        return None

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            if provider == "ollama":
                # Standard Ollama: /api/tags — send Bearer if key provided (Ollama Cloud)
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                r = await client.get(f"{base_url}/api/tags", headers=headers, timeout=12.0)
                r.raise_for_status()
                data = r.json()
                models = sorted(m["name"] for m in data.get("models", []))

            elif provider == "azure":
                # Step 1: Fetch the global model catalog (api-key header, NOT Bearer)
                # /openai/deployments always 404 on Foundry-connected resources;
                # /v1/models also 404. Only /openai/models works for listing.
                r = await client.get(
                    f"{base_url}/openai/models",
                    headers={"api-key": api_key},
                    params={"api-version": "2024-02-01"},
                    timeout=12.0,
                )
                r.raise_for_status()
                data = r.json()
                candidates = _extract_azure_alias_candidates(data.get("data", []))

                # Step 2: Probe candidates in parallel (max 10 concurrent) to find
                # which ones are actually deployed on this resource. Failures
                # (DeploymentNotFound) return in ~250 ms; successes in ~1 s.
                sem = _asyncio.Semaphore(10)
                probe_tasks = [
                    _probe_azure_deployment(client, sem, mid, api_key, base_url)
                    for mid in candidates
                ]
                results = await _asyncio.gather(*probe_tasks)
                models = sorted((m for m in results if m is not None), key=str.lower)

            else:
                # OpenAI-compatible (openai + other): standard /v1/models
                r = await client.get(
                    f"{base_url}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                r.raise_for_status()
                data = r.json()
                models = sorted(m["id"] for m in data.get("data", []))

        return {"ok": True, "models": models}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "models": [], "error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"ok": False, "models": [], "error": str(exc)}


@router.get("/admin/assistant/resources")
def admin_assistant_resources(_: None = Depends(require_admin_token)):
    return {"items": supported_admin_assistant_resources()}


@router.post("/admin/assistant/draft")
def admin_assistant_draft(req: AdminAssistantDraftReq, _: None = Depends(require_admin_token)):
    try:
        messages = build_admin_assistant_messages(
            resource=req.resource,
            history=[msg.model_dump() for msg in req.history],
            message=req.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    try:
        raw = generate_chat(messages=messages)
        parsed = extract_admin_assistant_json(raw)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Assistant returned invalid JSON: {exc}") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None

    validated_payload, errors = _assistant_validate_payload(req.resource, parsed["draft"])
    return {
        "ok": True,
        "resource": req.resource,
        "resource_title": _assistant_resource_title(req.resource),
        "assistant_reply": parsed["reply"],
        "draft": parsed["draft"],
        "validated_payload": validated_payload,
        "valid": len(errors) == 0,
        "errors": errors,
    }


@router.post("/admin/assistant/save")
def admin_assistant_save(req: AdminAssistantSaveReq, _: None = Depends(require_admin_token)):
    validated_payload, errors = _assistant_validate_payload(req.resource, req.payload)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    return _assistant_save_validated_payload(req.resource, validated_payload)


@router.get("/admin/prompts")
def admin_prompts_list(_: None = Depends(require_admin_token)):
    items: list[dict] = []
    for logical_name, fn in PROMPT_NAME_TO_FILE.items():
        path = PROMPTS_DIR / fn
        if not path.is_file():
            continue
        st = path.stat()
        bak = PROMPTS_DIR / (fn + ".bak")
        items.append(
            {
                "name": logical_name,
                "filename": fn,
                "size_bytes": st.st_size,
                "last_modified": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
                "has_backup": bak.is_file(),
            }
        )
    return {"items": items}


@router.get("/admin/prompts/{name}")
def admin_prompts_get(name: str, _: None = Depends(require_admin_token)):
    path, bak, fn = _prompt_paths(name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Prompt file not found")
    st = path.stat()
    content = path.read_text(encoding="utf-8")
    return {
        "name": name,
        "filename": fn,
        "content": content,
        "size_bytes": st.st_size,
        "last_modified": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
        "has_backup": bak.is_file(),
    }


@router.put("/admin/prompts/{name}")
def admin_prompts_put(name: str, req: PromptPutReq, _: None = Depends(require_admin_token)):
    path, bak, fn = _prompt_paths(name)
    try:
        if req.restore_from_backup:
            if not bak.is_file():
                raise HTTPException(status_code=404, detail="No backup file (.bak) for this prompt")
            text = bak.read_text(encoding="utf-8")
            path.write_text(text, encoding="utf-8")
            st = path.stat()
            return {"ok": True, "name": name, "size_bytes": st.st_size}

        text = req.content if req.content is not None else ""
        if path.is_file():
            shutil.copyfile(path, bak)
        path.write_text(text, encoding="utf-8")
        st = path.stat()
        return {"ok": True, "name": name, "size_bytes": st.st_size}
    except HTTPException:
        raise
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write prompt: {e}") from None


@router.get("/admin/stats")
def admin_stats(_: None = Depends(require_admin_token)):
    return {"items": list_stats()}


@router.get("/admin/skills")
def admin_skills(_: None = Depends(require_admin_token)):
    return {"items": list_skills()}


@router.post("/admin/skills")
def admin_create_skill(req: SkillCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_skill(
            key=req.key.strip(),
            label=req.label.strip(),
            linked_stat=req.linked_stat.strip().upper(),
            rank_ceiling=req.rank_ceiling,
            sort_order=req.sort_order,
            description=(req.description or "").strip() if req.description is not None else None,
            trigger_keywords=(req.trigger_keywords or "").strip() or None,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "skill_exists":
            raise HTTPException(status_code=409, detail="Skill key already exists") from None
        if str(e) == "invalid_linked_stat":
            raise HTTPException(status_code=422, detail="linked_stat must reference an existing stat key") from None
        if str(e) == "invalid_rank_ceiling":
            raise HTTPException(status_code=422, detail="rank_ceiling must be >= 1") from None
        raise HTTPException(status_code=422, detail="Invalid skill payload") from None


@router.get("/admin/dc")
def admin_dc(_: None = Depends(require_admin_token)):
    return {"items": list_dc()}


@router.get("/admin/xp-rewards")
def admin_xp_rewards(_: None = Depends(require_admin_token)):
    return {"items": list_xp_rewards()}


@router.patch("/admin/xp-rewards/{key}")
def admin_patch_xp_reward(
    key: str, req: XpRewardPatchReq, _: None = Depends(require_admin_token)
):
    try:
        item = update_xp_reward(
            key,
            label=req.label,
            description=req.description,
            xp_amount=req.xp_amount,
            is_active=req.is_active,
            sort_order=req.sort_order,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="XP reward key not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_xp_amount":
            raise HTTPException(status_code=422, detail="xp_amount must be >= 0") from None
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/admin/weapons")
def admin_weapons(_: None = Depends(require_admin_token)):
    return {"items": list_weapons()}


@router.post("/admin/weapons")
def admin_create_weapon(req: WeaponCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_weapon(
            key=req.key,
            label=req.label.strip(),
            damage_die=req.damage_die,
            linked_stat=req.linked_stat.strip().upper(),
            allowed_classes=req.allowed_classes,
            description=req.description,
            weapon_type=req.weapon_type,
            two_handed=req.two_handed,
            finesse=req.finesse,
            range_m=req.range_m,
            targeting=req.targeting,
            aoe_radius_m=req.aoe_radius_m,
            magic_school=req.magic_school,
            value_gp=req.value_gp,
            weight_kg=req.weight_kg,
            note=req.note,
            effect_json=req.effect_json,
            is_active=req.is_active,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "weapon_exists":
            raise HTTPException(status_code=409, detail="Weapon key already exists") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="damage_die must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "invalid_linked_stat":
            raise HTTPException(status_code=422, detail="linked_stat must reference an existing stat key") from None
        if str(e) == "invalid_allowed_classes":
            raise HTTPException(status_code=422, detail="allowed_classes must be subset of [warrior,ranger,scholar]") from None
        if str(e) == "invalid_weapon_type":
            raise HTTPException(status_code=422, detail="weapon_type must be one of: melee, ranged, spell") from None
        if str(e) == "invalid_targeting":
            raise HTTPException(status_code=422, detail="targeting must be one of: single, aoe_radius") from None
        if str(e) == "invalid_aoe_radius_m":
            raise HTTPException(
                status_code=422,
                detail="aoe_radius_m must be > 0 when targeting=aoe_radius (null for targeting=single)",
            ) from None
        if str(e) == "invalid_magic_school":
            raise HTTPException(status_code=422, detail="magic_school max length is 80 chars") from None
        if str(e) == "invalid_value_gp":
            raise HTTPException(status_code=422, detail="value_gp must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        raise HTTPException(status_code=422, detail="Invalid weapon payload") from None


@router.patch("/admin/weapons/{key}")
def admin_patch_weapon(key: str, req: WeaponPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_weapon(
            key,
            label=req.label,
            damage_die=req.damage_die,
            linked_stat=req.linked_stat.strip().upper() if req.linked_stat is not None else None,
            allowed_classes=req.allowed_classes,
            description=req.description,
            weapon_type=req.weapon_type,
            two_handed=req.two_handed,
            finesse=req.finesse,
            range_m=req.range_m,
            targeting=req.targeting,
            aoe_radius_m=req.aoe_radius_m,
            magic_school=req.magic_school,
            value_gp=req.value_gp,
            weight_kg=req.weight_kg,
            note=req.note,
            effect_json=req.effect_json,
            is_active=req.is_active,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Weapon not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="damage_die must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "invalid_linked_stat":
            raise HTTPException(status_code=422, detail="linked_stat must reference an existing stat key") from None
        if str(e) == "invalid_allowed_classes":
            raise HTTPException(status_code=422, detail="allowed_classes must be subset of [warrior,ranger,scholar]") from None
        if str(e) == "invalid_weapon_type":
            raise HTTPException(status_code=422, detail="weapon_type must be one of: melee, ranged, spell") from None
        if str(e) == "invalid_targeting":
            raise HTTPException(status_code=422, detail="targeting must be one of: single, aoe_radius") from None
        if str(e) == "invalid_aoe_radius_m":
            raise HTTPException(
                status_code=422,
                detail="aoe_radius_m must be > 0 when targeting=aoe_radius (null for targeting=single)",
            ) from None
        if str(e) == "invalid_magic_school":
            raise HTTPException(status_code=422, detail="magic_school max length is 80 chars") from None
        if str(e) == "invalid_value_gp":
            raise HTTPException(status_code=422, detail="value_gp must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        raise HTTPException(status_code=422, detail="Invalid weapon payload") from None


@router.delete("/admin/weapons/{key}")
def admin_delete_weapon(key: str, force: bool = False, _: None = Depends(require_admin_token)):
    try:
        delete_weapon(key, force=force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Weapon not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except LookupError:
        raise HTTPException(
            status_code=409,
            detail="Weapon is referenced in active character sheets. Cannot delete.",
        ) from None
    except ValueError as e:
        if str(e) == "in_use":
            raise HTTPException(
                status_code=409,
                detail="Weapon is referenced by loot table entries. Cannot delete.",
            ) from None
        raise


@router.get("/admin/enemies")
def admin_enemies(_: None = Depends(require_admin_token)):
    return {"items": list_enemies()}


@router.post("/admin/enemies")
def admin_create_enemy(req: EnemyCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_enemy(
            key=req.key,
            label=req.label.strip(),
            hp_base=req.hp_base,
            ac_base=req.ac_base,
            attack_bonus=req.attack_bonus,
            dex_modifier=req.dex_modifier,
            damage_die=req.damage_die,
            description=req.description,
            tier=req.tier,
            attacks_per_turn=req.attacks_per_turn,
            damage_bonus=req.damage_bonus,
            damage_type=req.damage_type,
            xp_award=req.xp_award,
            conditions_immune=req.conditions_immune,
            skills_json=req.skills_json,
            loot_table_key=req.loot_table_key,
            drop_chance=req.drop_chance,
            note=req.note,
            is_active=req.is_active,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "enemy_exists":
            raise HTTPException(status_code=409, detail="Enemy key already exists") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="damage_die must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "invalid_hp_base":
            raise HTTPException(status_code=422, detail="hp_base must be >= 1") from None
        if str(e) == "invalid_ac_base":
            raise HTTPException(status_code=422, detail="ac_base must be >= 1") from None
        if str(e) == "invalid_attack_bonus":
            raise HTTPException(status_code=422, detail="attack_bonus must be >= 0") from None
        if str(e) == "invalid_tier":
            raise HTTPException(status_code=422, detail="tier must be one of: weak, standard, elite, boss") from None
        if str(e) == "invalid_damage_type":
            raise HTTPException(
                status_code=422,
                detail="damage_type must be one of: physical, magic, fire, poison, misc",
            ) from None
        if str(e) == "invalid_attacks_per_turn":
            raise HTTPException(status_code=422, detail="attacks_per_turn must be >= 1") from None
        if str(e) == "invalid_xp_award":
            raise HTTPException(status_code=422, detail="xp_award must be >= 0") from None
        if str(e) == "invalid_conditions_immune":
            raise HTTPException(status_code=422, detail="conditions_immune must be a list of valid condition keys") from None
        if str(e) == "invalid_skills_json":
            raise HTTPException(status_code=422, detail="skills_json must be an object: {skill_key: integer_rank_or_bonus}") from None
        if str(e) == "invalid_loot_table_key":
            raise HTTPException(status_code=422, detail="loot_table_key must reference an existing loot table") from None
        if str(e) == "invalid_drop_chance":
            raise HTTPException(status_code=422, detail="invalid_drop_chance") from None
        raise HTTPException(status_code=422, detail="Invalid enemy payload") from None


@router.patch("/admin/enemies/{key}")
def admin_patch_enemy(key: str, req: EnemyPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_enemy(
            key,
            label=req.label,
            hp_base=req.hp_base,
            ac_base=req.ac_base,
            attack_bonus=req.attack_bonus,
            dex_modifier=req.dex_modifier,
            damage_die=req.damage_die,
            description=req.description,
            tier=req.tier,
            attacks_per_turn=req.attacks_per_turn,
            damage_bonus=req.damage_bonus,
            damage_type=req.damage_type,
            xp_award=req.xp_award,
            conditions_immune=req.conditions_immune,
            skills_json=req.skills_json,
            loot_table_key=req.loot_table_key,
            note=req.note,
            drop_chance=req.drop_chance,
            is_active=req.is_active,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Enemy not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="damage_die must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "invalid_hp_base":
            raise HTTPException(status_code=422, detail="hp_base must be >= 1") from None
        if str(e) == "invalid_ac_base":
            raise HTTPException(status_code=422, detail="ac_base must be >= 1") from None
        if str(e) == "invalid_attack_bonus":
            raise HTTPException(status_code=422, detail="attack_bonus must be >= 0") from None
        if str(e) == "invalid_tier":
            raise HTTPException(status_code=422, detail="tier must be one of: weak, standard, elite, boss") from None
        if str(e) == "invalid_damage_type":
            raise HTTPException(
                status_code=422,
                detail="damage_type must be one of: physical, magic, fire, poison, misc",
            ) from None
        if str(e) == "invalid_attacks_per_turn":
            raise HTTPException(status_code=422, detail="attacks_per_turn must be >= 1") from None
        if str(e) == "invalid_xp_award":
            raise HTTPException(status_code=422, detail="xp_award must be >= 0") from None
        if str(e) == "invalid_conditions_immune":
            raise HTTPException(status_code=422, detail="conditions_immune must be a list of valid condition keys") from None
        if str(e) == "invalid_skills_json":
            raise HTTPException(status_code=422, detail="skills_json must be an object: {skill_key: integer_rank_or_bonus}") from None
        if str(e) == "invalid_loot_table_key":
            raise HTTPException(status_code=422, detail="loot_table_key must reference an existing loot table") from None
        if str(e) == "invalid_drop_chance":
            raise HTTPException(status_code=422, detail="invalid_drop_chance") from None
        raise HTTPException(status_code=422, detail="Invalid enemy payload") from None


@router.delete("/admin/enemies/{key}")
def admin_delete_enemy(key: str, req: EnemyDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_enemy(key, force=req.force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Enemy not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None


@router.get("/admin/npcs")
def admin_list_npcs(active_only: bool = Query(False), _: None = Depends(require_admin_token)):
    return list_npcs_public(active_only=active_only)


@router.get("/admin/npcs/{npc_id}")
def admin_get_npc(npc_id: int, _: None = Depends(require_admin_token)):
    return get_npc_public(npc_id=npc_id)


@router.post("/admin/npcs")
def admin_create_npc(req: NpcCreateReq, _: None = Depends(require_admin_token)):
    return create_npc_public(body=req)


@router.patch("/admin/npcs/{npc_id}")
def admin_patch_npc(npc_id: int, req: NpcPatchReq, _: None = Depends(require_admin_token)):
    return patch_npc_public(npc_id=npc_id, body=req)


@router.delete("/admin/npcs/{npc_id}")
def admin_delete_npc(npc_id: int, _: None = Depends(require_admin_token)):
    return delete_npc_public(npc_id=npc_id)


@router.get("/admin/conditions")
def admin_conditions(_: None = Depends(require_admin_token)):
    return {"items": list_conditions()}


@router.post("/admin/conditions")
def admin_create_condition(req: ConditionCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_condition(
            key=req.key,
            label=req.label.strip(),
            effect_json=req.effect_json,
            description=req.description,
            stackable=req.stackable,
            auto_remove=req.auto_remove,
            is_active=req.is_active,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "condition_exists":
            raise HTTPException(status_code=409, detail="Condition key already exists") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_effect_json":
            raise HTTPException(status_code=422, detail="effect_json must be a valid JSON string") from None
        if str(e) == "invalid_effect_json_schema":
            raise HTTPException(status_code=422, detail="effect_json must follow schema v1 (schema_version, effect_category, effects[])") from None
        raise HTTPException(status_code=422, detail="Invalid condition payload") from None


@router.patch("/admin/conditions/{key}")
def admin_patch_condition(key: str, req: ConditionPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_condition(
            key,
            label=req.label,
            effect_json=req.effect_json,
            description=req.description,
            stackable=req.stackable,
            auto_remove=req.auto_remove,
            is_active=req.is_active,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Condition not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_effect_json":
            raise HTTPException(status_code=422, detail="effect_json must be a valid JSON string") from None
        if str(e) == "invalid_effect_json_schema":
            raise HTTPException(status_code=422, detail="effect_json must follow schema v1 (schema_version, effect_category, effects[])") from None
        raise HTTPException(status_code=422, detail="Invalid condition payload") from None


@router.delete("/admin/conditions/{key}")
def admin_delete_condition(key: str, req: ConditionDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_condition(key, force=req.force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Condition not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None


@router.get("/admin/items")
def admin_items(_: None = Depends(require_admin_token)):
    return {"items": list_items()}


@router.post("/admin/items")
def admin_create_item(req: ItemCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_item(
            key=req.key,
            label=req.label.strip(),
            item_type=req.item_type,
            description=req.description or "",
            value_gp=req.value_gp,
            weight_kg=req.weight_kg,
            allowed_classes=req.allowed_classes,
            ac_bonus=req.ac_bonus,
            effect_type=req.effect_type,
            effect_dice=req.effect_dice,
            effect_bonus=req.effect_bonus,
            effect_target=req.effect_target,
            charges=req.charges,
            effect_json=req.effect_json,
            ai_generated=req.ai_generated,
            approved=req.approved,
            note=req.note,
            is_active=req.is_active,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "item_exists":
            raise HTTPException(status_code=409, detail="Item key already exists") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_item_type":
            raise HTTPException(
                status_code=422,
                detail="item_type must be one of: weapon, armor, consumable, misc, quest, narrative",
            ) from None
        if str(e) == "invalid_effect_json":
            raise HTTPException(status_code=422, detail="effect_json must be valid JSON") from None
        if str(e) == "invalid_effect_json_schema":
            raise HTTPException(status_code=422, detail="effect_json must follow schema v1 (schema_version, effect_category, effects[])") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="effect_dice must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "legacy_effect_requires_effect_json":
            raise HTTPException(
                status_code=422,
                detail="Legacy item effect fields can only auto-convert heal/restore/apply-remove-condition. Use effect_json for stat buffs or custom effects.",
            ) from None
        if str(e) == "invalid_value_gp":
            raise HTTPException(status_code=422, detail="value_gp must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        if str(e) == "invalid_ac_bonus":
            raise HTTPException(status_code=422, detail="ac_bonus must be >= 0") from None
        if str(e) == "invalid_charges":
            raise HTTPException(status_code=422, detail="charges must be >= 1") from None
        if str(e) in ("invalid_allowed_classes", "invalid_proficiency_classes"):
            raise HTTPException(status_code=422, detail="allowed_classes must be subset of [warrior,ranger,scholar]") from None
        raise HTTPException(status_code=422, detail="Invalid item payload") from None


@router.patch("/admin/items/{key}")
def admin_patch_item(key: str, req: ItemPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_item(
            key,
            label=req.label,
            item_type=req.item_type,
            description=req.description,
            value_gp=req.value_gp,
            weight_kg=req.weight_kg,
            allowed_classes=req.allowed_classes,
            ac_bonus=req.ac_bonus,
            effect_type=req.effect_type,
            effect_dice=req.effect_dice,
            effect_bonus=req.effect_bonus,
            effect_target=req.effect_target,
            charges=req.charges,
            effect_json=req.effect_json,
            ai_generated=req.ai_generated,
            approved=req.approved,
            note=req.note,
            is_active=req.is_active,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_item_type":
            raise HTTPException(
                status_code=422,
                detail="item_type must be one of: weapon, armor, consumable, misc, quest, narrative",
            ) from None
        if str(e) == "invalid_effect_json":
            raise HTTPException(status_code=422, detail="effect_json must be valid JSON") from None
        if str(e) == "invalid_effect_json_schema":
            raise HTTPException(status_code=422, detail="effect_json must follow schema v1 (schema_version, effect_category, effects[])") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="effect_dice must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "legacy_effect_requires_effect_json":
            raise HTTPException(
                status_code=422,
                detail="Legacy item effect fields can only auto-convert heal/restore/apply-remove-condition. Use effect_json for stat buffs or custom effects.",
            ) from None
        if str(e) == "invalid_value_gp":
            raise HTTPException(status_code=422, detail="value_gp must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        if str(e) == "invalid_ac_bonus":
            raise HTTPException(status_code=422, detail="ac_bonus must be >= 0") from None
        if str(e) == "invalid_charges":
            raise HTTPException(status_code=422, detail="charges must be >= 1") from None
        if str(e) in ("invalid_allowed_classes", "invalid_proficiency_classes"):
            raise HTTPException(status_code=422, detail="allowed_classes must be subset of [warrior,ranger,scholar]") from None
        raise HTTPException(status_code=422, detail="Invalid item payload") from None


@router.delete("/admin/items/{key}")
def admin_delete_item(key: str, req: ItemDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_item(key, force=req.force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "in_use":
            raise HTTPException(
                status_code=409,
                detail="Item is referenced by loot table entries. Cannot delete.",
            ) from None
        raise HTTPException(status_code=422, detail="Invalid delete request") from e


@router.get("/admin/consumables")
def admin_consumables(_: None = Depends(require_admin_token)):
    return {"items": list_consumables()}


@router.post("/admin/consumables")
def admin_create_consumable(req: ConsumableCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_consumable(
            key=req.key,
            label=req.label.strip(),
            description=req.description or "",
            effect_type=req.effect_type,
            effect_dice=req.effect_dice,
            effect_bonus=req.effect_bonus,
            effect_target=req.effect_target,
            weight_kg=req.weight_kg,
            charges=req.charges,
            base_price=req.value_gp,
            note=req.note,
            is_active=req.is_active,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "consumable_exists":
            raise HTTPException(status_code=409, detail="Consumable key already exists") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_effect_type":
            raise HTTPException(status_code=422, detail="effect_type is invalid") from None
        if str(e) == "invalid_effect_target":
            raise HTTPException(status_code=422, detail="effect_target must be one of: self, ally, any") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="effect_dice must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "legacy_effect_requires_effect_json":
            raise HTTPException(
                status_code=422,
                detail="Legacy consumable fields can only auto-convert heal/restore/apply-remove-condition. Use effect_json via item editor for stat buffs or custom effects.",
            ) from None
        if str(e) == "invalid_charges":
            raise HTTPException(status_code=422, detail="charges must be >= 1") from None
        if str(e) in ("invalid_base_price", "invalid_value_gp"):
            raise HTTPException(status_code=422, detail="value_gp must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        if str(e) == "invalid_ac_bonus":
            raise HTTPException(status_code=422, detail="ac_bonus must be >= 0") from None
        raise HTTPException(status_code=422, detail="Invalid consumable payload") from None


@router.patch("/admin/consumables/{key}")
def admin_patch_consumable(key: str, req: ConsumablePatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_consumable(
            key,
            new_key=req.new_key,
            label=req.label,
            description=req.description,
            effect_type=req.effect_type,
            effect_dice=req.effect_dice,
            effect_bonus=req.effect_bonus,
            effect_target=req.effect_target,
            weight_kg=req.weight_kg,
            charges=req.charges,
            base_price=req.value_gp,
            note=req.note,
            is_active=req.is_active,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Consumable not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "consumable_exists":
            raise HTTPException(status_code=409, detail="Consumable key already exists") from None
        if str(e) == "invalid_effect_type":
            raise HTTPException(status_code=422, detail="effect_type is invalid") from None
        if str(e) == "invalid_effect_target":
            raise HTTPException(status_code=422, detail="effect_target must be one of: self, ally, any") from None
        if str(e) == "invalid_damage_die":
            raise HTTPException(status_code=422, detail="effect_dice must match ^\\d*d\\d+$ (e.g. d6, 2d8)") from None
        if str(e) == "legacy_effect_requires_effect_json":
            raise HTTPException(
                status_code=422,
                detail="Legacy consumable fields can only auto-convert heal/restore/apply-remove-condition. Use effect_json via item editor for stat buffs or custom effects.",
            ) from None
        if str(e) == "invalid_charges":
            raise HTTPException(status_code=422, detail="charges must be >= 1") from None
        if str(e) in ("invalid_base_price", "invalid_value_gp"):
            raise HTTPException(status_code=422, detail="value_gp must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        if str(e) == "invalid_ac_bonus":
            raise HTTPException(status_code=422, detail="ac_bonus must be >= 0") from None
        raise HTTPException(status_code=422, detail="Invalid consumable payload") from None


@router.delete("/admin/consumables/{key}")
def admin_delete_consumable(key: str, req: ConsumableDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_consumable(key, force=req.force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Consumable not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "in_use":
            raise HTTPException(
                status_code=409,
                detail="Cannot delete — used in a loot table.",
            ) from None
        raise HTTPException(status_code=422, detail="Invalid delete request") from e


@router.get("/admin/archetypes")
def admin_archetypes(_: None = Depends(require_admin_token)):
    return {"items": list_archetypes()}


@router.patch("/admin/archetypes/{key}")
def admin_patch_archetype(key: str, req: ArchetypePatchReq, _: None = Depends(require_admin_token)):
    try:
        row = update_archetype(
            key,
            label=req.label,
            description=req.description,
            starter_items_json=req.starter_items_json,
            starter_gold_gp=req.starter_gold_gp,
            is_active=req.is_active,
            force=req.force,
        )
        return {"archetype": row}
    except KeyError:
        raise HTTPException(status_code=404, detail="Archetype not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_starter_items_json":
            raise HTTPException(status_code=422, detail="starter_items_json must be a JSON array of objects") from None
        if str(e) == "invalid_starter_gold_gp":
            raise HTTPException(status_code=422, detail="starter_gold_gp must be >= 0") from None
        raise HTTPException(status_code=422, detail="Invalid archetype payload") from None


@router.get("/admin/loot-tables")
def admin_loot_tables(_: None = Depends(require_admin_token)):
    return {"items": list_loot_tables()}


@router.post("/admin/loot-tables")
def admin_create_loot_table(req: LootTableCreateReq, _: None = Depends(require_admin_token)):
    try:
        item = create_loot_table(
            key=req.key,
            label=req.label.strip(),
            description=req.description or "",
            is_active=req.is_active,
            gold_min=req.gold_min,
            gold_max=req.gold_max,
        )
        return {"item": item}
    except ValueError as e:
        if str(e) == "loot_table_exists":
            raise HTTPException(status_code=409, detail="Loot table key already exists") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "invalid_gold_range":
            raise HTTPException(status_code=422, detail="gold_min/gold_max must be >= 0 and gold_min <= gold_max") from None
        raise HTTPException(status_code=422, detail="Invalid loot table payload") from None


@router.patch("/admin/loot-tables/{key}")
def admin_patch_loot_table(key: str, req: LootTablePatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_loot_table(
            key,
            new_key=req.new_key,
            label=req.label,
            description=req.description,
            is_active=req.is_active,
            gold_min=req.gold_min,
            gold_max=req.gold_max,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Loot table not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="key must be lowercase_snake_case and 1-40 chars") from None
        if str(e) == "loot_table_exists":
            raise HTTPException(status_code=409, detail="Loot table key already exists") from None
        if str(e) == "invalid_gold_range":
            raise HTTPException(status_code=422, detail="gold_min/gold_max must be >= 0 and gold_min <= gold_max") from None
        raise HTTPException(status_code=422, detail="Invalid loot table payload") from None


@router.delete("/admin/loot-tables/{key}")
def admin_delete_loot_table(key: str, req: LootTableDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_loot_table(key, force=req.force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Loot table not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Row is locked. Use force=true to override.") from None


@router.get("/admin/loot-tables/{key}/entries")
def admin_loot_table_entries(key: str, _: None = Depends(require_admin_token)):
    try:
        return {"items": list_loot_entries(key)}
    except ValueError as e:
        if str(e) == "loot_table_not_found":
            raise HTTPException(status_code=404, detail="Loot table not found") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="Invalid loot table key") from None
        raise


@router.post("/admin/loot-tables/{key}/entries")
def admin_upsert_loot_entry(key: str, req: LootEntryReq, _: None = Depends(require_admin_token)):
    try:
        row = upsert_loot_entry(
            key,
            item_key=req.item_key,
            consumable_key=req.consumable_key,
            weapon_key=req.weapon_key,
            weight=req.weight,
            qty_min=req.qty_min,
            qty_max=req.qty_max,
        )
        return {"item": row}
    except ValueError as e:
        if str(e) == "loot_table_not_found":
            raise HTTPException(status_code=404, detail="Loot table not found") from None
        if str(e) == "item_not_found":
            raise HTTPException(status_code=422, detail="item_key must reference an existing item") from None
        if str(e) == "invalid_loot_entry_source":
            raise HTTPException(
                status_code=422,
                detail="Exactly one of item_key or weapon_key must be set (consumable_key is deprecated: use item_key).",
            ) from None
        if str(e) == "weapon_not_found":
            raise HTTPException(status_code=422, detail="weapon_key must reference an existing weapon") from None
        if str(e) == "invalid_weight":
            raise HTTPException(status_code=422, detail="weight must be >= 1") from None
        if str(e) == "invalid_qty_range":
            raise HTTPException(status_code=422, detail="qty_min and qty_max must be >= 1 and qty_min <= qty_max") from None
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="Invalid key format") from None
        raise HTTPException(status_code=422, detail="Invalid loot entry payload") from None


@router.delete("/admin/loot-tables/{key}/entries/weapon/{weapon_key}")
def admin_delete_loot_entry_weapon(key: str, weapon_key: str, _: None = Depends(require_admin_token)):
    try:
        delete_loot_entry(key, weapon_key=weapon_key)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Loot entry not found") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="Invalid key format") from None
        if str(e) == "invalid_loot_entry_source":
            raise HTTPException(
                status_code=422,
                detail="Exactly one of item_key or weapon_key must be set (consumable_key is deprecated: use item_key).",
            ) from None
        raise


@router.delete("/admin/loot-tables/{key}/entries/consumable/{consumable_key}")
def admin_delete_loot_entry_consumable(key: str, consumable_key: str, _: None = Depends(require_admin_token)):
    try:
        delete_loot_entry(key, consumable_key=consumable_key)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Loot entry not found") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="Invalid key format") from None
        if str(e) == "invalid_loot_entry_source":
            raise HTTPException(
                status_code=422,
                detail="Exactly one of item_key or weapon_key must be set (consumable_key is deprecated: use item_key).",
            ) from None
        raise


@router.delete("/admin/loot-tables/{key}/entries/{item_key}")
def admin_delete_loot_entry(key: str, item_key: str, _: None = Depends(require_admin_token)):
    try:
        delete_loot_entry(key, item_key)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Loot entry not found") from None
    except ValueError as e:
        if str(e) == "invalid_key":
            raise HTTPException(status_code=422, detail="Invalid key format") from None
        raise


@router.patch("/admin/stats/{key}")
def admin_patch_stat(key: str, req: StatPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_stat(
            key,
            label=req.label,
            description=req.description,
            sort_order=req.sort_order,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Stat not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Stat is locked; set force=true to override") from None


@router.patch("/admin/skills/{key}")
def admin_patch_skill(key: str, req: SkillPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_skill(
            key,
            label=req.label,
            linked_stat=req.linked_stat,
            rank_ceiling=req.rank_ceiling,
            sort_order=req.sort_order,
            description=req.description,
            trigger_keywords=req.trigger_keywords,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Skill is locked; set force=true to override") from None
    except ValueError as e:
        if str(e) == "invalid_linked_stat":
            raise HTTPException(status_code=422, detail="linked_stat must reference an existing stat key") from None
        if str(e) == "invalid_rank_ceiling":
            raise HTTPException(status_code=422, detail="rank_ceiling must be >= 1") from None
        raise HTTPException(status_code=422, detail="Invalid skill payload") from None


@router.delete("/admin/skills/{key}")
def admin_delete_skill(key: str, req: SkillDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_skill(key, force=req.force)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="Skill is locked; set force=true to override") from None
    except LookupError as e:
        parts = str(e).split(":")
        if len(parts) >= 3 and parts[0] == "skill_in_use":
            raise HTTPException(
                status_code=409,
                detail=f"Skill is referenced in character sheet (character_id={parts[1]}, rank={parts[2]})",
            ) from None
        raise HTTPException(status_code=409, detail="Skill is referenced and cannot be deleted") from None


@router.patch("/admin/dc/{key}")
def admin_patch_dc(key: str, req: DcPatchReq, _: None = Depends(require_admin_token)):
    try:
        item = update_dc(
            key,
            label=req.label,
            value=req.value,
            sort_order=req.sort_order,
            description=req.description,
            force=req.force,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="DC tier not found") from None
    except PermissionError:
        raise HTTPException(status_code=423, detail="DC tier is locked; set force=true to override") from None
    except ValueError as e:
        if str(e) == "invalid_dc_value":
            raise HTTPException(status_code=422, detail="value must be >= 1") from None
        raise HTTPException(status_code=422, detail="Invalid dc payload") from None


@router.get("/admin/accounts")
def admin_accounts(_: None = Depends(require_admin_token)):
    return {"items": list_accounts()}


@router.post("/admin/accounts/create")
def admin_create_account(req: AccountCreateReq, _: None = Depends(require_admin_token)):
    try:
        row = create_account_admin(
            username=req.username,
            password=req.password,
            display_name=req.display_name,
            is_admin=req.is_admin,
        )
        return {
            "ok": True,
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "is_admin": row["is_admin"],
            "is_active": row["is_active"],
            "created_at": row["created_at"],
        }
    except ValueError as e:
        code = str(e)
        if code == "username_taken":
            raise HTTPException(status_code=409, detail="Username already exists") from None
        if code == "invalid_username":
            raise HTTPException(
                status_code=422,
                detail="username must be 3–40 chars: letters, digits, underscore, hyphen",
            ) from None
        if code == "invalid_password":
            raise HTTPException(status_code=422, detail="password must be at least 8 characters") from None
        if code == "invalid_is_admin":
            raise HTTPException(status_code=422, detail="is_admin must be 0 or 1") from None
        raise HTTPException(status_code=422, detail="Invalid account payload") from None


@router.patch("/admin/accounts/{account_id}")
def admin_patch_account(
    account_id: int, req: AccountPatchReq, _: None = Depends(require_admin_token)
):
    try:
        item = update_account(
            account_id,
            display_name=req.display_name,
            is_active=req.is_active,
            is_admin=req.is_admin,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found") from None
    except ValueError as e:
        if str(e) == "invalid_is_active":
            raise HTTPException(status_code=422, detail="is_active must be 0 or 1") from None
        if str(e) == "invalid_is_admin":
            raise HTTPException(status_code=422, detail="is_admin must be 0 or 1") from None
        raise HTTPException(status_code=422, detail="Invalid account payload") from None


@router.post("/admin/accounts/{account_id}/reset-sheet")
def admin_reset_account_sheet(account_id: int, _: None = Depends(require_admin_token)):
    try:
        return reset_account_sheet(account_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found") from None


@router.post("/admin/accounts/{account_id}/set-password")
def admin_set_account_password(
    account_id: int, req: AccountPasswordResetReq, _: None = Depends(require_admin_token)
):
    try:
        return set_account_password(account_id, req.new_password)
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters") from None


@router.get("/admin/users/{user_id}/activity")
def admin_user_activity(user_id: int, _: None = Depends(require_admin_token)):
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.id, c.title, c.status, c.created_at,
                ch.name AS char_name, ch.sheet_json,
                (SELECT COUNT(*) FROM campaign_turns ct WHERE ct.campaign_id = c.id) AS turn_count,
                (SELECT MAX(ct2.created_at) FROM campaign_turns ct2 WHERE ct2.campaign_id = c.id) AS last_turn_at
            FROM campaigns c
            JOIN campaign_members cm ON cm.campaign_id = c.id AND cm.user_id = ?
            LEFT JOIN characters ch ON ch.campaign_id = c.id AND ch.user_id = ?
            ORDER BY c.created_at DESC
            """,
            (user_id, user_id),
        ).fetchall()
        items = []
        for r in rows:
            item: dict = {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "created_at": r["created_at"],
                "char_name": r["char_name"],
                "turn_count": r["turn_count"] or 0,
                "last_turn_at": r["last_turn_at"],
            }
            if r["sheet_json"]:
                try:
                    sheet = json.loads(r["sheet_json"])
                    item["char_archetype"] = sheet.get("archetype")
                    item["char_current_hp"] = sheet.get("current_hp")
                    item["char_max_hp"] = sheet.get("max_hp")
                    item["char_xp"] = sheet.get("xp_lifetime_earned")
                    item["char_conditions"] = sheet.get("conditions", [])
                except Exception:
                    pass
            items.append(item)
        return {"items": items}
    finally:
        conn.close()


@router.get("/admin/campaigns")
def admin_list_campaigns(
    owner_id: int = Query(..., description="Campaign owner user id"),
    _: None = Depends(require_admin_token),
):
    return {"items": list_campaigns_by_owner(owner_id)}


@router.get("/admin/campaigns/live")
def admin_campaigns_live(_: None = Depends(require_admin_token)):
    """All campaigns with character, location, last turn snippet, and scene progress."""
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                c.id, c.title, c.status, c.created_at, c.ended_at,
                c.gm_plan_json,
                ga.username AS owner_username,
                ch.id AS char_id, ch.name AS char_name, ch.location AS char_location,
                ch.sheet_json,
                (SELECT ct.user_text || '|||' || ct.assistant_text
                 FROM campaign_turns ct
                 WHERE ct.campaign_id = c.id
                 ORDER BY ct.id DESC LIMIT 1) AS last_turn_raw,
                (SELECT ct.created_at
                 FROM campaign_turns ct
                 WHERE ct.campaign_id = c.id
                 ORDER BY ct.id DESC LIMIT 1) AS last_turn_at,
                (SELECT COUNT(*) FROM campaign_turns ct WHERE ct.campaign_id = c.id) AS turn_count
            FROM campaigns c
            LEFT JOIN users ga ON ga.id = c.owner_user_id
            LEFT JOIN characters ch ON ch.campaign_id = c.id
            ORDER BY c.id DESC
        """).fetchall()

        items = []
        for r in rows:
            sheet = {}
            try:
                sheet = json.loads(r["sheet_json"] or "{}")
            except Exception:
                pass

            gm_plan = {}
            try:
                gm_plan = json.loads(r["gm_plan_json"] or "{}")
            except Exception:
                pass

            # Extract scene progress from gm_plan
            scene_current = 0
            scene_total = 0
            arc_title = None
            try:
                arcs = gm_plan.get("arcs", {})
                active_arc_id = gm_plan.get("active_arc_id")
                if active_arc_id and active_arc_id in arcs:
                    arc = arcs[active_arc_id]
                    arc_title = arc.get("title") or active_arc_id
                    scene_goals = arc.get("scene_goals", [])
                    scene_total = len(scene_goals)
                    # Count completed scenes: first non-completed is current
                    completed = sum(1 for sg in scene_goals if isinstance(sg, dict) and sg.get("status") == "completed")
                    scene_current = completed + 1 if completed < scene_total else scene_total
            except Exception:
                pass

            # Last turn text
            last_turn_player = None
            last_turn_gm = None
            if r["last_turn_raw"]:
                parts = r["last_turn_raw"].split("|||", 1)
                last_turn_player = (parts[0] or "")[:200]
                last_turn_gm = (parts[1] or "")[:200] if len(parts) > 1 else None

            conditions_raw = sheet.get("conditions", [])
            if isinstance(conditions_raw, str):
                try:
                    conditions_raw = json.loads(conditions_raw)
                except Exception:
                    conditions_raw = []

            items.append({
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "created_at": r["created_at"],
                "ended_at": r["ended_at"],
                "owner_username": r["owner_username"],
                "char_id": r["char_id"],
                "char_name": r["char_name"],
                "char_location": r["char_location"],
                "char_archetype": sheet.get("archetype"),
                "char_level": sheet.get("level"),
                "char_current_hp": sheet.get("current_hp"),
                "char_max_hp": sheet.get("max_hp"),
                "char_conditions": conditions_raw,
                "scene_current": scene_current,
                "scene_total": scene_total,
                "arc_title": arc_title,
                "last_turn_player": last_turn_player,
                "last_turn_gm": last_turn_gm,
                "last_turn_at": r["last_turn_at"],
                "turn_count": r["turn_count"],
            })

        return {"items": items}
    finally:
        conn.close()


@router.get("/admin/campaigns/{campaign_id}/turns")
def admin_get_campaign_turns(
    campaign_id: int,
    limit: int = Query(default=15, ge=1, le=100),
    _: None = Depends(require_admin_token),
):
    """Last N turns for a campaign (newest first → reversed for display)."""
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT id, turn_number, user_text, assistant_text, route, created_at
               FROM campaign_turns
               WHERE campaign_id = ?
               ORDER BY id DESC LIMIT ?""",
            (campaign_id, limit),
        ).fetchall()
        turns = [dict(r) for r in reversed(rows)]
        return {"items": turns}
    finally:
        conn.close()


@router.post("/admin/campaigns/{campaign_id}/regenerate-summary")
def admin_regenerate_campaign_summary(
    campaign_id: int, _: None = Depends(require_admin_token)
):
    try:
        return regenerate_campaign_summary_admin(campaign_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None


@router.get("/admin/campaigns/{campaign_id}/gm-plan")
def admin_get_campaign_gm_plan(campaign_id: int, _: None = Depends(require_admin_token)):
    try:
        return get_campaign_gm_plan_admin(campaign_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None


@router.put("/admin/campaigns/{campaign_id}/gm-plan")
def admin_put_campaign_gm_plan(
    campaign_id: int,
    req: AdminGmPlanPutReq,
    _: None = Depends(require_admin_token),
):
    try:
        return replace_campaign_gm_plan_admin(campaign_id, req.gm_plan_json)
    except KeyError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None


@router.post("/admin/campaigns/{campaign_id}/gm-plan/advance-scene")
def admin_advance_campaign_scene(
    campaign_id: int,
    req: AdminAdvanceSceneReq,
    _: None = Depends(require_admin_token),
):
    try:
        return advance_campaign_scene_admin(campaign_id, note=req.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None


@router.post("/admin/campaigns/{campaign_id}/gm-plan/regenerate-initial")
def admin_regenerate_campaign_gm_plan(
    campaign_id: int,
    _: None = Depends(require_admin_token),
):
    try:
        return regenerate_campaign_gm_plan_admin(campaign_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e) or "GM plan regeneration failed") from None


@router.get("/admin/characters")
def admin_list_characters(
    owner_id: int | None = Query(None, description="When set, only characters owned by this user"),
    _: None = Depends(require_admin_token),
):
    """Lista postaci (id, imię, kampania); optional filter by owner_id includes sheet_json."""
    if owner_id is not None:
        return {"items": list_characters_by_owner(owner_id)}
    return {"items": list_characters_admin()}


@router.delete("/admin/characters/{character_id}")
def admin_delete_character(character_id: int, _: None = Depends(require_admin_token)):
    """
    Delete a user's hero (character row) and all turns for that character.
    Intended for rare admin / recovery use; campaign remains (may have zero characters).
    """
    try:
        return delete_character_admin(character_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Character not found") from None


@router.post("/admin/characters/{character_id}/recreate")
def admin_recreate_character(
    character_id: int, req: AdminCharacterRecreateReq, _: None = Depends(require_admin_token)
):
    """
    Rebuild sheet in place: same `characters.id` (turn history unchanged).
    Body: `sheet_json` like POST /campaigns/{id}/characters, optional `name`, optional `clear_inventory`.
    """
    try:
        return recreate_character_in_place(
            character_id,
            name=req.name,
            sheet_json=req.sheet_json,
            clear_inventory=req.clear_inventory,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Character not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/admin/accounts/{account_id}")
def admin_delete_account(account_id: int, _: None = Depends(require_admin_token)):
    try:
        soft_delete_account(account_id)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found") from None


@router.get("/admin/users/{user_id}/llm-settings")
def admin_get_user_llm_settings(user_id: int, _: None = Depends(require_admin_token)):
    return {"ok": True, "settings": get_user_llm_settings_masked(user_id=user_id)}


@router.put("/admin/users/{user_id}/llm-settings")
def admin_put_user_llm_settings(
    user_id: int, req: UserLlmSettingsReq, _: None = Depends(require_admin_token)
):
    api_key = req.api_key
    if api_key is not None and not api_key.strip():
        api_key = None
    upsert_user_llm_settings(
        user_id=user_id,
        mode=req.mode,
        provider=req.provider,
        base_url=req.base_url,
        model=req.model,
        api_key=api_key,
    )
    return {"ok": True, "settings": get_user_llm_settings_masked(user_id=user_id)}


@router.get("/admin/settings/loki")
def admin_get_loki_settings(_: None = Depends(require_admin_token)):
    stored = get_stored_loki_url()
    env = (os.getenv("LOKI_URL") or "").strip()
    return {
        "ok": True,
        "loki_url": get_display_loki_url(),
        "stored": stored,
        "from_env": env,
        "builtin_default": DEFAULT_LOKI_URL,
    }


@router.put("/admin/settings/loki")
def admin_put_loki_settings(req: LokiUrlSettingsReq, _: None = Depends(require_admin_token)):
    set_stored_loki_url(req.loki_url)
    stored = get_stored_loki_url()
    env = (os.getenv("LOKI_URL") or "").strip()
    return {
        "ok": True,
        "loki_url": get_display_loki_url(),
        "stored": stored,
        "from_env": env,
        "builtin_default": DEFAULT_LOKI_URL,
    }


def _sqlite_integrity_ok(path: str) -> bool:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
        return len(rows) == 1 and str(rows[0][0]).lower() == "ok"
    finally:
        conn.close()


@router.get("/admin/db/info")
def admin_db_info(_: None = Depends(require_admin_token)):
    path = ADMIN_SQLITE_PATH
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        ver_row = conn.execute("SELECT sqlite_version() AS v").fetchone()
        sqlite_version = str(ver_row["v"]) if ver_row else ""
        names = [
            str(r["name"])
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        tables: list[dict] = []
        for name in names:
            if not _SAFE_SQLITE_TABLE.match(name):
                continue
            try:
                n = conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()
                row_count = int(n["n"]) if n else 0
            except sqlite3.Error:
                row_count = -1
            tables.append({"name": name, "row_count": row_count})
        return {
            "db_path": path,
            "db_size_bytes": size,
            "sqlite_version": sqlite_version,
            "tables": tables,
        }
    finally:
        conn.close()


@router.post("/admin/db/migrate")
def admin_db_migrate(_: None = Depends(require_admin_token)):
    try:
        run_admin_migrations()
        return {"ok": True, "message": "Migrations complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/admin/db/backup")
def admin_db_backup(_: None = Depends(require_admin_token)):
    if not os.path.isfile(ADMIN_SQLITE_PATH):
        raise HTTPException(status_code=404, detail="Database file not found")
    fname = f"ai_gm_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.db"
    return FileResponse(
        path=ADMIN_SQLITE_PATH,
        media_type="application/octet-stream",
        filename=fname,
    )


@router.post("/admin/db/restore")
async def admin_db_restore(
    file: UploadFile = File(...),
    _: None = Depends(require_admin_token),
):
    fn = (file.filename or "").strip().lower()
    if not fn.endswith(".db"):
        raise HTTPException(status_code=422, detail="File must have a .db extension")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")

    tmp_path = ADMIN_DB_RESTORE_TMP
    try:
        with open(tmp_path, "wb") as out:
            out.write(raw)

        if not _sqlite_integrity_ok(tmp_path):
            raise HTTPException(status_code=422, detail="Integrity check failed")

        if os.path.isfile(ADMIN_SQLITE_PATH):
            shutil.copy2(ADMIN_SQLITE_PATH, ADMIN_DB_BAK_PATH)
        shutil.move(tmp_path, ADMIN_SQLITE_PATH)
    except HTTPException:
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    except Exception as e:
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"ok": True, "message": "Database restored. Restart backend to reload."}


@router.get("/admin/config/export")
def admin_export_config(_: None = Depends(require_admin_token)):
    return export_config()


@router.get("/admin/config/catalog-snapshot")
def admin_export_catalog_snapshot(_: None = Depends(require_admin_token)):
    """All game_config_* catalogue tables (items, weapons, loot, …) for read-only / LLM context."""
    return export_catalog_snapshot()


@router.post("/admin/config/catalog-snapshot/import")
def admin_import_catalog_snapshot(
    body: dict = Body(...),
    dry_run: bool = False,
    _: None = Depends(require_admin_token),
):
    """
    Replace Game Design catalogue tables from a JSON file produced by
    ``GET /admin/config/catalog-snapshot``. Ignores ``game_config_meta`` in the file.
    """
    result = import_catalog_snapshot(body, dry_run=dry_run)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("errors") or ["Import failed"])
    return result


@router.post("/admin/config/import")
def admin_import_config(
    req: ConfigImportReq,
    dry_run: bool = False,
    _: None = Depends(require_admin_token),
):
    result = import_config(req.model_dump(), dry_run=dry_run)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("errors") or ["Import failed"])
    return result


@router.get("/admin/slash-commands")
def admin_slash_commands_get(_: None = Depends(require_admin_token)):
    """Editable descriptions for chat `/` commands (stored in game_config_meta)."""
    return {"commands": get_merged_slash_commands()}


@router.put("/admin/slash-commands")
def admin_slash_commands_put(
    req: SlashCommandsPutReq,
    _: None = Depends(require_admin_token),
):
    try:
        out = set_slash_commands_ui([c.model_dump() for c in req.commands])
        return {"ok": True, "commands": out}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/admin/overview")
def admin_overview(_: None = Depends(require_admin_token)):
    """Dashboard overview: stat cards + recent audit log + recent game turns."""
    path = ADMIN_SQLITE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        users_total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        campaigns_active = conn.execute(
            "SELECT COUNT(*) FROM campaigns WHERE status = 'active'"
        ).fetchone()[0]
        turns_today = conn.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE created_at >= ?", (today,)
        ).fetchone()[0]
        active_combats = conn.execute(
            "SELECT COUNT(*) FROM active_combat WHERE status = 'active'"
        ).fetchone()[0]

        db_size_mb = round(os.path.getsize(path) / (1024 * 1024), 2) if os.path.isfile(path) else 0

        from app.services.llm_admin_service import get_admin_llm_settings_snapshot
        llm_snap = get_admin_llm_settings_snapshot()
        llm_preset_name = (llm_snap.get("active_preset") or {}).get("name") or llm_snap.get("model") or "—"

        audit_rows = conn.execute(
            "SELECT table_name, row_key, operation, performed_at FROM admin_audit_log ORDER BY id DESC LIMIT 10"
        ).fetchall()
        recent_audit = [
            {
                "table_name": r["table_name"],
                "row_key": r["row_key"],
                "operation": r["operation"],
                "performed_at": r["performed_at"],
            }
            for r in audit_rows
        ]

        turn_rows = conn.execute(
            """
            SELECT ct.id, c.title AS campaign_title, ct.user_text, ct.assistant_text, ct.created_at
            FROM campaign_turns ct
            JOIN campaigns c ON c.id = ct.campaign_id
            ORDER BY ct.id DESC LIMIT 10
            """
        ).fetchall()
        recent_turns = [
            {
                "id": r["id"],
                "campaign_title": r["campaign_title"],
                "user_text": (r["user_text"] or "")[:120],
                "assistant_text": (r["assistant_text"] or "")[:120],
                "created_at": r["created_at"],
            }
            for r in turn_rows
        ]

        return {
            "users_total": users_total,
            "campaigns_active": campaigns_active,
            "turns_today": turns_today,
            "active_combats": active_combats,
            "db_size_mb": db_size_mb,
            "llm_preset_name": llm_preset_name,
            "recent_audit": recent_audit,
            "recent_turns": recent_turns,
        }
    finally:
        conn.close()


# ── Campaign Designer ─────────────────────────────────────────────────────────

_DESIGNER_SYSTEM = """Jesteś kreatywnym asystentem mistrza gry (GM) dla mrocznej fantasy RPG w języku polskim.
Tworzysz krótkie, gotowe do użycia fragmenty kampanii: haki fabularne, opisy lokacji, szkice NPCów i opisy starć.

ZASADY:
- Pisz wyłącznie po polsku.
- Zachowaj klimat mrocznej, średniowiecznej fantasy.
- Odpowiedź ZAWSZE w formacie JSON:
  {"title": "<krótki tytuł>", "content": "<treść 100-300 słów>"}
- Tytuł: zwięzły, intrygujący (max 10 słów).
- Treść: konkretna, gotowa do odczytania graczowi lub użycia przez GM.
- Nie dodawaj żadnych wyjaśnień poza JSON-em."""

_DESIGNER_TYPE_HINTS = {
    "hook": "hak fabularny — tajemnicze zlecenie, plotka, zdarzenie wciągające gracza w przygodę",
    "location": "opis lokacji — atmosfera, charakterystyczne detale, potencjalne zagrożenia i sekrety",
    "npc": "szkic NPCa — imię, wygląd, motywacja, sekret, styl dialogu",
    "encounter": "opis starcia — sytuacja, wrogowie, warunki terenu, możliwe rozwiązania inne niż walka",
}


@router.post("/admin/campaign-designer/generate")
def campaign_designer_generate(
    req: CampaignDesignerGenerateReq,
    _: None = Depends(require_admin_token),
):
    hint = _DESIGNER_TYPE_HINTS.get(req.snippet_type, req.snippet_type)
    messages = [
        {"role": "system", "content": _DESIGNER_SYSTEM},
        {"role": "user", "content": f"Typ: {hint}\n\nBrief od GM: {req.brief}"},
    ]

    # Build llm_config from requested preset (unmasked key), or use global active preset
    llm_config = None
    if req.preset_id is not None:
        try:
            preset = get_llm_preset(req.preset_id, mask_api_key=False)
            llm_config = {
                "provider": preset["provider"],
                "base_url": preset["base_url"],
                "model": preset["model"],
                "api_key": preset.get("api_key") or "",
            }
        except KeyError:
            raise HTTPException(status_code=404, detail="Preset not found") from None

    try:
        raw = generate_chat(messages=messages, llm_config=llm_config)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}") from e

    title, content = None, None
    try:
        json_match = re.search(r'\{[^{}]*"title"[^{}]*"content"[^{}]*\}', raw, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            title = parsed.get("title", "").strip()
            content = parsed.get("content", "").strip()
    except Exception:
        pass

    if not title or not content:
        content = raw.strip()
        title = req.brief[:60].strip()

    return {
        "snippet_type": req.snippet_type,
        "title": title,
        "content": content,
        "raw": raw,
    }


@router.get("/admin/campaign-designer/snippets")
def campaign_designer_list_snippets(
    snippet_type: str | None = Query(default=None),
    _: None = Depends(require_admin_token),
):
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if snippet_type:
            rows = conn.execute(
                "SELECT * FROM campaign_snippets WHERE is_active=1 AND snippet_type=? ORDER BY id DESC",
                (snippet_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM campaign_snippets WHERE is_active=1 ORDER BY id DESC",
            ).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/admin/campaign-designer/snippets")
def campaign_designer_save_snippet(
    req: CampaignDesignerSaveReq,
    _: None = Depends(require_admin_token),
):
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "INSERT INTO campaign_snippets (snippet_type, title, content, tags) VALUES (?,?,?,?)",
            (req.snippet_type, req.title, req.content, req.tags),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM campaign_snippets WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.delete("/admin/campaign-designer/snippets/{snippet_id}")
def campaign_designer_delete_snippet(
    snippet_id: int,
    _: None = Depends(require_admin_token),
):
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    try:
        conn.execute(
            "UPDATE campaign_snippets SET is_active=0 WHERE id=?", (snippet_id,)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── Hook Generator (multi-hook from text or PDF) ───────────────────────────────

_HOOKS_SYSTEM = """Jesteś kreatywnym asystentem mistrza gry (GM) dla mrocznej fantasy RPG w języku polskim.
Na podstawie podanego materiału źródłowego (opis, historia, fragment książki) wygeneruj DOKŁADNIE {count} oryginalnych haków fabularnych.

ZASADY:
- Pisz wyłącznie po polsku.
- Każdy hak musi być unikalny i zaskakujący.
- Zachowaj klimat mrocznej, średniowiecznej fantasy.
- Odpowiedź WYŁĄCZNIE jako tablica JSON (bez żadnego tekstu przed ani po):
[
  {{"title": "Tytuł haka 1", "content": "Opis 50-150 słów. Konkretna sytuacja wciągająca gracza."}},
  {{"title": "Tytuł haka 2", "content": "..."}},
  ...
]"""


class HookGenerateReq(BaseModel):
    source_text: str = Field(..., min_length=10, max_length=30000)
    count: int = Field(default=4, ge=1, le=8)
    preset_id: int | None = None


def _build_llm_config_from_preset(preset_id: int | None) -> dict | None:
    if preset_id is None:
        return None
    try:
        preset = get_llm_preset(preset_id, mask_api_key=False)
        return {
            "provider": preset["provider"],
            "base_url": preset["base_url"],
            "model": preset["model"],
            "api_key": preset.get("api_key") or "",
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Preset not found") from None


@router.post("/admin/campaign-designer/extract-pdf")
async def campaign_designer_extract_pdf(
    file: UploadFile = File(...),
    _: None = Depends(require_admin_token),
):
    """Extract text from an uploaded PDF or TXT file."""
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            pages = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
            text = "\n\n".join(pages)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"PDF parse error: {e}") from e
    else:
        # txt / md / other text
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"File decode error: {e}") from e

    MAX_CHARS = 25000
    truncated = len(text) > MAX_CHARS
    return {
        "text": text[:MAX_CHARS],
        "total_chars": len(text),
        "truncated": truncated,
        "pages": len(reader.pages) if filename.endswith(".pdf") else None,
    }


@router.post("/admin/campaign-designer/generate-hooks")
def campaign_designer_generate_hooks(
    req: HookGenerateReq,
    _: None = Depends(require_admin_token),
):
    """Generate multiple hook ideas from source text."""
    system = _HOOKS_SYSTEM.replace("{count}", str(req.count))
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Materiał źródłowy:\n\n{req.source_text[:20000]}"},
    ]
    llm_config = _build_llm_config_from_preset(req.preset_id)

    try:
        raw = generate_chat(messages=messages, llm_config=llm_config)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}") from e

    # Parse JSON array from response
    hooks = []
    try:
        arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if arr_match:
            parsed = json.loads(arr_match.group())
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and item.get("title") and item.get("content"):
                        hooks.append({
                            "title": str(item["title"]).strip(),
                            "content": str(item["content"]).strip(),
                        })
    except Exception:
        pass

    if not hooks:
        # Fallback: wrap the entire raw response as one hook
        hooks = [{"title": "Wygenerowany hak", "content": raw.strip()}]

    return {"hooks": hooks, "raw": raw}


# ── World AI generation (location / npc / enemy) ──────────────────────────────

_WORLD_GEN_PROMPTS = {
    "location": {
        "system": """Jesteś asystentem mistrza gry. Generujesz opisy lokacji dla mrocznej fantasy RPG po polsku.
Odpowiedź WYŁĄCZNIE jako JSON:
{"key": "snake_case_klucz", "label": "Nazwa lokacji", "type": "sub", "description": "Opis 80-150 słów. Atmosfera, detale, zagrożenia, sekrety."}""",
        "hint": "Lokacja do gry fantasy",
    },
    "npc": {
        "system": """Jesteś asystentem mistrza gry. Generujesz postacie NPC dla mrocznej fantasy RPG po polsku.
Odpowiedź WYŁĄCZNIE jako JSON:
{"key": "snake_case_klucz", "label": "Imię i nazwisko", "npc_type": "neutral", "description": "Opis 60-120 słów. Wygląd, osobowość, motywacja, sekret.", "personality": ""}""",
        "hint": "Postać NPC do gry fantasy",
    },
    "enemy": {
        "system": """Jesteś asystentem mistrza gry. Generujesz wrogów dla mrocznej fantasy RPG po polsku.
Odpowiedź WYŁĄCZNIE jako JSON:
{"key": "snake_case_klucz", "label": "Nazwa wroga", "tier": "standard", "hp_base": 20, "ac_base": 12, "attack_bonus": 3, "damage_bonus": 1, "damage_die": "d6", "attacks_per_turn": 1, "damage_type": "physical", "xp_award": 30, "description": "Opis 40-80 słów. Wygląd, zachowanie, taktyka."}""",
        "hint": "Wróg/przeciwnik do gry fantasy",
    },
    "rule": {
        "system": """Jesteś asystentem mistrza gry. Generujesz regułę lokacji dla mrocznej fantasy RPG.
Reguła to mechanizm wpływający na zachowanie gracza w lokacji (np. zakaz walki, wymóg przedmiotu, premia do odpoczynku).
Odpowiedź WYŁĄCZNIE jako JSON:
{"key": "snake_case_klucz", "value": true, "label": "Czytelna nazwa", "description": "Krótki opis efektu 1-2 zdania."}
Wartość `value` może być: true/false (boolean), liczba całkowita, lub krótki string.""",
        "hint": "Reguła lokacji fantasy RPG",
    },
}


class WorldGenReq(BaseModel):
    entity_type: Literal["location", "npc", "enemy", "rule"]
    brief: str = Field(..., min_length=3, max_length=500)
    preset_id: int | None = None


@router.post("/admin/campaign-designer/generate-entity")
def campaign_designer_generate_entity(
    req: WorldGenReq,
    _: None = Depends(require_admin_token),
):
    """Generate a location, NPC, or enemy entity for direct use in the World tab."""
    cfg = _WORLD_GEN_PROMPTS[req.entity_type]
    messages = [
        {"role": "system", "content": cfg["system"]},
        {"role": "user", "content": f"Brief: {req.brief}"},
    ]
    llm_config = _build_llm_config_from_preset(req.preset_id)

    try:
        raw = generate_chat(messages=messages, llm_config=llm_config)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}") from e

    try:
        obj_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if obj_match:
            parsed = json.loads(obj_match.group())
            return {"entity": parsed, "raw": raw}
    except Exception:
        pass

    raise HTTPException(status_code=422, detail=f"LLM returned unparseable response: {raw[:200]}")


# ── Task 26: Scholar Spells — Admin endpoints ─────────────────────────────────

@router.get("/admin/spells")
def admin_list_spells(_: None = Depends(require_admin_token)):
    """List all active spells in the game_config_spells table."""
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM game_config_spells WHERE is_active = 1 ORDER BY tier, key"
        ).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/admin/characters/{character_id}/spells")
def admin_character_spells(character_id: int, _: None = Depends(require_admin_token)):
    """Return the spell book for a character."""
    from app.services.spell_service import get_character_spells
    return {"spells": get_character_spells(character_id)}


@router.post("/admin/characters/{character_id}/spells/learn")
def admin_learn_spell(
    character_id: int,
    req: dict = Body(...),
    _: None = Depends(require_admin_token),
):
    """Teach a character a new spell (rank 1)."""
    from app.services.spell_service import learn_spell
    spell_key = req.get("spell_key", "")
    if not spell_key:
        raise HTTPException(status_code=400, detail="spell_key is required")
    try:
        result = learn_spell(character_id, spell_key)
        return {"ok": True, "spell": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/admin/characters/{character_id}/spells/upgrade")
def admin_upgrade_spell(
    character_id: int,
    req: dict = Body(...),
    _: None = Depends(require_admin_token),
):
    """Upgrade a character's spell to the next rank (max 3)."""
    from app.services.spell_service import upgrade_spell
    spell_key = req.get("spell_key", "")
    if not spell_key:
        raise HTTPException(status_code=400, detail="spell_key is required")
    try:
        result = upgrade_spell(character_id, spell_key)
        return {"ok": True, "spell": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
