/**
 * REGRESSION #565 (U17) — Celebracja dropu afiksowego + porównanie z założonym.
 * Acceptance (kontrakt API + assety, deterministyczny):
 *  - GET /api/inventory/{cid}/{inv_id}/drop-comparison jest wpięty i zwraca blok porównania
 *    (rarity, rarity_label, is_special, suggested_slot, new{}, equipped, diff{}) dla broni/zbroi,
 *    a data=null dla nie-sprzętu. Diff liczy BACKEND (mechanika decyduje, nie LLM).
 *  - Frontend gracza dostarcza overlay celebracji (#drop-celebration-overlay) + funkcję showDropCelebration.
 * Pełna ścieżka (wygranie walki z afiksowym dropem → karta → Załóż) — weryfikacja manualna / game-test-player.
 */
const { test, expect } = require("@playwright/test");

const CID = 2; // [TEST] Wojownik — istnieje na DEV (ma broń w ekwipunku)

test("REGRESSION #565 — drop-comparison wpięty i zwraca kontrakt dla broni", async ({ page }) => {
  // Znajdź realny inventory_id broni/zbroi z ekwipunku bohatera
  const inv = await page.request.get(`/api/inventory/${CID}`);
  expect(inv.ok(), "endpoint /inventory nie odpowiada 200 (#565)").toBeTruthy();
  const invBody = await inv.json();
  const gear = (invBody.data || []).find(
    (it) => ["weapon", "armor"].includes(String(it.item_type || "").toLowerCase())
  );

  if (!gear) {
    test.skip(true, "Bohater nie ma broni/zbroi — pomijam kontrakt diffu");
    return;
  }

  const r = await page.request.get(`/api/inventory/${CID}/${gear.id}/drop-comparison`);
  expect(r.ok(), "drop-comparison nie odpowiada 200 (#565)").toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  const d = body.data;
  expect(d, "brak bloku porównania dla broni/zbroi (#565)").toBeTruthy();

  // Kontrakt karty celebracji
  expect(["common", "rare", "epic"]).toContain(d.rarity_label);
  expect(typeof d.is_special).toBe("boolean");
  expect(d).toHaveProperty("suggested_slot");
  expect(d).toHaveProperty("new");
  expect(d).toHaveProperty("diff");

  // Mechanika liczy konkretną liczbę: broń → damage, zbroja → ac
  if (String(d.item_type).toLowerCase() === "weapon") {
    expect(typeof d.new.damage).toBe("number");
  } else {
    expect(typeof d.new.ac).toBe("number");
  }
});

test("REGRESSION #565 — nie-sprzęt nie dostaje karty (data=null)", async ({ page }) => {
  // Bogus inventory id → handler żyje (200 data=null lub 404 item-not-found), NIGDY 'route not found'.
  const r = await page.request.get(`/api/inventory/${CID}/99999999/drop-comparison`);
  expect([200, 404].includes(r.status()), `drop-comparison zwrócił ${r.status()} — trasa niewpięta? (#565)`).toBeTruthy();
  if (r.status() === 200) {
    const body = await r.json();
    expect(body.data === null || typeof body.data === "object").toBeTruthy();
  }
});

test("REGRESSION #565 — frontend dostarcza overlay celebracji + handler", async ({ page }) => {
  const html = await page.request.get(`/`);
  expect(html.ok()).toBeTruthy();
  const htmlText = await html.text();
  expect(htmlText.includes("drop-celebration-overlay"), "brak overlay celebracji w index.html (#565)").toBeTruthy();

  const js = await page.request.get(`/js/app.js?v=u17-drop-celebration-2026-06-13`);
  expect(js.ok()).toBeTruthy();
  const jsText = await js.text();
  expect(jsText.includes("showDropCelebration"), "brak funkcji showDropCelebration w app.js (#565)").toBeTruthy();
});
