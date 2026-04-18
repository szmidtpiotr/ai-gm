#!/usr/bin/env node
/**
 * Lista modeli z LLMAPI (OpenAI-compatible GET /v1/models).
 * Użycie: node scripts/list-llmapi-models.js [--text-only]
 *   --text-only  tylko modele z wejściem wyłącznie tekstowym (bez image na wejściu)
 */

const BASE = 'https://api.llmapi.ai';

const textOnly = process.argv.includes('--text-only');

async function main() {
  const url = `${BASE}/v1/models?exclude_deprecated=true`;
  const res = await fetch(url);
  const body = await res.text();
  if (!res.ok) {
    console.error(`HTTP ${res.status}: ${body.slice(0, 500)}`);
    process.exit(1);
  }
  const j = JSON.parse(body);
  const items = j.data || [];
  let rows = items.filter((m) => {
    const arch = m.architecture || {};
    const outs = arch.output_modalities || [];
    if (!outs.includes('text')) return false;
    if (!textOnly) return true;
    const ins = arch.input_modalities || [];
    return ins.includes('text') && !ins.includes('image');
  });
  rows = rows.sort((a, b) => String(a.id).localeCompare(String(b.id)));
  console.log(`# ${rows.length} modeli (LLMAPI, ${textOnly ? 'tylko text→text' : 'output: text'})`);
  rows.forEach((m) => {
    const name = m.name ? `  # ${m.name}` : '';
    console.log(`${m.id}${name}`);
  });
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
