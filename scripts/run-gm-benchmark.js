#!/usr/bin/env node
/**
 * GM LLM benchmark — OpenAI-compatible chat completions (LLMAPI).
 * Env: LLMAPI_API_KEY (required)
 */

const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://api.llmapi.ai';
const TIMEOUT_MS = 60_000;
const MAX_RETRIES = 2; // 2 retries after first failure => up to 3 attempts
const ROOT = path.join(__dirname, '..');
const CONFIG_MODELS = path.join(ROOT, 'config', 'models.json');
const CONFIG_TESTS = path.join(ROOT, 'config', 'tests.json');
const OUT_RAW = path.join(ROOT, 'output', 'raw');
const OUT_RESULTS = path.join(ROOT, 'output', 'results');

const verbose = process.argv.includes('--verbose') || process.argv.includes('-v');

function logErr(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  fs.appendFileSync(path.join(OUT_RESULTS, 'errors.log'), line, 'utf8');
  console.error(msg);
}

function ensureDirs() {
  [OUT_RAW, OUT_RESULTS].forEach((d) => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  });
}

function safeFilePart(s) {
  return String(s)
    .replace(/[/\\?%*:|"<>]/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 120);
}

function countWords(text) {
  if (!text || !String(text).trim()) return 0;
  return String(text)
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function escapeCsvCell(val) {
  const s = String(val ?? '');
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function fetchChatCompletion({ apiKey, model, systemPrompt, userPrompt, temperature, maxTokens }) {
  const url = `${BASE_URL.replace(/\/$/, '')}/v1/chat/completions`;
  const body = {
    model,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature,
    max_tokens: maxTokens,
  };

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const rawText = await res.text();
    let json;
    try {
      json = JSON.parse(rawText);
    } catch {
      throw new Error(`Non-JSON response (HTTP ${res.status}): ${rawText.slice(0, 500)}`);
    }

    if (!res.ok) {
      const detail = json.error?.message || json.message || JSON.stringify(json);
      const err = new Error(`HTTP ${res.status}: ${detail}`);
      err.httpStatus = res.status;
      throw err;
    }

    const content =
      json.choices?.[0]?.message?.content ??
      json.choices?.[0]?.delta?.content ??
      '';

    return { raw: json, content: typeof content === 'string' ? content : String(content ?? '') };
  } finally {
    clearTimeout(t);
  }
}

function httpStatusFromError(e) {
  if (e && typeof e.httpStatus === 'number') return e.httpStatus;
  const m = String(e?.message || e).match(/HTTP (\d{3}):/);
  return m ? Number(m[1]) : null;
}

/** Nie ponawiaj przy błędach konta / uprawnień — retry nie pomoże. */
function isNonRetryableClientError(status) {
  return status === 401 || status === 403 || status === 404;
}

async function runWithRetry(fn, label) {
  let lastErr;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      const msg = e instanceof Error ? e.message : String(e);
      logErr(`${label} attempt ${attempt + 1}/${MAX_RETRIES + 1}: ${msg}`);
      const st = httpStatusFromError(e);
      if (st != null && isNonRetryableClientError(st)) {
        throw lastErr;
      }
      if (attempt < MAX_RETRIES) await sleep(800 * (attempt + 1));
    }
  }
  throw lastErr;
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function writeManualScoreSheet(models, tests) {
  const header =
    'model,test_id,polish,gm_style,coherence,creativity,constraint_fit,actionability,notes\n';
  const lines = [];
  for (const m of models) {
    for (const t of tests) {
      lines.push(
        [
          escapeCsvCell(m.model),
          escapeCsvCell(t.id),
          '',
          '',
          '',
          '',
          '',
          '',
          '',
        ].join(',')
      );
    }
  }
  fs.writeFileSync(path.join(OUT_RESULTS, 'manual-score-sheet.csv'), header + lines.join('\n') + '\n', 'utf8');
}

function buildMarkdown(results, models, tests) {
  const lines = [];
  lines.push('# Wyniki benchmarku GM (LLMAPI)');
  lines.push('');
  lines.push(`Data: ${new Date().toISOString()}`);
  lines.push(`Base URL: ${BASE_URL}`);
  lines.push('');

  lines.push('## Tabela zbiorcza');
  lines.push('');
  lines.push('| Model | Test | Nazwa | Latency (ms) | Znaki | Słowa |');
  lines.push('| --- | --- | --- | ---: | ---: | ---: |');
  for (const r of results) {
    if (r.error) continue;
    lines.push(
      `| ${r.model_label} | ${r.test_id} | ${r.test_name.replace(/\|/g, '\\|')} | ${r.latency_ms} | ${r.chars} | ${r.words} |`
    );
  }
  lines.push('');

  lines.push('## Według modelu');
  lines.push('');
  const byModel = new Map();
  for (const r of results) {
    const k = r.model;
    if (!byModel.has(k)) byModel.set(k, []);
    byModel.get(k).push(r);
  }
  for (const m of models) {
    if (!m.enabled) continue;
    lines.push(`### ${m.label} (\`${m.model}\`)`);
    lines.push('');
    const list = byModel.get(m.model) || [];
    for (const r of list) {
      lines.push(`#### ${r.test_id} — ${r.test_name}`);
      lines.push('');
      if (r.error) {
        lines.push(`*Błąd:* \`${String(r.error).replace(/`/g, "'")}\``);
      } else {
        lines.push('```');
        lines.push(r.response_text || '');
        lines.push('```');
      }
      lines.push('');
    }
  }

  lines.push('## Według testu');
  lines.push('');
  const byTest = new Map();
  for (const r of results) {
    if (!byTest.has(r.test_id)) byTest.set(r.test_id, []);
    byTest.get(r.test_id).push(r);
  }
  for (const t of tests) {
    lines.push(`### ${t.id} — ${t.name}`);
    lines.push('');
    const list = byTest.get(t.id) || [];
    for (const r of list) {
      lines.push(`#### ${r.model_label} (\`${r.model}\`)`);
      lines.push('');
      if (r.error) {
        lines.push(`*Błąd:* \`${String(r.error).replace(/`/g, "'")}\``);
      } else {
        lines.push('```');
        lines.push(r.response_text || '');
        lines.push('```');
      }
      lines.push('');
    }
  }

  return lines.join('\n');
}

async function main() {
  ensureDirs();
  fs.writeFileSync(
    path.join(OUT_RESULTS, 'errors.log'),
    `--- benchmark run ${new Date().toISOString()} ---\n`,
    'utf8'
  );

  const apiKey = process.env.LLMAPI_API_KEY;
  if (!apiKey || !String(apiKey).trim()) {
    console.error('Brak LLMAPI_API_KEY w środowisku.');
    process.exit(1);
  }

  const models = loadJson(CONFIG_MODELS);
  const testsConfig = loadJson(CONFIG_TESTS);
  const defaults = testsConfig.defaults || {};
  const tests = testsConfig.tests || [];

  const systemPrompt =
    defaults.system_prompt ||
    'Jesteś mistrzem gry w tekstowym RPG. Odpowiadasz po polsku.';
  const temperature = typeof defaults.temperature === 'number' ? defaults.temperature : 0.75;
  const maxTokens = typeof defaults.max_tokens === 'number' ? defaults.max_tokens : 1200;

  const enabledModels = models.filter((m) => m.enabled);
  if (!enabledModels.length) {
    console.error('Brak włączonych modeli w config/models.json');
    process.exit(1);
  }

  /** @type {object[]} */
  const results = [];
  const started = Date.now();

  for (const m of enabledModels) {
    for (const t of tests) {
      const label = `${m.model} ${t.id}`;
      if (verbose) console.log(`→ ${label}`);

      const rawPath = path.join(
        OUT_RAW,
        `${safeFilePart(m.model)}__${safeFilePart(t.id)}.json`
      );

      const row = {
        model: m.model,
        model_label: m.label,
        test_id: t.id,
        test_name: t.name,
        user_prompt: t.user_prompt,
        latency_ms: null,
        chars: null,
        words: null,
        response_text: '',
        error: null,
        raw_response_path: rawPath,
      };

      try {
        const bundle = await runWithRetry(async () => {
          const t0 = Date.now();
          const out = await fetchChatCompletion({
            apiKey,
            model: m.model,
            systemPrompt,
            userPrompt: t.user_prompt,
            temperature,
            maxTokens,
          });
          return {
            raw: out.raw,
            content: out.content,
            latency_ms: Date.now() - t0,
          };
        }, label);

        fs.writeFileSync(rawPath, JSON.stringify(bundle.raw, null, 2), 'utf8');

        row.latency_ms = bundle.latency_ms;
        row.response_text = bundle.content;
        row.chars = bundle.content.length;
        row.words = countWords(bundle.content);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        row.error = msg;
        fs.writeFileSync(
          rawPath,
          JSON.stringify({ error: msg, model: m.model, test_id: t.id }, null, 2),
          'utf8'
        );
      }

      results.push(row);
      if (verbose) console.log(`  ✓ ${label} (${row.latency_ms ?? 'err'} ms)`);
    }
  }

  const meta = {
    generated_at: new Date().toISOString(),
    base_url: BASE_URL,
    duration_ms: Date.now() - started,
    defaults: { temperature, max_tokens: maxTokens },
    results,
  };

  fs.writeFileSync(
    path.join(OUT_RESULTS, 'benchmark-results.json'),
    JSON.stringify(meta, null, 2),
    'utf8'
  );

  const csvHeader = 'model,test_id,test_name,latency_ms,chars,words,response_text\n';
  const csvBody = results.map((r) =>
    [
      escapeCsvCell(r.model),
      escapeCsvCell(r.test_id),
      escapeCsvCell(r.test_name),
      r.latency_ms ?? '',
      r.chars ?? '',
      r.words ?? '',
      escapeCsvCell(r.error ? `[ERROR] ${r.error}` : r.response_text),
    ].join(',')
  );
  fs.writeFileSync(
    path.join(OUT_RESULTS, 'benchmark-results.csv'),
    csvHeader + csvBody.join('\n') + '\n',
    'utf8'
  );

  fs.writeFileSync(
    path.join(OUT_RESULTS, 'benchmark-results.md'),
    buildMarkdown(results, enabledModels, tests),
    'utf8'
  );

  writeManualScoreSheet(enabledModels, tests);

  console.log(`Gotowe. Wyniki: output/results/ (${results.length} przebiegów)`);
}

main().catch((e) => {
  logErr(`FATAL: ${e instanceof Error ? e.stack || e.message : e}`);
  process.exit(1);
});
