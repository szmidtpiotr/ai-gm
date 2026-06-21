/**
 * REGRESSION #821 (B15) — Summony jako kombatant-towarzysz.
 * Weryfikuje kontrakt danych: 4 czary przywołania (summon_familiar, summon_elemental,
 * animate_dead, shadow_clone) są zaseedowane jako spell_type='summon' z profilem
 * towarzysza w effect_json (hp / attack_bonus / damage_die / lifetime_rounds / zone).
 * Acceptance: admin widzi czary summon w katalogu, każdy z profilem combatanta-towarzysza.
 */
const { test, expect } = require("@playwright/test");

const EXPECTED = ["summon_familiar", "summon_elemental", "animate_dead", "shadow_clone"];

test("REGRESSION #821 — czary summon zaseedowane z profilem w effect_json", async ({ page }) => {
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(loginResp.ok(), `admin dev-login failed: ${loginResp.status()} (#821)`).toBeTruthy();
  const { token } = await loginResp.json();

  const r = await page.request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/spells nie odpowiada 200 (#821)").toBeTruthy();
  const body = await r.json();
  const spells = Array.isArray(body) ? body : (body.spells || body.items || []);
  expect(spells.length, "katalog czarów pusty").toBeGreaterThan(0);

  const byKey = {};
  for (const s of spells) byKey[s.key] = s;

  for (const key of EXPECTED) {
    const sp = byKey[key];
    expect(sp, `brak czaru summon '${key}' w katalogu (#821)`).toBeTruthy();
    expect(String(sp.spell_type), `${key} musi mieć spell_type='summon'`).toBe("summon");
    // Profil towarzysza w effect_json
    let prof = sp.effect_json;
    if (typeof prof === "string") prof = JSON.parse(prof || "{}");
    expect(prof, `${key} bez effect_json (profil summona)`).toBeTruthy();
    expect(Number(prof.hp), `${key}.hp > 0`).toBeGreaterThan(0);
    expect(Number(prof.lifetime_rounds), `${key}.lifetime_rounds > 0`).toBeGreaterThan(0);
    expect(prof.damage_die, `${key}.damage_die ustawione`).toBeTruthy();
  }
});
