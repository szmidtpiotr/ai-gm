"""#1336 BL-C1 — endpointy rzemiosła.

  GET  /api/locations/{loc_ref}/crafting  — przepisy lokalnych rzemieślników
  POST /api/characters/{character_id}/craft — wykonanie przepisu

Cienkie wrappery na crafting_service (logika + walidacja tam).
"""

from fastapi import APIRouter, Body, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.jwt_auth import resolve_authed_user_id
from app.services import crafting_service
from app.services.crafting_service import CraftError

router = APIRouter(tags=["Crafting"])


@router.get("/locations/{loc_ref}/crafting")
def location_crafting(loc_ref: str):
    """Przepisy dostępne u rzemieślników w lokacji (loc_ref = klucz lub id)."""
    try:
        return crafting_service.get_location_crafting(loc_ref)
    except CraftError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


class CraftRequest(BaseModel):
    recipe_key: str
    target_inventory_id: int | None = None
    user_id: int | None = None


@router.post("/characters/{character_id}/craft")
def craft_recipe(
    character_id: int,
    body: CraftRequest = Body(...),
    user_id: int | None = Query(None),
    authorization: str | None = Header(default=None),
):
    """Wykonaj przepis — bohater dostarcza komponenty, rzemieślnik wytwarza za opłatą."""
    resolve_authed_user_id(authorization, body.user_id or user_id)
    try:
        return crafting_service.craft(
            character_id,
            body.recipe_key,
            target_inventory_id=body.target_inventory_id,
        )
    except CraftError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
