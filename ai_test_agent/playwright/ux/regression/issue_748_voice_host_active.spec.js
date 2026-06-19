/**
 * REGRESSION #748 ([SETUP]) — Whisper/.16 podłączony do gry.
 * Acceptance: proxy /voice/healthz dociera do aktywnego hosta (status ok, stt+tts loaded),
 * a /voice/config odpowiada 200 (tabela voice_config istnieje — zapis ustawień głosu nie wykrasza).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #748 — /voice/healthz dociera do aktywnego hosta", async ({ page }) => {
  const r = await page.request.get("/voice/healthz");
  expect(r.ok(), "/voice/healthz nie zwraca 200 — brak aktywnego hosta? (#748)").toBeTruthy();
  const body = await r.json();
  // Gdyby host był nieaktywny, proxy fallbackowałby na nieistniejący voice-service:8300
  // → 502 'voice host unreachable'. Status ok = realny host (np. .16) odpowiada.
  expect(body.status, "host głosu nie raportuje status=ok (#748)").toBe("ok");
  expect(body.stt_loaded, "STT (Whisper) nie załadowany na aktywnym hoście (#748)").toBeTruthy();
});

test("REGRESSION #748 — /voice/config 200 (tabela voice_config istnieje)", async ({ page }) => {
  const r = await page.request.get("/voice/config");
  expect(r.ok(), "/voice/config nie zwraca 200 (#748)").toBeTruthy();
  const post = await page.request.post("/voice/config", {
    data: { tts_speed: 1.0 },
    headers: { "Content-Type": "application/json" },
  });
  expect(post.ok(), "zapis /voice/config wykrasza — brak tabeli voice_config? (#748)").toBeTruthy();
});
