/**
 * REGRESSION #837 (M1) — Sekcja Zgłoszenia mobile: card-view @390px + drawer czytelny.
 * Acceptance: @390px tabela renderuje się jako karty (nie pozioma tabela), drawer otwiera
 * się bez overflow, brak regresji desktop @1280px.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_URL = process.env.BASE_URL || "http://frontend:80";

async function loginAdmin(page) {
  await page.goto(`${ADMIN_URL}/admin/`);
  await page.waitForTimeout(1500);
  const userInput = page.locator('input[type="text"]').first();
  const passInput = page.locator('input[type="password"]').first();
  if (await userInput.isVisible()) {
    await userInput.fill("demo");
    await passInput.fill("demo");
    await page.locator('button:has-text("Zaloguj")').click();
    await page.waitForTimeout(1500);
  }
}

test("REGRESSION #837 — bug-reports API zwraca dane (klucz reports)", async ({ request }) => {
  // Login to get token
  const loginRes = await request.post(`${ADMIN_URL}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(loginRes.ok(), "admin login failed").toBeTruthy();
  const { token } = await loginRes.json();

  const res = await request.get(`${ADMIN_URL}/api/admin/bug-reports`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(res.ok(), "bug-reports endpoint nie zwraca 200").toBeTruthy();
  const body = await res.json();
  // API zwraca klucz 'reports' (nie 'items') — frontend obsługuje oba
  expect(
    Array.isArray(body.reports) || Array.isArray(body.items),
    "odpowiedź musi mieć klucz 'reports' lub 'items' jako tablicę"
  ).toBeTruthy();
});

test("REGRESSION #837 — bugreports section ma wrapper .data-table--cards", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAdmin(page);

  await page.evaluate(() => {
    const btn = document.querySelector('[data-section="bugreports"]');
    if (btn) btn.click();
  });
  await page.waitForTimeout(2000);

  // Wrapper tabeli musi mieć klasę data-table--cards
  const wrapper = await page.locator(".data-table--cards").count();
  expect(wrapper, "brak wrappera .data-table--cards w sekcji bugreports").toBeGreaterThan(0);
});

test("REGRESSION #837 — desktop @1280px tabela nie zmienia się w karty", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await loginAdmin(page);

  await page.evaluate(() => {
    const btn = document.querySelector('[data-section="bugreports"]');
    if (btn) btn.click();
  });
  await page.waitForTimeout(2000);

  // Na desktop tabela musi być widoczna jako thead (nie ukryta jak w card-view)
  const thead = page.locator("#br-table thead");
  await expect(thead).toBeVisible();
});
