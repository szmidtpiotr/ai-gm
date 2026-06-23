/**
 * REGRESSION #920 (W15) — Admin CMS panel dla wizytówki: GET/PUT treści showcase.
 * Acceptance: admin może odczytać i zapisać historia.json przez API /api/admin/showcase/{key}.
 * Auth wymagana (401 bez tokenu), dane zwracane jako JSON.
 */
const { test, expect } = require('@playwright/test');

test('REGRESSION #920 — showcase GET requires auth (401 without token)', async ({ page }) => {
  const r = await page.request.get('/api/admin/showcase/historia');
  expect(r.status(), '#920: GET bez tokenu musi zwrócić 401').toBe(401);
});

test('REGRESSION #920 — showcase GET returns 200 + JSON for valid key', async ({ page }) => {
  // Login
  const loginResp = await page.request.post('/api/admin/dev-login', {
    data: { username: 'demo', password: 'demo' },
  });
  expect(loginResp.ok(), '#920: dev-login powinno zwrócić 200').toBeTruthy();
  const { token } = await loginResp.json();

  const r = await page.request.get('/api/admin/showcase/historia', {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), '#920: GET /api/admin/showcase/historia powinno zwrócić 200').toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.stages), '#920: historia.json musi mieć pole stages (array)').toBeTruthy();
  expect(body.stages.length, '#920: historia musi mieć co najmniej 1 etap').toBeGreaterThan(0);
});

test('REGRESSION #920 — showcase GET 404 for invalid key', async ({ page }) => {
  const loginResp = await page.request.post('/api/admin/dev-login', {
    data: { username: 'demo', password: 'demo' },
  });
  const { token } = await loginResp.json();

  const r = await page.request.get('/api/admin/showcase/nonexistent_key', {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), '#920: nieistniejący klucz musi zwrócić 404').toBe(404);
});

test('REGRESSION #920 — showcase admin section appears in /admin/ nav', async ({ page }) => {
  await page.goto('/admin/');
  await page.waitForTimeout(800);

  // Login if overlay present
  const overlay = await page.$('#login-overlay.open');
  if (overlay) {
    await page.fill('#login-user', 'demo');
    await page.fill('#login-pass', 'demo');
    await page.click('#login-submit');
    await page.waitForTimeout(600);
  }

  // Navigate to showcase section
  await page.goto('/admin/#showcase');
  await page.waitForTimeout(1000);

  const heading = await page.textContent('.section-heading');
  expect(heading, '#920: sekcja Wizytówka powinna być widoczna').toContain('Wizytówka');
});
