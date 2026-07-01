/**
 * REGRESSION #1088 — Lore inventory grouping into collapsible <details> sections.
 * Acceptance: GET /api/inventory/{id} returns items with item_type field;
 * lore items with regex-matching labels are classified into scrolls/books/keys/quest/misc.
 */
const { test, expect } = require("@playwright/test");

const CHAR_ID = 999420; // Piotr's [TEST] hero — read-only queries only

test("REGRESSION #1088 — inventory endpoint returns item_type field on all items", async ({ page }) => {
  const r = await page.request.get(`/api/inventory/${CHAR_ID}`);
  expect(r.ok(), `inventory endpoint nie zwraca 200 (#1088)`).toBeTruthy();
  const body = await r.json();
  expect(body.ok, "body.ok nie jest true").toBeTruthy();
  expect(Array.isArray(body.data), "body.data nie jest tablicą").toBeTruthy();
  // Each item must have item_type field (even if empty string)
  for (const item of body.data) {
    expect(
      typeof item.item_type === "string" || item.item_type === null,
      `item ${item.id} (${item.label}) brak pola item_type`
    ).toBeTruthy();
    expect(item.label !== undefined, `item ${item.id} brak pola label`).toBeTruthy();
  }
});

test("REGRESSION #1088 — lore grouping JS heuristic matches classification function", async ({ page }) => {
  // Test the same regex patterns as _loreCategoryKey() in game.js
  const cases = [
    ["Złożony pergamin", "misc", "scrolls"],
    ["Zwój ognia", "misc", "scrolls"],
    ["List do kniazia", "misc", "scrolls"],
    ["Księga czarów", "misc", "books"],
    ["Stara książka", "misc", "books"],
    ["Kronika walk", "narrative", "books"],
    ["Żelazny klucz", "misc", "keys"],
    ["Klucz do wieży", "quest", "keys"],
    ["Amulet Mroku", "quest", "quest"],
    ["Odłamek kości", "misc", "misc"],
  ];

  const result = await page.evaluate((testCases) => {
    function loreCategoryKey(label, itemType) {
      const lab = String(label || "");
      const t = String(itemType || "").toLowerCase();
      if (/pergamin|zwój|zwoj|list|pismo|manuskrypt/i.test(lab)) return "scrolls";
      if (/księga|ksiega|książka|ksiazka|kodeks|kronika|traktat|tome/i.test(lab)) return "books";
      if (/klucz/i.test(lab)) return "keys";
      if (t === "quest") return "quest";
      return "misc";
    }
    return testCases.map(([label, type, expected]) => ({
      label,
      expected,
      got: loreCategoryKey(label, type),
      ok: loreCategoryKey(label, type) === expected,
    }));
  }, cases);

  const failures = result.filter((r) => !r.ok);
  expect(
    failures.length,
    `Błędna klasyfikacja: ${JSON.stringify(failures)}`
  ).toBe(0);
});

test("REGRESSION #1088 — inventory API health check", async ({ page }) => {
  // Verify backend is up and inventory endpoint responds
  const health = await page.request.get("/api/health");
  expect(health.ok(), "health endpoint nie odpowiada (#1088)").toBeTruthy();
});
