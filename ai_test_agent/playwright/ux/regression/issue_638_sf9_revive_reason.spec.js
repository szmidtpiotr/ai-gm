/**
 * REGRESSION #638 (SF9 cz.2) — różnicowany komunikat wskrzeszenia po preview.reason.
 * Acceptance:
 *  - window.sf9DisabledReason({reason:'resurrection_disabled'}) → „Wskrzeszenia wyłączone przez Mistrza Gry."
 *  - window.sf9DisabledReason({reason:'no_uses_remaining'})    → „Brak pozostałych wskrzeszeń."
 *  - brak/inny/null powód → fallback „Wskrzeszenie nie jest dostępne dla tego konta."
 * Kontrakt JS (deterministyczny, bez LLM) — front CZYTA gotowy preview.reason z backendu, NIC nie liczy.
 * Część 3 (gating przycisku) poza zakresem — decyzja Piotra: przycisk zostaje ukryty przy !enabled.
 */
const { test, expect } = require("@playwright/test");

const DISABLED = "Wskrzeszenia wyłączone przez Mistrza Gry.";
const NO_USES = "Brak pozostałych wskrzeszeń.";
const FALLBACK = "Wskrzeszenie nie jest dostępne dla tego konta.";

// Front gracza ładuje app.js jako zwykły <script>; helper wystawiamy na window do testu kontraktu.
async function loadPlayerApp(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.sf9DisabledReason === "function", null, {
    timeout: 15000,
  });
}

test("REGRESSION #638 — sf9DisabledReason mapuje znane powody na polskie komunikaty", async ({ page }) => {
  await loadPlayerApp(page);

  const disabled = await page.evaluate(() => window.sf9DisabledReason({ enabled: false, reason: "resurrection_disabled" }));
  expect(disabled, "powód resurrection_disabled").toBe(DISABLED);

  const noUses = await page.evaluate(() => window.sf9DisabledReason({ enabled: false, reason: "no_uses_remaining" }));
  expect(noUses, "powód no_uses_remaining").toBe(NO_USES);
});

test("REGRESSION #638 — nieznany/brak powodu daje fallback (nie wybucha na null)", async ({ page }) => {
  await loadPlayerApp(page);

  const unknown = await page.evaluate(() => window.sf9DisabledReason({ enabled: false, reason: "coś_nowego" }));
  expect(unknown, "nieznany powód → fallback").toBe(FALLBACK);

  const noReason = await page.evaluate(() => window.sf9DisabledReason({ enabled: false }));
  expect(noReason, "brak pola reason → fallback").toBe(FALLBACK);

  const nullPreview = await page.evaluate(() => window.sf9DisabledReason(null));
  expect(nullPreview, "null preview → fallback (brak wyjątku)").toBe(FALLBACK);
});

test("REGRESSION #638 — app.js definiuje helper i wystawia go na window", async ({ page }) => {
  const src = await page.request.get("/js/app.js");
  expect(src.ok(), "app.js dostępny").toBeTruthy();
  const body = await src.text();
  expect(body.includes("function sf9DisabledReason"), "app.js definiuje sf9DisabledReason").toBeTruthy();
  expect(body.includes("window.sf9DisabledReason"), "helper wystawiony na window dla testu").toBeTruthy();
});
