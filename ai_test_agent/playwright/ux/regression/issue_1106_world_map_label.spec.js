/**
 * REGRESSION #1106 — World map current-hex name must not be truncated / invisible.
 * Acceptance: header shows full current hex label; SVG label for the current hex is
 * rendered in full (no slice(0,14)) regardless of zoom, with a larger halo'd font.
 * No login/campaign needed — initWorldMap() wires up #wmap-title/#wmap-svg on page load
 * regardless of auth state, so we exercise the real _wmRender/_wmUpdateTitle functions directly.
 */
const { test, expect } = require("@playwright/test");

const LONG_LABEL = "Tundra Wiecznego Mrozu";

test("REGRESSION #1106 — header and current-hex label show the full name, not truncated", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector("#wmap-svg", { timeout: 15000, state: "attached" });

  const result = await page.evaluate((label) => {
    _wmap.currentHex = { q: 3, r: -2, label };
    _wmap.hexes = [
      { q: 3, r: -2, status: "discovered", hex_type: "tundra", label },
    ];
    _wmap.hexTypes = { tundra: { map_color: "#345", map_icon: "❄️" } };
    _wmap.zoom = 1.0;
    _wmUpdateTitle();
    _wmRender();
    return {
      title: document.getElementById("wmap-title")?.textContent || "",
      svgHtml: document.getElementById("wmap-svg").innerHTML,
    };
  }, LONG_LABEL);

  expect(result.title, "header must contain the full hex label").toContain(LONG_LABEL);
  expect(result.svgHtml, "current-hex SVG label must contain the full name, not a slice(0,14)").toContain(LONG_LABEL);
  expect(result.svgHtml, "must not contain the old truncated form").not.toContain("Tundra Wieczne<");
});

test("REGRESSION #1106 — current-hex label renders even below the old zoom>=1.0 threshold", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector("#wmap-svg", { timeout: 15000, state: "attached" });

  const svgHtml = await page.evaluate((label) => {
    _wmap.currentHex = { q: 3, r: -2, label };
    _wmap.hexes = [
      { q: 3, r: -2, status: "discovered", hex_type: "tundra", label },
    ];
    _wmap.hexTypes = { tundra: { map_color: "#345", map_icon: "❄️" } };
    _wmap.zoom = 0.7; // below the old `zoom >= 1.0` gate that used to hide all labels
    _wmRender();
    return document.getElementById("wmap-svg").innerHTML;
  }, LONG_LABEL);

  expect(svgHtml, "current hex label must render even at low zoom").toContain(LONG_LABEL);
});
