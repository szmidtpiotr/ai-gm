/**
 * REGRESSION #1073 — narracyjne terminy krytyka w system_prompt.txt zgodne z UI (#641).
 * Acceptance: GET /api/admin/prompts/system_prompt zawiera 'Krytyczny sukces' / 'Krytyczna
 * porażka' (kolejność jak na karcie kości gracza), nie zawiera starej odwróconej kolejności
 * 'Sukces krytyczny' / 'Porażka krytyczna'; terminy mechaniczne 'Nat 20'/'Nat 1' nietknięte.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login musi zwrócić 200 (#1073)").toBeTruthy();
  const body = await r.json();
  expect(body.token, "dev-login musi zwrócić token (#1073)").toBeTruthy();
  return body.token;
}

test("REGRESSION #1073 — prompt używa 'Krytyczny sukces'/'Krytyczna porażka' (kolejność UI)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/prompts/system_prompt", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "pobranie system_prompt musi zwrócić 200 (#1073)").toBeTruthy();
  const body = await r.json();
  const text = body.content || body.text || JSON.stringify(body);
  expect(text.includes("Krytyczny sukces"), "brak 'Krytyczny sukces' w prompcie (#1073)").toBeTruthy();
  expect(text.includes("Krytyczna porażka"), "brak 'Krytyczna porażka' w prompcie (#1073)").toBeTruthy();
  expect(text.includes("Sukces krytyczny"), "stara odwrócona kolejność 'Sukces krytyczny' wciąż w prompcie (#1073)").toBeFalsy();
  expect(text.includes("Porażka krytyczna"), "stara odwrócona kolejność 'Porażka krytyczna' wciąż w prompcie (#1073)").toBeFalsy();
});

test("REGRESSION #1073 — terminy mechaniczne Nat 20/Nat 1 (logika) nietknięte", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/prompts/system_prompt", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const text = body.content || body.text || JSON.stringify(body);
  expect(text.includes("Nat 20 = automatyczny sukces"), "reguła Nat 20 (logika) zniknęła (#1073)").toBeTruthy();
  expect(text.includes("Nat 1 = automatyczna porażka"), "reguła Nat 1 (logika) zniknęła (#1073)").toBeTruthy();
});
