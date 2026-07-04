/**
 * REGRESSION #1174 (SEC) — push.js escapuje username/display_name (XSS).
 * Acceptance: player-controlled username z <img onerror> / apostrofem renderuje się
 * jako TEKST — nie tworzy elementu, nie wykonuje kodu w kontekście admina.
 */
const { test, expect } = require("@playwright/test");

const XSS_USER = `<img src=x onerror="window.__xss=true">EVIL'});window.__xss2=true;//`;
const XSS_DISPLAY = `<b onmouseover="window.__xss3=true">disp</b>`;

test("REGRESSION #1174 — push subscriptions username escapowany", async ({ page }) => {
  // token do przejścia bramki logowania /admin/ (treść nieistotna — push API mockujemy)
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.status(), "dev-login nie zadziałał").toBe(200);
  const token = (await login.json()).token;

  // mock listy subskrypcji ze złośliwym username/display_name
  await page.route("**/api/admin/push/subscriptions", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        subscriptions: [
          {
            user_id: 4242,
            username: XSS_USER,
            display_name: XSS_DISPLAY,
            subscription_count: 2,
            last_subscribed_at: null,
          },
        ],
      }),
    })
  );

  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);

  await page.goto("/admin/#push");
  await page.waitForSelector("#push-tbody tr", { timeout: 15000 });

  // 1. onerror/onmouseover NIE odpalił się (payload nie stał się elementem)
  const xss = await page.evaluate(() => ({
    a: window.__xss, b: window.__xss2, c: window.__xss3,
  }));
  expect(xss.a, "innerHTML <img onerror> odpalił się").toBeFalsy();
  expect(xss.b, "onclick apostrof breakout odpalił się").toBeFalsy();
  expect(xss.c, "display_name <b onmouseover> odpalił się").toBeFalsy();

  // 2. Żaden wstrzyknięty <img>/<b onmouseover> nie powstał w wierszu
  const injected = await page.evaluate(
    () => document.querySelectorAll('#push-tbody img, #push-tbody b[onmouseover]').length
  );
  expect(injected, "payload utworzył realny element DOM").toBe(0);

  // 3. Username widoczny jako tekst (escapowany), nie jako znacznik
  const cellText = await page.textContent("#push-tbody td[data-label='Gracz']");
  expect(cellText).toContain("onerror");
});
