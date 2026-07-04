"""Namespace-default admin auth (#1187).

Twardnienie po #1154. Zamiast dokładać `Depends(require_admin_token)` do każdego
routera osobno (łatwo zapomnieć — stąd 7 gołych routerów w #1154), CAŁY namespace
``/api/admin/*`` jest chroniony domyślnie przez jedną warstwę HTTP. Nowy router
pod ``/api/admin`` jest bezpieczny od pierwszej linii, bez pamiętania o guardzie.

Świadomy opt-out: ścieżka w ``ADMIN_AUTH_ALLOWLIST`` przechodzi bez tokena. Lista
ma być MAŁA — każdy wpis to dziura w namespace admina.
"""
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.services.admin_auth import verify_admin_token

ADMIN_PREFIX = "/api/admin"

# Ścieżki pod /api/admin celowo publiczne (bez tokena admina).
# TRZYMAJ WĄSKO — każdy wpis rozszczelnia namespace.
ADMIN_AUTH_ALLOWLIST: set[str] = {
    # login wydaje token — nie może go wymagać, bo wtedy nikt się nie zaloguje
    "/api/admin/dev-login",
}


def is_admin_namespace(path: str) -> bool:
    """Czy ścieżka należy do chronionego namespace /api/admin.

    Granica na '/', żeby '/api/admin-spectate' (widz gracza) NIE był łapany.
    """
    return path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/")


def is_allowlisted(path: str) -> bool:
    """Dokładne dopasowanie — bez prefix-matchu, żeby nie rozszczelniać."""
    return path in ADMIN_AUTH_ALLOWLIST


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    return authorization.removeprefix("Bearer ").strip()


async def admin_namespace_guard(request: Request, call_next):
    """Warstwa: /api/admin/* wymaga ważnego tokena admina domyślnie."""
    path = request.url.path
    if (
        request.method != "OPTIONS"
        and is_admin_namespace(path)
        and not is_allowlisted(path)
    ):
        token = _extract_token(request.headers.get("authorization"))
        # verify_admin_token robi sync-owe zapytanie do SQLite — do threadpoolu,
        # żeby nie blokować pętli async.
        if not token or not await run_in_threadpool(verify_admin_token, token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid admin token"},
            )
    return await call_next(request)
