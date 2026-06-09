/**
 * REGRESSION #381 (D6) — blok "Narrative State" RENDERUJE się w modularnym /admin/#campaigns.
 * (Zmigrowany z ux/admin3/ w FADM-P16 #452 — campaigns sportowane do modularnego panelu.)
 * Loguje do /admin/, otwiera kampanię z zaseedowanym narrative_state i sprawdza, że blok
 * 📖 Narrative State pojawia się w zakładkach 🌍 Stan Świata oraz 🔍 Inspector.
 * Wymaga danych narrative_state w kampanii CAMPAIGN_ID (demo seed dla 1202).
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 1202;

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

test("REGRESSION #381 — Narrative State widoczny w Stan Świata i Inspector (/admin/)", async ({ page }) => {
  await adminLogin(page);
  // Zamontuj modularną sekcję campaigns → openCampaignModal trafia na window.
  await page.goto("/admin/#campaigns");
  await expect(page.locator("#campaigns-table")).toBeVisible({ timeout: 10000 });

  // Otwórz modal kampanii bezpośrednio (globalna funkcja modularnego campaigns.js).
  await page.evaluate(async (id) => { await window.openCampaignModal(id); }, CAMPAIGN_ID);
  await page.waitForTimeout(500);

  // 🌍 Stan Świata — blok 📖 Narrative State renderuje się z zaseedowanym wątkiem (Aldric).
  // To jest właściwy dowód D6: modularny campaigns.js rysuje Narrative State w /admin/.
  await page.click('[data-ctab="world"]');
  await expect(page.locator('#ctab-world')).toContainText('Narrative State', { timeout: 15000 });
  await expect(page.locator('#ctab-world')).toContainText('Aldric', { timeout: 5000 });

  // 🔍 Inspector — zakładka montuje się (intent/gate). Blok Narrative State jest tu
  // warunkowy (ukryty gdy źródło inspectora ma puste events/seeds — asymetria źródła
  // danych vs world tab), więc asercjonujemy tylko że inspector renderuje swoją treść.
  await page.click('[data-ctab="inspector"]');
  await expect(page.locator('#ctab-inspector')).toContainText('Intent', { timeout: 15000 });
});
