/**
 * REGRESSION #933 (KRESY-HEX) — Wszystkie typy terenu mapy Kresów mają konfigurację koloru/ikony.
 * Acceptance: /api/admin/world/hex-terrain-config zwraca heath/snow/sea/mountain/village/lake/bridge;
 * bridge ma encounter_base_chance > 0; osada Strażyn (q=33,r=6) ma location_key='strazyn'.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const body = await resp.json();
  return body.token;
}

test("REGRESSION #933 — Kresy hex_types registered in terrain config", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/world/hex-terrain-config", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `hex-terrain-config nie odpowiada 200 (#933): ${r.status()}`).toBeTruthy();

  const body = await r.json();
  const types = (Array.isArray(body) ? body : body.types ?? body.data ?? []).map(
    (t) => t.hex_type ?? t.type ?? t.key
  );

  const required = ["heath", "snow", "sea", "mountain", "village", "lake", "bridge"];
  for (const ht of required) {
    expect(types, `hex_type '${ht}' brakuje w terrain config (#933)`).toContain(ht);
  }
});

test("REGRESSION #933 — bridge has encounter_base_chance > 0 (toll)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/world/hex-terrain-config", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();

  const body = await r.json();
  const types = Array.isArray(body) ? body : body.types ?? body.data ?? [];
  const bridge = types.find((t) => (t.hex_type ?? t.type ?? t.key) === "bridge");

  expect(bridge, "bridge brakuje w terrain config (#933)").toBeTruthy();
  const chance = bridge.encounter_base_chance ?? bridge.encounterBaseChance ?? 0;
  expect(chance, `bridge encounter_base_chance powinno być > 0 (myto), got ${chance}`).toBeGreaterThan(0);
});

test("REGRESSION #933 — Strażyn hex has location_key=strazyn", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/world/map?map_level=0", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `world/map nie odpowiada 200 (#933): ${r.status()}`).toBeTruthy();

  const data = await r.json();
  const hexes = Array.isArray(data) ? data : data.hexes ?? data.data ?? [];
  const strazyn = hexes.find((h) => h.q === 33 && h.r === 6);
  expect(strazyn, "Brak hexu q=33,r=6 (Strażyn) w world_hexes (#933)").toBeTruthy();
  expect(
    strazyn.location_key,
    `Strażyn (33,6) powinien mieć location_key='strazyn', got ${strazyn.location_key}`
  ).toBe("strazyn");
});
