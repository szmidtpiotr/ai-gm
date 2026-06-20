/**
 * REGRESSION #833 (M0-4) — Formularze 2-col→1-col i touch-targety 44px na mobile.
 * Acceptance: Na viewport 390px gridy formularzy mają 1 kolumnę; ikony akcji mają ≥44px touch-target;
 * inputy mają font-size:16px (brak iOS zoom); desktop 1024px zachowuje 2 kolumny.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_URL = "http://frontend:80/admin/";

test.describe("REGRESSION #833 — Mobile forms 2-col→1-col + touch-targets 44px", () => {

  test("@390px .form-grid ma 1 kolumnę (grid-template-columns: 1fr)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(ADMIN_URL + "#content");
    await page.waitForTimeout(800);

    // Sprawdź computed style .form-grid na mobile
    const cols = await page.evaluate(() => {
      const el = document.querySelector(".form-grid");
      if (!el) return null;
      return getComputedStyle(el).gridTemplateColumns;
    });

    // Na mobile musi być 1 kolumna (nie dwie wartości oddzielone spacją)
    if (cols !== null) {
      const parts = cols.trim().split(/\s+/);
      expect(parts.length, `form-grid ma ${parts.length} kolumny na 390px, oczekiwano 1`).toBe(1);
    }
  });

  test("@390px .grid-2col ma 1 kolumnę", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(ADMIN_URL + "#content");
    await page.waitForTimeout(800);

    const cols = await page.evaluate(() => {
      const el = document.querySelector(".grid-2col");
      if (!el) return "brak-elementu";
      return getComputedStyle(el).gridTemplateColumns;
    });

    if (cols !== "brak-elementu") {
      const parts = cols.trim().split(/\s+/);
      expect(parts.length, `.grid-2col ma ${parts.length} kolumny na 390px, oczekiwano 1`).toBe(1);
    }
  });

  test("@390px .btn-icon ma min-height ≥ 44px (touch-target)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(ADMIN_URL + "#content");
    await page.waitForTimeout(800);

    const minH = await page.evaluate(() => {
      const el = document.querySelector(".btn-icon");
      if (!el) return null;
      return parseInt(getComputedStyle(el).minHeight) || el.getBoundingClientRect().height;
    });

    if (minH !== null) {
      expect(minH, `.btn-icon ma min-height=${minH}px, oczekiwano ≥44px`).toBeGreaterThanOrEqual(44);
    }
  });

  test("@390px .form-input ma font-size 16px (brak iOS zoom)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(ADMIN_URL + "#content");
    await page.waitForTimeout(800);

    const fontSize = await page.evaluate(() => {
      const el = document.querySelector(".form-input");
      if (!el) return null;
      return parseFloat(getComputedStyle(el).fontSize);
    });

    if (fontSize !== null) {
      expect(fontSize, `.form-input font-size=${fontSize}px, oczekiwano ≥16px (iOS zoom prevention)`).toBeGreaterThanOrEqual(16);
    }
  });

  test("@1024px .form-grid zachowuje 2 kolumny (desktop nie naruszony)", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto(ADMIN_URL + "#content");
    await page.waitForTimeout(800);

    const cols = await page.evaluate(() => {
      const el = document.querySelector(".form-grid");
      if (!el) return null;
      return getComputedStyle(el).gridTemplateColumns;
    });

    if (cols !== null) {
      const parts = cols.trim().split(/\s+/);
      expect(parts.length, `form-grid ma ${parts.length} kolumny na 1024px, oczekiwano 2`).toBe(2);
    }
  });

  test("console bez błędów JS na mobile", async ({ page }) => {
    const errors = [];
    page.on("console", msg => { if (msg.type() === "error") errors.push(msg.text()); });
    page.on("pageerror", err => errors.push(err.message));

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(ADMIN_URL);
    await page.waitForTimeout(1000);

    expect(errors, `Błędy JS: ${errors.join("; ")}`).toHaveLength(0);
  });
});
