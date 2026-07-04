/**
 * REGRESSION #1186 + #1171 — jedna spójna ochrona podwójnej tury.
 * #1171 (klient): game.js ma flagę in-flight `_turnInFlight`, która blokuje sendTurn ORAZ
 *   ścieżkę Enter (handleSendMessage) do końca streamu; watchdog `_resetInputState` nie
 *   re-enable przycisku w trakcie żywego streamu.
 * #1186 (backend): serwerowy turn-lock — weryfikowany rygorystycznie w pytest
 *   (backend/tests/test_issue1186_turn_lock.py: 2 równoległe acquire → 1 wygrywa, 1 busy→409).
 *   Python nie jest serwowany przez nginx, więc tu sprawdzamy kontrakt źródła klienta + cache-bust.
 *
 * Acceptance: served game.js zawiera guard, index.html ma zbumpowany ?v (świeży moduł u gracza).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1171 — in-flight guard blokuje sendTurn + Enter + watchdog", async ({ page }) => {
  const r = await page.request.get("/js/screens/game.js?probe=1171");
  expect(r.ok(), "game.js nie serwuje się (200)").toBeTruthy();
  const src = await r.text();

  // Flaga in-flight istnieje na poziomie modułu.
  expect(src, "brak flagi _turnInFlight (#1171)").toMatch(/let\s+_turnInFlight\s*=\s*false/);

  // sendTurn odrzuca drugą turę gdy _turnInFlight i sam ją ustawia.
  const st = src.indexOf("async function sendTurn");
  expect(st, "brak sendTurn").toBeGreaterThan(-1);
  const stHead = src.slice(st, st + 800);
  expect(stHead, "sendTurn nie sprawdza _turnInFlight (#1171)").toMatch(/if\s*\(_turnInFlight\)\s*return/);
  expect(stHead, "sendTurn nie ustawia _turnInFlight = true").toMatch(/_turnInFlight\s*=\s*true/);

  // Ścieżka Enter (handleSendMessage) też blokowana.
  const hs = src.indexOf("async function handleSendMessage");
  expect(hs, "brak handleSendMessage").toBeGreaterThan(-1);
  const hsHead = src.slice(hs, hs + 400);
  expect(hsHead, "handleSendMessage (Enter) nie sprawdza _turnInFlight (#1171)").toMatch(/if\s*\(_turnInFlight\)\s*return/);

  // Watchdog nie może re-enable w trakcie żywego streamu.
  const ris = src.indexOf("function _resetInputState");
  expect(ris, "brak _resetInputState").toBeGreaterThan(-1);
  const risHead = src.slice(ris, ris + 400);
  expect(risHead, "_resetInputState re-enable w trakcie streamu (#1171)").toMatch(/if\s*\(_turnInFlight\)\s*return/);
});

test("REGRESSION #1186 — cache-bust game.js zbumpowany (świeży guard u gracza)", async ({ page }) => {
  const r = await page.request.get("/index.html");
  expect(r.ok(), "index.html nie serwuje się (200)").toBeTruthy();
  const html = await r.text();
  const m = html.match(/screens\/game\.js\?v=([^"']+)/);
  expect(m, "brak importu game.js z ?v w index.html").toBeTruthy();
  expect(m[1], "?v nie zbumpowany po fixie #1186/#1171").toContain("1186");
});
