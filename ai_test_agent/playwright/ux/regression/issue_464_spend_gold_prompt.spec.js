/**
 * REGRESSION #464 (F4) — system prompt instruuje LLM o tagu [SPEND_GOLD:key].
 * Acceptance: GET /api/admin/prompts/system_prompt zawiera sekcję SPEND_GOLD
 * oraz klucze usług, dzięki czemu LLM emituje tag i silnik odejmuje złoto z bazy.
 */
const { test, expect } = require("@playwright/test");

const SERVICE_KEYS = [
  "inn_night", "inn_night_fine", "healer_light", "healer_heavy",
  "stable_night", "blacksmith_repair", "messenger", "guide_day",
];

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login musi zwrócić 200 (#464)").toBeTruthy();
  const body = await r.json();
  expect(body.token, "dev-login musi zwrócić token (#464)").toBeTruthy();
  return body.token;
}

test("REGRESSION #464 — system prompt dokumentuje tag SPEND_GOLD", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/prompts/system_prompt", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "pobranie system_prompt musi zwrócić 200 (#464)").toBeTruthy();
  const body = await r.json();
  const text = body.content || body.text || JSON.stringify(body);
  expect(text.includes("[SPEND_GOLD:"), "prompt musi opisać format tagu [SPEND_GOLD:] (#464)").toBeTruthy();
  expect(text.includes("## SPEND_GOLD"), "prompt musi mieć sekcję ## SPEND_GOLD (#464)").toBeTruthy();
});

test("REGRESSION #464 — prompt wymienia klucze usług (LLM nie zmyśla kwoty)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/prompts/system_prompt", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const text = body.content || body.text || JSON.stringify(body);
  const missing = SERVICE_KEYS.filter((k) => !text.includes(k));
  expect(missing, `klucze usług nieobecne w prompcie: ${missing.join(", ")} (#464)`).toEqual([]);
});
