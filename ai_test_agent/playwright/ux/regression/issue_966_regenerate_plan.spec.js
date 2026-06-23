/**
 * REGRESSION #966 (BUG) — admin GM-plan API ujawnia plan_degraded; regeneracja planu z panelu.
 * Acceptance: GET /api/admin/campaigns/{id}/gm-plan zwraca pole `plan_degraded` (boolean),
 * dzięki któremu zakładka Plan GM pokazuje badge „⚠ Plan uproszczony" + przycisk „♻ Regeneruj plan MG".
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r2.json()).token;
}

test("REGRESSION #966 — gm-plan endpoint exposes plan_degraded flag", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  // 1. Znajdź jakąkolwiek kampanię.
  const listRes = await page.request.get("/api/admin/campaigns/live", { headers: auth });
  expect(listRes.ok(), `GET /api/admin/campaigns/live failed: ${listRes.status()}`).toBeTruthy();
  const { items } = await listRes.json();
  expect(items.length, "Brak kampanii do sprawdzenia (#966)").toBeGreaterThan(0);
  const campId = items[0].id;

  // 2. GET gm-plan — nowy kontrakt #966: pole plan_degraded musi istnieć i być boolem.
  const planRes = await page.request.get(`/api/admin/campaigns/${campId}/gm-plan`, { headers: auth });
  expect(planRes.ok(), `GET gm-plan failed: ${planRes.status()}`).toBeTruthy();
  const body = await planRes.json();
  expect("plan_degraded" in body, "odpowiedź gm-plan musi zawierać plan_degraded (#966)").toBeTruthy();
  expect(typeof body.plan_degraded, "plan_degraded musi być boolean").toBe("boolean");
});
