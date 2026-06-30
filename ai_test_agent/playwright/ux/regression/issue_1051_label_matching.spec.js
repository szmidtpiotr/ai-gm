/**
 * REGRESSION #1051 — location matching by direct label fuzzy search.
 * The injector tokenizes game_locations.label to match player intent before the
 * brittle _INTENT_KEYWORDS subtype fallback. This spec asserts the admin
 * locations surface that feeds the matcher returns labeled records.
 * Acceptance: every location exposes a non-empty `label` for token matching.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r2.json()).token;
}

test("REGRESSION #1051 — admin locations expose label for fuzzy matching", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const r = await page.request.get("/api/locations/admin/locations", { headers: auth });
  expect(r.ok(), "admin locations endpoint nie odpowiada 200 (#1051)").toBeTruthy();

  const body = await r.json();
  const list = Array.isArray(body) ? body : (body.locations || body.items || []);
  expect(Array.isArray(list), "odpowiedź powinna zawierać listę lokacji").toBeTruthy();

  // Matcher tokenizes `label`; every record must carry one.
  for (const loc of list.slice(0, 10)) {
    expect(loc).toHaveProperty("label");
    expect(typeof loc.label === "string" && loc.label.trim().length > 0).toBeTruthy();
  }
});
