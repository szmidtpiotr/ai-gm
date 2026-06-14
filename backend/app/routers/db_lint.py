"""U12 (#560, ślad #559) — endpoint db_lint: GET /api/admin/db-lint.

Audyt integralności bazy treści. Wymaga tokenu admina (raport ujawnia
wewnętrzne klucze/strukturę bazy — nie może być publiczny).
"""
from fastapi import APIRouter, Depends, Header, HTTPException

from app.services.admin_auth import verify_admin_token

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin_token(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/db-lint")
def get_db_lint(_: None = Depends(_require_admin_token)):
    """Uruchom audyt integralności bazy i zwróć raport JSON.

    Returns:
        {"errors": [...], "warnings": [...], "exit_code": int, "report": str}
        exit_code: 0=czysto, 1=warnings, 2=errors
    """
    from app.services.db_lint_service import run_lint, format_report
    result = run_lint()
    result["report"] = format_report(result)
    return result
