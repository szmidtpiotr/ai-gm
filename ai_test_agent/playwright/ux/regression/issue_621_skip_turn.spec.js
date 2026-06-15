/**
 * REGRESSION #621 — silnik walki honoruje strukturalny skip_turn (slowed/stunned).
 * Acceptance (pełny dowód = pytest backend/tests/test_issue621_skip_turn.py, 4/4):
 *   wróg ze `stunned`/`slowed` traci turę (event block_action via skip_turn).
 * Tu (kontrakt web): katalog kondycji nadal serwuje `slowed` i `stunned` — stany, które
 * naprawiony silnik teraz egzekwuje. effect_json nie jest wystawiany przez API, więc samo
 * pominięcie tury weryfikuje pytest (deterministycznie, bez żywej walki/LLM).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #621 — katalog kondycji serwuje slowed + stunned", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#621)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body) ? body : body.conditions || body.data || [];
  const keys = new Set(list.map((c) => String(c.key || "")));
  expect(keys.has("slowed"), "brak kondycji `slowed` w katalogu (#621)").toBeTruthy();
  expect(keys.has("stunned"), "brak kondycji `stunned` w katalogu (#621)").toBeTruthy();
});
