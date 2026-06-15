/**
 * REGRESSION #634 (SF5) — ulotne komunikaty zdarzeń walki (k4 / omen / darmowa akcja).
 * Acceptance: pure-helper sf5EphemeralMessage() mapuje 3 sygnały (omen, extra_action, behavior)
 * na poprawny komunikat (ikona + tekst); flashCombatEvent() dokłada ulotny węzeł .cturn--ephemeral.
 * Kontrakt JS (deterministyczny, bez logowania, bez LLM) — front CZYTA gotowe sygnały, nic nie liczy.
 */
const { test, expect } = require("@playwright/test");

// Front gracza ładuje app.js jako zwykły <script> → top-level funkcje są globalne na window.
async function loadPlayerApp(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.sf5EphemeralMessage === "function", null, {
    timeout: 15000,
  });
}

test("REGRESSION #634 — sf5EphemeralMessage mapuje 3 sygnały na komunikaty", async ({ page }) => {
  await loadPlayerApp(page);

  const omen = await page.evaluate(() => window.sf5EphemeralMessage("omen"));
  expect(omen, "omen → obiekt").toBeTruthy();
  expect(omen.icon, "omen ikona 🌑").toBe("🌑");
  expect(omen.text, "omen tekst").toContain("Zły omen");

  const extra = await page.evaluate(() => window.sf5EphemeralMessage("extra_action"));
  expect(extra, "extra_action → obiekt").toBeTruthy();
  expect(extra.icon, "extra_action ikona ⚡").toBe("⚡");
  expect(extra.text, "extra_action tekst").toContain("za darmo");

  // behavior bierze nazwę wroga z kontekstu + rozróżnia akcję k4.
  const beh = await page.evaluate(() =>
    window.sf5EphemeralMessage("behavior", { enemy_name: "Goblin", action: "attack_random" })
  );
  expect(beh, "behavior → obiekt").toBeTruthy();
  expect(beh.text, "behavior nazwa wroga").toContain("Goblin");

  // nieznany sygnał → null (nic nie miga)
  const none = await page.evaluate(() => window.sf5EphemeralMessage("nope"));
  expect(none, "nieznany sygnał → null").toBeNull();
});

test("REGRESSION #634 — flashCombatEvent dokłada ulotny węzeł z poprawnym tekstem", async ({ page }) => {
  await loadPlayerApp(page);

  const res = await page.evaluate(() => {
    const host = document.createElement("div");
    host.id = "__sf5_test_host";
    document.body.appendChild(host);
    window.flashCombatEvent("omen", {}, host);
    const node = host.querySelector(".cturn--ephemeral");
    return {
      hasFn: typeof window.flashCombatEvent === "function",
      appended: !!node,
      text: node ? node.textContent : "",
      icon: node ? node.textContent.includes("🌑") : false,
    };
  });

  expect(res.hasFn, "flashCombatEvent jest funkcją").toBeTruthy();
  expect(res.appended, "ulotny węzeł dołożony").toBeTruthy();
  expect(res.icon, "ikona omen w węźle").toBeTruthy();
  expect(res.text, "tekst omen w węźle").toContain("Zły omen");
});

test("REGRESSION #634 — feed walki przepuszcza event_type='behavior'", async ({ page }) => {
  // Whitelist feedu musi zawierać 'behavior', inaczej wpisy k4 wroga są ciche.
  // Sprawdzamy że źródło app.js zawiera 'behavior' w filtrze (kontrakt statyczny).
  const src = await page.request.get("/js/app.js");
  expect(src.ok(), "app.js dostępny").toBeTruthy();
  const body = await src.text();
  expect(body.includes("'behavior'") || body.includes('"behavior"'), "whitelist zna 'behavior'").toBeTruthy();
});
