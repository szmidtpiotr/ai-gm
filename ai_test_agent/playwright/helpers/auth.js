const fs = require("fs");
const path = require("path");

function loadConfig() {
  const candidates = [
    process.env.AI_TEST_CONFIG_PATH && path.resolve(process.env.AI_TEST_CONFIG_PATH),
    path.resolve(__dirname, "../../../data-dev/ai_test_config.json"),
    path.resolve(__dirname, "../../../backend/ai_test_config.json"),
  ].filter(Boolean);
  const cfgPath = candidates.find((p) => fs.existsSync(p)) || candidates[0];
  // eslint-disable-next-line global-require, import/no-dynamic-require
  return require(cfgPath);
}

module.exports = { loadConfig };
