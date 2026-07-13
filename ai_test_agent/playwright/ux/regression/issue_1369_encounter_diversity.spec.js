/**
 * REGRESSION #1369 (BL) — różnorodność spotkań poz. 1-2 na trakcie.
 * Weryfikuje efekt fixu przez katalog wrogów admina:
 *   1) nowi wrogowie różnorodności (dziki_pies, wilk_stepowy, zbieg, klusownik,
 *      pijawczy_roj) istnieją, są global+permanent+active i mają teren road/river.
 *   2) rekordy testowe (enemy, old_man, s2_pw_*, goblin_u31, unknown_attacker) NIE są
 *      już world_scope='global' — nie wejdą do puli spotkań.
 * Acceptance: pula road/plains poz. 1-2 przestaje być samą rodziną bandytów.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r2.json()).token;
}

test("REGRESSION #1369 — diversity enemies seeded, junk not global", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const resp = await page.request.get("/api/admin/enemies", { headers: auth });
  expect(resp.ok(), "/api/admin/enemies nie odpowiada 200 (#1369)").toBeTruthy();
  const items = (await resp.json()).items || [];
  const byKey = Object.fromEntries(items.map((e) => [e.key, e]));

  // 1) nowi wrogowie różnorodności obecni + globalni + na terenie
  const DIVERSITY = ["dziki_pies", "wilk_stepowy", "zbieg", "klusownik", "pijawczy_roj"];
  for (const k of DIVERSITY) {
    const e = byKey[k];
    expect(e, `brak wroga różnorodności '${k}' (#1369)`).toBeTruthy();
    expect(e.world_scope).toBe("global");
    expect(e.is_active).toBeTruthy();
    expect((e.terrain_tags || "").length, `${k} bez terrain_tags`).toBeGreaterThan(0);
  }

  // co najmniej 3 z nowych beastów siedzą na 'road' (trakt) — różnorodność traktu
  const onRoad = DIVERSITY.filter((k) => (byKey[k]?.terrain_tags || "").includes("road"));
  expect(onRoad.length, "za mało wrogów różnorodności na road").toBeGreaterThanOrEqual(3);

  // 2) śmieci testowe nie są już world_scope='global' (poza pulą)
  const JUNK = ["enemy", "old_man", "s2_pw_bandyta_lucznik", "goblin_u31", "unknown_attacker"];
  for (const k of JUNK) {
    const e = byKey[k];
    if (e) {
      expect(e.world_scope, `śmieć '${k}' nadal global → wejdzie do puli (#1369)`).not.toBe("global");
    }
  }
});
