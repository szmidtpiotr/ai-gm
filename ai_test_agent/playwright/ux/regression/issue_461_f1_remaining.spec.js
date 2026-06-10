/**
 * REGRESSION #461 F1 (remaining types) — heal_on_hit + ac_bonus registered in Effect Object schema.
 * Schema API must accept gear_bonus / heal_on_hit and gear_bonus / ac_bonus Effect Objects.
 * Engine coverage: heal_on_hit life-steal is verified in pytest (requires live combat loop).
 * Acceptance: POST /admin/weapons with heal_on_hit effect_json round-trips without validation error.
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

test("REGRESSION #461 F1 remaining — heal_on_hit Effect Object round-trips through weapon API", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const weaponKey = "rgr461_lifesteal_blade";

  // Teardown any leftover from prior run
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });

  const effectJson = {
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [{ type: "heal_on_hit", value: 3 }],
  };

  // Create weapon with heal_on_hit Effect Object (effect_json must be a JSON string)
  const create = await request.post(`${BASE}/api/admin/weapons`, {
    headers,
    data: {
      key: weaponKey,
      label: "Lifesteal Blade (regression 461)",
      damage_die: "1d8",
      linked_stat: "STR",
      weapon_type: "melee",
      allowed_classes: ["warrior", "ranger"],
      is_active: true,
      effect_json: JSON.stringify(effectJson),
    },
  });
  expect(create.ok(), `POST /admin/weapons failed: ${create.status()} — ${await create.text()}`).toBeTruthy();

  // Read back and verify effect_json schema preserved
  const list = await request.get(`${BASE}/api/admin/weapons`, { headers });
  expect(list.ok(), `GET /admin/weapons failed: ${list.status()}`).toBeTruthy();
  const items = (await list.json()).items ?? (await list.json());
  const weapon = (Array.isArray(items) ? items : []).find((w) => w.key === weaponKey);
  expect(weapon, `Weapon ${weaponKey} not found after create (#461)`).toBeTruthy();

  const parsed = typeof weapon.effect_json === "string"
    ? JSON.parse(weapon.effect_json)
    : weapon.effect_json;
  expect(parsed?.effect_category, "effect_category should be gear_bonus (#461)").toBe("gear_bonus");
  const hoh = (parsed?.effects || []).find((e) => e.type === "heal_on_hit");
  expect(hoh, "heal_on_hit effect should be present (#461)").toBeTruthy();
  expect(Number(hoh.value), "heal_on_hit value should be 3 (#461)").toBe(3);

  // Cleanup
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });
});

test("REGRESSION #461 F1 remaining — ac_bonus Effect Object accepted by schema validator", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const weaponKey = "rgr461_shieldblade";
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });

  const effectJson = {
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [{ type: "ac_bonus", value: 2 }],
  };

  const create = await request.post(`${BASE}/api/admin/weapons`, {
    headers,
    data: {
      key: weaponKey,
      label: "Shield Blade (regression 461 ac_bonus)",
      damage_die: "1d6",
      linked_stat: "STR",
      weapon_type: "melee",
      allowed_classes: ["warrior"],
      is_active: true,
      effect_json: JSON.stringify(effectJson),
    },
  });
  expect(create.ok(), `POST /admin/weapons with ac_bonus failed: ${create.status()} — ${await create.text()}`).toBeTruthy();

  // Cleanup
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });
});
