import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  statusTitle:    "Status usługi głosowej",
  statusRefresh:  "Odśwież",
  globalTitle:    "Globalne przełączniki",
  ttsGlobal:      "TTS (globalnie)",
  ttsGlobalHint:  "Czytaj odpowiedzi GM głosem",
  sttGlobal:      "STT (globalnie)",
  sttGlobalHint:  "Umożliw graczom mówienie do mikrofonu",
  clientTtsTitle: "Automatyczny odczyt — typ dymku",
  clientTtsHint:  "Zapis w localStorage tej przeglądarki. Dotyczy automatycznego TTS po wiadomościach w aplikacji gracza.",
  ttsTitle:       "Konfiguracja TTS (Piper)",
  voiceLabel:     "Głos",
  speedLabel:     "Szybkość (length_scale)",
  noiseLabel:     "Ekspresja (noise_scale)",
  noiseWLabel:    "Wariancja (noise_w)",
  saveTts:        "Zapisz TTS",
  testTitle:      "Test głosu",
  testText:       "Tekst testowy",
  playBtn:        "▶ Odtwórz głos GM",
  sttTitle:       "Konfiguracja STT (Whisper)",
  modelLabel:     "Model",
  langLabel:      "Język",
  beamLabel:      "Beam size",
  sttNote:        "Zmiana modelu Whisper może chwilę potrwać (~10s).",
  saveStt:        "Zapisz STT",
  silenceTitle:   "Auto-stop ciszy STT",
  silenceMsLabel: "stt_silence_auto_stop_ms",
  silenceMsHint:  "Czas ciszy po którym nasłuch kończy się automatycznie.",
  minRmsLabel:    "stt_min_voice_rms_threshold",
  minRmsHint:     "Minimalny poziom RMS traktowany jako mowa.",
  noiseMultLabel: "stt_noise_multiplier",
  noiseMultHint:  "Mnożnik progu względem tła/szumu.",
  saveSilence:    "Zapisz parametry ciszy",
  offline:        "OFFLINE",
  online:         "ONLINE",
};

const CLIENT_TTS_ROWS = [
  { key: "ai-gm:tts:narrative", defaultOn: true,  label: "Narracja GM",                     hint: "route: narrative" },
  { key: "ai-gm:tts:memory",    defaultOn: false, label: "/mem — odpowiedź z pamięci",       hint: "route: memory" },
  { key: "ai-gm:tts:helpme",    defaultOn: false, label: "/helpme — pomoc meta",             hint: "route: helpme" },
  { key: "ai-gm:tts:dice",      defaultOn: false, label: "Rzuty skill",                      hint: "route: dice" },
  { key: "ai-gm:tts:combat",    defaultOn: false, label: "Mechanika walki w czacie",         hint: "route: combat" },
];

export async function init(panel) {
  if (panel.__voicePollId) {
    clearInterval(panel.__voicePollId);
    panel.__voicePollId = null;
  }

  panel.innerHTML = `
    <div class="voice-layout">

      <!-- Row 1: Status + Global toggles -->
      <div class="voice-top-row">

        <div class="system-section voice-status-card">
          <div class="system-section-title">${LABELS.statusTitle}</div>
          <div class="voice-status-line">
            <span id="voice-status-badge" class="voice-badge voice-badge-offline">${LABELS.offline}</span>
            <span id="voice-status-detail" class="system-help-text"></span>
          </div>
          <pre id="voice-status-meta" class="voice-meta-pre"></pre>
          <button type="button" class="secondary-btn" id="voice-refresh-btn" style="margin-top:10px">
            🔄 ${LABELS.statusRefresh}
          </button>
        </div>

        <div class="system-section">
          <div class="system-section-title">${LABELS.globalTitle}</div>
          <div class="voice-toggle-row">
            <label class="voice-toggle-label">
              <input type="checkbox" id="tts-global-toggle" class="voice-toggle-check" />
              <span class="voice-toggle-slider"></span>
            </label>
            <div>
              <div class="voice-toggle-name">${LABELS.ttsGlobal}</div>
              <div class="system-help-text">${LABELS.ttsGlobalHint}</div>
            </div>
          </div>
          <div class="voice-toggle-row" style="margin-top:12px">
            <label class="voice-toggle-label">
              <input type="checkbox" id="stt-global-toggle" class="voice-toggle-check" />
              <span class="voice-toggle-slider"></span>
            </label>
            <div>
              <div class="voice-toggle-name">${LABELS.sttGlobal}</div>
              <div class="system-help-text">${LABELS.sttGlobalHint}</div>
            </div>
          </div>
        </div>

      </div>

      <!-- Row 2: Client TTS prefs -->
      <div class="system-section">
        <div class="system-section-title">${LABELS.clientTtsTitle}</div>
        <p class="system-help-text" style="margin-bottom:10px">${LABELS.clientTtsHint}</p>
        <div id="client-tts-rows" class="voice-client-rows"></div>
      </div>

      <!-- Row 3: TTS config + STT config side by side -->
      <div class="voice-config-row">

        <div class="system-section">
          <div class="system-section-title">${LABELS.ttsTitle}</div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.voiceLabel}</label>
            <select id="voice-select" class="field-input"></select>
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.speedLabel}</label>
            <input id="tts-speed" type="number" class="field-input" min="0.5" max="2.0" step="0.05" style="width:120px" />
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.noiseLabel}</label>
            <input id="tts-noise-scale" type="number" class="field-input" min="0.0" max="1.0" step="0.05" style="width:120px" />
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.noiseWLabel}</label>
            <input id="tts-noise-w" type="number" class="field-input" min="0.0" max="1.0" step="0.05" style="width:120px" />
          </div>
          <button type="button" class="primary-btn" id="save-tts-btn" style="margin-top:4px">${LABELS.saveTts}</button>

          <div class="system-section-title" style="margin-top:18px">${LABELS.testTitle}</div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.testText}</label>
            <textarea id="tts-preview-text" class="field-input" rows="3"
              style="width:100%;resize:vertical">Witaj, wędrowcze. Czego szukasz w tych mrokach?</textarea>
          </div>
          <button type="button" class="secondary-btn" id="play-tts-btn">${LABELS.playBtn}</button>
        </div>

        <div class="system-section">
          <div class="system-section-title">${LABELS.sttTitle}</div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.modelLabel}</label>
            <select id="stt-model" class="field-input">
              ${["tiny","small","medium","large-v2"].map(m => `<option value="${m}">${m}</option>`).join("")}
            </select>
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.langLabel}</label>
            <select id="stt-lang" class="field-input">
              ${["pl","auto","en"].map(l => `<option value="${l}">${l}</option>`).join("")}
            </select>
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.beamLabel}</label>
            <input id="stt-beam" type="number" class="field-input" min="1" max="10" step="1" style="width:80px" />
          </div>
          <p class="system-help-text" style="margin-bottom:8px">${LABELS.sttNote}</p>
          <button type="button" class="primary-btn" id="save-stt-btn">${LABELS.saveStt}</button>

          <div class="system-section-title" style="margin-top:18px">${LABELS.silenceTitle}</div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.silenceMsLabel}</label>
            <input id="stt-silence-ms" type="number" class="field-input" min="500" max="10000" step="100" style="width:120px" />
            <span class="system-help-text">${LABELS.silenceMsHint}</span>
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.minRmsLabel}</label>
            <input id="stt-min-rms" type="number" class="field-input" min="0.001" max="0.2" step="0.001" style="width:120px" />
            <span class="system-help-text">${LABELS.minRmsHint}</span>
          </div>
          <div class="voice-field">
            <label class="system-field-label">${LABELS.noiseMultLabel}</label>
            <input id="stt-noise-mult" type="number" class="field-input" min="1.0" max="5.0" step="0.1" style="width:120px" />
            <span class="system-help-text">${LABELS.noiseMultHint}</span>
          </div>
          <button type="button" class="primary-btn" id="save-silence-btn" style="margin-top:4px">${LABELS.saveSilence}</button>
        </div>

      </div>
    </div>`;

  // ── Client TTS localStorage prefs ──
  const clientTtsWrap = panel.querySelector("#client-tts-rows");
  CLIENT_TTS_ROWS.forEach(({ key, defaultOn, label, hint }) => {
    const stored = localStorage.getItem(key);
    const checked = stored === null ? defaultOn : stored === "1";
    const row = document.createElement("label");
    row.className = "voice-client-row";
    row.innerHTML = `
      <input type="checkbox" class="voice-client-check" ${checked ? "checked" : ""} />
      <span class="voice-client-label">${label}</span>
      <code class="voice-client-hint">${hint}</code>`;
    row.querySelector("input").addEventListener("change", e => {
      try { localStorage.setItem(key, e.target.checked ? "1" : "0"); } catch { /* noop */ }
    });
    clientTtsWrap.appendChild(row);
  });

  // ── State ──
  const state = { health: null, config: null, voices: [], audio: null };

  // ── DOM refs ──
  const statusBadge   = panel.querySelector("#voice-status-badge");
  const statusDetail  = panel.querySelector("#voice-status-detail");
  const statusMeta    = panel.querySelector("#voice-status-meta");
  const ttsGlobalTog  = panel.querySelector("#tts-global-toggle");
  const sttGlobalTog  = panel.querySelector("#stt-global-toggle");
  const voiceSelect   = panel.querySelector("#voice-select");
  const speedInput    = panel.querySelector("#tts-speed");
  const noiseScale    = panel.querySelector("#tts-noise-scale");
  const noiseW        = panel.querySelector("#tts-noise-w");
  const previewText   = panel.querySelector("#tts-preview-text");
  const modelSelect   = panel.querySelector("#stt-model");
  const langSelect    = panel.querySelector("#stt-lang");
  const beamInput     = panel.querySelector("#stt-beam");
  const silenceMs     = panel.querySelector("#stt-silence-ms");
  const minRms        = panel.querySelector("#stt-min-rms");
  const noiseMult     = panel.querySelector("#stt-noise-mult");

  function applyHealth(health) {
    state.health = health;
    const ok = health?.status === "ok";
    const fullyLoaded = ok && health.tts_loaded && health.stt_loaded;
    statusBadge.textContent  = ok ? LABELS.online : LABELS.offline;
    statusBadge.className    = `voice-badge ${ok ? (fullyLoaded ? "voice-badge-online" : "voice-badge-warn") : "voice-badge-offline"}`;
    statusDetail.textContent = ok
      ? `TTS: ${health.tts_loaded ? "✓" : "✗"}  STT: ${health.stt_loaded ? "✓" : "✗"}  ${health.tts_voice ? `głos: ${health.tts_voice}` : ""}`
      : (health?.error || "brak połączenia");
    statusMeta.textContent = JSON.stringify(
      ok ? { tts_loaded: !!health.tts_loaded, stt_loaded: !!health.stt_loaded,
             tts_voice: health.tts_voice, stt_model: health.stt_model,
             available_voices: health.available_voices || [] }
         : (health || { status: "offline" }),
      null, 2
    );
  }

  function applyConfig(cfg) {
    state.config = cfg || {};
    ttsGlobalTog.checked  = !!cfg.tts_enabled;
    sttGlobalTog.checked  = !!cfg.stt_enabled;
    speedInput.value      = String(cfg.tts_speed       ?? 1.0);
    noiseScale.value      = String(cfg.tts_noise_scale ?? 0.67);
    noiseW.value          = String(cfg.tts_noise_w     ?? 0.8);
    modelSelect.value     = String(cfg.stt_model       || "small");
    langSelect.value      = String(cfg.stt_language    || "pl");
    beamInput.value       = String(cfg.stt_beam_size   ?? 5);
    silenceMs.value       = String(cfg.stt_silence_auto_stop_ms      ?? 2000);
    minRms.value          = String(cfg.stt_min_voice_rms_threshold   ?? 0.01);
    noiseMult.value       = String(cfg.stt_noise_multiplier          ?? 1.5);
  }

  function applyVoices(voices, selected) {
    state.voices = Array.isArray(voices) ? voices : [];
    voiceSelect.innerHTML = "";
    state.voices.forEach(v => {
      const opt = document.createElement("option");
      opt.value = v; opt.textContent = v;
      voiceSelect.appendChild(opt);
    });
    if (selected && state.voices.includes(selected)) voiceSelect.value = selected;
  }

  async function loadAll() {
    try {
      const [health, cfg, voiceResp] = await Promise.all([
        adminFetch("/voice/healthz"),
        adminFetch("/voice/config"),
        adminFetch("/voice/voices"),
      ]);
      applyHealth(health);
      applyConfig(cfg);
      applyVoices(voiceResp?.voices || [], cfg?.tts_voice || health?.tts_voice);
    } catch (err) {
      applyHealth({ status: "offline", error: err.message || "voice-service offline" });
      showToast("Nie można załadować konfiguracji Voice.", "error");
    }
  }

  async function savePartial(payload, successText) {
    await adminFetch("/voice/config", { method: "POST", body: JSON.stringify(payload) });
    if (successText) showToast(successText, "success");
    await loadAll();
  }

  function busy(btn, isBusy) {
    if (!btn) return;
    if (isBusy) { btn.dataset.prev = btn.textContent; btn.textContent = "⏳"; btn.disabled = true; }
    else        { btn.textContent = btn.dataset.prev || btn.textContent; btn.disabled = false; }
  }

  // ── Event listeners ──
  panel.querySelector("#voice-refresh-btn").addEventListener("click", async () => {
    const btn = panel.querySelector("#voice-refresh-btn");
    busy(btn, true);
    try {
      applyHealth(await adminFetch("/voice/healthz"));
    } catch (err) {
      applyHealth({ status: "offline", error: err.message });
      showToast("Voice health refresh failed.", "error");
    } finally { busy(btn, false); }
  });

  ttsGlobalTog.addEventListener("change", async () => {
    try {
      await savePartial({ tts_enabled: ttsGlobalTog.checked }, "Zapisano");
    } catch (err) {
      showToast(err.message || "Nie zapisano TTS.", "error");
      ttsGlobalTog.checked = !ttsGlobalTog.checked;
    }
  });

  sttGlobalTog.addEventListener("change", async () => {
    try {
      await savePartial({ stt_enabled: sttGlobalTog.checked }, "Zapisano");
    } catch (err) {
      showToast(err.message || "Nie zapisano STT.", "error");
      sttGlobalTog.checked = !sttGlobalTog.checked;
    }
  });

  panel.querySelector("#save-tts-btn").addEventListener("click", async () => {
    const btn = panel.querySelector("#save-tts-btn");
    busy(btn, true);
    try {
      await savePartial({
        tts_voice:       voiceSelect.value,
        tts_speed:       Number(speedInput.value),
        tts_noise_scale: Number(noiseScale.value),
        tts_noise_w:     Number(noiseW.value),
      }, "TTS zapisane");
    } catch (err) { showToast(err.message || "Nie zapisano TTS.", "error"); }
    finally { busy(btn, false); }
  });

  panel.querySelector("#save-stt-btn").addEventListener("click", async () => {
    const btn = panel.querySelector("#save-stt-btn");
    busy(btn, true);
    try {
      await savePartial({
        stt_model:    modelSelect.value,
        stt_language: langSelect.value,
        stt_beam_size: Number(beamInput.value),
      }, "STT zapisane");
    } catch (err) { showToast(err.message || "Nie zapisano STT.", "error"); }
    finally { busy(btn, false); }
  });

  panel.querySelector("#save-silence-btn").addEventListener("click", async () => {
    const btn = panel.querySelector("#save-silence-btn");
    busy(btn, true);
    try {
      await savePartial({
        stt_silence_auto_stop_ms:    Number(silenceMs.value),
        stt_min_voice_rms_threshold: Number(minRms.value),
        stt_noise_multiplier:        Number(noiseMult.value),
      }, "Parametry STT zapisane");
    } catch (err) { showToast(err.message || "Nie zapisano parametrów ciszy.", "error"); }
    finally { busy(btn, false); }
  });

  panel.querySelector("#play-tts-btn").addEventListener("click", async () => {
    const text = previewText.value.trim();
    if (!text) { showToast("Podaj tekst do testu TTS.", "info"); return; }
    const btn = panel.querySelector("#play-tts-btn");
    busy(btn, true);
    try {
      const query = new URLSearchParams({
        text,
        voice: voiceSelect.value,
        speed: String(Number(speedInput.value)),
      });
      const base = (localStorage.getItem("aigm_admin_baseurl") || "").replace(/\/+$/, "");
      const resp = await fetch(`${base}/voice/tts?${query.toString()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      if (state.audio) { try { state.audio.pause(); } catch { /* noop */ } }
      const blobUrl = URL.createObjectURL(blob);
      const audio = new Audio(blobUrl);
      state.audio = audio;
      audio.onended = () => URL.revokeObjectURL(blobUrl);
      audio.onerror = () => URL.revokeObjectURL(blobUrl);
      await audio.play();
    } catch (err) {
      showToast(`Błąd TTS: ${err.message || "unknown"}`, "error");
    } finally { busy(btn, false); }
  });

  await loadAll();

  const pollId = setInterval(async () => {
    try { applyHealth(await adminFetch("/voice/healthz")); }
    catch { applyHealth({ status: "offline" }); }
  }, 30000);
  panel.__voicePollId = pollId;
}
