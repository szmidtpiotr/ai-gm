"""Phase 9A-4 — NPC shop API."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import shop_service

router = APIRouter(tags=["shop"])


class ShopBuyRequest(BaseModel):
    character_id: int
    item_type: str
    item_key: str
    trade_in_inventory_id: Optional[int] = None


class ShopSellRequest(BaseModel):
    character_id: int
    inventory_id: int


class ShopRentRequest(BaseModel):
    character_id: int
    item_type: str
    item_key: str
    duration_turns: int


class ShopReturnRentalRequest(BaseModel):
    character_id: int


def _map_shop_error(e: ValueError) -> HTTPException:
    msg = str(e).lower()
    if "npc_not_found" in msg:
        return HTTPException(status_code=404, detail="NPC not found")
    if "npc_not_shop" in msg:
        return HTTPException(status_code=404, detail="NPC is not a shop")
    if "item_not_in_shop" in msg:
        return HTTPException(status_code=404, detail="Item not available in this shop")
    if "inventory_not_found" in msg:
        return HTTPException(status_code=404, detail="Inventory item not found")
    if "rental_not_found" in msg:
        return HTTPException(status_code=404, detail="Rental not found")
    if "rental_not_active" in msg:
        return HTTPException(status_code=409, detail="Rental is not active")
    if "insufficient_gold" in msg:
        return HTTPException(status_code=402, detail="Not enough gold")
    if "price_or_catalog_missing" in msg:
        return HTTPException(status_code=404, detail="Item price is not configured")
    if "trade_in_not_found" in msg:
        return HTTPException(status_code=404, detail="Trade-in item not found in inventory")
    if "trade_in_not_sellable" in msg:
        return HTTPException(status_code=400, detail="Trade-in item cannot be sold")
    if "invalid_duration" in msg:
        return HTTPException(status_code=400, detail="Rental duration must be at least 1 turn")
    return HTTPException(status_code=400, detail=str(e))


@router.get("/shop/{npc_id}")
def get_shop(npc_id: int, character_id: int = Query(...)):
    try:
        data = shop_service.get_shop_inventory(npc_id=npc_id, character_id=character_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.get("/shop/by-key/{npc_key}")
def get_shop_by_key(npc_key: str, character_id: int = Query(...)):
    try:
        data = shop_service.get_shop_inventory_by_key(npc_key=npc_key, character_id=character_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/shop/{npc_id}/buy")
def post_shop_buy(npc_id: int, body: ShopBuyRequest):
    try:
        data = shop_service.buy_item(
            character_id=body.character_id,
            npc_id=npc_id,
            item_type=body.item_type,
            item_key=body.item_key,
            trade_in_inventory_id=body.trade_in_inventory_id,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/shop/{npc_id}/sell")
def post_shop_sell(npc_id: int, body: ShopSellRequest):
    # npc_id is kept in path for symmetric API and future validation rules.
    _ = npc_id
    try:
        data = shop_service.sell_item(
            character_id=body.character_id,
            inventory_id=body.inventory_id,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/shop/{npc_id}/rent")
def post_shop_rent(npc_id: int, body: ShopRentRequest):
    try:
        data = shop_service.rent_item(
            character_id=body.character_id,
            npc_id=npc_id,
            item_type=body.item_type,
            item_key=body.item_key,
            duration_turns=body.duration_turns,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/shop/rentals/{rental_id}/return")
def post_return_rental(rental_id: int, body: ShopReturnRentalRequest):
    try:
        data = shop_service.return_rental(
            character_id=body.character_id,
            rental_id=rental_id,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e
