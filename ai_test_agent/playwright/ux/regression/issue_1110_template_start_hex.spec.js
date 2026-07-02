/**
 * REGRESSION #1110 — start_hex szablonu (Kuźnia) wyznacza start kampanii.
 * Placement end-to-end (resolve_starting_hex) pokryty pytestem (ciężka ścieżka LLM).
 * Ten spec pilnuje kontraktu danych, na którym stoi fix: szablon niesie start_hex,
 * a hex-availability oznacza go jako is_current (marker startu na mapie pickera).
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  return token;
}

test("REGRESSION #1110 — szablon z start_hex oznacza go jako is_current w hex-availability", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const tplResp = await page.request.get("/api/admin/forge/templates", { headers: auth });
  expect(tplResp.ok()).toBeTruthy();
  const templates = (await tplResp.json()).items || [];
  const withHex = templates.filter((t) => t.start_hex_q != null && t.start_hex_r != null);
  test.skip(!withHex.length, "brak szablonu z przypisanym start_hex");

  const t = withHex[0];
  const av = await page.request.get(`/api/admin/forge/templates/${t.id}/hex-availability`, { headers: auth });
  expect(av.ok()).toBeTruthy();
  const hexes = (await av.json()).hexes || [];

  const current = hexes.find((h) => h.is_current);
  expect(current, `brak hexa is_current dla szablonu ${t.id}`).toBeTruthy();
  expect(current.q, "is_current.q != start_hex_q").toBe(t.start_hex_q);
  expect(current.r, "is_current.r != start_hex_r").toBe(t.start_hex_r);
});
