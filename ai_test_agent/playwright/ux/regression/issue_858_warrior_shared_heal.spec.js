/**
 * REGRESSION #858 — bandaż jako uniwersalne (class-agnostic) leczenie w walce.
 * Acceptance: bandaż leczy SIEBIE (effect_target='self'), a wojownik startuje z bandażem
 *             (bazowe leczenie w walce, odpowiednik mikstury/spella maga). Bandaż NIE jest warrior-only.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #858 — bandaż leczy SIEBIE (effect_target=self)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/consumables`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `consumables endpoint must return 200: ${r.status()}`).toBeTruthy();
  const items = (await r.json()).items || [];
  const bandage = items.find((x) => x.key === "bandage");
  expect(bandage, "bandaż musi istnieć w katalogu konsumabli").toBeTruthy();
  expect(bandage.effect_type, "bandaż musi leczyć HP").toBe("heal_hp");
  expect(bandage.effect_target, "bandaż musi leczyć SIEBIE (self), nie sojusznika").toBe("self");
});

test("REGRESSION #858 — wojownik startuje z bandażem (bazowe leczenie w walce)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/archetypes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `archetypes endpoint must return 200: ${r.status()}`).toBeTruthy();
  const items = (await r.json()).items || [];
  const warrior = items.find((x) => x.key === "warrior");
  expect(warrior, "archetyp wojownika musi istnieć").toBeTruthy();
  const starter = JSON.parse(warrior.starter_items_json || "[]");
  const hasBandage = starter.some((it) => it && it.consumable_key === "bandage");
  expect(hasBandage, "starter wojownika musi zawierać bandaż (#858)").toBeTruthy();
});
