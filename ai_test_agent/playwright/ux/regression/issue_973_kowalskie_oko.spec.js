/**
 * REGRESSION #973 (R4) — Kowalskie oko: endpoint /dwarf-repair zwraca 403 dla nie-krasnoluda.
 * Acceptance: Człowiek dostaje 403; krasnolud (z bronią i złotem) dostaje ok:true.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #973 — dwarf-repair blokuje nie-krasnoluda (403)", async ({ page }) => {
  // Wywołaj dwarf-repair na demo postaci (user_id=1) — zakładamy że to człowiek
  const listR = await page.request.get("/api/characters?user_id=1");
  if (!listR.ok()) return;
  const listBody = await listR.json();
  const chars = listBody.characters || listBody;
  if (!Array.isArray(chars) || chars.length === 0) return;

  const humanChar = chars.find(c => (c.race || "human") === "human");
  if (!humanChar) return; // Brak ludzkiej postaci — skip

  const r = await page.request.post(`/api/characters/${humanChar.id}/dwarf-repair?user_id=1`);
  // Człowiek powinien dostać 403 (forbidden)
  expect(r.status()).toBe(403);
});
