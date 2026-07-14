/**
 * REGRESSION #1378 - LLM error handling nie zwraca surowego body providera,
 * backend zostaje zdrowy po deployu klasyfikacji bledow.
 * Acceptance: /api/health OK po rebuildzie (llm_service.py/turns.py bez bledu skladni);
 * bledy 4xx z /turns zwracaja czysty JSON detail (string lub error_code/message),
 * nigdy surowy stack trace/HTML. Klasyfikacja budget_exhausted/timeout/provider_down/
 * config_error jest pokryta przez 13 testow pytest (test_issue1378_llm_error_classification.py) -
 * ten spec pilnuje tylko kontraktu widocznego z przegladarki/CI, nie mockuje providera.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1378 - backend health OK po deployu klasyfikacji bledow LLM", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend nie odpowiada po zmianach llm_service.py/turns.py (#1378)").toBeTruthy();
  const body = await r.json();
  expect(["ok", "degraded"]).toContain(body.status ?? "ok");
});

test("REGRESSION #1378 - blad /turns to czysty JSON, nie surowy stack trace", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/999999999/turns", {
    data: { character_id: 1, text: "test" },
  });
  expect(r.status(), "nieoczekiwany kod statusu").toBe(404);
  const body = await r.json();
  expect(body).toHaveProperty("detail");
  const detailText = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  expect(detailText.toLowerCase()).not.toContain("traceback");
  expect(detailText.toLowerCase()).not.toContain("<html");
});
