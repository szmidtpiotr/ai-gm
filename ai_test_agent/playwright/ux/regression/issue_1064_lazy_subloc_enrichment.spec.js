/**
 * REGRESSION #1064 (FAZA ML-2) — lazy LLM-enrichment sub-lokacji przy pierwszym wejściu gracza.
 * Acceptance: admin manual edit of a generic (ai_generated=0) sub-location's label/description
 * flips ai_generated=1, so a later lazy-enrich on player entry never overwrites the admin's text.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1064)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1064)").toBeTruthy();
  return token;
}

test("REGRESSION #1064 — manual edit of generic sub-loc marks ai_generated=1", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };
  const key = `test_loc_pw1064_${Date.now()}`;

  const created = await page.request.post("/api/locations", {
    ...auth,
    data: { key, label: "Test Sub #1064", location_type: "sub" },
  });
  expect(created.status(), "POST /api/locations must return 201 (#1064)").toBe(201);

  try {
    const patched = await page.request.patch(`/api/locations/admin/locations/${key}`, {
      ...auth,
      data: { description: "Ręcznie wpisany opis admina." },
    });
    expect(patched.ok(), "PATCH must return 200 (#1064)").toBeTruthy();
    const body = await patched.json();
    expect(body.ai_generated, "admin edit must set ai_generated=1 so lazy-enrich skips it (#1064)").toBe(1);
  } finally {
    await page.request.delete(`/api/locations/${key}`, auth);
    await page.request.delete(`/api/locations/${key}?force=true`, auth);
  }
});

test("REGRESSION #1064 — enrich-sublocs still skips already-enriched sub-locs (lazy=once contract)", async ({ page }) => {
  const r = await page.request.post("/api/admin/world/locations/__nonexistent_test_key_1064__/enrich-sublocs", {
    data: {},
    headers: { "Content-Type": "application/json" },
  });
  expect(r.ok(), "enrich-sublocs endpoint must return 200 even for unknown key (#1064)").toBeTruthy();
  const body = await r.json();
  expect(body.enriched).toBe(0);
});
