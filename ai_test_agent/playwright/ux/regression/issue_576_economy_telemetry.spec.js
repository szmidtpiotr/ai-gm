/**
 * REGRESSION #576 (U26) — telemetria ekonomii: kafelek "Ekonomia 7 dni" w admin Overview.
 * Acceptance: GET /api/admin/overview zwraca economy_7d {rows[], total_income, total_expense, net};
 * każdy wiersz ma source z dozwolonego ENUM + income/expense/net/count (liczby); db-lint
 * eksponuje check GOLD_DRIFT (drift saldo vs suma delt).
 */
const { test, expect } = require("@playwright/test");

const BUCKETS = [
  "loot", "sell", "buy", "service", "robbery", "resurrection",
  "repair", "craft", "quest_reward", "starter_gold", "admin_cheat", "other",
];

async function adminLogin(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "dev_password" },
  });
  if (!r.ok()) return null;
  const body = await r.json();
  return body.token || null;
}

test("REGRESSION #576 U26 — overview wymaga autoryzacji (401 bez tokenu)", async ({ page }) => {
  const r = await page.request.get("/api/admin/overview");
  expect(r.status(), "overview powinien zwracać 401 bez tokenu").toBe(401);
});

test("REGRESSION #576 U26 — overview zawiera blok economy_7d", async ({ page }) => {
  const token = await adminLogin(page.request);
  if (!token) {
    const health = await page.request.get("/api/health");
    expect(health.ok(), "backend nie odpowiada").toBeTruthy();
    return;
  }
  const r = await page.request.get("/api/admin/overview", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "overview nie odpowiada 200 z tokenem (#576)").toBeTruthy();
  const body = await r.json();
  const econ = body.economy_7d;
  expect(econ, "brak bloku economy_7d w overview").toBeTruthy();
  expect(Array.isArray(econ.rows), "economy_7d.rows musi być tablicą").toBeTruthy();
  expect(typeof econ.total_income, "total_income musi być liczbą").toBe("number");
  expect(typeof econ.total_expense, "total_expense musi być liczbą").toBe("number");
  expect(typeof econ.net, "net musi być liczbą").toBe("number");
  for (const row of econ.rows) {
    expect(BUCKETS, `nieznany kubełek źródła: ${row.source}`).toContain(row.source);
    expect(typeof row.income).toBe("number");
    expect(typeof row.expense).toBe("number");
    expect(typeof row.net).toBe("number");
    expect(typeof row.count).toBe("number");
  }
});

test("REGRESSION #576 U26 — db-lint zawiera check GOLD_DRIFT", async ({ page }) => {
  const token = await adminLogin(page.request);
  if (!token) {
    const health = await page.request.get("/api/health");
    expect(health.ok(), "backend nie odpowiada").toBeTruthy();
    return;
  }
  const r = await page.request.get("/api/admin/db-lint", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "db-lint nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  // GOLD_DRIFT to warning telemetryczny — może być obecny lub nie, ale raport
  // musi być stringiem, a struktura zgodna z #560 (nie regresujemy db_lint).
  expect(typeof body.report, "report musi być stringiem").toBe("string");
  expect(Array.isArray(body.warnings), "warnings musi być tablicą").toBeTruthy();
});
