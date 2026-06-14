/**
 * REGRESSION #547 (G20) — eksport kampanii do powieści (Bielik/Ollama na .170).
 *
 * G20 to narzędzie OFFLINE/CLI bez UI gracza (UI dopiero w FAZIE G), więc pełny
 * przebieg generacji weryfikuje pytest + ręczny pilot oceniany przez Piotra.
 * Tutaj sprawdzamy web-obserwowalny KONTRAKT DANYCH, na którym stoi eksporter:
 * endpoint historii kampanii zwraca tury z polami user_text/assistant_text —
 * czyli materiał źródłowy dla nowelizacji istnieje i ma właściwy kształt.
 *
 * Acceptance: GET /api/admin/campaigns/61/turns zwraca >=8 tur z tekstem MG.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  if (!r.ok()) return null;
  const b = await r.json();
  return b.token || b.access_token || null;
}

test("REGRESSION #547 — materiał źródłowy eksportu (tury kampanii) dostępny", async ({ page }) => {
  const token = await adminToken(page);
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const r = await page.request.get("/api/admin/campaigns/61/turns?limit=50", { headers });
  expect(r.ok(), "endpoint historii kampanii nie odpowiada 200 (#547)").toBeTruthy();

  const body = await r.json();
  const turns = body.items || body.turns || (Array.isArray(body) ? body : []);
  expect(turns.length, "kampania 61 ma za mało tur na nowelizację (#547)").toBeGreaterThanOrEqual(8);

  // materiał źródłowy: co najmniej jedna tura ma tekst Mistrza Gry (proza wejściowa)
  const hasGmText = turns.some((t) => (t.assistant_text || "").trim().length > 0);
  expect(hasGmText, "brak tekstu MG — eksporter nie miałby z czego pisać (#547)").toBeTruthy();
});
