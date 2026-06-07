/**
 * REGRESSION #379 (D4) — Auto-screening admin queue.
 * L1 (mechaniczna walidacja) + L2 (LLM scoring 0-100); score>80 i L1 pass →
 * auto-approve, reszta → kolejka admina. L1 to twarda bramka.
 * Acceptance (deterministyczny, bez LLM): endpoint dry_run zwraca dla każdego
 * pending rekordu wynik L1 ({passed, errors}). Pełna logika decyzji w pytest
 * test_issue379_auto_screening.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #379 — auto-screen dry_run zwraca kontrakt L1 dla kolejki", async ({ page }) => {
  for (const type of ["enemy", "item"]) {
    const r = await page.request.post(`/api/admin/world/auto-screen-queue/${type}?dry_run=1`);
    expect(r.ok(), `POST /auto-screen-queue/${type}?dry_run nie odpowiada 200 (#379)`).toBeTruthy();
    const body = await r.json();
    expect(body.entity_type, "odpowiedź musi zawierać entity_type (#379)").toBe(type);
    expect(body.dry_run, "dry_run musi być true (#379)").toBeTruthy();
    expect(Array.isArray(body.results), "results musi być tablicą (#379)").toBeTruthy();
    expect(typeof body.screened, "screened musi być liczbą (#379)").toBe("number");
    // Każdy wynik dry_run niesie L1 z polem passed (bool) i errors (tablica).
    for (const res of body.results) {
      expect(res.key, "wynik bez klucza (#379)").toBeTruthy();
      expect(res.l1, "wynik musi zawierać L1 (#379)").toBeTruthy();
      expect(typeof res.l1.passed, "l1.passed musi być bool (#379)").toBe("boolean");
      expect(Array.isArray(res.l1.errors), "l1.errors musi być tablicą (#379)").toBeTruthy();
    }
  }
});
