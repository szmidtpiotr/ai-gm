"""Phase 8C — inventory and item read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import loot_service

router = APIRouter(tags=["inventory"])

_ITEM_TYPES = {"armor", "weapon", "consumable", "misc", "quest"}


class EquipRequest(BaseModel):
    """slot null/omit = unequip this row (8E-3)."""

    inventory_id: int
    slot: str | None = None
    # HI4 (#627): tryb Inspektora Bohatera — guard live-lock (409) + audyt mutacji.
    inspector: bool = False
    force: bool = False


class GoldDeltaRequest(BaseModel):
    delta: int
    reason: str = ""


class UseRequest(BaseModel):
    inventory_id: int


@router.get("/inventory/{character_id}")
def get_inventory(character_id: int):
    try:
        data = loot_service.get_character_inventory(character_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg:
            raise HTTPException(status_code=404, detail="Character not found") from e
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/inventory/{character_id}/{inventory_id}/detail")
def get_inventory_item_detail(character_id: int, inventory_id: int):
    """D5 (#380) — full detail for one inventory entry (item-view modal)."""
    try:
        data = loot_service.get_inventory_item_detail(character_id, inventory_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/inventory/{character_id}/{inventory_id}/drop-comparison")
def get_inventory_drop_comparison(character_id: int, inventory_id: int):
    """U17 (#565) — celebration data for a weapon/armor drop: rarity, affixes, stat
    diff vs the equipped item, suggested slot. Returns data=None for non-gear."""
    try:
        data = loot_service.build_drop_comparison(character_id, inventory_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/inventory/{character_id}/equip")
def post_inventory_equip(character_id: int, body: EquipRequest):
    # HI4 (#627): mutacja inspektora → blokada podczas walki/tury + audyt.
    # Zwykłe wywołania (gra) nie ustawiają `inspector` → ścieżka niezmieniona.
    if body.inspector:
        from app.services import inspector_guard

        inspector_guard.guard_or_raise(character_id, force=body.force)
    try:
        slot_raw = body.slot
        if slot_raw is None or (isinstance(slot_raw, str) and not str(slot_raw).strip()):
            data = loot_service.unequip_item(character_id, body.inventory_id)
            op = "inspector:unequip"
        else:
            data = loot_service.equip_item(character_id, body.inventory_id, str(slot_raw))
            op = "inspector:equip"
        if body.inspector:
            from app.services import inspector_guard

            inspector_guard.audit(
                character_id,
                op,
                {"inventory_id": body.inventory_id, "slot": body.slot},
                data if isinstance(data, dict) else {"result": str(data)},
            )
        return {"ok": True, "data": data}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg or "inventory entry not found" in msg:
            raise HTTPException(status_code=404, detail=str(e)) from e
        if "invalid slot" in msg:
            raise HTTPException(status_code=400, detail="invalid slot") from e
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/inventory/{character_id}/use")
def post_inventory_use(character_id: int, body: UseRequest):
    try:
        data = loot_service.use_inventory_item(character_id, body.inventory_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg or "inventory entry not found" in msg:
            raise HTTPException(status_code=404, detail=str(e)) from e
        if "condition_not_found" in msg:
            raise HTTPException(status_code=422, detail="Referenced condition was not found") from e
        if "not usable" in msg or "unsupported_item_effect" in msg or "no usable effects" in msg:
            raise HTTPException(status_code=400, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/inventory/{character_id}/{inventory_id}")
def delete_inventory_entry(character_id: int, inventory_id: int, force: bool = Query(False)):
    try:
        data = loot_service.delete_inventory_item(character_id, inventory_id, force=force)
        return {"ok": True, "data": data}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg or "inventory entry not found" in msg:
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/items")
def get_items(item_type: str | None = Query(None)):
    if item_type is not None and str(item_type).strip().lower() not in _ITEM_TYPES:
        raise HTTPException(status_code=400, detail="invalid item_type")
    data = loot_service.list_config_items(item_type=item_type)
    return {"ok": True, "data": data}


@router.get("/items/{key}")
def get_item(key: str):
    data = loot_service.get_config_item(key)
    if not data:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True, "data": data}


@router.get("/characters/{character_id}/gold")
def get_character_gold(character_id: int):
    try:
        g = loot_service.get_character_gold(character_id)
        return {"ok": True, "data": {"gold_gp": g}}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg:
            raise HTTPException(status_code=404, detail="Character not found") from e
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/characters/{character_id}/gold")
def post_character_gold_delta(character_id: int, body: GoldDeltaRequest):
    try:
        if int(body.delta) == 0:
            raise HTTPException(status_code=400, detail="delta must be non-zero")
        g = loot_service.apply_character_gold_delta(character_id, int(body.delta), body.reason or None)
        return {"ok": True, "data": {"gold_gp": g}}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg:
            raise HTTPException(status_code=404, detail="Character not found") from e
        if "non-zero" in msg or "negative" in msg:
            raise HTTPException(status_code=400, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
