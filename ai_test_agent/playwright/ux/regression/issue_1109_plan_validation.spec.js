/**
 * REGRESSION #1109 — generate-plan nie tworzy orphan-beatów + panel walidacji w Przeglądzie.
 * Acceptance: validate-plan na naprawionym szablonie zwraca 0 błędów; edytor szablonu
 * pokazuje panel "Walidacja planu" w zakładce Przegląd.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  return token;
}

// ── Test 1: żaden aktywny szablon z planem nie ma błędów walidacji ───────────
test("REGRESSION #1109 — szablony z planem przechodzą validate-plan (0 błędów)", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const tplResp = await page.request.get("/api/admin/forge/templates", { headers: auth });
  expect(tplResp.ok()).toBeTruthy();
  const templates = (await tplResp.json()).items || [];
  const withPlan = templates.filter((t) => t.gm_plan_json && (t.gm_plan_json.acts || []).length);
  test.skip(!withPlan.length, "brak szablonów z planem");

  for (const t of withPlan) {
    const v = await page.request.post("/api/admin/forge/validate-plan", {
      headers: auth,
      data: { gm_plan_json: t.gm_plan_json },
    });
    expect(v.ok(), `validate-plan nie 200 dla ${t.id}`).toBeTruthy();
    const body = await v.json();
    expect(
      body.errors.length,
      `szablon ${t.id} "${t.title}" ma błędy: ${JSON.stringify(body.errors)}`
    ).toBe(0);
  }
});

// ── Test 2: panel walidacji renderuje się w zakładce Przegląd ────────────────
test("REGRESSION #1109 — Przegląd pokazuje panel Walidacja planu", async ({ page }) => {
  const token = await adminToken(page);
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
  await page.goto("/admin/#forge");

  await page.locator('.stab[data-forgetab="templates"]').click();
  // otwórz pierwszy szablon (klik w kartę)
  const firstCard = page.locator("#forge-templates-grid .card").first();
  await expect(firstCard).toBeVisible({ timeout: 15000 });
  await firstCard.click();

  // edytor + zakładka Przegląd (domyślnie aktywna) + panel walidacji
  await expect(page.locator("#tpl-validation-panel")).toBeVisible({ timeout: 10000 });
  // panel kończy ładowanie — pokazuje wynik (✅ lub 🔴/🟡 lub "brak planu")
  await expect
    .poll(async () => (await page.locator("#tpl-validation-panel").innerText()).trim(), { timeout: 8000 })
    .not.toBe("Ładowanie…");
});
