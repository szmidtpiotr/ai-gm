const express = require("express");
const path = require("path");
const fs = require("fs");
const { run } = require("./orchestrator");

const app = express();
app.use(express.json());

const SCENARIOS_DIR = path.resolve(__dirname, "../scenarios");

app.post("/agent/run", async (req, res) => {
  const { scenario_file: scenarioFile = "cheat_location.json", headed = false } = req.body || {};
  const scenarioPath = path.join(SCENARIOS_DIR, scenarioFile);
  if (!fs.existsSync(scenarioPath)) {
    return res.status(404).json({ error: `Scenario not found: ${scenarioFile}` });
  }
  const scenario = JSON.parse(fs.readFileSync(scenarioPath, "utf8"));

  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  if (res.flushHeaders) res.flushHeaders();

  const send = (data) => {
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  };

  try {
    const result = await run(scenario, {
      headed: !!headed,
      onStep: (stepData) => send(stepData),
    });
    send({ done: true, ...result });
  } catch (err) {
    send({ done: true, success: false, reason: "error", error: err && err.message ? err.message : String(err) });
  } finally {
    res.end();
  }
});

app.get("/agent/scenarios", (_req, res) => {
  if (!fs.existsSync(SCENARIOS_DIR)) {
    return res.json({ scenarios: [] });
  }
  const files = fs.readdirSync(SCENARIOS_DIR).filter((f) => f.endsWith(".json"));
  res.json({ scenarios: files });
});

const PORT = Number(process.env.AGENT_PORT || 4000);
app.listen(PORT, () => {
  console.log(`[agent/server] http://127.0.0.1:${PORT}  POST /agent/run  GET /agent/scenarios`);
});

module.exports = { app };
