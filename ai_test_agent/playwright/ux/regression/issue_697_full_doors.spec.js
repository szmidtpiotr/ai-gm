/**
 * REGRESSION #697 (L-doors / Decyzja 2b) — generator wypełnia wszystkie drzwi kafla.
 * Acceptance: w wygenerowanym grafie każde narysowane drzwi prowadzi gdzieś — gdy
 * kategoria ma komplet 1-drzwiowych „zaślepek" (N/S/E/W), open_doors === 0.
 * Weryfikacja przez admin endpoint /api/admin/dungeon-tiles/preview-graph/{category}.
 */
const { test, expect } = require("@playwright/test");

async function getAdminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login musi się udać (#697)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #697 — preview-graph raportuje open_doors i caps_complete", async ({ page }) => {
  const token = await getAdminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  // Znajdź kategorię kafelków z jakimikolwiek kafelkami
  const cats = await page.request.get("/api/admin/dungeon-tile-categories", { headers: auth });
  expect(cats.ok(), "brak listy kategorii (#697)").toBeTruthy();
  const categories = (await cats.json()).categories || [];
  test.skip(categories.length === 0, "brak kategorii kafelków do sprawdzenia");

  let checkedAny = false;
  for (const cat of categories) {
    const r = await page.request.get(
      `/api/admin/dungeon-tiles/preview-graph/${encodeURIComponent(cat.key)}?count=4`,
      { headers: auth }
    );
    // 400 = za mała pula tej kategorii — pomijamy, to nie regresja #697
    if (r.status() === 400) continue;
    expect(r.ok(), `preview-graph ${cat.key} nie odpowiada 200 (#697)`).toBeTruthy();
    const body = await r.json();
    checkedAny = true;

    expect(typeof body.open_doors, "brak pola open_doors (#697)").toBe("number");
    expect(typeof body.caps_complete, "brak pola caps_complete (#697)").toBe("boolean");
    expect(body.entry_node, "graf musi mieć wejście (fallback nie blokuje lochu)").toBeTruthy();

    // KLUCZOWE: gdy kategoria ma komplet zaślepek → ZERO niepołączonych drzwi
    if (body.caps_complete) {
      expect(body.open_doors, `kategoria ${cat.key} ma zaślepki, ale zostały otwarte drzwi (#697)`).toBe(0);
    }
  }
  test.skip(!checkedAny, "żadna kategoria nie ma puli ≥2 kafli — nic do sprawdzenia");
});
