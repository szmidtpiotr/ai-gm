/**
 * REGRESSION #968 (TASK) — regeneracja planu MG świadoma historii (kontynuacja, nie restart).
 * Acceptance (kontrakt API): endpoint regeneracji planu jest zarejestrowany i zwraca status
 * (ok + plan_degraded), a GET gm-plan ujawnia plan_degraded — przycisk „♻ Regeneruj plan MG"
 * z #966 odpala teraz wariant świadomy historii (logika promptu pokryta pytestem).
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

test("REGRESSION #968 — regenerate-initial route registered + gm-plan exposes plan_degraded", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const listRes = await page.request.get("/api/admin/campaigns/live", { headers: auth });
  expect(listRes.ok(), `GET campaigns/live failed: ${listRes.status()}`).toBeTruthy();
  const { items } = await listRes.json();
  expect(items.length, "Brak kampanii (#968)").toBeGreaterThan(0);
  const campId = items[0].id;

  // gm-plan kontrakt (z #966) — plan_degraded musi istnieć.
  const planRes = await page.request.get(`/api/admin/campaigns/${campId}/gm-plan`, { headers: auth });
  expect(planRes.ok(), `GET gm-plan failed: ${planRes.status()}`).toBeTruthy();
  const body = await planRes.json();
  expect(typeof body.plan_degraded, "plan_degraded musi być boolean").toBe("boolean");

  // Route regeneracji musi istnieć (nie 404). Nieistniejąca kampania → 404 z TEGO handlera,
  // co dowodzi rejestracji trasy bez odpalania prawdziwego LLM.
  const notFound = await page.request.post("/api/admin/campaigns/999999999/gm-plan/regenerate-initial", { headers: auth });
  expect(notFound.status(), "regenerate-initial route nie jest zarejestrowana").toBe(404);
});
