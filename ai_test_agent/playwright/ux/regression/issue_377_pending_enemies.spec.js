/**
 * REGRESSION #377 (D2) — Pending flow wrogów.
 * Nieznany klucz wroga w [COMBAT_START:...] → rekord review_status='pending_review'
 * w game_config_enemies, widoczny w kolejce recenzji admina (Bestiariusz → Oczekujące).
 * Acceptance: endpoint /api/admin/world/pending/enemies zwraca listę, a licznik
 * /pending/counts zawiera klucz `enemies` — to dane, z których panel rysuje sekcję "Wróg".
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #377 — kolejka pending enemies odpowiada poprawnym kontraktem", async ({ page }) => {
  // 1) Lista pending wrogów — kształt {items: []}
  const list = await page.request.get("/api/admin/world/pending/enemies");
  expect(list.ok(), "GET /pending/enemies nie odpowiada 200 (#377)").toBeTruthy();
  const listBody = await list.json();
  expect(Array.isArray(listBody.items), "/pending/enemies.items musi być tablicą (#377)").toBeTruthy();

  // Każdy rekord (jeśli są) musi mieć review_status=pending_review i klucz.
  for (const e of listBody.items) {
    expect(e.key, "pending wróg bez klucza (#377)").toBeTruthy();
    expect(e.review_status, "pending wróg musi mieć review_status=pending_review (#377)").toBe("pending_review");
  }

  // 2) Licznik kolejki zawiera `enemies` — badge w panelu admina liczy na ten klucz.
  const counts = await page.request.get("/api/admin/world/pending/counts");
  expect(counts.ok(), "GET /pending/counts nie odpowiada 200 (#377)").toBeTruthy();
  const countsBody = await counts.json();
  expect(typeof countsBody.enemies, "pending/counts musi mieć numeryczny klucz enemies (#377)").toBe("number");
  expect(countsBody.enemies, "licznik enemies >= długości listy (#377)").toBeGreaterThanOrEqual(listBody.items.length);
});
