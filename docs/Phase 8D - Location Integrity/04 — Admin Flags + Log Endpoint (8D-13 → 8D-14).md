Jesteś programistą Python/FastAPI pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Jak działa autoryzacja admin? (token? rola w sesji? middleware?)
   Pokaż mi fragment kodu gdzie sprawdzana jest rola admin.
2. Czy jest już endpoint PATCH dla sesji? Żebym nie tworzył konfliktu.
3. Czy prefix /api/admin jest już używany? Jakie endpointy tam istnieją?
4. Czy game_config_meta już istnieje jako helper/service czy tylko raw SQL?
5. Czy cokolwiek może failować w testach po dodaniu nowych endpointów admin?

Jeśli nie widzisz blokerów — zaimplementuj poniższe endpointy.

---

## Zadanie 8D-13: Zarządzanie flagami sesji

PATCH /api/admin/session/{session_id}/flags
GET   /api/admin/session/{session_id}/flags
DELETE /api/admin/session/{session_id}/flags/{flag_key}

Dostęp: tylko admin.

PATCH body (dowolna kombinacja):
{"location_integrity_enabled": 0, "location_parser_json_enabled": 1}

Merge logic (NIE nadpisuj całego JSON — tylko zmienione klucze):
def get_effective_flag(key: str, session_id: int) -> int:
    session_flags = get_session_flags(session_id)  # JSON z game_sessions
    if key in session_flags:
        return session_flags[key]
    return int(get_global_flag(key))  # game_config_meta

PATCH/GET response:
{
  "session_id": 42,
  "effective_flags": {"location_integrity_enabled": 0, ...},
  "session_overrides": {"location_integrity_enabled": 0},
  "global_defaults": {"location_integrity_enabled": 1, ...}
}

DELETE → usuwa nadpisanie dla konkretnej flagi (wraca do global defaultu).

---

## Zadanie 8D-14: Log viewer blokad lokalizacji

GET /api/admin/session/{session_id}/location-log
GET /api/admin/location-log  (wszystkie sesje, dla Grafana overview)

Query params: ?limit=50, ?since=2026-04-25T00:00:00

Response:
[{
  "id": 1, "session_id": 42, "character_id": 7,
  "attempted_move": "Las Czarny",
  "current_location_key": "tavern_hanged_man",
  "reason_blocked": "Teleportacja między makro-lokalizacjami",
  "created_at": "2026-04-25T10:32:11"
}]

---

## Wymagania końcowe
- Testy: toggle flagi, merge logic, get log
- python3 -m pytest → wszystkie passed