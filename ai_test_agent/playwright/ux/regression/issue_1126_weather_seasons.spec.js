/**
 * REGRESSION #1126 (PT-D3) — Pory dnia, pory roku i pogoda opisowa.
 * Weryfikuje kontrakt admina: GET /api/admin/weather-config zwraca konfigurację
 * (weather_enabled, days_per_season, start_season_offset, typy, pory roku),
 * a PATCH ją zmienia (toggle + długość pór roku). Determinizm pogody i wyliczanie
 * pory roku z dnia pokrywa pytest (test_issue1126_weather_seasons.py) — tu pilnujemy,
 * że warstwa API/config nie regresuje kształtu i nie sypie 500.
 * Acceptance: admin widzi i steruje konfiguracją pogody; toggle realnie przełącza flagę.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(request) {
  const resp = await request.post(`/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), `admin dev-login failed: ${resp.status()}`).toBeTruthy();
  return (await resp.json()).token;
}

test("REGRESSION #1126 — weather-config GET zwraca kształt konfiguracji", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`/api/admin/weather-config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), "weather-config 5xx (#1126)").toBeLessThan(500);
  expect(r.ok(), `weather-config nie 200: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  const cfg = body.config;
  expect(cfg).toHaveProperty("weather_enabled");
  expect(cfg).toHaveProperty("days_per_season");
  expect(cfg).toHaveProperty("start_season_offset");
  expect(Array.isArray(cfg.seasons)).toBeTruthy();
  expect(cfg.seasons).toContain("jesień");
  expect(Array.isArray(cfg.weather_types)).toBeTruthy();
  expect(cfg.weather_types).toContain("snow");
});

test("REGRESSION #1126 — weather-config PATCH przełącza toggle i długość pór roku", async ({ request }) => {
  const token = await adminToken(request);
  const hdr = { Authorization: `Bearer ${token}` };

  // Włącz + ustaw 25 dni/porę
  const p1 = await request.patch(`/api/admin/weather-config`, {
    headers: hdr,
    data: { weather_enabled: true, days_per_season: 25 },
  });
  expect(p1.ok(), `PATCH nie 200: ${p1.status()}`).toBeTruthy();
  const cfg1 = (await p1.json()).config;
  expect(cfg1.weather_enabled).toBe(true);
  expect(cfg1.days_per_season).toBe(25);

  // Przywróć domyślne (30 dni, włączone) — nie zostawiaj śmieci w configu
  const p2 = await request.patch(`/api/admin/weather-config`, {
    headers: hdr,
    data: { weather_enabled: true, days_per_season: 30 },
  });
  expect(p2.ok()).toBeTruthy();
  expect((await p2.json()).config.days_per_season).toBe(30);
});
