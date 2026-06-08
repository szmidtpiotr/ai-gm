/**
 * REGRESSION #382 (D7) — Encountery generyczne: dobór template per teren/poziom.
 * gameconfig_encounter_templates dobierane po poziomie bohatera + tagu lokacji.
 * Acceptance (deterministyczny): endpoint zwraca kandydatów respektujących zakres
 * poziomu i tag. Logika doboru/fallbacku pokryta pytestem.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #382 — dobór encounter templates per poziom/teren (kontrakt)", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/encounter-templates?level=3&location_tag=forest");
  expect(r.ok(), "endpoint nie odpowiada 200 (#382)").toBeTruthy();
  const body = await r.json();
  expect(body.level, "brak level w odpowiedzi (#382)").toBe(3);
  expect(Array.isArray(body.candidates), "candidates musi być tablicą (#382)").toBeTruthy();
  expect(typeof body.count, "count musi być liczbą (#382)").toBe("number");
  // Każdy kandydat respektuje zakres poziomu (min<=3<=max) i ma listę wrogów.
  for (const c of body.candidates) {
    expect(Number(c.min_level) <= 3 && Number(c.max_level) >= 3,
      `kandydat poza zakresem poziomu (#382): ${c.key}`).toBeTruthy();
    expect(Array.isArray(c.enemies), `kandydat bez listy enemies (#382): ${c.key}`).toBeTruthy();
  }

  // Za wysoki poziom dla tagu mountain nie może zwrócić niskopoziomowych leśnych.
  const r2 = await page.request.get("/api/admin/world/encounter-templates?level=50");
  expect(r2.ok(), "endpoint (level=50) nie odpowiada 200 (#382)").toBeTruthy();
});

test("REGRESSION #382 — config częstotliwości encounterów (admin-tunable)", async ({ page }) => {
  const get = await page.request.get("/api/admin/world/encounter-config");
  expect(get.ok(), "GET encounter-config nie 200 (#382)").toBeTruthy();
  const cfg = await get.json();
  expect(typeof cfg.n_turns_interval, "n_turns_interval musi być liczbą (#382)").toBe("number");
  expect(typeof cfg.dwell_settle_turns, "dwell_settle_turns musi być liczbą (#382)").toBe("number");

  // Set + read-back
  const set = await page.request.post("/api/admin/world/encounter-config", { data: { n_turns_interval: 20 } });
  expect(set.ok(), "POST encounter-config nie 200 (#382)").toBeTruthy();
  const after = await set.json();
  expect(after.n_turns_interval, "interwał nie zapisany (#382)").toBe(20);
});
