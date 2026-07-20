const express = require("express");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const { run } = require("./orchestrator");
const { validateScenario } = require("./scenario_validator");
const { probePlannerConnectivity } = require("./llm_client");

const app = express();
app.use(express.json({ limit: "2mb" }));

const SCENARIOS_DIR = path.resolve(__dirname, "../scenarios");

/** Exposed for GET /agent/screenshot while a run is active. */
const sessionRef = { page: null };

/** Kontrola zatrzymania - globalny stan dla aktywnego runu */
const runState = {
  cancelled: false,
  currentRunId: null,
  cancelCallbacks: [],
};

function logStructured(level, event, data = {}) {
  const ts = new Date().toISOString();
  const logEntry = {
    ts,
    level,
    service: "test-agent",
    event,
    ...data,
  };
  console.log(JSON.stringify(logEntry));
}

function resetRunState(runId) {
  runState.cancelled = false;
  runState.currentRunId = runId;
  runState.cancelCallbacks = [];
}

function cancelRun() {
  runState.cancelled = true;
  logStructured("info", "run_cancel_requested", { run_id: runState.currentRunId });
  // Wywołaj zarejestrowane callbacki (np. do przerwania browser.close())
  runState.cancelCallbacks.forEach((cb) => {
    try { cb(); } catch (e) { /* ignore */ }
  });
}

function isRunCancelled() {
  return runState.cancelled;
}

function onCancel(callback) {
  runState.cancelCallbacks.push(callback);
}

function loadScenarioFromFile(scenarioFile) {
  const scenarioPath = path.join(SCENARIOS_DIR, scenarioFile);
  if (!fs.existsSync(scenarioPath)) {
    return { error: `Scenario not found: ${scenarioFile}`, status: 404 };
  }
  return { scenario: JSON.parse(fs.readFileSync(scenarioPath, "utf8")) };
}

function normalizePlannerLlmForNode(plannerLlm) {
  if (!plannerLlm) return null;
  if (typeof plannerLlm !== "object") return null;
  // Format backendowy (internal): { llm_api_url, llm_model, llm_api_key? }
  if (plannerLlm.llm_api_url) {
    return plannerLlm;
  }
  // Format z panelu (jak /api/test_runner/start): { provider, base_url, model, api_key? }
  const baseUrl = plannerLlm.base_url || plannerLlm.baseUrl;
  const model = plannerLlm.model;
  const apiKey = plannerLlm.api_key ?? plannerLlm.apiKey;
  if (baseUrl && model) {
    const out = { llm_api_url: baseUrl, llm_model: model };
    if (apiKey !== undefined) out.llm_api_key = apiKey;
    return out;
  }
  return null;
}

app.post("/agent/planner_ping", async (req, res) => {
  const planner_llm = req.body && req.body.planner_llm != null ? req.body.planner_llm : null;
  logStructured("info", "planner_ping", { has_custom_llm: !!planner_llm });
  try {
    const out = await probePlannerConnectivity(normalizePlannerLlmForNode(planner_llm));
    logStructured("info", "planner_ping_result", { reachable: out.reachable, error: out.error });
    return res.json(out);
  } catch (err) {
    logStructured("error", "planner_ping_error", { error: err && err.message ? err.message : String(err) });
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
  const runId = req.body && req.body.run_id ? req.body.run_id : `run_${Date.now()}`;

  // Reset cancellation state for new run
  resetRunState(runId);
  logStructured("info", "run_started", { run_id: runId, scenario_file: scenarioFile, headed: !!headed });

  let scenario;
  if (inlineScenario != null && typeof inlineScenario === "object") {
    scenario = inlineScenario;
  } else {
    const loaded = loadScenarioFromFile(scenarioFile);
    if (loaded.error) {
      logStructured("error", "run_scenario_load_failed", { run_id: runId, error: loaded.error });
      return res.status(loaded.status).json({ error: loaded.error });
    }
    scenario = loaded.scenario;
  }

  const verr = validateScenario(scenario);
  if (verr.length) {
    logStructured("error", "run_scenario_invalid", { run_id: runId, errors: verr });
    return res.status(400).json({ error: "Invalid scenario", details: verr });
  }

  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  if (res.flushHeaders) res.flushHeaders();

  const send = (data) => {
    try {
      res.write(`data: ${JSON.stringify(data)}\n\n`);
    } catch (e) {
      // Connection may be closed
    }
  };

  // Register cancellation callback to close response
  onCancel(() => {
    send({ done: true, success: false, reason: "cancelled", error: "Test zatrzymany przez użytkownika" });
    try { res.end(); } catch (e) { /* ignore */ }
  });

  try {
    const result = await run(scenario, {
      headed: !!headed,
      onStep: (stepData) => {
        logStructured("debug", "run_step", { run_id: runId, step: stepData.step, action: stepData.action?.type });
        send(stepData);
      },
      sessionRef,
      plannerLlm: normalizePlannerLlmForNode(plannerLlm),
      isCancelled: isRunCancelled,
    });
    logStructured("info", "run_completed", { run_id: runId, success: result.success, reason: result.reason, steps: result.steps });
    if (!isRunCancelled()) {
      send({ done: true, ...result });
    }
  } catch (err) {
    logStructured("error", "run_error", { run_id: runId, error: err && err.message ? err.message : String(err) });
    if (!isRunCancelled()) {
      send({ done: true, success: false, reason: "error", error: err && err.message ? err.message : String(err) });
    }
  } finally {
    runState.currentRunId = null;
    try { res.end(); } catch (e) { /* ignore */ }
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
  logStructured("info", "list_scenarios");
  if (!fs.existsSync(SCENARIOS_DIR)) {
    return res.json({ scenarios: [] });
  }
  const files = fs.readdirSync(SCENARIOS_DIR).filter((f) => f.endsWith(".json"));
  res.json({ scenarios: files });
});

app.post("/agent/stop", (req, res) => {
  const { run_id } = req.body || {};
  logStructured("info", "stop_requested", { run_id, current_run_id: runState.currentRunId });

  // Sprawdź czy run_id pasuje do aktualnego
  if (run_id && runState.currentRunId && runState.currentRunId !== run_id) {
    return res.json({ success: false, message: "Inny test jest aktualnie uruchomiony" });
  }

  if (!runState.currentRunId) {
    return res.json({ success: false, message: "Brak aktywnego testu" });
  }

  cancelRun();
  res.json({ success: true, message: "Zatrzymywanie testu...", run_id: runState.currentRunId });
});

// ── Playwright specs (all ux/ suites: regression, acceptance, admin3, …) ──────
const PLAYWRIGHT_SPECS_DIR = path.resolve(__dirname, "../playwright/ux/regression");
const PLAYWRIGHT_UX_DIR = path.resolve(__dirname, "../playwright/ux");

// Recursively collect *.spec.js under a root, returning posix paths relative to it.
function _walkSpecs(root, rel = "") {
  const out = [];
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(root, rel), { withFileTypes: true });
  } catch (_) {
    return out;
  }
  for (const e of entries) {
    const childRel = rel ? `${rel}/${e.name}` : e.name;
    if (e.isDirectory()) {
      out.push(..._walkSpecs(root, childRel));
    } else if (e.isFile() && e.name.endsWith(".spec.js")) {
      out.push(childRel);
    }
  }
  return out;
}

function _parseSpecMeta(filePath) {
  try {
    const src = fs.readFileSync(filePath, "utf8");
    // Extract first /** ... */ block
    const match = src.match(/^\/\*\*([\s\S]*?)\*\//);
    const description = match
      ? match[1].split("\n").map((l) => l.replace(/^\s*\*\s?/, "").trim()).filter(Boolean).join(" ")
      : "";
    // Count test() calls
    const testCount = (src.match(/^\s*test\(/gm) || []).length;
    return { description, testCount };
  } catch (_) {
    return { description: "", testCount: 0 };
  }
}

function _issueFromFilename(filename) {
  const m = filename.match(/issue_(\d+)/i);
  return m ? Number(m[1]) : null;
}

app.get("/playwright/specs", (_req, res) => {
  logStructured("info", "playwright_list_specs");
  try {
    if (!fs.existsSync(PLAYWRIGHT_UX_DIR)) {
      return res.json({ specs: [] });
    }
    // `filename` is a posix path relative to playwright/ux (e.g.
    // "regression/issue_391_story_stale.spec.js", "acceptance/c_series.spec.js").
    const specs = _walkSpecs(PLAYWRIGHT_UX_DIR)
      .sort()
      .map((rel) => {
        const { description, testCount } = _parseSpecMeta(path.join(PLAYWRIGHT_UX_DIR, rel));
        const base = rel.split("/").pop();
        const group = rel.includes("/") ? rel.split("/")[0] : "ux";
        return {
          filename: rel,
          group,
          label: base.replace(".spec.js", "").replace(/_/g, " "),
          issue: _issueFromFilename(base),
          description,
          testCount,
        };
      });
    return res.json({ specs });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
});

// #1488 — caller may point a run at another stack (isolated sandbox instead of the
// live DEV one). Only http(s) URLs are accepted; anything else falls back to the
// agent's own env, so a malformed value can never silently redirect a run.
function safeUrl(raw) {
  if (typeof raw !== "string" || !raw) return null;
  try {
    const u = new URL(raw);
    return u.protocol === "http:" || u.protocol === "https:" ? raw : null;
  } catch (_) {
    return null;
  }
}

app.post("/playwright/run", (req, res) => {
  const { spec, baseUrl, backendUrl } = req.body || {};
  // spec is a path relative to playwright/ux — either a single *.spec.js file or
  // a suite folder (regression / acceptance / admin3). Empty → run every suite.
  if (spec && (spec.includes("..") || !/^[A-Za-z0-9_./-]+$/.test(spec))) {
    res.status(400).json({ error: "invalid spec path" });
    return;
  }
  const specArg = spec ? `playwright/ux/${spec}` : "playwright/ux";
  const targetBase = safeUrl(baseUrl);
  const targetBackend = safeUrl(backendUrl);

  logStructured("info", "playwright_run_start", {
    spec: spec || "all",
    baseUrl: targetBase || process.env.BASE_URL,
  });

  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  if (res.flushHeaders) res.flushHeaders();

  const send = (data) => {
    try { res.write(`data: ${JSON.stringify(data)}\n\n`); } catch (_) { /* closed */ }
  };

  const args = ["playwright", "test", specArg, "--config=playwright/playwright.config.js", "--reporter=line"];
  const child = spawn("npx", args, {
    cwd: path.resolve(__dirname, ".."),
    env: {
      ...process.env,
      FORCE_COLOR: "0",
      ...(targetBase ? { BASE_URL: targetBase } : {}),
      ...(targetBackend ? { BACKEND_URL: targetBackend } : {}),
    },
  });
  if (targetBase) send({ type: "log", line: `🎯 Cel testów: ${targetBase}` });

  child.stdout.on("data", (chunk) => {
    chunk.toString().split("\n").filter(Boolean).forEach((line) => send({ type: "log", line }));
  });
  child.stderr.on("data", (chunk) => {
    chunk.toString().split("\n").filter(Boolean).forEach((line) => send({ type: "log", line, isErr: true }));
  });
  child.on("close", (code) => {
    logStructured("info", "playwright_run_done", { spec: spec || "all", exitCode: code });
    send({ type: "done", success: code === 0, exitCode: code });
    try { res.end(); } catch (_) { /* ignore */ }
  });
  child.on("error", (err) => {
    send({ type: "done", success: false, error: err.message });
    try { res.end(); } catch (_) { /* ignore */ }
  });
});

const PORT = Number(process.env.AGENT_PORT || 4000);
app.listen(PORT, () => {
  logStructured("info", "server_started", { port: PORT });
  console.log(
    `[agent/server] http://127.0.0.1:${PORT}  POST /agent/run  POST /agent/stop  GET /agent/screenshot  GET /agent/scenarios  POST /agent/planner_ping`
  );
});

module.exports = { app, sessionRef };
