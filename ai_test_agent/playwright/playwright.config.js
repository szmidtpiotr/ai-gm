const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./",
  timeout: 120000,
  use: {
    headless: process.env.HEADED !== "1",
    baseURL: process.env.BASE_URL || "http://192.168.1.61:3002",
    video: "on",
    screenshot: "only-on-failure",
  },
  outputDir: "../playwright-results",
  reporter: [["html", { outputFolder: "../playwright-report" }], ["list"]],
});
