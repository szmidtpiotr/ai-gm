"""U12 (#559) — endpoint db_lint: GET /api/admin/db-lint."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/db-lint")
def get_db_lint():
    """Uruchom audyt integralności bazy i zwróć raport JSON.

    Returns:
        {"errors": [...], "warnings": [...], "exit_code": int}
        exit_code: 0=czysto, 1=warnings, 2=errors
    """
    from app.services.db_lint_service import run_lint
    return run_lint()
