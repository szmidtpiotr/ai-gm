/**
 * REGRESSION #764 — System amunicji: łuki wymagają strzał, kusze bełtów.
 * Acceptance: istnieją przedmioty strzały/bełty (stackowalne) i każda broń
 * dystansowa ma poprawnie przypisaną amunicję (ammo_key) w katalogu.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "ai_test_player", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił tokenu (#764)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #764 — strzały/bełty w katalogu + mapowanie broni", async ({ request }) => {
  const token = await adminToken(request);
  const auth = { Authorization: `Bearer ${token}` };

  // 1) Amunicja istnieje jako consumable.
  const cr = await request.get("/api/admin/consumables", { headers: auth });
  expect(cr.ok(), "GET /admin/consumables != 200").toBeTruthy();
  const cbody = await cr.json();
  const consumables = cbody.items || cbody.data || cbody || [];
  const keys = consumables.map((c) => c.key);
  expect(keys, "brak 'arrows' w katalogu consumable").toContain("arrows");
  expect(keys, "brak 'bolts' w katalogu consumable").toContain("bolts");

  // 2) Broń dystansowa wskazuje wymaganą amunicję (ammo_key).
  const wr = await request.get("/api/admin/weapons", { headers: auth });
  expect(wr.ok(), "GET /admin/weapons != 200").toBeTruthy();
  const wbody = await wr.json();
  const weapons = wbody.items || wbody.data || wbody || [];
  const byKey = Object.fromEntries(weapons.map((w) => [w.key, w]));

  expect(byKey.shortbow, "brak shortbow w katalogu").toBeTruthy();
  expect(byKey.shortbow.ammo_key, "łuk powinien wymagać strzał").toBe("arrows");
  if (byKey.crossbow) {
    expect(byKey.crossbow.ammo_key, "kusza powinna wymagać bełtów").toBe("bolts");
  }

  // 3) Żadna broń do walki wręcz nie wymaga amunicji.
  const melee = weapons.filter((w) => (w.weapon_type || "melee") === "melee");
  for (const m of melee) {
    expect(m.ammo_key == null, `broń wręcz ${m.key} nie powinna mieć ammo_key`).toBeTruthy();
  }
});
