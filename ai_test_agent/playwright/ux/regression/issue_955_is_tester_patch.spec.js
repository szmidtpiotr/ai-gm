/**
 * REGRESSION #955 (BUG) — Flaga Tester zapisuje się przez PATCH /admin/accounts.
 * Acceptance: po PATCH z is_tester=1 endpoint GET /admin/accounts zwraca is_tester=1 dla tego użytkownika.
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

test("REGRESSION #955 — is_tester persists via PATCH /admin/accounts", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  // 1. Get list of accounts to find a test user
  const listRes = await page.request.get("/api/admin/accounts", {
    headers: auth,
  });
  expect(listRes.ok(), `GET /api/admin/accounts failed: ${listRes.status()}`).toBeTruthy();
  const { items: accounts } = await listRes.json();
  expect(accounts.length, "No accounts returned").toBeGreaterThan(0);

  // Use first non-admin account for test, or first account if all are admin
  const target = accounts.find((a) => !a.is_admin) || accounts[0];
  const userId = target.id;
  const originalIsTester = target.is_tester ?? 0;

  // 2. PATCH to set is_tester=1
  const patchRes = await page.request.patch(`/api/admin/accounts/${userId}`, {
    headers: { ...auth, "Content-Type": "application/json" },
    data: JSON.stringify({
      display_name: target.display_name,
      is_active: target.is_active ?? 1,
      is_admin: target.is_admin ?? 0,
      is_tester: 1,
    }),
  });
  expect(patchRes.ok(), `PATCH /api/admin/accounts/${userId} failed: ${patchRes.status()}`).toBeTruthy();

  const patched = await patchRes.json();
  expect(patched.item?.is_tester, "PATCH response must return is_tester=1").toBe(1);

  // 3. Re-read via GET list — verify persistence
  const verifyRes = await page.request.get("/api/admin/accounts", {
    headers: auth,
  });
  expect(verifyRes.ok()).toBeTruthy();
  const { items: verifyList } = await verifyRes.json();
  const verifyUser = verifyList.find((a) => a.id === userId);
  expect(verifyUser, `User ${userId} not in account list after PATCH`).toBeTruthy();
  expect(verifyUser.is_tester, "is_tester must persist in DB (re-read shows 1)").toBe(1);

  // 4. Cleanup — restore original value
  await page.request.patch(`/api/admin/accounts/${userId}`, {
    headers: { ...auth, "Content-Type": "application/json" },
    data: JSON.stringify({
      display_name: target.display_name,
      is_active: target.is_active ?? 1,
      is_admin: target.is_admin ?? 0,
      is_tester: originalIsTester,
    }),
  });
});
