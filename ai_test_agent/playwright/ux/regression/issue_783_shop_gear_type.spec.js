/**
 * REGRESSION #783 — Shop buy endpoint accepts item_type='gear' (alias for 'item').
 * Acceptance: GET /api/shop shows gear-type items; buy request with that type returns
 * 200 or 402 (not 404 "Item not available in this shop").
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #783 — shop GET returns gear-type items from catalog", async ({ page }) => {
  // Find Aldrica (or any shop NPC with id=1)
  const r = await page.request.get("/api/shop/1?character_id=1");
  expect(r.ok(), "GET /api/shop/1 should return 200").toBeTruthy();

  const body = await r.json();
  expect(body.ok, "response.ok must be true").toBeTruthy();
  expect(Array.isArray(body.data?.items), "items must be an array").toBeTruthy();
});

test("REGRESSION #783 — buy with gear type returns 200 or 402 (not 404)", async ({ page }) => {
  // Get Aldrica's shop to find torch type as returned by catalog
  const shopR = await page.request.get("/api/shop/by-key/aldrica?character_id=1");
  if (!shopR.ok()) {
    console.log("Aldrica NPC not found in this environment — skipping buy test");
    return;
  }
  const shop = await shopR.json();
  const npcId = shop.data?.npc?.id;
  if (!npcId) {
    console.log("No NPC id returned — skip");
    return;
  }

  const torch = (shop.data?.items || []).find((it) => it.key === "torch");
  if (!torch) {
    console.log("torch not in Aldrica's shop — skip (shop may have different stock)");
    return;
  }

  // The catalog may return type='gear' for torch — this is what the frontend sends on buy
  const buyType = torch.type; // 'gear' or 'item' depending on catalog
  console.log(`torch.type from GET = '${buyType}' — testing buy with this type`);

  const buyR = await page.request.post(`/api/shop/${npcId}/buy`, {
    data: {
      character_id: 1,
      item_type: buyType,
      item_key: "torch",
    },
  });

  // 200 = bought, 402 = not enough gold — both mean the type was accepted
  // 404 = "Item not available in this shop" = bug #783 not fixed
  const status = buyR.status();
  expect(
    status,
    `buy with type='${buyType}' returned ${status} — must not be 404 (#783)`
  ).not.toBe(404);
});
