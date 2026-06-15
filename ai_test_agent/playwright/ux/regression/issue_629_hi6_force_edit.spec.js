/**
 * REGRESSION #629 (HI6) — Inspektor: opcja „Wymuś edycję" (force) gdy live-lock.
 * Dla bohatera zablokowanego walką/turą modal MUSI pokazać przycisk force, a jego
 * włączenie odblokowuje kontrolki edycji (mutacje lecą z force:true → backend omija 409).
 * Acceptance: live-lock → toggle widoczny, kontrolki disabled; po kliknięciu → enabled.
 * Wymaga zaseedowanego active_combat na kampanii testowej (robi to runner przed testem).
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#629)").toBeTruthy();
  return (await r.json()).token;
}

// Znajdź bohatera, który JEST live-locked (runner zaseedował active_combat).
async function findLockedHero(page, headers) {
  const live = await page.request.get("/api/admin/campaigns/live", { headers });
  expect(live.ok(), "lista kampanii live nie odpowiada 200 (#629)").toBeTruthy();
  const camps = (await live.json()).items || [];
  for (const c of camps) {
    if (c.char_id == null) continue;
    const full = await page.request.get(`/api/admin/characters/${c.char_id}/full`, { headers });
    if (!full.ok()) continue;
    const body = await full.json();
    if (body.is_live_locked) return { id: c.char_id, name: body.name };
  }
  return null;
}

async function loginUi(page, token) {
  await page.addInitScript(t => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #629 — force toggle odblokowuje edycję live-locked bohatera", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const locked = await findLockedHero(page, headers);
  expect(locked, "brak live-locked bohatera — runner nie zaseedował active_combat? (#629)").toBeTruthy();

  await loginUi(page, token);
  await page.goto("/admin/#heroes");
  // Otwórz modal Inspektora bezpośrednio (heroes.js eksportuje openInspector).
  await page.waitForLoadState("networkidle");
  await page.evaluate(async id => {
    const m = await import("/admin/sections/heroes.js?v=38");
    await m.openInspector(id);
  }, locked.id);

  // Modal i baner live-lock muszą się pojawić.
  await expect(page.locator("#hero-inspector-overlay"), "modal nie otwarty (#629)").toBeVisible({ timeout: 15000 });

  // Stepper statu MUSI być disabled, dopóki force OFF.
  const statBtn = page.locator('#hero-sheet-edit [data-hi-stat]').first();
  await expect(statBtn, "stepper statu nie widoczny (#629)").toBeVisible({ timeout: 15000 });
  await expect(statBtn, "stepper powinien być disabled przy live-lock bez force (#629)").toBeDisabled();

  // Force toggle musi być w banerze.
  const forceToggle = page.locator("[data-hi-force-toggle]");
  await expect(forceToggle, "brak przycisku Wymuś edycję przy live-lock (#629)").toBeVisible({ timeout: 15000 });

  // Włącz force → stepper się odblokowuje.
  await forceToggle.click();
  await expect(
    page.locator('#hero-sheet-edit [data-hi-stat]').first(),
    "po włączeniu force stepper nadal disabled (#629)"
  ).toBeEnabled({ timeout: 15000 });
});
