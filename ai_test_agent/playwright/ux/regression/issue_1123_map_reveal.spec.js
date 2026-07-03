/**
 * REGRESSION #1123 (PT13) — Mapy jako przedmioty odkrywają fog of war.
 * Weryfikuje kontrakt: przedmiot item_type='map' istnieje w katalogu, jego
 * effect_json ma poprawny tryb (radius/region/hexes), a endpoint przedmiotów
 * zwraca go jako "map" (fundament pod użycie z ekwipunku → discovered=1).
 * Acceptance: katalog zna typ 'map' i wystawia go przez /api/items.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1123 — katalog wystawia przedmiot typu 'map' z payloadem reveal", async ({ page }) => {
  // Lista wszystkich przedmiotów (bez filtra typu — /api/items?item_type nie zna 'map')
  const r = await page.request.get("/api/items");
  expect(r.ok(), "GET /api/items nie zwraca 200 (#1123)").toBeTruthy();
  const body = await r.json();
  const items = body.data || body.items || [];
  const maps = items.filter((it) => String(it.item_type || "").toLowerCase() === "map");

  // Jest co najmniej jedna mapa w katalogu (seed przykładowej mapy).
  expect(maps.length, "brak przedmiotu typu 'map' w katalogu — seed nie wykonany (#1123)").toBeGreaterThan(0);

  // Każda mapa ma effect_json z poprawnym trybem odkrywania.
  const modes = new Set(["radius", "region", "hexes"]);
  for (const m of maps) {
    let ej = m.effect_json;
    if (typeof ej === "string") {
      try { ej = JSON.parse(ej); } catch { ej = null; }
    }
    expect(ej, `mapa ${m.key} bez effect_json (#1123)`).toBeTruthy();
    // flat {mode:...} lub wrapped {effects:[{type:'map_reveal',mode:...}]}
    let mode = ej.mode;
    if (!mode && Array.isArray(ej.effects)) {
      const e = ej.effects.find((x) => x && x.type === "map_reveal");
      mode = e && e.mode;
    }
    expect(modes.has(String(mode).toLowerCase()), `mapa ${m.key} ma zły tryb '${mode}' (#1123)`).toBeTruthy();
  }
});
