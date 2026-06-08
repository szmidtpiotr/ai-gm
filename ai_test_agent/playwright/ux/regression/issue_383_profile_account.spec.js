/**
 * REGRESSION #383 (D8) — Ekran profilu: konto (email edit) + znajomi + LLM.
 * Backend: PATCH /me/profile obsługuje teraz email (walidacja + unikalność, gated).
 * LLM: /users/{id}/llm-settings. Logika edycji email w pytest test_issue383_*.
 * Acceptance (deterministyczny): profil-edit jest auth-gated (401 bez tokena),
 * a ustawienia LLM odpowiadają poprawnym kontraktem.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #383 — profil-edit gated + LLM settings kontrakt", async ({ page }) => {
  // Edycja konta wymaga auth (email/username) — bez tokena 401.
  const noauth = await page.request.patch("/api/me/profile", { data: { email: "x@x.pl" } });
  expect(noauth.status(), "PATCH /me/profile bez auth musi dać 401 (#383)").toBe(401);

  // LLM settings — kontrakt (no-auth per-user)
  const llm = await page.request.get("/api/users/1/llm-settings");
  expect(llm.ok(), "GET llm-settings nie 200 (#383)").toBeTruthy();
  const s = await llm.json();
  expect("mode" in s, "llm-settings musi mieć pole mode (#383)").toBeTruthy();
  // api_key NIE może wyciekać w maskowanym widoku
  expect(s.api_key === undefined || s.api_key === null || s.api_key === "",
    "llm-settings nie może ujawniać api_key (#383)").toBeTruthy();
});
