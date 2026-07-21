"""#1527 (fala 4) — Kontrola świata: lint zamiast cichej samonaprawy.

Endpointy pod `/api/admin/world/lint` (auth: warstwa `/api/admin`, #1187):

* `GET  /api/admin/world/lint`          — lista wykrytych rozjazdów
* `GET  /api/admin/world/lint/count`    — sama liczba (badge w nawigacji)
* `POST /api/admin/world/lint/fix`      — napraw JEDEN rozjazd (`issue_id`)
* `GET  /api/admin/world/lint/history`  — kronika napraw (start + panel)
"""
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.services.world_lint_service import (
    LINT_LIST_LIMIT,
    assign_host,
    create_host,
    duplicate_compare,
    fix_world_lint_issue,
    fix_world_lint_rule,
    host_candidates,
    host_suggestion_context,
    lint_flags,
    lint_history,
    lint_issue_count,
    resolve_duplicate,
    run_world_lint,
)

router = APIRouter(prefix="/api/admin/world", tags=["admin-world-lint"])


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


class LintFixRequest(BaseModel):
    issue_id: str


class LintFixRuleRequest(BaseModel):
    rule: str


@router.get("/lint")
def get_world_lint(limit: int = LINT_LIST_LIMIT):
    """Raport lintu świata dla zakładki 🩺 Kontrola świata."""
    conn = _get_db()
    try:
        return run_world_lint(conn, limit=max(1, min(int(limit), 1000)))
    finally:
        conn.close()


@router.get("/lint/count")
def get_world_lint_count():
    """Sama liczba rozjazdów — badge przy pozycji „Świat" w nawigacji."""
    conn = _get_db()
    try:
        return {"count": lint_issue_count(conn)}
    finally:
        conn.close()


@router.post("/lint/fix")
def post_world_lint_fix(payload: LintFixRequest):
    """Napraw jeden rozjazd. Reguły treściowe odmawiają (400) — nie zgadujemy."""
    conn = _get_db()
    try:
        result = fix_world_lint_issue(conn, payload.issue_id)
    finally:
        conn.close()
    if not result["fixed"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/lint/fix-rule")
def post_world_lint_fix_rule(payload: LintFixRuleRequest):
    """Napraw całą grupę jednej reguły („Napraw wszystkie").

    Celowo NIE ma endpointu „napraw wszystko" dla całego lintu — globalny guzik
    odtworzyłby ciche zamiatanie, tylko z jednym kliknięciem zamiast crona.
    """
    conn = _get_db()
    try:
        result = fix_world_lint_rule(conn, payload.rule)
    finally:
        conn.close()
    if result["refused"]:
        raise HTTPException(status_code=400, detail=result["messages"][0])
    return result


class AssignHostRequest(BaseModel):
    location_key: str
    npc_key: str


class CreateHostRequest(BaseModel):
    location_key: str
    label: str
    npc_type: str = "neutral"
    description: str = ""


class ResolveDuplicateRequest(BaseModel):
    keep: str
    drop: str
    move_assets: bool = True


@router.get("/lint/flags")
def get_world_lint_flags():
    """Mapa `klucz lokacji → problemy` — znacznik 🩺 w zakładkach Lokacje/Floating/Do zatwierdzenia."""
    conn = _get_db()
    try:
        return {"flags": lint_flags(conn)}
    finally:
        conn.close()


@router.get("/lint/host-candidates")
def get_host_candidates(location_key: str):
    """NPC bez przydziału — lista do rozwijanej listy „wybierz gospodarza"."""
    conn = _get_db()
    try:
        return {"candidates": host_candidates(conn, location_key)}
    finally:
        conn.close()


@router.post("/lint/assign-host")
def post_assign_host(payload: AssignHostRequest):
    conn = _get_db()
    try:
        result = assign_host(conn, payload.location_key, payload.npc_key)
    finally:
        conn.close()
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/lint/create-host")
def post_create_host(payload: CreateHostRequest):
    conn = _get_db()
    try:
        result = create_host(
            conn, payload.location_key, label=payload.label,
            npc_type=payload.npc_type, description=payload.description,
        )
    finally:
        conn.close()
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


class SuggestHostRequest(BaseModel):
    location_key: str


@router.post("/lint/suggest-host")
def post_suggest_host(payload: SuggestHostRequest):
    """🤖 Podpowiedź AI: imię, rola i jednozdaniowy opis gospodarza pasujący do miejsca.

    Nic nie zapisuje — zwraca propozycję do formularza, którą admin akceptuje
    albo poprawia. Model dostaje fakty o lokacji (nazwa, kraina, podtyp, rodzic),
    żeby karczmarz z Kresów nie brzmiał jak karczmarz z Siwych Grań.
    """
    conn = _get_db()
    try:
        ctx = host_suggestion_context(conn, payload.location_key)
    finally:
        conn.close()
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Nie ma lokacji „{payload.location_key}”.")

    from app.services.llm_service import (
        content_llm_enabled, generate_chat, resolve_content_llm_config,
    )
    from app.services.world_naming_service import (
        clean_person_label, looks_like_modern_polish_name, name_already_taken,
        naming_prompt_block,
    )

    conn = _get_db()
    try:
        naming = naming_prompt_block(conn, ctx["region"])
    finally:
        conn.close()

    sys_prompt = (
        "Jesteś twórcą postaci pobocznych do gry fantasy osadzonej w świecie Kresy. "
        "Tworzysz gospodarza konkretnego miejsca usługowego: postać z imieniem, rzemiosłem "
        "i jednym charakterystycznym szczegółem.\n\n"
        f"{naming}\n\n"
        "POZOSTAŁE ZASADY:\n"
        "- Rola z listy: neutral (zwykły mieszkaniec), merchant (handluje), "
        "quest_giver (daje zadania), ally (sojusznik).\n"
        "- Opis: JEDNO zdanie po polsku, konkret zamiast ogólników.\n"
        'Zwróć WYŁĄCZNIE JSON: {"label":"...","npc_type":"merchant","description":"..."}'
    )
    user_prompt = (
        f"Miejsce: {ctx['label']} (klucz {ctx['key']})\n"
        f"Rodzaj: {ctx['role_pl'] or ctx['subtype'] or 'nieokreślony'}\n"
        f"Kraina: {ctx['region'] or 'kresy'}\n"
        + (f"Leży w: {ctx['parent_label']}\n" if ctx["parent_label"] else "")
        + (f"Opis miejsca: {ctx['description'][:400]}\n" if ctx["description"] else "")
        + "\nZaproponuj gospodarza tego miejsca."
    )
    import json
    import re

    def _ask(extra_system: str = "") -> dict:
        try:
            cfg = resolve_content_llm_config() if content_llm_enabled() else None
            raw = generate_chat(
                messages=[{"role": "system", "content": sys_prompt + extra_system},
                          {"role": "user", "content": user_prompt}],
                llm_config=cfg, call_type="world_lint_host_suggest",
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Model nie odpowiedział: {exc}") from None
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            raise HTTPException(status_code=502, detail="Model nie zwrócił poprawnej propozycji.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502, detail="Model nie zwrócił poprawnej propozycji."
            ) from None

    conn = _get_db()
    try:
        data = _ask()
        label = clean_person_label(data.get("label") or "")
        naming_retry = ""
        # Dwa sposoby, na jakie model psuje kanon nazw:
        #  1. sięga po współczesne polskie imię („Agnieszka Kruk"),
        #  2. kopiuje żywcem przykład, który dostał (few-shot kusi).
        # Na każdy z nich dajemy JEDNO drugie podejście z twardszą instrukcją,
        # zamiast wypuszczać złą propozycję na ekran.
        if looks_like_modern_polish_name(label):
            naming_retry = "modern_polish"
        elif name_already_taken(conn, label):
            naming_retry = "duplicate"
        if naming_retry:
            reason = ("to wspolczesne polskie imie/nazwisko"
                      if naming_retry == "modern_polish"
                      else "taka postac juz istnieje w swiecie")
            data = _ask(
                f"\n\nUWAGA: poprzednia propozycja ({label}) jest zla: {reason}. "
                "Zaproponuj INNE, NOWE imie, scisle w stylu krainy opisanym wyzej."
            )
            label = clean_person_label(data.get("label") or "")
        naming_warning = looks_like_modern_polish_name(label) or name_already_taken(conn, label)
    finally:
        conn.close()

    return {
        "label": label,
        "npc_type": data.get("npc_type") if data.get("npc_type") in
        ("neutral", "merchant", "quest_giver", "ally") else "neutral",
        "description": str(data.get("description") or "").strip(),
        "naming_retry": naming_retry or None,
        "naming_warning": naming_warning,
        "context": ctx,
    }


@router.get("/lint/duplicate-compare")
def get_duplicate_compare(a: str, b: str):
    """Dwie karty duplikatu obok siebie — fakty do decyzji, którą zostawić."""
    conn = _get_db()
    try:
        return duplicate_compare(conn, a, b)
    finally:
        conn.close()


@router.post("/lint/resolve-duplicate")
def post_resolve_duplicate(payload: ResolveDuplicateRequest):
    """Rozstrzygnij duplikat: człowiek wskazuje, którą kartę zostawić."""
    conn = _get_db()
    try:
        result = resolve_duplicate(
            conn, keep=payload.keep, drop=payload.drop, move_assets=payload.move_assets
        )
    finally:
        conn.close()
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/lint/history")
def get_world_lint_history(limit: int = 50):
    """Kronika napraw — co naprawił start backendu, co naprawił człowiek."""
    conn = _get_db()
    try:
        return {"entries": lint_history(conn, limit=max(1, min(int(limit), 500)))}
    finally:
        conn.close()
