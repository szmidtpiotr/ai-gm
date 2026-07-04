/**
 * REGRESSION #1161 — wynik hazardu nie ginie gdy brak złota na przegraną (przegrana ograniczona do salda).
 * Pełna logika pokryta pytestem backend/tests/test_issue1161_gamble_lowgold.py (RED→GREEN:
 *   saldo 5, przegrana 100 → traci 5, saldo 0, summary NIE None).
 * Ten spec pilnuje kontraktu: skill 'gamble' musi istnieć — inaczej cała ścieżka wypłaty hazardu
 * nigdy nie odpala.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1161)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1161)").toBeTruthy();
  return token;
}

test("REGRESSION #1161 — skill 'gamble' istnieje (ścieżka hazardu osiągalna)", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/admin/skills", auth);
  expect(r.ok(), "/api/admin/skills nie odpowiada 200 (#1161)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body) ? body : (body.skills ?? body.items ?? []);

  const gamble = list.find((s) => String(s.key || "").toLowerCase() === "gamble");
  expect(gamble, "brak skilla 'gamble' — ścieżka wypłaty hazardu martwa (#1161)").toBeTruthy();
});
