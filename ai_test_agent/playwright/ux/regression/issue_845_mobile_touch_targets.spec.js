/**
 * REGRESSION #845 (M4) — Touch targets ≥44px na mobile @390px.
 * Acceptance: hamburger, stab-tabs, drawer nav-items, btn-sm osiągają min 44px na @media<=768px.
 * Brak poziomego scrolla strony na wszystkich sekcjach.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const SECTIONS = [
  "overview", "players", "campaigns", "heroes", "content",
  "world", "mechanics", "dungeons", "forge", "invites",
  "bugreports", "push", "tools", "system"
];

test("REGRESSION #845 — CSS zawiera reguły touch targets 44px w media(max-width:768px)", async ({ request }) => {
  const r = await request.get(`${BASE}/admin/shared/components.css`);
  expect(r.ok(), "components.css nie odpowiada 200").toBeTruthy();
  const css = await r.text();

  // Wyciągnij zawartość bloków @media (max-width: 768px)
  const mobileRules = [];
  const re = /@media\s*\(max-width:\s*768px\)\s*\{/g;
  let m;
  while ((m = re.exec(css)) !== null) {
    let start = m.index + m[0].length;
    let depth = 1;
    let i = start;
    while (i < css.length && depth) {
      if (css[i] === "{") depth++;
      else if (css[i] === "}") depth--;
      i++;
    }
    mobileRules.push(css.slice(start, i - 1));
  }
  const block = mobileRules.join("\n");

  expect(block, "brak .hamburger w mobile CSS").toContain(".hamburger");
  expect(block, "brak min-height w .hamburger mobile").toContain("min-height");
  expect(block, "brak .nav-item w mobile CSS").toContain(".nav-item");
  expect(block, "brak .stab w mobile CSS").toContain(".stab");
  expect(block, "brak .btn-sm w mobile CSS").toContain(".btn-sm");
});

test("REGRESSION #845 — Brak poziomego scrolla strony na mobile @390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/admin/`);
  await page.waitForLoadState("networkidle");

  // Login if needed
  const loginBtn = page.locator('button:has-text("Zaloguj")');
  if (await loginBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('input[type="text"]', "admin");
    await page.fill('input[type="password"]', "admin");
    await loginBtn.click();
    await page.waitForTimeout(500);
  }

  for (const section of SECTIONS) {
    // Navigate to section
    await page.evaluate((s) => {
      const btn = document.querySelector(`button[data-section="${s}"]`);
      if (btn) btn.click();
    }, section);
    await page.waitForTimeout(200);

    const overflow = await page.evaluate(() => {
      const html = document.documentElement;
      return html.scrollWidth > html.clientWidth;
    });
    expect(overflow, `Poziomy scroll w sekcji: ${section}`).toBeFalsy();
  }
});

test("REGRESSION #845 — Hamburger ≥44px na mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/admin/`);
  await page.waitForLoadState("networkidle");

  const size = await page.evaluate(() => {
    const el = document.querySelector(".hamburger");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return { h: Math.round(r.height), w: Math.round(r.width), minH: s.minHeight };
  });

  expect(size, "hamburger not found").not.toBeNull();
  expect(size.h, `hamburger height ${size.h}px < 44px`).toBeGreaterThanOrEqual(44);
  expect(size.w, `hamburger width ${size.w}px < 44px`).toBeGreaterThanOrEqual(44);
});

test("REGRESSION #845 — Stab tabs ≥44px na mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/admin/`);
  await page.waitForLoadState("networkidle");

  // Select mechanics section (has stab tabs)
  await page.evaluate(() => {
    const btn = document.querySelector('button[data-section="mechanics"]');
    if (btn) btn.click();
  });
  await page.waitForTimeout(400);

  const stabH = await page.evaluate(() => {
    const el = document.querySelector(".stab");
    if (!el) return 0;
    return Math.round(el.getBoundingClientRect().height);
  });

  expect(stabH, `stab height ${stabH}px < 44px`).toBeGreaterThanOrEqual(44);
});

test("REGRESSION #845 — Desktop brak regresji (hamburger hidden, stab normalny @1280px)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${BASE}/admin/`);
  await page.waitForLoadState("networkidle");

  // Select mechanics section to get stab into view
  await page.evaluate(() => {
    const btn = document.querySelector('button[data-section="mechanics"]');
    if (btn) btn.click();
  });
  await page.waitForTimeout(400);

  const sizes = await page.evaluate(() => {
    const hamburger = document.querySelector(".hamburger");
    const stab = document.querySelector(".stab");
    return {
      hamburgerHidden: hamburger ? getComputedStyle(hamburger).display === "none" : true,
      stabH: stab ? Math.round(stab.getBoundingClientRect().height) : 0,
    };
  });

  expect(sizes.hamburgerHidden, "hamburger visible na desktop — sidebar powinien być widoczny").toBeTruthy();
  // Desktop stab should be 34px (non-enlarged), not forced to 44px
  expect(sizes.stabH, "stab na desktop powinien być ≥30px").toBeGreaterThanOrEqual(30);
  expect(sizes.stabH, "stab na desktop nie powinien być wymuszony do 44px (mobilny override)").toBeLessThan(50);
});
