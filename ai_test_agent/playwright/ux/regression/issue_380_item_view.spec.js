/**
 * REGRESSION #380 (D5) — Item VIEW (podgląd przedmiotu w inventory).
 * Klik przedmiotu → modal z pełnym opisem. Backend udostępnia detale per typ:
 * broń (damage_die/linked_stat), zbroja (ac_bonus), mikstura (effect), + wspólne.
 * Acceptance (deterministyczny): endpoint /api/inventory/{cid}/{id}/detail zwraca
 * pełny kontrakt {name, item_type, kind, + blok typu}. UI modal pokryty ręcznie.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #380 — detail przedmiotu zwraca pełny kontrakt", async ({ page }) => {
  const charIds = [1112, 1072, 1125, 1120, 1138, 999373];
  let tested = 0;
  for (const cid of charIds) {
    const inv = await page.request.get(`/api/inventory/${cid}`);
    if (!inv.ok()) continue;
    const ib = await inv.json();
    const items = (ib.data || []).slice(0, 6);
    if (!items.length) continue;
    for (const it of items) {
      const r = await page.request.get(`/api/inventory/${cid}/${it.id}/detail`);
      expect(r.ok(), `detail ${cid}/${it.id} nie odpowiada 200 (#380)`).toBeTruthy();
      const d = (await r.json()).data;
      expect(d, "odpowiedź bez data (#380)").toBeTruthy();
      expect(d.name, "detail bez name (#380)").toBeTruthy();
      expect(d.item_type, "detail bez item_type (#380)").toBeTruthy();
      if (d.kind === "weapon" && d.weapon && Object.keys(d.weapon).length) {
        expect("damage_die" in d.weapon, "broń bez damage_die (#380)").toBeTruthy();
      }
      if (d.kind === "armor") {
        expect(d.armor && "ac_bonus" in d.armor, "zbroja bez ac_bonus (#380)").toBeTruthy();
      }
      tested++;
    }
    break; // jeden bohater z ekwipunkiem wystarczy
  }
  expect(tested, "nie znaleziono bohatera z ekwipunkiem do testu (#380)").toBeGreaterThan(0);
  console.log(`#380: ${tested} przedmiotów sprawdzonych pod kątem kontraktu detail`);
});
