/**
 * REGRESSION #957 — D-pad lochu: tap kierunku/⊕ musi reagować.
 * Przyczyna: setPointerCapture na kontenerze .dungeon-nav__dirs w pointerdown tłumił
 * click przycisków-dzieci. Fix: capture dopiero po przekroczeniu progu dragu (w onMove).
 * Acceptance (deterministyczny): w serwowanym app.js setPointerCapture jest gated za
 * _DPAD_DRAG_THRESHOLD i nie ma go w nagłówku pointerdown; przyciski są dziećmi kontenera.
 */
const { test, expect } = require("@playwright/test");

function extractInitDpadDrag(src) {
  const start = src.indexOf("function initDpadDrag()");
  const nxt = src.indexOf("\nfunction ", start + 1);
  return src.slice(start, nxt === -1 ? src.length : nxt);
}

test("REGRESSION #957 — setPointerCapture gated za progiem dragu (nie przy tapie)", async ({ page }) => {
  const resp = await page.request.get("/front/js/app.js");
  expect(resp.ok(), "app.js musi się serwować (#957)").toBeTruthy();
  const body = extractInitDpadDrag(await resp.text());

  const cap = body.indexOf("setPointerCapture");
  const thr = body.indexOf("_DPAD_DRAG_THRESHOLD");
  expect(cap, "setPointerCapture musi istnieć (przeciąganie D-pada)").toBeGreaterThan(-1);
  expect(thr, "_DPAD_DRAG_THRESHOLD musi istnieć").toBeGreaterThan(-1);
  expect(cap, "setPointerCapture musi być PO progu dragu, nie przy tapie (#957)").toBeGreaterThan(thr);

  // Nagłówek pointerdown (do onMove) nie może chwytać wskaźnika.
  const pd = body.indexOf("addEventListener('pointerdown'");
  const onmove = body.indexOf("onMove", pd);
  const head = body.slice(pd, onmove);
  expect(head.includes("setPointerCapture"), "pointerdown nie może chwytać wskaźnika przy tapie (#957)").toBeFalsy();
});

test("REGRESSION #957 — przyciski kierunków i ⊕ są dziećmi .dungeon-nav__dirs", async ({ page }) => {
  const resp = await page.request.get("/front/index.html");
  const html = await resp.text();
  // Kontener i przyciski istnieją w DOM (capture na kontenerze obejmowałby je wszystkie).
  expect(html, ".dungeon-nav__dirs musi istnieć").toContain("dungeon-nav__dirs");
  expect(html, "środkowy ⊕ #dungeon-nav-center musi istnieć").toContain('id="dungeon-nav-center"');
  expect(html, "przyciski kierunków [data-dungeon-dir] muszą istnieć").toContain("data-dungeon-dir");
});
