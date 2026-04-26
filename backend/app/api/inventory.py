"""Phase 8C — inventory and item read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import loot_service

router = APIRouter(tags=["inventory"])

_ITEM_TYPES = {"armor", "weapon", "consumable", "misc", "quest"}


class EquipRequest(BaseModel):
    inventory_id: int
    slot: str


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


@router.post("/inventory/{character_id}/equip")
def post_inventory_equip(character_id: int, body: EquipRequest):
    try:
        data = loot_service.equip_item(character_id, body.inventory_id, body.slot)
        return {"ok": True, "data": data}
    except ValueError as e:
        msg = str(e).lower()
        if "character not found" in msg or "inventory entry not found" in msg:
            raise HTTPException(status_code=404, detail=str(e)) from e
        if "invalid slot" in msg:
            raise HTTPException(status_code=400, detail="invalid slot") from e
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
