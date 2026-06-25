/**
 * REGRESSION #989 — dialogi NPC po polsku: myślnik od nowej linii, nie cudzysłów inline.
 * Acceptance: kwestia NPC z cudzysłowu wplecionego w narrację renderuje się jako
 * osobny akapit dialogu zaczynający się od "— ", a cytat z listu/pergaminu zachowuje cudzysłowy.
 */
const { test, expect } = require("@playwright/test");

// Renderer formatGmNarrative + splitInlineDialogue są globalne (klasyczny <script>),
// więc wołamy je w kontekście strony po załadowaniu UI gracza.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.formatGmNarrative === "function", { timeout: 15000 });
});

test("REGRESSION #989 — kwestia NPC w cudzysłowie → akapit dialogu od myślnika", async ({ page }) => {
  const input =
    'Podchodzisz do żołnierza. "Nie wiem, jak się nazywał ten, co padł" mówi nisko, zachrypniętym głosem.';
  const html = await page.evaluate((t) => window.formatGmNarrative(t), input);

  // dialog stał się osobnym akapitem mowy
  expect(html, "brak akapitu dialogu gm-p--speech (#989)").toContain("gm-p--speech");
  // kwestia zaczyna się od myślnika, bez cudzysłowów wokół niej
  expect(html).toContain("— Nie wiem, jak się nazywał ten, co padł");
  // żaden prosty cudzysłów nie otacza już mówionej kwestii
  expect(html).not.toContain('"Nie wiem');
});

test("REGRESSION #989 — polski cudzysłów „…” mówiony → też myślnik", async ({ page }) => {
  const html = await page.evaluate((t) => window.formatGmNarrative(t), "„Witaj w Kresach” mówi starzec.");
  expect(html).toContain("gm-p--speech");
  expect(html).toContain("— Witaj w Kresach");
});

test("REGRESSION #989 — cytat z pergaminu (bez czasownika mówienia) zachowuje cudzysłów", async ({ page }) => {
  const input = 'Na pergaminie czytasz: "Strzeż się wilków z północy." Litery są wyblakłe.';
  const html = await page.evaluate((t) => window.formatGmNarrative(t), input);
  // nie zamieniamy cytatu pisanego na myślnik — treść listu zostaje w cudzysłowie
  expect(html, "cytat z pergaminu nie powinien stać się linią dialogu (#989)").not.toContain("gm-p--speech");
  expect(html).toContain("Strzeż się wilków");
});
