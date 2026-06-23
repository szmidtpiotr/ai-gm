/**
 * REGRESSION #897 — Bottom nav icons must be SVG (not emoji).
 * Acceptance: all 3 mbb-btn__icon spans contain inline SVG with currentColor stroke,
 * no raw emoji characters (🎲/👤/🎒) present.
 */
const { test, expect } = require("@playwright/test");

const EMOJI_CHARS = ["🎲", "👤", "🎒"];

test("REGRESSION #897 — bottom nav icons are SVG not emoji", async ({ page }) => {
  const r = await page.request.get("/front/index.html");
  expect(r.ok(), "index.html must respond 200 (#897)").toBeTruthy();
  const html = await r.text();

  const iconMatches = [...html.matchAll(/<span class="mbb-btn__icon"[^>]*>([\s\S]*?)<\/span>/g)];
  expect(iconMatches.length, "Must have exactly 3 mbb-btn__icon spans").toBe(3);

  for (const [, content] of iconMatches) {
    for (const emoji of EMOJI_CHARS) {
      expect(content, `Icon span must not contain emoji '${emoji}'`).not.toContain(emoji);
    }
    expect(content, "Icon span must contain SVG element").toContain("<svg");
    expect(content, "SVG must use currentColor for accent color inheritance").toContain("currentColor");
  }
});

test("REGRESSION #897 — bottom nav structure preserved (3 tabs, labels)", async ({ page }) => {
  const r = await page.request.get("/front/index.html");
  expect(r.ok()).toBeTruthy();
  const html = await r.text();

  expect(html).toContain('data-mbb="game"');
  expect(html).toContain('data-mbb="character"');
  expect(html).toContain('data-mbb="inventory"');
  for (const label of ["Gra", "Postać", "Ekwipunek"]) {
    expect(html, `Tab label '${label}' must remain`).toContain(label);
  }
});
