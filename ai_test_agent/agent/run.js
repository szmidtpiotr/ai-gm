const path = require("path");
const fs = require("fs");
const { run } = require("./orchestrator");

const args = process.argv.slice(2);
const scenarioArg = args.find((a) => a.startsWith("--scenario="))?.split("=")[1] || "cheat_location.json";
const headed = args.includes("--headed");

const scenarioPath = path.resolve(__dirname, "../scenarios", scenarioArg);
if (!fs.existsSync(scenarioPath)) {
  console.error(`[run] brak pliku: ${scenarioPath}`);
  process.exit(2);
}
const scenario = JSON.parse(fs.readFileSync(scenarioPath, "utf8"));

run(scenario, {
  headed,
  onStep: (s) => console.log("[step]", JSON.stringify(s)),
})
  .then((r) => {
    console.log("[result]", JSON.stringify(r));
    process.exit(r.success ? 0 : 1);
  })
  .catch((e) => {
    console.error("[error]", e.message);
    process.exit(2);
  });
