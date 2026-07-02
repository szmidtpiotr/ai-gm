/**
 * REGRESSION #1070 — buty (armor_coverage='feet') i płaszcze ('back') były martwym
 * contentem: backend odrzucał walidację, manekin gracza nie miał komórek na te sloty.
 * Acceptance: admin może stworzyć zbroję z coverage feet/back (POST /admin/items),
 * cheat 'add item' auto-zakłada ją na anatomiczny slot feet/back, a
 * GET /api/inventory/{id} zwraca ją wyekwipowaną na tym slocie.
 */
const { test, expect } = require('@playwright/test');

async function adminToken(page) {
  const r = await page.request.post('/api/admin/dev-login', {
    data: { username: 'demo', password: 'demo' },
  });
  expect(r.ok(), 'dev-login nie zwrócił 200 (#1070)').toBeTruthy();
  return (await r.json()).token;
}

test('REGRESSION #1070 — boots/cloak equip to feet/back slots', async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = Date.now();
  const bootsKey = `test_boots_${suffix}`;
  const cloakKey = `test_cloak_${suffix}`;

  for (const [key, label, coverage] of [
    [bootsKey, 'Testowe buty', 'feet'],
    [cloakKey, 'Testowy płaszcz', 'back'],
  ]) {
    const createR = await page.request.post('/api/admin/items', {
      headers,
      data: { key, label, item_type: 'armor', armor_coverage: coverage, ac_bonus: 1 },
    });
    expect(createR.ok(), `POST /admin/items (${coverage}) musi zwrócić 200 (#1070)`).toBeTruthy();
  }

  const heroesR = await page.request.get('/api/admin/sandbox/heroes', { headers });
  expect(heroesR.ok()).toBeTruthy();
  const { heroes } = await heroesR.json();
  expect(heroes.length, 'brak bohaterów do sklonowania w sandboxie').toBeGreaterThan(0);

  const setupR = await page.request.post('/api/admin/sandbox/setup', {
    headers,
    data: { hero_id: heroes[0].id },
  });
  expect(setupR.ok(), 'sandbox/setup nie odpowiada 200 (#1070)').toBeTruthy();
  const { character_id } = await setupR.json();

  for (const [key, coverage] of [[bootsKey, 'feet'], [cloakKey, 'back']]) {
    const cheatR = await page.request.post(`/api/admin/cheat/${character_id}`, {
      headers,
      data: { cmd: 'add item', key },
    });
    expect(cheatR.ok(), `cheat 'add item' (${coverage}) nie odpowiada 200 (#1070)`).toBeTruthy();
    const cheatBody = await cheatR.json();
    expect(
      cheatBody.result?.equipped_slot,
      `nowy item (${coverage}) powinien auto-założyć się na slot '${coverage}' (#1070)`
    ).toBe(coverage);
  }

  const invR = await page.request.get(`/api/inventory/${character_id}`);
  expect(invR.ok()).toBeTruthy();
  const invBody = await invR.json();
  const bootsRow = invBody.data.find((it) => it.key === bootsKey);
  const cloakRow = invBody.data.find((it) => it.key === cloakKey);
  expect(bootsRow?.equipped, 'buty powinny być equipped=1').toBe(1);
  expect(bootsRow?.slot, "buty powinny leżeć na slot='feet'").toBe('feet');
  expect(cloakRow?.equipped, 'płaszcz powinien być equipped=1').toBe(1);
  expect(cloakRow?.slot, "płaszcz powinien leżeć na slot='back'").toBe('back');
});
