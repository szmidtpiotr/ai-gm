/**
 * REGRESSION #652 (B7) — tier-gating nauki czarów: dane tieru istnieją i bramka ma sens.
 * Logika bramki (max_tier=ceil(level/2)) + model trafienia (pojedynek WIS/CON + zwrot ½ many)
 * w pełni pokryte pytest test_issue652_b7_spell_tier_and_save.py (28/28). Ten spec to
 * kontrakt danych: katalog czarów wystawia `tier`, istnieją czary tier>1 (gate nie jest no-op).
 * Acceptance: GET /api/admin/spells zwraca pozycje z polem tier; min. jeden czar tier>1.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login demo/demo nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina").toBeTruthy();
  return body.token;
}

test("REGRESSION #652 — katalog czarów wystawia tier i istnieją czary tier>1 (bramka ma sens)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  expect(items.length, "katalog czarów pusty").toBeGreaterThan(0);

  // Każdy czar ma pole tier (wejście bramki).
  expect(items.every((s) => Number.isInteger(s.tier)), "nie każdy czar ma całkowity tier").toBeTruthy();

  // Istnieje czar tier>1 — inaczej max_tier=ceil(level/2) byłby bez znaczenia.
  const highTier = items.filter((s) => (s.tier || 1) > 1);
  expect(highTier.length, "brak czarów tier>1 — bramka tieru byłaby no-op").toBeGreaterThan(0);
});
