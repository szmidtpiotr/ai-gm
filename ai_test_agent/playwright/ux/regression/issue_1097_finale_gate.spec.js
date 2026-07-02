/**
 * REGRESSION #1097 — soft finale gate: player-triggered campaign completion.
 *
 * #1097 replaces #1009's auto-flip (all acts + 0 main quests → instant
 * status='completed') with a sticky `finale_available` flag; the player pulls
 * the actual completion via POST /campaigns/{id}/finish. A full live-LLM
 * playthrough to the gate-open state is non-deterministic (dozens of turns) —
 * that end-to-end path belongs to /game-smoke-pw, not this spec. This spec
 * deterministically pins the two API contracts #1097 adds/changes:
 *   1. GET /campaigns/{id} always exposes `finale_available` (bool).
 *   2. POST /finish on a campaign whose gate is NOT open (or caller isn't the
 *      host) is always REJECTED (409 finale_not_available / 403 not_host) and
 *      never flips status to 'completed'.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1097 — GET /campaigns/{id} exposes finale_available", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1");
  if (r.status() === 404) {
    console.log("Campaign 1 not in this environment — skipping");
    return;
  }
  expect(r.ok(), `campaign fetch nie odpowiada 200 (#1097): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(
    typeof body.finale_available === "boolean",
    `finale_available musi być boolean w GET /campaigns/{id} (#1097): got ${JSON.stringify(body.finale_available)}`
  ).toBeTruthy();
});

test("REGRESSION #1097 — POST /finish rejected when gate not open, status untouched", async ({ page }) => {
  const before = await page.request.get("/api/campaigns/1");
  if (before.status() === 404) {
    console.log("Campaign 1 not in this environment — skipping");
    return;
  }
  const beforeBody = await before.json();
  if (beforeBody.finale_available && beforeBody.status !== "completed") {
    console.log("Campaign 1 already has finale_available=true — skipping blocked-path assertion");
    return;
  }
  if (beforeBody.status === "completed" || beforeBody.status === "ended") {
    console.log("Campaign 1 already terminal — skipping blocked-path assertion");
    return;
  }

  // user_id=1 (Demo) legacy query fallback — endpoint requires an authed caller
  // (host-guard). Either 409 (gate closed) or 403 (not host) proves the guard
  // holds; what matters is status never silently flips.
  const r = await page.request.post("/api/campaigns/1/finish?user_id=1");
  expect([403, 409], `finish musi być odrzucony gdy bramka zamknięta (#1097): got ${r.status()}`).toContain(r.status());
  const body = await r.json().catch(() => ({}));
  expect(["finale_not_available", "not_host"], "#1097: detail musi być finale_not_available lub not_host")
    .toContain(body.detail);

  const after = await page.request.get("/api/campaigns/1");
  const afterBody = await after.json();
  expect(afterBody.status, "#1097: status nie może się zmienić przy zablokowanym /finish").not.toBe("completed");
});
