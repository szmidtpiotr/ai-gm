"""Phase 8D — Locations API (CRUD + drzewo makro/sub)."""

import json
import sqlite3
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field

from app.migrations_admin import DB_PATH
from app.services.admin_auth import verify_admin_token


def require_admin_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency weryfikująca admin token z header Authorization."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

router = APIRouter(prefix="/locations", tags=["Locations"])


# ============================================================================
# Pydantic Models
# ============================================================================

class LocationBase(BaseModel):
    """Base model dla lokalizacji."""
    key: Optional[str] = Field(default=None, min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    parent_key: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location_type: str = Field(default="macro", pattern="^(macro|sub)$")
    rules: Optional[dict | str] = None
    enemy_keys: List[str] = Field(default_factory=list)
    npc_keys: List[str] = Field(default_factory=list)
    safe_for_rest: bool = False
    # Stage 2B-Schema provenance & reuse fields
    created_by: str = Field(default="admin_manual", pattern="^(seed|admin_manual|admin_kreator|gm_runtime|import|adventure_forge)$")
    location_subtype: Optional[str] = Field(default=None, max_length=50)
    biome: Optional[str] = Field(default=None, max_length=50)
    tier: int = Field(default=1, ge=1, le=5)
    canonical: bool = True
    source_campaign_id: Optional[int] = None
    # Hex-world linkage (added in hex_linkage migration)
    world_hex_q: Optional[int] = None
    world_hex_r: Optional[int] = None
    local_hex_q: Optional[int] = None
    local_hex_r: Optional[int] = None
    is_generic: int = 0
    hex_type_key: Optional[str] = None
    # Cosmetic image (added in location-image migration)
    image_url: Optional[str] = None


class LocationCreate(LocationBase):
    """Model dla tworzenia lokalizacji (POST)."""
    pass


class LocationResponse(LocationBase):
    """Model odpowiedzi z ID i timestampami."""
    id: int
    is_active: int = 1
    created_at: str
    updated_at: str
    usage_count: int = 0
    children: List["LocationResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class LocationDetailResponse(LocationResponse):
    """Szczegóły lokalizacji z parentem."""
    parent: Optional[dict] = None


# ============================================================================
# Helper functions
# ============================================================================

def get_db_connection() -> sqlite3.Connection:
    """Zwraca połączenie do bazy danych."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_location_dict(row: sqlite3.Row) -> dict:
    """Konwertuje wiersz SQLite na dict z parsed JSON fields."""
    result = dict(row)
    # Parsuj JSON strings
    for key in ["enemy_keys", "npc_keys"]:
        if result.get(key) and isinstance(result[key], str):
            try:
                result[key] = json.loads(result[key])
            except json.JSONDecodeError:
                result[key] = []
        else:
            result[key] = result.get(key) or []
    # Parsuj rules (JSON string -> object) dla spójności z frontendem
    if isinstance(result.get("rules"), str) and result["rules"].strip():
        try:
            result["rules"] = json.loads(result["rules"])
        except json.JSONDecodeError:
            # Zachowaj oryginalny string, jeśli to nie jest poprawny JSON
            pass
    return result


def serialize_rules(value: dict | str | None) -> str | None:
    """Normalizuje rules do formatu przechowywanego w DB (TEXT/JSON)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    return text or None


def slugify_location_key(label: str) -> str:
    """Generuje lowercase_snake_case key z label."""
    value = str(label or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:100]


def build_location_tree(
    locations: List[dict],
    parent_id: Optional[int] = None
) -> List[dict]:
    """Buduje zagnieżdżone drzewo lokalizacji."""
    tree = []
    for loc in locations:
        if loc.get("parent_id") == parent_id:
            children = build_location_tree(locations, loc["id"])
            if children:
                loc["children"] = children
            else:
                loc["children"] = []
            tree.append(loc)
    return tree


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=List[LocationResponse])
async def list_locations(
    type: Optional[str] = Query(default="all", description="macro|sub|all"),
    parent_id: Optional[int] = Query(default=None, description="Filtruj po parent_id"),
    active_only: int = Query(default=1, ge=0, le=1, description="Tylko aktywne"),
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca drzewo lokalizacji.
    
    Query params:
    - type: macro|sub|all (domyślnie: all)
    - parent_id: tylko dzieci danego parenta
    - active_only: 1 (domyślnie) lub 0
    """
    conn = get_db_connection()
    try:
        # Buduj WHERE clause
        where_clauses = []
        params = []
        
        if active_only == 1:
            where_clauses.append("is_active = 1")
        
        if type in ("macro", "sub"):
            where_clauses.append("location_type = ?")
            params.append(type)
        
        if parent_id is not None:
            where_clauses.append("parent_id = ?")
            params.append(parent_id)
        
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        
        # Pobierz wszystkie pasujące lokalizacje
        cursor = conn.execute(
            f"""
            SELECT * FROM game_locations
            {where_sql}
            ORDER BY location_type DESC, label ASC
            """,
            params
        )
        rows = cursor.fetchall()
        
        # Konwertuj na dicts
        locations = [row_to_location_dict(row) for row in rows]
        
        # Jeśli filtrujemy po parent_id, nie budujemy drzewa — zwracamy flat list
        if parent_id is not None:
            return locations
        
        # Zbuduj drzewo (root nodes = parent_id IS NULL)
        tree = build_location_tree(locations, None)
        return tree
    finally:
        conn.close()


@router.post("", response_model=LocationResponse, status_code=201)
async def create_location(
    data: LocationCreate,
    _admin: None = Depends(require_admin_token),
):
    """
    Tworzy nową lokalizację.
    
    Walidacja:
    - key musi być unikalny (422 jeśli istnieje)
    - parent_id jeśli podany, musi istnieć (404 jeśli nie)
    """
    conn = get_db_connection()
    try:
        key = (data.key or "").strip() if data.key else ""
        if not key:
            if not data.label or not str(data.label).strip():
                raise HTTPException(status_code=422, detail="Label is required to auto-generate key")
            key = slugify_location_key(data.label)
        if not key:
            raise HTTPException(status_code=422, detail="Could not auto-generate key from label")
        # Sprawdź czy key już istnieje
        existing = conn.execute(
            "SELECT 1 FROM game_locations WHERE key = ?",
            (key,)
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=422,
                detail=f"Lokalizacja z kluczem '{key}' już istnieje"
            )
        
        # Sprawdź czy parent istnieje (jeśli podany)
        if data.parent_id is None and data.parent_key:
            parent_row = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1",
                (data.parent_key.strip(),)
            ).fetchone()
            if not parent_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Parent lokalizacja o key '{data.parent_key}' nie istnieje lub jest nieaktywna"
                )
            data.parent_id = int(parent_row["id"])

        if data.parent_id is not None:
            parent = conn.execute(
                "SELECT 1 FROM game_locations WHERE id = ? AND is_active = 1",
                (data.parent_id,)
            ).fetchone()
            
            if not parent:
                raise HTTPException(
                    status_code=404,
                    detail=f"Parent lokalizacja o ID {data.parent_id} nie istnieje lub jest nieaktywna"
                )
        
        # Konwertuj listy na JSON
        enemy_keys_json = json.dumps(data.enemy_keys) if data.enemy_keys else "[]"
        npc_keys_json = json.dumps(data.npc_keys) if data.npc_keys else "[]"
        
        # Wstaw nową lokalizację
        cursor = conn.execute(
            """
            INSERT INTO game_locations
                (key, label, description, parent_id, location_type, rules,
                 enemy_keys, npc_keys, safe_for_rest,
                 created_by, location_subtype, biome, tier, canonical, source_campaign_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                data.label,
                data.description,
                data.parent_id,
                data.location_type,
                serialize_rules(data.rules),
                enemy_keys_json,
                npc_keys_json,
                1 if data.safe_for_rest else 0,
                data.created_by,
                data.location_subtype,
                data.biome,
                data.tier,
                1 if data.canonical else 0,
                data.source_campaign_id,
            )
        )
        conn.commit()
        
        # Pobierz utworzoną lokalizację
        new_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM game_locations WHERE id = ?",
            (new_id,)
        ).fetchone()
        
        return row_to_location_dict(row)
    finally:
        conn.close()


@router.get("/{key}", response_model=LocationDetailResponse)
async def get_location(
    key: str,
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca szczegóły pojedynczej lokalizacji z parentem i dziećmi.
    
    404 gdy lokalizacja nie istnieje lub is_active = 0.
    """
    conn = get_db_connection()
    try:
        # Pobierz lokalizację
        row = conn.execute(
            "SELECT * FROM game_locations WHERE key = ? AND is_active = 1",
            (key,)
        ).fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Lokalizacja '{key}' nie istnieje lub jest nieaktywna"
            )
        
        location = row_to_location_dict(row)
        
        # Pobierz parenta (jeśli istnieje)
        if location.get("parent_id"):
            parent_row = conn.execute(
                "SELECT key, label FROM game_locations WHERE id = ? AND is_active = 1",
                (location["parent_id"],)
            ).fetchone()
            
            if parent_row:
                location["parent"] = dict(parent_row)
            else:
                location["parent"] = None
        else:
            location["parent"] = None
        
        # Pobierz wszystkie lokalizacje do budowy drzewa dzieci
        cursor = conn.execute(
            "SELECT * FROM game_locations WHERE is_active = 1 ORDER BY label"
        )
        all_locations = [row_to_location_dict(r) for r in cursor.fetchall()]
        
        # Zbuduj drzewo dzieci dla tej lokalizacji
        children = build_location_tree(all_locations, location["id"])
        location["children"] = children
        
        return location
    finally:
        conn.close()


@router.put("/{key}", response_model=LocationResponse)
async def update_location(
    key: str,
    data: LocationCreate,
    _admin: None = Depends(require_admin_token),
):
    """
    Aktualizuje istniejącą lokalizację.
    
    - Nie można zmienić parent_id (struktura drzewa jest immutable)
    - Nie można zmienić key (to jest identyfikator)
    """
    conn = get_db_connection()
    try:
        # Sprawdź czy lokalizacja istnieje
        existing = conn.execute(
            "SELECT id, parent_id FROM game_locations WHERE key = ? AND is_active = 1",
            (key,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Lokalizacja '{key}' nie istnieje lub jest nieaktywna"
            )
        
        # Nie pozwalamy zmieniać parent_id (struktura drzewa immutable)
        # ani key (to jest identyfikator)
        
        # Konwertuj listy na JSON
        enemy_keys_json = json.dumps(data.enemy_keys) if data.enemy_keys else "[]"
        npc_keys_json = json.dumps(data.npc_keys) if data.npc_keys else "[]"
        
        # Aktualizuj lokalizację
        conn.execute(
            """
            UPDATE game_locations
            SET label = ?,
                description = ?,
                rules = ?,
                enemy_keys = ?,
                npc_keys = ?,
                safe_for_rest = ?,
                location_subtype = ?,
                biome = ?,
                tier = ?,
                canonical = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE key = ?
            """,
            (
                data.label,
                data.description,
                serialize_rules(data.rules),
                enemy_keys_json,
                npc_keys_json,
                1 if data.safe_for_rest else 0,
                data.location_subtype,
                data.biome,
                data.tier,
                1 if data.canonical else 0,
                key,
            )
        )
        conn.commit()
        
        # Pobierz zaktualizowaną lokalizację
        row = conn.execute(
            "SELECT * FROM game_locations WHERE key = ?",
            (key,)
        ).fetchone()
        
        return row_to_location_dict(row)
    finally:
        conn.close()


class DeleteLocationReq(BaseModel):
    force: bool = False


@router.delete("/{key}", status_code=204)
async def delete_location(
    key: str,
    force: bool = Query(default=False),
    req: DeleteLocationReq | None = None,
    _admin: None = Depends(require_admin_token),
):
    """
    Soft-delete lokalizacji (is_active = 0).

    Nie usuwa fizycznie - tylko deaktywuje.
    Blokowane jeśli lokalizacja ma aktywne dzieci (chyba że force=true, wtedy deaktywujemy też dzieci).

    force=true also hard-deletes a row that was already soft-deleted (is_active=0),
    so admins can purge ghost rows the validator left behind. Session pointers
    that referenced the row are cleared first to avoid FK orphans.
    """
    conn = get_db_connection()
    try:
        # Accept force from either query string (?force=true) or JSON body.
        if req is not None and req.force:
            force = True

        # Sprawdź czy lokalizacja istnieje (active OR inactive — force can purge inactive)
        location = conn.execute(
            "SELECT id, is_active FROM game_locations WHERE key = ?",
            (key,)
        ).fetchone()

        if not location:
            raise HTTPException(
                status_code=404,
                detail=f"Lokalizacja '{key}' nie istnieje"
            )

        location_id = location["id"]
        already_inactive = not location["is_active"]

        if already_inactive:
            if not force:
                raise HTTPException(
                    status_code=404,
                    detail=f"Lokalizacja '{key}' jest już nieaktywna (use force=true to purge)"
                )
            # Hard purge: clear any session pointer that references this row, then DELETE.
            conn.execute(
                "UPDATE game_sessions SET current_location_id = NULL WHERE current_location_id = ?",
                (location_id,)
            )
            conn.execute("DELETE FROM game_locations WHERE id = ?", (location_id,))
            conn.commit()
            return None

        # Sprawdź czy ma aktywne dzieci
        children = conn.execute(
            "SELECT key FROM game_locations WHERE parent_id = ? AND is_active = 1",
            (location_id,)
        ).fetchall()

        if children:
            if not force:
                raise HTTPException(
                    status_code=422,
                    detail=f"Nie można usunąć lokalizacji '{key}' - ma aktywne podlokalizacje: {[c['key'] for c in children]}. Użyj force=true aby usunąć razem z dziećmi."
                )
            # Force=true: deaktywujemy też wszystkie dzieci
            for child in children:
                conn.execute(
                    "UPDATE game_locations SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                    (child["key"],)
                )

        # Soft delete
        conn.execute(
            "UPDATE game_locations SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
            (key,)
        )
        conn.commit()

        return None
    finally:
        conn.close()


@router.get("/admin/locations", response_model=List[LocationResponse])
async def list_locations_admin(
    active_only: int = Query(default=0, ge=0, le=1, description="Tylko aktywne (0 = wszystkie, 1 = tylko active)"),
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca płaską listę wszystkich lokalizacji dla admin panelu (nie drzewo).
    
    Używane przez tabelę admina do bulk operacji.
    """
    conn = get_db_connection()
    try:
        where_sql = ""
        params = []
        if active_only == 1:
            where_sql = "WHERE is_active = 1"
        
        cursor = conn.execute(
            f"""
            SELECT * FROM game_locations
            {where_sql}
            ORDER BY location_type DESC, label ASC
            """,
            params
        )
        rows = cursor.fetchall()
        
        locations = [row_to_location_dict(row) for row in rows]
        return locations
    finally:
        conn.close()


@router.patch("/admin/locations/{key}")
async def patch_location(
    key: str,
    data: dict,
    _admin: None = Depends(require_admin_token),
):
    """
    Częściowa aktualizacja lokalizacji (dla inline edit w tabeli).
    
    Obsługuje pola: label, description, is_active, rules, enemy_keys
    """
    conn = get_db_connection()
    try:
        # Sprawdź czy lokalizacja istnieje
        existing = conn.execute(
            "SELECT * FROM game_locations WHERE key = ?",
            (key,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Lokalizacja '{key}' nie istnieje"
            )
        
        location = row_to_location_dict(existing)
        
        # Buduj update
        updates = []
        params = []
        
        if "label" in data:
            updates.append("label = ?")
            params.append(data["label"])
        if "description" in data:
            updates.append("description = ?")
            params.append(data["description"])
        if "is_active" in data:
            updates.append("is_active = ?")
            params.append(1 if data["is_active"] else 0)
        if "rules" in data:
            if isinstance(data["rules"], dict):
                updates.append("rules = ?")
                params.append(json.dumps(data["rules"]))
            else:
                updates.append("rules = ?")
                params.append(str(data["rules"]))
        if "enemy_keys" in data and isinstance(data["enemy_keys"], list):
            updates.append("enemy_keys = ?")
            params.append(json.dumps(data["enemy_keys"]))
        if "safe_for_rest" in data:
            updates.append("safe_for_rest = ?")
            params.append(1 if data["safe_for_rest"] else 0)
        if "location_subtype" in data:
            updates.append("location_subtype = ?")
            params.append(str(data["location_subtype"]).strip() or None if data["location_subtype"] is not None else None)
        if "biome" in data:
            updates.append("biome = ?")
            params.append(str(data["biome"]).strip() or None if data["biome"] is not None else None)
        if "tier" in data:
            try:
                tier_val = int(data["tier"])
                if not (1 <= tier_val <= 5):
                    raise ValueError
                updates.append("tier = ?")
                params.append(tier_val)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="tier must be an integer 1–5")
        if "canonical" in data:
            updates.append("canonical = ?")
            params.append(1 if data["canonical"] else 0)
        if "npc_keys" in data and isinstance(data["npc_keys"], list):
            updates.append("npc_keys = ?")
            params.append(json.dumps(data["npc_keys"]))
        if "review_status" in data:
            allowed = {"pending_review", "permanent", "discarded"}
            val = str(data["review_status"]).strip()
            if val not in allowed:
                raise HTTPException(status_code=422, detail=f"review_status must be one of {sorted(allowed)}")
            updates.append("review_status = ?")
            params.append(val)
        if "approved" in data:
            updates.append("approved = ?")
            params.append(1 if data["approved"] else 0)
        if "image_url" in data:
            updates.append("image_url = ?")
            params.append(str(data["image_url"]).strip() if data["image_url"] else None)

        if not updates:
            return location
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(key)
        
        conn.execute(
            f"UPDATE game_locations SET {', '.join(updates)} WHERE key = ?",
            params
        )
        conn.commit()
        
        # Pobierz zaktualizowaną
        row = conn.execute("SELECT * FROM game_locations WHERE key = ?", (key,)).fetchone()
        return row_to_location_dict(row)
    finally:
        conn.close()
