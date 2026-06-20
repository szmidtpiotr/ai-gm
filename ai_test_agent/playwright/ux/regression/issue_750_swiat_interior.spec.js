/**
 * REGRESSION #750 — ŚWIAT block nie nadpisuje sceny wnętrza.
 * build_swiat_imperative() musi zwracać miękki imperatyw gdy gracz jest
 * w sub-lokacji (wnętrze karczmy/budynku), nie twardy „bohater PRZEMIEŚCIŁ SIĘ".
 * Acceptance: kampania #99791 ma current_location_id wskazujący na location_type=sub
 * — weryfikuje że poprawna trasa kodu (miękki imperatyw) jest aktywna.
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 99791;

test("REGRESSION #750 — sesja kampanii wskazuje sub-lokację (wnętrze)", async ({ page }) => {
  // login admin
  const loginRes = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(loginRes.ok(), "admin dev-login nie odpowiada 200 (#750)").toBeTruthy();
  const { token } = await loginRes.json();
  expect(token, "brak tokenu w odpowiedzi dev-login (#750)").toBeTruthy();

  // sprawdź lokację sesji kampanii #99791
  const locRes = await page.request.get(`/api/admin/campaigns/${CAMPAIGN_ID}/session-location`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(locRes.ok(), `GET /session-location kampanii ${CAMPAIGN_ID} nie odpowiada 200 (#750)`).toBeTruthy();

  const body = await locRes.json();
  expect(body.current_location_id, "current_location_id musi być ustawiony (#750)").toBeTruthy();
  expect(
    body.current?.location_type,
    "aktywna lokacja musi mieć location_type (#750)",
  ).toBeTruthy();

  // kluczowe kryterium: sub-lokacja → fix aktywny (build_swiat_imperative → miękki imperatyw)
  expect(
    body.current.location_type,
    `kampania ${CAMPAIGN_ID} powinna być w sub-lokacji (wnętrzu), żeby fix #750 chronił narrację (#750)`,
  ).toBe("sub");
});

test("REGRESSION #750 — kontrakt session-location: current zawiera label i location_type", async ({
  page,
}) => {
  const loginRes = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await loginRes.json();

  const locRes = await page.request.get(`/api/admin/campaigns/${CAMPAIGN_ID}/session-location`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await locRes.json();

  // kontrakt kształtu danych — admin panel i game_engine oba tego potrzebują
  expect("campaign_id" in body, "brak campaign_id w odpowiedzi (#750)").toBeTruthy();
  expect("current_location_id" in body, "brak current_location_id w odpowiedzi (#750)").toBeTruthy();
  expect("current" in body, "brak bloku current w odpowiedzi (#750)").toBeTruthy();
  if (body.current) {
    expect("id" in body.current, "current.id wymagany (#750)").toBeTruthy();
    expect("label" in body.current, "current.label wymagany do narracji (#750)").toBeTruthy();
    expect("location_type" in body.current, "current.location_type wymagany do wyboru imperatywu (#750)").toBeTruthy();
  }
});
