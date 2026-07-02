/**
 * REGRESSION #1108 — Kuźnia: modal mapy do ręcznego wyboru hexa startowego szablonu
 * + fix scoringu auto-przydziału (snow NIE wygrywa z town/plains).
 * Acceptance: endpoint hex-availability klasyfikuje hexy (free_good/free_atypical/occupied);
 * auto-przydział nigdy nie ląduje na snow/ruins gdy istnieje wolny town/plains; przycisk
 * "🗺 Przydziel teren" w Kuźni otwiera modal mapy z legendą.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  return token;
}

async function adminLogin(page, token) {
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

// ── Test 1: endpoint dostępności hexów klasyfikuje teren ─────────────────────
test("REGRESSION #1108 — hex-availability klasyfikuje hexy", async ({ page }) => {
  const token = await adminToken(page);
  // znajdź jakiś szablon
  const tplResp = await page.request.get("/api/admin/forge/templates", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(tplResp.ok(), "lista szablonów nie odpowiada 200").toBeTruthy();
  const tplBody = await tplResp.json();
  const templates = tplBody.items || tplBody.templates || tplBody || [];
  test.skip(!templates.length, "brak szablonów w Kuźni na DEV");
  const tplId = templates[0].id;

  const r = await page.request.get(`/api/admin/forge/templates/${tplId}/hex-availability`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "hex-availability nie odpowiada 200 (#1108)").toBeTruthy();
  const body = await r.json();
  const hexes = body.hexes || [];
  expect(hexes.length, "brak hexów — świat pusty?").toBeGreaterThan(0);

  const statuses = new Set(hexes.map((h) => h.status));
  // każdy hex ma dozwolony status
  const allowed = new Set(["free_good", "free_atypical", "occupied"]);
  for (const s of statuses) expect(allowed.has(s), `nieznany status: ${s}`).toBeTruthy();
  // pola markerów obecne
  expect(hexes.every((h) => "is_current" in h && "is_template_start" in h)).toBeTruthy();
});

// ── Test 2: auto-przydział preferuje town/plains (fix scoringu) ───────────────
test("REGRESSION #1108 — auto-przydział nie ląduje na snow gdy jest town/plains", async ({ page }) => {
  const token = await adminToken(page);
  const tplResp = await page.request.get("/api/admin/forge/templates", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const tplBody = await tplResp.json();
  const templates = tplBody.items || tplBody.templates || tplBody || [];
  test.skip(!templates.length, "brak szablonów");
  const tplId = templates[0].id;

  const r = await page.request.post(`/api/admin/forge/templates/${tplId}/allocate-hex`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  // 200 = przydzielono; 422 = brak wolnych hexów (dozwolony stan pustego świata)
  if (r.status() === 422) {
    test.skip(true, "brak wolnych hexów na DEV");
  }
  expect(r.ok(), "allocate-hex nie odpowiada 200 (#1108)").toBeTruthy();
  const body = await r.json();
  const h = body.start_hex || {};
  // Fix scoringu: gdy przydzielono normalnie (bez warning), teren MUSI być preferowany.
  if (!body.warning) {
    expect(
      ["town", "plains", "castle"].includes(h.hex_type),
      `auto-przydział bez warning powinien wybrać town/plains — dostano ${h.hex_type}`
    ).toBeTruthy();
  }
});

// ── Test 3: przycisk "Przydziel teren" otwiera modal mapy ────────────────────
test("REGRESSION #1108 — modal mapy otwiera się z legendą i SVG", async ({ page }) => {
  const token = await adminToken(page);
  await adminLogin(page, token);
  await page.goto("/admin/#forge");

  // Kuźnia ma subtaby — przejdź do "📖 Szablony", gdzie są karty szablonów.
  const szablonyTab = page.locator('.stab[data-forgetab="templates"]');
  await expect(szablonyTab).toBeVisible({ timeout: 15000 });
  await szablonyTab.click();

  // poczekaj na kartę szablonu z przyciskiem
  const btn = page.locator('button:has-text("Przydziel teren")').first();
  await expect(btn, "brak przycisku Przydziel teren (brak szablonów?)").toBeVisible({ timeout: 15000 });
  await btn.click();

  // modal z SVG mapy
  await expect(page.locator("#forge-hex-svg")).toBeVisible({ timeout: 10000 });
  // legenda zawiera opis kolorów
  await expect(page.locator(".modal-overlay.open")).toContainText("zajęty");
  // hexy narysowane
  const polys = await page.locator("#forge-hex-svg polygon").count();
  expect(polys, "SVG mapy nie ma hexów").toBeGreaterThan(0);
});
