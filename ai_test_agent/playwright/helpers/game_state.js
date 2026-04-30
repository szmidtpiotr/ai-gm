const { loadConfig } = require("./auth");

function backendUrl() {
  return process.env.BACKEND_URL || "http://192.168.1.61:8100";
}

async function resetTestEnv() {
  const base = backendUrl();
  const endpoint = `${base}/api/debug/reset_test_env`;
  let res;
  try {
    res = await fetch(endpoint, { method: "POST" });
  } catch (e) {
    const { formatNodeFetchError } = require("../../agent/llm_client");
    throw new Error(
      `reset_test_env sieć (${endpoint}): ${formatNodeFetchError(e)} — ustaw BACKEND_URL (w Dockerze http://backend:8000).`,
    );
  }
  const data = await res.json().catch(() => ({}));
  if (!data.reset) {
    throw new Error(`reset_test_env failed: ${JSON.stringify(data)}`);
  }
  return data;
}

async function getPlayerState(characterId) {
  let res;
  try {
    res = await fetch(`${backendUrl()}/api/debug/player_state?character_id=${characterId}`);
  } catch (e) {
    const { formatNodeFetchError } = require("../../agent/llm_client");
    throw new Error(`player_state sieć: ${formatNodeFetchError(e)}`);
  }
  return res.json();
}

module.exports = { loadConfig, resetTestEnv, getPlayerState };
