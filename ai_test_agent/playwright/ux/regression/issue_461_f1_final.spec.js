/**
 * REGRESSION #461 F1 final — apply_condition, static_stat_modifier Effect Objects
 * accepted by schema validator. Engine coverage (combat-start AC/stat injection +
 * on-hit condition application) is verified in pytest unit tests.
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

test("REGRESSION #461 F1 final — apply_condition Effect Object round-trips through weapon API", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const weaponKey = "rgr461f1_burning_sword";
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });

  const effectJson = {
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [{ type: "apply_condition", condition_key: "burning", duration_rounds: 2 }],
  };

  const create = await request.post(`${BASE}/api/admin/weapons`, {
    headers,
    data: {
      key: weaponKey,
      label: "Burning Sword (regression 461 apply_condition)",
      damage_die: "1d8",
      linked_stat: "STR",
      weapon_type: "melee",
      allowed_classes: ["warrior", "ranger"],
      is_active: true,
      effect_json: JSON.stringify(effectJson),
    },
  });
  expect(
    create.ok(),
    `POST /admin/weapons with apply_condition failed: ${create.status()} — ${await create.text()}`
  ).toBeTruthy();

  // Read back and verify schema preserved
  const list = await request.get(`${BASE}/api/admin/weapons`, { headers });
  expect(list.ok(), `GET /admin/weapons failed: ${list.status()}`).toBeTruthy();
  const items = (await list.json()).items ?? (await list.json());
  const weapon = (Array.isArray(items) ? items : []).find((w) => w.key === weaponKey);
  expect(weapon, `Weapon ${weaponKey} not found after create (#461 final)`).toBeTruthy();

  const parsed =
    typeof weapon.effect_json === "string"
      ? JSON.parse(weapon.effect_json)
      : weapon.effect_json;
  expect(parsed?.effect_category, "effect_category should be gear_bonus").toBe("gear_bonus");
  const cond = (parsed?.effects || []).find((e) => e.type === "apply_condition");
  expect(cond, "apply_condition effect should be present").toBeTruthy();
  expect(cond?.condition_key, "condition_key should be burning").toBe("burning");

  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });
});

test("REGRESSION #461 F1 final — static_stat_modifier Effect Object accepted by schema validator", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const weaponKey = "rgr461f1_strength_sword";
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });

  const effectJson = {
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [{ type: "static_stat_modifier", stat: "STR", value: 2 }],
  };

  const create = await request.post(`${BASE}/api/admin/weapons`, {
    headers,
    data: {
      key: weaponKey,
      label: "Strength Sword (regression 461 stat_modifier)",
      damage_die: "1d8",
      linked_stat: "STR",
      weapon_type: "melee",
      allowed_classes: ["warrior"],
      is_active: true,
      effect_json: JSON.stringify(effectJson),
    },
  });
  expect(
    create.ok(),
    `POST /admin/weapons with static_stat_modifier failed: ${create.status()} — ${await create.text()}`
  ).toBeTruthy();

  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });
});

test("REGRESSION #461 F1 final — combo weapon (ac_bonus + static_stat_modifier) accepted", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const weaponKey = "rgr461f1_combo_sword";
  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });

  const effectJson = {
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [
      { type: "ac_bonus", value: 1 },
      { type: "static_stat_modifier", stat: "DEX", value: 2 },
    ],
  };

  const create = await request.post(`${BASE}/api/admin/weapons`, {
    headers,
    data: {
      key: weaponKey,
      label: "Combo Sword (regression 461 multi-effect)",
      damage_die: "1d8",
      linked_stat: "DEX",
      weapon_type: "melee",
      allowed_classes: ["warrior", "ranger"],
      is_active: true,
      effect_json: JSON.stringify(effectJson),
    },
  });
  expect(
    create.ok(),
    `POST /admin/weapons with combo effects failed: ${create.status()} — ${await create.text()}`
  ).toBeTruthy();

  await request.delete(`${BASE}/api/admin/weapons/${weaponKey}`, { headers });
});
