from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from app.services.admin_accounts import (
    list_accounts,
    reset_account_sheet,
    soft_delete_account,
    update_account,
)
from app.services.admin_auth import issue_dev_admin_token, verify_admin_token
from app.services.admin_config_transfer import export_config, import_config
from app.services.admin_config import (
    create_condition,
    create_enemy,
    create_weapon,
    create_skill,
    delete_condition,
    delete_enemy,
    delete_weapon,
    delete_skill,
    list_conditions,
    list_enemies,
    list_weapons,
    list_dc,
    list_skills,
    list_stats,
    update_condition,
    update_enemy,
    update_weapon,
    update_dc,
    update_skill,
    update_stat,
)
from app.services.user_llm_settings import (
    get_user_llm_settings_full,
    get_user_llm_settings_masked,
    upsert_user_llm_settings,
)

router = APIRouter()


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
    key: str
    label: str
    linked_stat: str
    rank_ceiling: int = 5
    sort_order: int = 0
    description: str | None = ""


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


class ConfigImportReq(BaseModel):
    config_version: str
    tables: dict
    exported_at: str | None = None
    exported_by: str | None = None
    excluded: list[str] | None = None


class UserLlmSettingsReq(BaseModel):
    provider: str
    base_url: str
    model: str
    api_key: str | None = None


class WeaponCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    damage_die: str
    linked_stat: str
    allowed_classes: list[str]
    is_active: bool = True


class WeaponPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    damage_die: str | None = None
    linked_stat: str | None = None
    allowed_classes: list[str] | None = None
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
    damage_die: str
    description: str | None = None
    is_active: bool = True


class EnemyPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    hp_base: int | None = None
    ac_base: int | None = None
    attack_bonus: int | None = None
    damage_die: str | None = None
    description: str | None = None
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
    is_active: bool = True


class ConditionPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    effect_json: str | None = None
    description: str | None = None
    is_active: bool | None = None
    force: bool = False


class ConditionDeleteReq(BaseModel):
    force: bool = False


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
            damage_die=req.damage_die,
            description=req.description,
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
            damage_die=req.damage_die,
            description=req.description,
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


@router.patch("/admin/accounts/{account_id}")
def admin_patch_account(
    account_id: int, req: AccountPatchReq, _: None = Depends(require_admin_token)
):
    try:
        item = update_account(
            account_id,
            display_name=req.display_name,
            is_active=req.is_active,
        )
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found") from None
    except ValueError as e:
        if str(e) == "invalid_is_active":
            raise HTTPException(status_code=422, detail="is_active must be 0 or 1") from None
        raise HTTPException(status_code=422, detail="Invalid account payload") from None


@router.post("/admin/accounts/{account_id}/reset-sheet")
def admin_reset_account_sheet(account_id: int, _: None = Depends(require_admin_token)):
    try:
        return reset_account_sheet(account_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found") from None


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


@router.get("/admin/config/export")
def admin_export_config(_: None = Depends(require_admin_token)):
    return export_config()


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
