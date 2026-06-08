/**
 * REGRESSION #402 (FADM-P0) — Bootstrap modularnej skorupy admin/.
 * /admin/ serwuje cienką skorupę: sidebar nav (14 sekcji, montowanych przez router JS),
 * <main id="panel">, hash-router. admin3 żyje równolegle (/admin3/ nietknięte).
 * Acceptance (deterministyczny): skorupa renderuje 14 przycisków nav + panel;
 * klik nav przepina hash i ustawia aktywną sekcję (router działa);
 * /admin3/ nadal odpowiada 200 (fallback).
 */
const { test, expect } = require("@playwright/test");

const SECTIONS = [
  "overview", "players", "campaigns", "content", "world", "map", "mechanics",
  "dungeons", "forge", "invites", "bugreports", "push", "tools", "system",
];

test("REGRESSION #402 — skorupa /admin/ renderuje nav 14 sekcji + panel + router", async ({ page }) => {
  await page.goto("/admin/");

  // Marker nowej modularnej skorupy (nie stary admin_panel v1) — atrybut na <html>.
  await expect(page.locator("[data-admin-shell]")).toHaveCount(1);
  // Kontener sekcji, do którego router montuje moduły.
  await expect(page.locator("#panel")).toHaveCount(1);

  // Wszystkie 14 sekcji obecne w nav (montowane przez router z listy SECTIONS).
  for (const s of SECTIONS) {
    await expect(page.locator(`.nav-item[data-section="${s}"]`)).toHaveCount(1);
  }

  // 1 akcja: klik nav → hash przepięty + sekcja oznaczona jako aktywna (router zadziałał).
  // Niezależne od tego, czy dana sekcja jest już sportowana (testuje samą skorupę).
  await page.locator('.nav-item[data-section="overview"]').click();
  await expect(page).toHaveURL(/#overview$/);
  await expect(page.locator('.nav-item[data-section="overview"]')).toHaveClass(/active/);
});

test("REGRESSION #402 — admin3 nadal żyje (fallback)", async ({ page }) => {
  const r = await page.request.get("/admin3/");
  expect(r.ok(), "/admin3/ musi nadal działać podczas migracji (#402)").toBeTruthy();
});
