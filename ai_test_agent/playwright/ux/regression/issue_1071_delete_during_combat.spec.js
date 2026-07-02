/**
 * REGRESSION #1071 — Usuwanie bohatera w trakcie aktywnej walki jest blokowane (live-lock).
 * Acceptance: DELETE /api/admin/characters/{id} na bohaterze w aktywnej walce → 409
 * {detail:{reason:"live_locked"}}, bohater NIE usunięty. Z ?force=true → 200 ok:true,
 * walka kończy się, bohater usunięty. Uses the combat sandbox (disposable [SBX] clone) —
 * never touches a real hero.
 */
const { test, expect } = require('@playwright/test');

async function adminToken(page) {
  const r = await page.request.post('/api/admin/dev-login', {
    data: { username: 'demo', password: 'demo' },
  });
  expect(r.ok(), 'dev-login nie zwrócił 200 (#1071)').toBeTruthy();
  return (await r.json()).token;
}

test('REGRESSION #1071 — delete blocked mid-combat, force=true kończy walkę i usuwa', async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const heroesR = await page.request.get('/api/admin/sandbox/heroes', { headers });
  expect(heroesR.ok(), 'GET sandbox/heroes nie odpowiada 200 (#1071)').toBeTruthy();
  const { heroes } = await heroesR.json();
  expect(heroes.length, 'brak bohaterów do sklonowania w sandboxie').toBeGreaterThan(0);
  const sourceHeroId = heroes[0].id;

  const enemiesR = await page.request.get('/api/admin/sandbox/enemies', { headers });
  expect(enemiesR.ok()).toBeTruthy();
  const { enemies } = await enemiesR.json();
  expect(enemies.length, 'brak przeciwników w game_config_enemies').toBeGreaterThan(0);
  const enemyKey = enemies[0].key;

  const setupR = await page.request.post('/api/admin/sandbox/setup', {
    headers,
    data: { hero_id: sourceHeroId },
  });
  expect(setupR.ok(), 'sandbox/setup nie odpowiada 200 (#1071)').toBeTruthy();
  const { campaign_id, character_id } = await setupR.json();

  const combatR = await page.request.post('/api/admin/sandbox/start-combat', {
    headers,
    data: { campaign_id, character_id, enemy_keys: [enemyKey] },
  });
  expect(combatR.ok(), 'sandbox/start-combat nie odpowiada 200 (#1071)').toBeTruthy();

  // Bez force: 409 live_locked, klon NIE usunięty.
  const blockedR = await page.request.delete(`/api/admin/characters/${character_id}`, { headers });
  expect(blockedR.status(), 'delete podczas walki powinien zwrócić 409 (#1071)').toBe(409);
  const blockedBody = await blockedR.json();
  expect(blockedBody.detail?.reason, 'detail.reason powinien być live_locked (#1071)').toBe('live_locked');

  const stillThereR = await page.request.get('/api/admin/sandbox/character/' + character_id, { headers });
  expect(stillThereR.ok(), 'klon zniknął mimo zablokowanego delete (#1071)').toBeTruthy();

  // Z force=true: 200 ok:true, klon usunięty.
  const forcedR = await page.request.delete(`/api/admin/characters/${character_id}?force=true`, { headers });
  expect(forcedR.ok(), 'delete z force=true powinien zwrócić 200 (#1071)').toBeTruthy();
  const forcedBody = await forcedR.json();
  expect(forcedBody.ok).toBeTruthy();
  expect(forcedBody.deleted_id).toBe(character_id);
});
