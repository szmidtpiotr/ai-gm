"""Phase 9A-4 — NPC shop API."""

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.jwt_auth import assert_character_owner
from app.services import shop_service
from app.services import guild_shop_service
from app.services import night_economy_service as night_econ

router = APIRouter(tags=["shop"])


class ShopBuyRequest(BaseModel):
    character_id: int
    item_type: str
    item_key: str


class ShopSellRequest(BaseModel):
    character_id: int
    inventory_id: int


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
    if "insufficient_gold" in msg:
        return HTTPException(status_code=402, detail="Not enough gold")
    if "price_or_catalog_missing" in msg:
        return HTTPException(status_code=404, detail="Item price is not configured")
    # #1127: night economy refusals → 403 with the player-facing Polish message.
    if "shop_closed_night" in msg:
        return HTTPException(status_code=403, detail=night_econ.SHOP_CLOSED_MSG)
    if "black_market_day" in msg:
        return HTTPException(status_code=403, detail=night_econ.BLACK_MARKET_DAY_MSG)
    # #1342 gildia kupiecka
    if "npc_not_guild" in msg:
        return HTTPException(status_code=404, detail="NPC is not a guild merchant")
    if "component_no_trade" in msg:
        return HTTPException(status_code=403, detail="Ten komponent jest niehandlowalny (tylko z farmienia)")
    return HTTPException(status_code=400, detail=str(e))


@router.get("/shop/{npc_id}")
def get_shop(npc_id: int, character_id: int = Query(...), location_key: str | None = Query(None)):
    try:
        data = shop_service.get_shop_inventory(npc_id=npc_id, character_id=character_id, location_key=location_key)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.get("/shop/by-key/{npc_key}")
def get_shop_by_key(npc_key: str, character_id: int = Query(...), location_key: str | None = Query(None)):
    try:
        data = shop_service.get_shop_inventory_by_key(npc_key=npc_key, character_id=character_id, location_key=location_key)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


# ── #1342 BL-D3 — Gildia kupiecka: handel komponentami ─────────────────────────

class GuildBuyRequest(BaseModel):
    character_id: int
    item_key: str


class GuildSellRequest(BaseModel):
    character_id: int
    inventory_id: int


@router.get("/guild-shop/{npc_id}")
def get_guild_shop(npc_id: int, character_id: int = Query(...)):
    try:
        data = guild_shop_service.get_guild_shop(npc_id=npc_id, character_id=character_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.get("/guild-shop/by-key/{npc_key}")
def get_guild_shop_by_key(npc_key: str, character_id: int = Query(...)):
    try:
        data = guild_shop_service.get_guild_shop_by_key(npc_key=npc_key, character_id=character_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/guild-shop/{npc_id}/buy")
def post_guild_buy(npc_id: int, body: GuildBuyRequest, authorization: str | None = Header(None)):
    assert_character_owner(body.character_id, authorization)
    try:
        data = guild_shop_service.buy_component(
            character_id=body.character_id, npc_id=npc_id, item_key=body.item_key,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/guild-shop/{npc_id}/sell")
def post_guild_sell(npc_id: int, body: GuildSellRequest, authorization: str | None = Header(None)):
    assert_character_owner(body.character_id, authorization)
    try:
        data = guild_shop_service.sell_component(
            character_id=body.character_id, npc_id=npc_id, inventory_id=body.inventory_id,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/shop/{npc_id}/buy")
def post_shop_buy(npc_id: int, body: ShopBuyRequest, authorization: str | None = Header(None)):
    assert_character_owner(body.character_id, authorization)
    try:
        data = shop_service.buy_item(
            character_id=body.character_id,
            npc_id=npc_id,
            item_type=body.item_type,
            item_key=body.item_key,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e


@router.post("/shop/{npc_id}/sell")
def post_shop_sell(npc_id: int, body: ShopSellRequest, authorization: str | None = Header(None)):
    assert_character_owner(body.character_id, authorization)
    try:
        # #1127: npc_id lets sell_item gate by shop hours / apply black-market ×0.6.
        data = shop_service.sell_item(
            character_id=body.character_id,
            inventory_id=body.inventory_id,
            npc_id=npc_id,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_shop_error(e) from e
