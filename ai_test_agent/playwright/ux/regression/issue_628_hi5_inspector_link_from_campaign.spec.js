/**
 * REGRESSION #628 (HI5) — link „Otwórz inspektora" z monitora kampanii.
 * Karta kampanii z bohaterem (zakładka Przegląd) musi mieć przycisk otwierający TEN SAM
 * modal Inspektora HI2 dla właściwego bohatera (reuse openInspector z heroes.js).
 * Acceptance: w Przeglądzie kampanii z char_id widać przycisk „Otwórz inspektora"; klik
 * otwiera #hero-inspector-overlay z imieniem tego bohatera; kontrakt /full nadal działa.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#628)").toBeTruthy();
  return (await r.json()).token;
}

// Znajdź aktywną kampanię konta Demo z przypisanym bohaterem.
async function pickCampaignWithHero(page, headers) {
  const r = await page.request.get("/api/admin/campaigns/live", { headers });
  expect(r.ok(), "lista kampanii live nie odpowiada 200 (#628)").toBeTruthy();
  const items = (await r.json()).items || [];
  const c = items.find(x => x.char_id != null);
  expect(c, "brak kampanii z bohaterem do testu linku (#628)").toBeTruthy();
  return c;
}

async function loginUi(page, token) {
  await page.addInitScript(t => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #628 — kontrakt /full bohatera z kampanii działa (cel linku)", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };
  const camp = await pickCampaignWithHero(page, headers);

  const full = await page.request.get(`/api/admin/characters/${camp.char_id}/full`, { headers });
  expect(full.ok(), "/full bohatera z kampanii nie odpowiada 200 (#628)").toBeTruthy();
  const body = await full.json();
  expect(body.name, "/full bez imienia bohatera (#628)").toBeTruthy();
  // Guard live-lock dziedziczony z HI1 — pole MUSI być obecne (modal go używa do blokady edycji).
  expect("is_live_locked" in body, "/full bez pola is_live_locked (#628)").toBeTruthy();
});

test("REGRESSION #628 — przycisk Otwórz-inspektora w Przeglądzie otwiera modal właściwego bohatera", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };
  const camp = await pickCampaignWithHero(page, headers);

  await loginUi(page, token);
  await page.goto("/admin/#campaigns");
  // Sekcja campaigns zarejestrowała openCampaignModal w window.
  await page.waitForFunction(() => typeof window.openCampaignModal === "function", { timeout: 15000 });
  await page.evaluate(id => window.openCampaignModal(id), camp.id);

  // Zakładka Przegląd ładuje się domyślnie — przycisk linku musi się pojawić.
  const linkBtn = page.locator("#ctab-overview [data-hi-open-inspector]");
  await expect(linkBtn, "brak przycisku Otwórz-inspektora w Przeglądzie (#628)").toBeVisible({ timeout: 15000 });

  await linkBtn.click();

  const overlay = page.locator("#hero-inspector-overlay");
  await expect(overlay, "klik nie otworzył modalu Inspektora (#628)").toBeVisible({ timeout: 15000 });

  // Tytuł modalu musi zawierać imię tego samego bohatera (reuse openInspector z właściwym id).
  const full = await (await page.request.get(`/api/admin/characters/${camp.char_id}/full`, { headers })).json();
  await expect(page.locator("#hero-modal-title"), "modal otwarty dla złego bohatera (#628)")
    .toContainText(full.name, { timeout: 15000 });
});
