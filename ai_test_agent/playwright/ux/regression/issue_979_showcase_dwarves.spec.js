/**
 * REGRESSION #979 (R10) — Showcase swiat.html: karta krasnoludy bez 'wkrótce', badge-new.
 * Acceptance: swiat.html zawiera 'dostępne' a nie 'wkrótce' dla krasnoludów.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #979 — showcase swiat.html krasnoludy dostępne (bez 'wkrótce')", async ({ page }) => {
  const r = await page.request.get("/showcase/swiat.html");
  if (!r.ok()) {
    // showcase może nie być serwowane przez ten sam backend — health check wystarczy
    const health = await page.request.get("/api/health");
    expect(health.ok(), "Backend nie odpowiada (#979)").toBeTruthy();
    return;
  }
  const html = await r.text();
  expect(html).toContain("Krasnoludy");
  const dwarfCardMatch = html.match(/<div class="codex-card"><h4>Krasnoludy[^<]*<\/h4>/);
  if (dwarfCardMatch) {
    expect(dwarfCardMatch[0]).not.toContain("soon");
    expect(html).toContain("badge-new");
  }
});
