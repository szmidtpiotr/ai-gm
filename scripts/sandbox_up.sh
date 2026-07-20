#!/usr/bin/env bash
# Podnieś izolowany sandbox do testów UI (#1488).
#
# To ten sam stack co e2e (docker-compose.e2e.yml): własna baza w wolumenie
# `e2e-data`, stub LLM, porty 13002/18100. Test Runner w panelu admina celuje w
# niego, gdy wybrany cel = „Sandbox" — dzięki temu Playwright nie klika żywego DEV
# i nie zostawia śmieci w prawdziwej bazie.
#
#   ./scripts/sandbox_up.sh      # podnieś + zaseeduj dane testowe
#   ./scripts/sandbox_down.sh    # zatrzymaj (dane w wolumenie zostają)
set -euo pipefail

cd "$(dirname "$0")/.."

E2E_FRONTEND_PORT="${E2E_FRONTEND_PORT:-13002}"
E2E_BACKEND_PORT="${E2E_BACKEND_PORT:-18100}"
export E2E_FRONTEND_PORT E2E_BACKEND_PORT

echo "=== Sandbox: start (frontend :${E2E_FRONTEND_PORT}, backend :${E2E_BACKEND_PORT}) ==="
docker compose -f docker-compose.e2e.yml up -d --build --wait

echo "=== Sandbox: seed danych testowych ==="
docker compose -f docker-compose.e2e.yml exec -T backend python3 scripts/seed_ai_test_env.py \
  || echo "OSTRZEŻENIE: seed nie powiódł się — testy mogą nie mieć danych startowych."

# Specy Playwrighta logują się jako demo/demo (tak jest na DEV). Bez tego konta
# każdy spec pada na pierwszym logowaniu i sandbox jest bezużyteczny.
echo "=== Sandbox: konto demo/demo ==="
docker compose -f docker-compose.e2e.yml exec -T backend python3 - <<'PY'
import sqlite3

import bcrypt

from app.core.db_runtime import resolve_db_path

pw = bcrypt.hashpw(b"demo", bcrypt.gensalt(rounds=12)).decode("ascii")
con = sqlite3.connect(resolve_db_path())
cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
row = con.execute("SELECT id FROM users WHERE username='demo'").fetchone()
if row:
    con.execute("UPDATE users SET password_hash=? WHERE id=?", (pw, row[0]))
    print(f"demo istnieje (id={row[0]}) — hasło ustawione")
else:
    fields = {"username": "demo", "email": "demo@example.invalid", "password_hash": pw}
    for optional, value in (("display_name", "Demo"), ("is_admin", 1), ("is_active", 1), ("role", "admin")):
        if optional in cols:
            fields[optional] = value
    con.execute(
        f"INSERT INTO users ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    print("demo utworzone")
con.commit()
con.close()
PY

if curl -fsS "http://127.0.0.1:${E2E_BACKEND_PORT}/api/healthz" >/dev/null 2>&1; then
  echo "✅ Sandbox gotowy. W panelu: /admin/#tools → 🎭 Playwright → cel „Sandbox”."
else
  echo "❌ Sandbox nie odpowiada na :${E2E_BACKEND_PORT}/api/healthz" >&2
  exit 1
fi
