/**
 * REGRESSION #1118 (PT8) — koszty terenu z hex_type_config (A* z wagami).
 * Acceptance: travel_hours w API: droga=0.5, las=2.0, góry=3.0, bagno=4.0; woda is_passable=0.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1118)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1118)").toBeTruthy();
  return token;
}

test("REGRESSION #1118 — terrain config zwraca poprawne travel_hours po PT8 migracji", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/admin/world/hex-terrain-config", auth);
  expect(r.ok(), "endpoint hex-terrain-config nie odpowiada 200 (#1118)").toBeTruthy();

  const rows = await r.json();
  const byType = Object.fromEntries(rows.map(row => [row.hex_type, row]));

  expect(byType["road"]?.travel_hours, "droga powinna mieć 0.5h (#1118)").toBe(0.5);
  expect(byType["forest"]?.travel_hours, "las powinien mieć 2.0h (#1118)").toBe(2.0);
  expect(byType["hills"]?.travel_hours, "wzgórza powinny mieć 2.0h (#1118)").toBe(2.0);
  expect(byType["mountains"]?.travel_hours, "góry powinny mieć 3.0h (#1118)").toBe(3.0);
  expect(byType["swamp"]?.travel_hours, "bagno powinno mieć 4.0h (#1118)").toBe(4.0);
  expect(byType["plains"]?.travel_hours, "równina powinna mieć 1.0h (#1118)").toBe(1.0);
});

test("REGRESSION #1118 — woda i morze mają is_passable=0 (nieprzejezdne)", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/admin/world/hex-terrain-config", auth);
  expect(r.ok(), "endpoint hex-terrain-config nie odpowiada 200 (#1118)").toBeTruthy();

  const rows = await r.json();
  const waterRow = rows.find(row => row.hex_type === "water");
  const seaRow = rows.find(row => row.hex_type === "sea");

  if (waterRow) {
    expect(waterRow.is_passable, "water musi mieć is_passable=0 (#1118)").toBe(0);
  }
  if (seaRow) {
    expect(seaRow.is_passable, "sea musi mieć is_passable=0 (#1118)").toBe(0);
  }
});
