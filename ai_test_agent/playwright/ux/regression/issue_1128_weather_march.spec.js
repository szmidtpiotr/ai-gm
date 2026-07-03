/**
 * REGRESSION #1128 (PT15) — Pogoda wpływa na tempo marszu: mnożnik kosztu godzin marszu wg stanu pogody.
 * Acceptance: admin weather-config zwraca march_multipliers z wartościami startowymi
 * (clear/clouds ×1.0, rain/fog ×1.25, storm/snow ×1.5, heat ×1.25) — surface, na którym
 * fix wystawia mnożniki (docelowo Sandbox-tunable). Kontrakt API, deterministyczny, bez LLM.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1128 — weather-config exposes march_multipliers", async ({ page }) => {
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(loginResp.ok(), "admin login must succeed (#1128)").toBeTruthy();
  const loginBody = await loginResp.json();
  const token = loginBody.token || loginBody.access_token;
  expect(token, "login must return token (#1128)").toBeTruthy();

  const r = await page.request.get("/api/admin/weather-config", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "weather-config must return 200 (#1128)").toBeTruthy();

  const body = await r.json();
  const cfg = body.config || body;
  const mm = cfg.march_multipliers;
  expect(mm, "config must expose march_multipliers (#1128)").toBeDefined();

  // Wartości startowe (Numbers Policy)
  expect(mm.clear, "clear ×1.0 (#1128)").toBe(1.0);
  expect(mm.clouds, "clouds ×1.0 (#1128)").toBe(1.0);
  expect(mm.rain, "rain ×1.25 (#1128)").toBe(1.25);
  expect(mm.fog, "fog ×1.25 (#1128)").toBe(1.25);
  expect(mm.storm, "storm ×1.5 (#1128)").toBe(1.5);
  expect(mm.snow, "snow ×1.5 (#1128)").toBe(1.5);
  expect(mm.heat, "heat ×1.25 (#1128)").toBe(1.25);
});
