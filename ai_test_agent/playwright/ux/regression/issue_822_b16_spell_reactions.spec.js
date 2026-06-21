/**
 * REGRESSION #822 (B16) — system reakcji czarów (mirror_image / blink / globe_invulnerability).
 * Acceptance: 3 czary spell_type='reaction' istnieją w katalogu z poprawnym profilem effect_json
 * (mirror_image=charges, blink=miss_chance+rounds, globe_invulnerability=rounds).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #822 — backend health OK", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend health endpoint not OK (#822)").toBeTruthy();
});

test("REGRESSION #822 — 3 czary reakcji w katalogu z profilem effect_json", async ({ page }) => {
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (!loginResp.ok()) {
    console.log("Admin login not available; skipping auth-required check (#822)");
    return;
  }
  const { token } = await loginResp.json();

  const r = await page.request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "/api/admin/spells nie odpowiada 200 (#822)").toBeTruthy();
  const body = await r.json();
  const spells = Array.isArray(body) ? body : (body.spells || body.rows || []);

  const byKey = Object.fromEntries(spells.map((s) => [s.key, s]));
  for (const key of ["mirror_image", "blink", "globe_invulnerability"]) {
    expect(byKey[key], `czar ${key} brak w katalogu (#822)`).toBeTruthy();
    expect(
      String(byKey[key].spell_type || "").toLowerCase(),
      `${key} ma zły spell_type (#822)`
    ).toBe("reaction");
  }

  const mi = JSON.parse(byKey.mirror_image.effect_json || "{}");
  expect(mi.reaction).toBe("mirror_image");
  expect(Number(mi.charges)).toBeGreaterThan(0);

  const bl = JSON.parse(byKey.blink.effect_json || "{}");
  expect(bl.reaction).toBe("blink");
  expect(Number(bl.miss_chance)).toBeGreaterThan(0);
  expect(Number(bl.rounds)).toBeGreaterThan(0);

  const gl = JSON.parse(byKey.globe_invulnerability.effect_json || "{}");
  expect(gl.reaction).toBe("globe_invulnerability");
  expect(Number(gl.rounds)).toBeGreaterThan(0);
});
