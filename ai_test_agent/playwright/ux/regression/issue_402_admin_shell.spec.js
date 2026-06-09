/**
 * REGRESSION #402 (FADM-P0) — Modularna skorupa admin/ (post-P15: samowystarczalna).
 * /admin/ serwuje cienką skorupę: sidebar nav (14 sekcji montowanych przez router JS),
 * <main id="panel">, hash-router, własny login (P13). Wszystkie sekcje sportowane (P14) →
 * zero bounce do admin3.
 * Acceptance (deterministyczny): skorupa renderuje 14 przycisków nav + panel + router działa;
 * /admin/#forge renderuje (nie bounce'uje); brak tokenu → modularny login (nie admin3).
 */
const { test, expect } = require("@playwright/test");

const SECTIONS = [
  "overview", "players", "campaigns", "content", "world", "map", "mechanics",
  "dungeons", "forge", "invites", "bugreports", "push", "tools", "system",
];

async function adminLogin(page) {
  // FADM-P16: token przez API + addInitScript → seed localStorage PRZED skryptami strony.
  // Brak goto tutaj: unika otwarcia login-overlay (P13), który przy nawigacji hash-only
  // nie znika i przechwytywał kliknięcia w sekcjach.
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #402 — skorupa /admin/ renderuje nav 14 sekcji + panel + router", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/");

  // Marker modularnej skorupy — atrybut na <html>.
  await expect(page.locator("[data-admin-shell]")).toHaveCount(1);
  await expect(page.locator("#panel")).toHaveCount(1);

  // Wszystkie 14 sekcji obecne w nav (montowane przez router z listy SECTIONS).
  for (const s of SECTIONS) {
    await expect(page.locator(`.nav-item[data-section="${s}"]`)).toHaveCount(1);
  }

  // Router: klik nav → hash przepięty + sekcja oznaczona jako aktywna.
  await page.locator('.nav-item[data-section="overview"]').click();
  await expect(page).toHaveURL(/#overview$/);
  await expect(page.locator('.nav-item[data-section="overview"]')).toHaveClass(/active/);
});

test("REGRESSION #402 — /admin/#forge renderuje (zero bounce do admin3)", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#forge");
  await page.waitForTimeout(1500);
  // Wszystkie sekcje sportowane → forge renderuje w modularnym, NIE redirectuje do admin3.
  expect(page.url(), "/admin/#forge nie może bounce'ować do admin3 (#402)").not.toContain("/admin3/");
  expect(page.url(), "powinien zostać na /admin/#forge (#402)").toContain("/admin/");
});

test("REGRESSION #402 — brak tokenu → modularny login (skorupa samowystarczalna)", async ({ page }) => {
  await page.goto("/admin/");
  await page.evaluate(() => {
    localStorage.removeItem("aigm_admin_token");
    localStorage.removeItem("aigm_admin_user");
  });
  await page.reload();
  // Modularny shell pokazuje WŁASNY login (P13), nie kieruje do admin3.
  await expect(page.locator("#login-overlay"), "modularny login overlay nie pojawił się (#402)").toBeVisible({ timeout: 5000 });
});
