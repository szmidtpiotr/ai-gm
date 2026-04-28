const express = require("express");
const path = require("path");
const fs = require("fs");
const { run } = require("./orchestrator");
const { validateScenario } = require("./scenario_validator");
const { probePlannerConnectivity } = require("./llm_client");

const app = express();
app.use(express.json({ limit: "2mb" }));

const SCENARIOS_DIR = path.resolve(__dirname, "../scenarios");

/** Exposed for GET /agent/screenshot while a run is active. */
const sessionRef = { page: null };

function loadScenarioFromFile(scenarioFile) {
  const scenarioPath = path.join(SCENARIOS_DIR, scenarioFile);
  if (!fs.existsSync(scenarioPath)) {
    return { error: `Scenario not found: ${scenarioFile}`, status: 404 };
  }
  return { scenario: JSON.parse(fs.readFileSync(scenarioPath, "utf8")) };
}

app.post("/agent/planner_ping", async (req, res) => {
  const planner_llm = req.body && req.body.planner_llm != null ? req.body.planner_llm : null;
  try {
    const out = await probePlannerConnectivity(planner_llm);
    return res.json(out);
  } catch (err) {
    return res.status(500).json({
      reachable: false,
      error: err && err.message ? err.message : String(err),
    });
  }
});

app.post("/agent/run", async (req, res) => {
  const {
    scenario: inlineScenario,
    scenario_file: scenarioFile = "cheat_location.json",
    headed = false,
    planner_llm: plannerLlm = null,
  } = req.body || {};
  let scenario;
  if (inlineScenario != null && typeof inlineScenario === "object") {
    scenario = inlineScenario;
  } else {
    const loaded = loadScenarioFromFile(scenarioFile);
    if (loaded.error) {
      return res.status(loaded.status).json({ error: loaded.error });
    }
    scenario = loaded.scenario;
  }

  const verr = validateScenario(scenario);
  if (verr.length) {
    return res.status(400).json({ error: "Invalid scenario", details: verr });
  }

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
      sessionRef,
      plannerLlm,
    });
    send({ done: true, ...result });
  } catch (err) {
    send({ done: true, success: false, reason: "error", error: err && err.message ? err.message : String(err) });
  } finally {
    res.end();
  }
});

app.get("/agent/screenshot", async (_req, res) => {
  if (!sessionRef.page) {
    return res.status(404).json({ error: "no active session" });
  }
  try {
    const buf = await sessionRef.page.screenshot({ type: "jpeg", quality: 70 });
    return res.json({ base64: buf.toString("base64") });
  } catch (err) {
    return res.status(503).json({ error: err && err.message ? err.message : String(err) });
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
  console.log(
    `[agent/server] http://127.0.0.1:${PORT}  POST /agent/run  GET /agent/screenshot  GET /agent/scenarios  POST /agent/planner_ping`
  );
});

module.exports = { app, sessionRef };
