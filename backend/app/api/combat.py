"""Phase 8A — combat state API (solo campaigns)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import combat_service as combat
from app.services.client_ui_config import is_slash_command_enabled

router = APIRouter(tags=["combat"])


class CombatStartRequest(BaseModel):
    enemy_keys: list[str] = Field(..., min_length=1)
    character_id: int | None = None


class ResolveAttackRequest(BaseModel):
    roll_result: int | None = None
    raw_d20: int | None = None
    attacker: str = "player"
    enemy_key: str | None = None
    target_id: str | None = None
    spell_key: str | None = None  # Scholar: which spell to cast


class ClaimLootRequest(BaseModel):
    character_id: int
    selected_indexes: list[int] = Field(default_factory=list)


def _first_character_id(campaign_id: int) -> int:
    conn = sqlite3.connect(combat.COMBAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM characters WHERE campaign_id = ? ORDER BY id ASC LIMIT 1",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=400, detail="Campaign has no character")
    return int(row["id"])


@router.post("/campaigns/{campaign_id}/combat/start")
def post_start_combat(campaign_id: int, body: CombatStartRequest):
    if not is_slash_command_enabled("/atak"):
        raise HTTPException(
            status_code=403,
            detail="Komenda /atak (start walki w silniku) jest wyłączona przez administratora.",
        )
    if combat.get_active_combat(campaign_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "W tej kampanii jest już aktywna walka. Zakończ ją (np. narracja po zwycięstwie, "
                "przycisk ucieczki) zanim rozpoczniesz nową sesję w silniku."
            ),
        )
    ch_id = body.character_id if body.character_id is not None else _first_character_id(campaign_id)
    try:
        state = combat.initiate_combat(campaign_id, ch_id, body.enemy_keys)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return state


@router.get("/campaigns/{campaign_id}/combat")
def get_combat(campaign_id: int):
    """Active combat only. When none, 200 + active:false (avoid 404 spam from UI polling)."""
    st = combat.get_active_combat(campaign_id)
    if not st:
        return {"active": False, "combat": None}
    return {"active": True, "combat": st}


@router.get("/campaigns/{campaign_id}/combat/turns")
def get_combat_turns(campaign_id: int, limit: int = Query(50, ge=1, le=200)):
    """Chronological combat engine log for the campaign's current combat row (active or ended)."""
    rows = combat.list_combat_turns_for_campaign(campaign_id, limit=limit)
    return {"turns": rows, "count": len(rows)}


@router.get("/campaigns/{campaign_id}/combat/turns/history")
def get_combat_turns_history(campaign_id: int, limit: int = Query(500, ge=1, le=2000)):
    """All combat_turns rows for the campaign across every combat (used to rehydrate chat after F5)."""
    rows = combat.list_all_combat_turns_for_campaign(campaign_id, limit=limit)
    return {"turns": rows, "count": len(rows)}


@router.post("/campaigns/{campaign_id}/combat/resolve-attack")
def post_resolve_attack(campaign_id: int, body: ResolveAttackRequest):
    try:
        res = combat.resolve_attack(
            campaign_id,
            body.roll_result,
            attacker=body.attacker,
            raw_d20=body.raw_d20,
            spell_key=body.spell_key,
            target_id=body.target_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # #598: dual-wield — drugi atak off-hand (ta sama tura) gdy para broni = 'dual_attack'.
    # PRZED advance_turn, by oba ataki rozliczyły się w jednej turze gracza. Tylko melee
    # (nie spell), tura nie zablokowana, walka wciąż aktywna (resolve_offhand_followup waliduje).
    if body.attacker == "player" and not res.get("blocked") and not body.spell_key:
        try:
            off = combat.resolve_offhand_followup(campaign_id)
        except ValueError:
            off = None
        if off is not None:
            res["offhand"] = off
            res["combat_state"] = off.get("combat_state", res.get("combat_state"))

    # #848: advance turn server-side after player attack so enemy turn is never lost on F5/reload.
    # Skip if blocked (turn not consumed: out_of_range, mana_insufficient, unsupported_effect).
    # Mirrors post_enemy_turn — advance only when combat still active.
    if body.attacker == "player" and not res.get("blocked"):
        snap = combat.load_combat_snapshot(campaign_id)
        if snap and snap.get("status") == "active":
            try:
                res["advance_turn"] = combat.advance_turn(campaign_id)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
        else:
            res["advance_turn"] = "ended"
        res["combat_state"] = combat.load_combat_snapshot(campaign_id)

    return res


@router.post("/campaigns/{campaign_id}/combat/zone-change")
def post_zone_change(campaign_id: int):
    """T34 — Player toggles their combat zone (engaged ↔ ranged). Consumes the turn."""
    try:
        return combat.change_player_zone(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/campaigns/{campaign_id}/combat/wrestling")
def post_wrestling(campaign_id: int, body: dict | None = None):
    """S17 — Zapasy: akcja bojowa, test przeciwny STR vs STR. Sukces nakłada kondycję na
    wroga (slowed), krytyk → stunned, krytyczna porażka → gracz sam slowed. Wymaga zwarcia
    (engaged) — cel poza zwarciem zwraca blocked bez konsumpcji tury. Konsumuje turę."""
    target_ref = str((body or {}).get("target_ref") or "").strip() or None
    try:
        return combat.resolve_wrestling(campaign_id, target_ref=target_ref)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/campaigns/{campaign_id}/combat/declare-reaction")
def post_declare_reaction(campaign_id: int, body: dict | None = None):
    """S15 — Player pre-declares a combat reaction (e.g. dodge) toggle. Does NOT consume the turn.
    Requires the player's turn and the matching skill rank >= 1 (skill-gated)."""
    rt = str((body or {}).get("reaction_type") or "dodge").strip().lower()
    try:
        return combat.declare_player_reaction(campaign_id, rt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/campaigns/{campaign_id}/combat/resolve-reaction")
def post_resolve_reaction(campaign_id: int, body: dict | None = None):
    """SF10 (#633) — rozlicza okno reakcji otwarte przez trafienie wroga.

    Body: ``{"choice": "take"|"dodge"|"block"}``. Brak choice → "take" (domyślne,
    tym samym wysyła frontend po timeout 8 s). Wymaga aktywnego `pending_reaction`.
    Po rozliczeniu ZAAWANSOWUJE turę (advance_turn) — turę wstrzymano przy oknie."""
    choice = str((body or {}).get("choice") or "take").strip().lower()
    try:
        res = combat.resolve_reaction(campaign_id, choice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # #864: po rozliczeniu okna reakcji wróg z attacks_per_turn>1 dokańcza pozostałe ciosy
    # tej samej tury PRZED advance_turn. Jeśli kolejny cios znów otworzy okno → pauza ponownie.
    extras = combat.resolve_enemy_followup_attacks(campaign_id)
    if extras:
        res["multiattack"] = extras
        last = extras[-1]
        for _k in ("combat_state", "player_hp_remaining", "player_incapacitated",
                   "reaction_window", "reaction_options", "enemy_name"):
            if _k in last:
                res[_k] = last[_k]
        if last.get("reaction_window"):
            res["advance_turn"] = "awaiting_reaction"
            res["combat_state"] = combat.load_combat_snapshot(campaign_id)
            return res

    snap = combat.load_combat_snapshot(campaign_id)
    if snap and snap.get("status") == "active":
        try:
            res["advance_turn"] = combat.advance_turn(campaign_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        res["advance_turn"] = "ended"
    res["combat_state"] = combat.load_combat_snapshot(campaign_id)
    return res


@router.post("/campaigns/{campaign_id}/combat/enemy-turn")
def post_enemy_turn(campaign_id: int):
    try:
        res = combat.resolve_attack(campaign_id, 0, attacker="enemy")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # #864: multi-attack — wróg z attacks_per_turn>1 wykonuje resztę ciosów w tej samej
    # turze, PRZED advance_turn (analogicznie do off-hand gracza w #598). Pomijamy, gdy
    # pierwszy cios otworzył okno reakcji (pauza — resztę dokończy resolve-reaction).
    if not res.get("reaction_window"):
        extras = combat.resolve_enemy_followup_attacks(campaign_id)
        if extras:
            res["multiattack"] = extras
            last = extras[-1]
            for _k in ("combat_state", "player_hp_remaining", "player_incapacitated",
                       "reaction_window", "reaction_options", "enemy_name"):
                if _k in last:
                    res[_k] = last[_k]

    # SF10 (#633): okno reakcji wstrzymuje turę — NIE zaawansowuj, dopóki gracz nie
    # rozliczy reakcji (resolve-reaction zrobi advance_turn). Zwróć stan z otwartym oknem.
    if res.get("reaction_window"):
        res["advance_turn"] = "awaiting_reaction"
        res["combat_state"] = combat.load_combat_snapshot(campaign_id)
        return res

    snap = combat.load_combat_snapshot(campaign_id)
    if snap and snap.get("status") == "active":
        try:
            new_turn = combat.advance_turn(campaign_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        res["advance_turn"] = new_turn
    else:
        res["advance_turn"] = "ended"
    res["combat_state"] = combat.load_combat_snapshot(campaign_id)
    return res


@router.post("/campaigns/{campaign_id}/combat/flee")
def post_flee(campaign_id: int):
    """
    End active combat as fled. Returns 409 if there is no active combat row
    (distinct from a missing HTTP route — avoids confusion with literal 404).
    Idempotent: if combat already ended with reason fled, returns 200 with already_ended.
    """
    if combat.get_active_combat(campaign_id):
        combat.end_combat(campaign_id, "fled")
        return {
            "fled": True,
            "already_ended": False,
            "combat_state": combat.load_combat_snapshot(campaign_id),
        }
    snap = combat.load_combat_snapshot(campaign_id)
    if (
        snap
        and str(snap.get("status") or "") == "ended"
        and str(snap.get("ended_reason") or "") == "fled"
    ):
        return {"fled": True, "already_ended": True, "combat_state": snap}
    raise HTTPException(
        status_code=409,
        detail=(
            "Brak aktywnej walki — ucieczka z silnika jest możliwa tylko gdy trwa walka "
            "(status active). Jeśli panel jest nieaktualny, odśwież stronę."
        ),
    )


class CastSpellRequest(BaseModel):
    spell_key: str
    character_id: int | None = None


@router.post("/campaigns/{campaign_id}/cast-spell")
def post_cast_spell(campaign_id: int, body: CastSpellRequest):
    """Cast a non-offensive spell (heal/defense/narrative) outside active combat."""
    from app.services import spell_service
    char_id = body.character_id if body.character_id is not None else _first_character_id(campaign_id)
    try:
        result = spell_service.cast_spell_out_of_combat(char_id, body.spell_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return result


@router.get("/campaigns/{campaign_id}/combat/ammo-spent")
def get_combat_ammo_spent(campaign_id: int):
    """#765: ile amunicji wystrzelono w (ostatniej) walce + szansa odzysku — dla pilla."""
    return {"ok": True, "data": combat.get_ammo_spent(campaign_id)}


@router.post("/campaigns/{campaign_id}/combat/recover-ammo")
def post_recover_ammo(campaign_id: int):
    """#765: odzyskaj część wystrzelonej amunicji (rzut per sztuka, 40% startowo)."""
    return {"ok": True, "data": combat.recover_combat_ammo(campaign_id)}


@router.post("/campaigns/{campaign_id}/combat/loot/claim")
def post_claim_loot(campaign_id: int, body: ClaimLootRequest):
    try:
        out = combat.claim_post_combat_loot(
            campaign_id,
            character_id=body.character_id,
            selected_indexes=body.selected_indexes or [],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "data": out}
