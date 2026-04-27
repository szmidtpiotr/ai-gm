import os
import re
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.admin_accounts import (
    create_account_admin,
    list_accounts,
    reset_account_sheet,
    soft_delete_account,
    update_account,
)
from app.services.admin_campaigns import (
    list_campaigns_by_owner,
    regenerate_campaign_summary_admin,
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
    update_skill,
    update_stat,
    update_archetype,
    upsert_loot_entry,
)
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
    force: bool = False


class SkillCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    linked_stat: str
    rank_ceiling: int = 5
    sort_order: int | None = None
    description: str | None = ""

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


class AccountPatchReq(BaseModel):
    display_name: str | None = None
    is_active: int | None = None
    is_admin: int | None = Field(default=None, description="0 = player, 1 = admin")


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
    exported_at: str | None = None
    exported_by: str | None = None
    excluded: list[str] | None = None


class SlashCommandItemReq(BaseModel):
    command: str
    description: str = Field(..., max_length=4000)
    enabled: bool


class SlashCommandsPutReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commands: list[SlashCommandItemReq]


class UserLlmSettingsReq(BaseModel):
    provider: str
    base_url: str
    model: str
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
    weight_kg: float = 0.0
    note: str | None = None
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
    weight_kg: float | None = None
    note: str | None = None
    is_active: bool | None = None
    force: bool = False


class WeaponDeleteReq(BaseModel):
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
    weight: float = 0.0
    proficiency_classes: list[str] = []
    weight_kg: float = 0.0
    note: str | None = None
    effect_json: str | None = None
    is_active: bool = True


class ItemPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    item_type: str | None = None
    description: str | None = None
    value_gp: int | None = None
    weight: float | None = None
    proficiency_classes: list[str] | None = None
    weight_kg: float | None = None
    note: str | None = None
    effect_json: str | None = None
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
    consumable_key: str | None = None
    weapon_key: str | None = None
    weight: int = 10
    qty_min: int = 1
    qty_max: int = 1

    @model_validator(mode="after")
    def _xor_loot_source(self) -> "LootEntryReq":
        ik = (self.item_key or "").strip() or None
        ck = (self.consumable_key or "").strip() or None
        wk = (self.weapon_key or "").strip() or None
        if sum(1 for x in (ik, ck, wk) if x is not None) != 1:
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
    base_price: int = 0
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
    base_price: int | None = None
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
            weight_kg=req.weight_kg,
            note=req.note,
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
            weight_kg=req.weight_kg,
            note=req.note,
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
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        raise HTTPException(status_code=422, detail="Invalid weapon payload") from None


@router.delete("/admin/weapons/{key}")
def admin_delete_weapon(key: str, req: WeaponDeleteReq, _: None = Depends(require_admin_token)):
    try:
        delete_weapon(key, force=req.force)
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
            weight=req.weight,
            proficiency_classes=req.proficiency_classes,
            weight_kg=req.weight_kg,
            note=req.note,
            effect_json=req.effect_json,
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
                detail="item_type must be one of: weapon, armor, consumable, misc, quest",
            ) from None
        if str(e) == "invalid_effect_json":
            raise HTTPException(status_code=422, detail="effect_json must be valid JSON") from None
        if str(e) in ("invalid_value_gp", "invalid_weight"):
            raise HTTPException(status_code=422, detail="value_gp and weight must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        if str(e) == "invalid_proficiency_classes":
            raise HTTPException(status_code=422, detail="proficiency_classes must be subset of [warrior,ranger,scholar]") from None
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
            weight=req.weight,
            proficiency_classes=req.proficiency_classes,
            weight_kg=req.weight_kg,
            note=req.note,
            effect_json=req.effect_json,
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
                detail="item_type must be one of: weapon, armor, consumable, misc, quest",
            ) from None
        if str(e) == "invalid_effect_json":
            raise HTTPException(status_code=422, detail="effect_json must be valid JSON") from None
        if str(e) in ("invalid_value_gp", "invalid_weight"):
            raise HTTPException(status_code=422, detail="value_gp and weight must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
        if str(e) == "invalid_proficiency_classes":
            raise HTTPException(status_code=422, detail="proficiency_classes must be subset of [warrior,ranger,scholar]") from None
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
            base_price=req.base_price,
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
        if str(e) == "invalid_charges":
            raise HTTPException(status_code=422, detail="charges must be >= 1") from None
        if str(e) == "invalid_base_price":
            raise HTTPException(status_code=422, detail="base_price must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
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
            base_price=req.base_price,
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
        if str(e) == "invalid_charges":
            raise HTTPException(status_code=422, detail="charges must be >= 1") from None
        if str(e) == "invalid_base_price":
            raise HTTPException(status_code=422, detail="base_price must be >= 0") from None
        if str(e) == "invalid_weight_kg":
            raise HTTPException(status_code=422, detail="weight_kg must be >= 0") from None
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
        if str(e) == "consumable_not_found":
            raise HTTPException(status_code=422, detail="consumable_key must reference an existing consumable") from None
        if str(e) == "invalid_loot_entry_source":
            raise HTTPException(
                status_code=422,
                detail="Exactly one of item_key, weapon_key, or consumable_key must be set for a loot entry.",
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
                detail="Exactly one of item_key, weapon_key, or consumable_key must be set for a loot entry.",
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
                detail="Exactly one of item_key, weapon_key, or consumable_key must be set for a loot entry.",
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


@router.get("/admin/campaigns")
def admin_list_campaigns(
    owner_id: int = Query(..., description="Campaign owner user id"),
    _: None = Depends(require_admin_token),
):
    return {"items": list_campaigns_by_owner(owner_id)}


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
