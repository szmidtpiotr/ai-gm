/**
 * REGRESSION #1039 (Faza RM) — admin przełącza dostępność krainy (coming↔live),
 * gracz odbija się od krainy niedostępnej z komunikatem blokady.
 * Acceptance: PATCH /api/admin/regions/{key}/status flipuje status w obie strony
 * (i wraca do stanu wyjściowego), a lista krain admina pokazuje też nie-live.
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
  expect(r2.ok(), "dev-login nie odpowiada 200").toBeTruthy();
  return (await r2.json()).token;
}

test("REGRESSION #1039 — admin widzi wszystkie krainy (live + coming/locked)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/regions", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/regions nie odpowiada 200 (#1039)").toBeTruthy();
  const { regions } = await r.json();
  expect(Array.isArray(regions) && regions.length >= 2).toBeTruthy();
  for (const reg of regions) {
    expect(["live", "coming", "locked"], `zły status ${reg.status}`).toContain(reg.status);
  }
  // Admin preview = pełna lista, nie tylko live.
  expect(regions.some((x) => x.status !== "live"), "brak krain nie-live w liście admina").toBeTruthy();
});

test("REGRESSION #1039 — toggle statusu krainy działa w obie strony", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const list = await (await page.request.get("/api/admin/regions", { headers })).json();
  // Wybierz krainę NIE-startową, żeby test nie zamykał Kresów graczom.
  const target = list.regions.find((x) => x.key !== "kresy");
  expect(target, "brak krainy testowej poza 'kresy'").toBeTruthy();
  const original = target.status;
  const flipped = original === "live" ? "coming" : "live";

  const up = await page.request.patch(`/api/admin/regions/${target.key}/status`, {
    headers, data: { status: flipped },
  });
  expect(up.ok(), "PATCH statusu nie odpowiada 200 (#1039)").toBeTruthy();
  expect((await up.json()).status).toBe(flipped);

  const after = await (await page.request.get("/api/admin/regions", { headers })).json();
  expect(after.regions.find((x) => x.key === target.key).status).toBe(flipped);

  // Przywróć stan wyjściowy i zdejmij override (status:null) — test nie zostawia
  // po sobie zmienionej dostępności świata ani nadpisanego kanonu.
  const back = await page.request.patch(`/api/admin/regions/${target.key}/status`, {
    headers, data: { status: original },
  });
  expect(back.ok()).toBeTruthy();
  const clear = await page.request.patch(`/api/admin/regions/${target.key}/status`, {
    headers, data: { status: null },
  });
  expect(clear.ok(), "reset override (status:null) nie odpowiada 200").toBeTruthy();
  expect((await clear.json()).overridden).toBe(false);
  const restored = await (await page.request.get("/api/admin/regions", { headers })).json();
  const back2 = restored.regions.find((x) => x.key === target.key);
  expect(back2.status).toBe(original);
  expect(back2.status_override == null, "override nie został zdjęty").toBeTruthy();
});

test("REGRESSION #1039 — nieprawidłowy status odrzucony (422)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.patch("/api/admin/regions/kresy/status", {
    headers: { Authorization: `Bearer ${token}` },
    data: { status: "enabled" },
  });
  expect(r.status(), "zły status powinien dać 422").toBe(422);
});

test("REGRESSION #1039 — nieznana kraina → 404", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.patch("/api/admin/regions/atlantyda/status", {
    headers: { Authorization: `Bearer ${token}` },
    data: { status: "live" },
  });
  expect(r.status()).toBe(404);
});
