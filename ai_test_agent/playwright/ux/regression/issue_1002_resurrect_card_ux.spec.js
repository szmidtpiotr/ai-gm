/**
 * REGRESSION #1002 — Dead hero badge + Wskrześ button accessible on campaign cards (mobile admin).
 * Acceptance: Na kafelku kampanii (bez otwierania modalu) widoczny znaczek 💀 i przycisk Wskrześ
 * gdy bohater ma HP ≤ 0. Czytelny komunikat gdy globalne wskrzeszenia wyłączone.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminLogin(page) {
  // addInitScript seeds localStorage BEFORE page scripts run — avoids login-overlay interception.
  const resp = await page.request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), `admin dev-login failed: ${resp.status()}`).toBeTruthy();
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
  return token;
}

test("REGRESSION #1002 — campaigns/live zawiera char_current_hp i char_status", async ({ request }) => {
  const resp = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();

  const r = await request.get(`${BASE}/api/admin/campaigns/live`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "campaigns/live nie odpowiada 200 (#1002)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  for (const item of items) {
    expect("char_current_hp" in item, `brak pola char_current_hp w kampanii ${item.id}`).toBeTruthy();
    // char_status wymagane do precyzyjnej detekcji martwego bohatera na kafelku (#1002)
    expect("char_status" in item, `brak pola char_status w kampanii ${item.id}`).toBeTruthy();
  }
});

test("REGRESSION #1002 — resurrection-config zwraca pole config.enabled", async ({ request }) => {
  const resp = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();

  const r = await request.get(`${BASE}/api/admin/resurrection-config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "resurrection-config nie odpowiada 200 (#1002)").toBeTruthy();
  const body = await r.json();
  // Response: {"ok": true, "config": {"enabled": bool, ...}}
  expect(body.config, "brak pola config w odpowiedzi resurrection-config (#1002)").toBeTruthy();
  expect(
    typeof body.config.enabled === "boolean",
    `config.enabled musi być boolean, got: ${typeof body.config?.enabled}`
  ).toBeTruthy();
});

test("REGRESSION #1002 — kafelek kampanii z martwym bohaterem pokazuje badge i przycisk wskrzeszenia", async ({ page, request }) => {
  // Sprawdź czy jest martwy bohater w DEV
  const resp = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  const r = await request.get(`${BASE}/api/admin/campaigns/live`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await r.json();
  const deadCamp = (body.items || []).find(
    (c) => (c.char_current_hp != null && c.char_current_hp <= 0) || c.char_status === "dead"
  );

  if (!deadCamp) {
    console.log("Brak martwego bohatera w DEV — pominięto test wizualny kafelka");
    return;
  }

  // Login przez addInitScript (unika login-overlay intercepting clicks)
  await adminLogin(page);
  await page.goto(`${BASE}/admin/#campaigns`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);

  // Przełącz na widok kafelków
  const cardsBtn = page.locator("[data-view=cards]").first();
  await expect(cardsBtn).toBeVisible({ timeout: 5000 });
  await cardsBtn.click();
  await page.waitForTimeout(800);

  // Badge 💀 musi być widoczny na kafelku BEZ otwierania modalu
  const deadBadge = page.locator("#campaigns-cards-grid .badge-red").filter({ hasText: /martw|dead|💀/i }).first();
  await expect(deadBadge, "Badge '💀 Bohater martwy' musi być widoczny na kafelku bez otwierania modalu (#1002)").toBeVisible({ timeout: 5000 });

  // Przycisk Wskrześ musi być na kafelku (nie w modalu)
  const resurrectBtn = page.locator("#campaigns-cards-grid button").filter({ hasText: /wskrześ/i }).first();
  await expect(resurrectBtn, "Przycisk 'Wskrześ' musi być dostępny na kafelku (#1002)").toBeVisible({ timeout: 3000 });
});
