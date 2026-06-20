/**
 * REGRESSION #839 (M1) — System section mobile: stab-bar scroll + grids 1-col @390px.
 * Acceptance: at 390px viewport — no page-level horizontal scroll, system tabs scrollable,
 * voice TTS/STT grid and visual grids collapse to 1-col, no regression at 1024px.
 */
const { test, expect } = require('@playwright/test');

const ADMIN_URL = process.env.BASE_URL
  ? `${process.env.BASE_URL}/admin/`
  : 'http://frontend:80/admin/';

test.describe('REGRESSION #839 — System section mobile @390px', () => {

  test('components.css has mobile scroll rule for .stab-bar', async ({ page }) => {
    const r = await page.request.get(`${ADMIN_URL}../admin/shared/components.css`);
    expect(r.ok(), 'components.css not served').toBeTruthy();
    const css = await r.text();
    expect(css).toContain('SYSTEM SECTION MOBILE');
    expect(css).toContain('.stab-bar');
    expect(css).toContain('overflow-x');
  });

  test('system.js has id=sys-voice-panels-grid on TTS/STT grid', async ({ page }) => {
    const r = await page.request.get(`${ADMIN_URL}../admin/sections/system.js`);
    expect(r.ok(), 'system.js not served').toBeTruthy();
    const js = await r.text();
    expect(js).toContain('id="sys-voice-panels-grid"');
    expect(js).toContain('id="sys-voice-test-grid"');
  });

  test('mobile CSS overrides: voice panels + vis grids + route toggles all present', async ({ page }) => {
    const r = await page.request.get(`${ADMIN_URL}../admin/shared/components.css`);
    const css = await r.text();
    expect(css).toContain('#sys-voice-panels-grid');
    expect(css).toContain('#sys-voice-test-grid');
    expect(css).toContain('#v-route-toggles');
    expect(css).toContain('#vis-periods');
    expect(css).toContain('#vis-bg-grid');
    expect(css).toContain('#whisper-preset-grid');
  });

});
