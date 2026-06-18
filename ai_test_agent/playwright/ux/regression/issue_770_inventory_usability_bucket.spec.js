/**
 * REGRESSION #770 — Inventory bucketing by usability (can_use) not item_type.
 * Acceptance: weapons/armor/consumables in top section (PLECAK), narrative/misc in bottom (PRZEDMIOTY NIEUŻYWALNE).
 * Character 999409 ([SMOKE] Wojownik) has weapon, armor, items — safe test character.
 */
const { test, expect } = require("@playwright/test");

async function loginDemo(page) {
  const r = await page.request.post("/api/auth/login", {
    data: { username: "demo", password: "demo" },
    headers: { "Content-Type": "application/json" },
  });
  expect(r.ok(), "login demo musi się udać").toBeTruthy();
}

async function getInventory(page, characterId) {
  const r = await page.request.get(`/api/inventory/${characterId}`);
  expect(r.ok(), `inventory endpoint dla char ${characterId} musi odpowiadać 200`).toBeTruthy();
  const body = await r.json();
  // endpoint wraps response: {"ok": true, "data": [...]}
  return Array.isArray(body) ? body : (body.data || []);
}

test("REGRESSION #770 — inventory items have can_use field for frontend bucketing", async ({ page }) => {
  await loginDemo(page);
  const items = await getInventory(page, 999409);

  expect(items.length, "musi być co najmniej 1 item").toBeGreaterThan(0);

  // Every item must have can_use boolean field
  for (const item of items) {
    expect(item).toHaveProperty("can_use");
    expect(typeof item.can_use, `item ${item.label} can_use musi być boolean`).toBe("boolean");
  }

  // Weapons: can_use=false (equippable, not consumed)
  const weapons = items.filter(i => String(i.item_type).toLowerCase() === "weapon");
  for (const w of weapons) {
    expect(w.can_use, `broń ${w.label} nie powinna mieć can_use=true`).toBeFalsy();
  }

  // Consumables: can_use=true
  const consumables = items.filter(i => String(i.item_type).toLowerCase() === "consumable");
  if (consumables.length > 0) {
    for (const c of consumables) {
      expect(c.can_use, `consumable ${c.label} powinien mieć can_use=true`).toBeTruthy();
    }
  }
});

test("REGRESSION #770 — narrative_item_* has can_use=false (lands in PRZEDMIOTY NIEUŻYWALNE not PLECAK)", async ({ page }) => {
  await loginDemo(page);

  // Campaign 99791 (Pierwsze Kroki) — character 999420 has narrative_item_* from #757 pattern
  // READ-ONLY test — no state changes to Mizel character
  const items = await getInventory(page, 999420);
  expect(items.length, "musi być co najmniej 1 item").toBeGreaterThan(0);

  const narrativeItem = items.find(i =>
    String(i.key || "").startsWith("narrative_item_") || i.is_narrative === true
  );

  if (narrativeItem) {
    expect(narrativeItem.can_use,
      `narrative_item ${narrativeItem.key} z can_use=true trafiłby do PLECAK zamiast PRZEDMIOTY NIEUŻYWALNE (#770)`
    ).toBeFalsy();
  }
});
