"""Notification dispatcher preview — Issue #602 (Faza N0/N2).

Admin / test (unauthenticated, like other /api/admin/* read surfaces):
    GET  /api/admin/notify/preview/{user_id}  — dry-run channel selection (no send)

#1178: the player GET/PUT /api/users/notify-prefs endpoints were removed — dead,
zero UI consumers. Prefs are still read/written internally via
`notification_service.get_prefs`/`set_prefs`.
"""

from fastapi import APIRouter

from app.services import notification_service as ns

router = APIRouter()


@router.get("/admin/notify/preview/{user_id}")
def admin_notify_preview(user_id: int):
    """Dry-run: which channel WOULD fire for this player. No send, no log."""
    return ns.preview_channel(user_id)
