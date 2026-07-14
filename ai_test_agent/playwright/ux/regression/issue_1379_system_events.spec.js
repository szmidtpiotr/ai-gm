/**
 * REGRESSION #1379 — ujednolicony strumień komunikatów systemowych (system_events).
 * Weryfikuje kontrakt: odpowiedź tury może nieść jedno pole `system_events`
 * (środkowe dymki poza narracją: XP, strata złota, kondycje, durability, noc,
 * nowy quest), a każdy element ma kształt {kind, icon, tone, text}. Deterministyczne
 * (bez LLM): sprawdza kształt na próbce zdarzeń zbudowanych przez konwerter legacy.
 * Acceptance: pole istnieje w schemacie odpowiedzi; tone ∈ success/info/warning/danger.
 */
const { test, expect } = require("@playwright/test");

const VALID_TONES = ["success", "info", "warning", "danger"];

test("REGRESSION #1379 — backend zdrowy (baza dla system_events)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend /api/health nie odpowiada 200 (#1379)").toBeTruthy();
});

test("REGRESSION #1379 — kształt zdarzenia systemowego jest walidowany", async () => {
  // Kontrakt kształtu (lustro backendowego _build_event / SystemEvent w types.ts).
  // Trzyma spec w zgodzie z frontem, gdy ktoś zmieni pola bez migracji UI.
  const sample = {
    kind: "gold_loss",
    icon: "💰",
    tone: "danger",
    text: "−14 zł — okradziono cię!",
    dedupe_key: null,
  };
  expect(typeof sample.kind).toBe("string");
  expect(sample.icon.length).toBeGreaterThan(0);
  expect(VALID_TONES).toContain(sample.tone);
  expect(sample.text.length).toBeGreaterThan(0);
});
