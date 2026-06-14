/**
 * REGRESSION #612 (S17) — Wrestling: skill nakłada kondycje wrogom (opposed STR vs STR).
 * Acceptance: skill 'wrestling' (STR) zaseedowany w katalogu + endpoint akcji bojowej
 * /combat/wrestling istnieje (400 bez aktywnej walki, nie 404). Deterministyczny kontrakt
 * — pełny przepływ STR vs STR + nakładanie kondycji pokrywa pytest real-engine.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  return token;
}

test("REGRESSION #612 — skill 'wrestling' (STR) zaseedowany w katalogu", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/skills", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/skills nie odpowiada 200 (#612)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body) ? body : (body.skills || body.items || []);
  const wrestling = list.find((s) => String(s.key) === "wrestling");
  expect(wrestling, "skill 'wrestling' musi być w katalogu (#612)").toBeTruthy();
  expect(String(wrestling.linked_stat).toUpperCase()).toBe("STR");
});

test("REGRESSION #612 — endpoint /combat/wrestling istnieje (400 bez walki, nie 404)", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/999999/combat/wrestling", {
    data: {},
  });
  // 400 = trasa istnieje, brak aktywnej walki; 404 = trasa nie zarejestrowana (regresja).
  expect(r.status(), "wrestling endpoint musi istnieć (400 nie 404) (#612)").toBe(400);
});
