/**
 * REGRESSION #409 (FADM-P7) — Port sekcji dungeons → modularny admin/.
 * Acceptance: /admin/#dungeons renderuje tabelę lochów z danymi z API,
 * cztery taby (lochy/zagadki/kafelki/kategorie) istnieją, sekcja działa w /admin/.
 */
const { test, expect } = require("@playwright/test");

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

test("REGRESSION #409 — /admin/#dungeons renderuje sekcję z tabelą lochów", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#dungeons");

  // Modular shell renders into #panel — wait for dungeons-table
  await expect(page.locator("#dungeons-table")).toBeVisible({ timeout: 10000 });

  // Table must have thead
  await expect(page.locator("#dungeons-table thead")).toBeVisible();

  // 4 stab-bar tabs present: dungeons / riddles / tiles / tilecats
  const TABS = ["dungeons", "riddles", "tiles", "tilecats"];
  for (const tab of TABS) {
    await expect(
      page.locator(`#dungeons-stab-bar .stab[data-dtab="${tab}"]`),
      `Tab ${tab} brak`
    ).toBeVisible();
  }
});

test("REGRESSION #409 — tabela lochów ładuje dane z API", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#dungeons");

  await expect(page.locator("#dungeons-table")).toBeVisible({ timeout: 10000 });

  // tbody should get real rows
  await expect
    .poll(async () => {
      const rows = await page.locator("#dungeons-table tbody tr").count();
      const loading = await page.locator("#dungeons-table tbody tr td")
        .filter({ hasText: "Ładowanie…" }).count();
      return rows > 0 && loading === 0;
    }, { timeout: 15000 })
    .toBeTruthy();
});


