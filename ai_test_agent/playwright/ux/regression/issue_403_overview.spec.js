/**
 * REGRESSION #403 (FADM-P1) — Port sekcji overview do modularnego admin/.
 * /admin/#overview montuje moduł sekcji: pasek 7 zakładek (Przegląd + 6 analityk),
 * 4 karty statystyk, 2 feedy (tury/audyt). Klik sub-tabu analityki ładuje panel
 * (loader podmienia „Ładowanie…"). Backend bez zmian.
 * Acceptance (deterministyczny): sekcja renderuje strukturę + przełączanie sub-tabów działa;
 * /admin3/#overview nadal żyje (fallback do czasu usunięcia z monolitu).
 */
const { test, expect } = require("@playwright/test");

const ADMIN_USER = process.env.AI_TEST_ADMIN_USER || "ai_test_player";
const ADMIN_PASS = process.env.AI_TEST_ADMIN_PASS || "demo";

// Loguje przez overlay admin3 → token ląduje w localStorage (współdzielony /admin/ ↔ /admin3/),
// więc apiFetch w sekcji overview ma Bearer i endpointy /api/admin/* odpowiadają 200.
async function adminLogin(page) {
  // Navigate to /api/health (same origin, no JS redirects) to safely clear stale token
  await page.goto("/api/health");
  await page.evaluate(() => localStorage.removeItem('aigm_admin_token'));
  // Use #forge hash — not in PORTED set, so requestAnimationFrame won't redirect to /admin/#players.
  await page.goto("/admin3/#forge");
  await page.waitForSelector("#login-overlay.open", { timeout: 15000 });
  await page.fill("#login-user", ADMIN_USER);
  await page.fill("#login-pass", ADMIN_PASS);
  await page.click("#login-submit");
  await page.locator("#login-overlay").waitFor({ state: "hidden", timeout: 20000 });
}

test("REGRESSION #403 — /admin/#overview renderuje sekcję + sub-taby", async ({ page }) => {
  // Strażnik błędów JS — skorupa + moduł nie mogą rzucać (import/runtime).
  const jsErrors = [];
  page.on("pageerror", (e) => jsErrors.push(e.message));

  await adminLogin(page);
  await page.goto("/admin/#overview");

  // Moduł zamontowany (nie placeholder „w trakcie migracji").
  await expect(page.locator("#section-overview")).toHaveCount(1);
  await expect(page.locator("#overview-tabs")).toHaveCount(1);
  // Przegląd + 6 zakładek analityki (overview/dice/combat/economy/events/llm).
  await expect(page.locator("#overview-tabs .stab")).toHaveCount(7);
  // 4 karty statystyk + 2 feedy.
  await expect(page.locator("#ovtab-overview .stat-card")).toHaveCount(4);
  await expect(page.locator("#ov-turns-feed")).toHaveCount(1);
  await expect(page.locator("#ov-audit-feed")).toHaveCount(1);
  // Główny panel domyślnie aktywny, filtr dni ukryty.
  await expect(page.locator("#ovtab-overview")).toHaveClass(/active/);

  // 1 akcja: przełącz na sub-tab „Kości" → panel aktywny, filtr dni widoczny,
  // loader podmienił „Ładowanie…" (API zawołane, DOM zaktualizowany — bary lub „Brak danych.").
  await page.locator('#overview-tabs .stab[data-anatab="dice"]').click();
  await expect(page.locator("#anatab-dice")).toHaveClass(/active/);
  await expect(page.locator("#ana-days-filter")).toBeVisible();
  await expect(page.locator("#ana-dice-chart")).not.toContainText("Ładowanie…", { timeout: 10000 });

  expect(jsErrors, `błędy JS na /admin/#overview: ${jsErrors.join(" | ")}`).toHaveLength(0);
});

test("REGRESSION #403 — admin3 nadal żyje (fallback)", async ({ page }) => {
  const r = await page.request.get("/admin3/");
  expect(r.ok(), "/admin3/ musi nadal działać podczas migracji (#403)").toBeTruthy();
});
