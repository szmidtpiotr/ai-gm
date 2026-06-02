const { defineConfig } = require("@playwright/test");

const baseURL = process.env.BASE_URL || "http://127.0.0.1:13002";

module.exports = defineConfig({
  testDir: "./ux",
  timeout: 120000,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  fullyParallel: false,
  use: {
    headless: process.env.HEADED !== "1",
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 390, height: 844 },
  },
  outputDir: "../playwright-results",
  reporter: [["list"], ["html", { outputFolder: "../playwright-report", open: "never" }]],
});
