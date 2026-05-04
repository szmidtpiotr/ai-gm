import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=20";
import { showToast } from "/admin_panel/shared/toast.js?v=20";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body?.detail) {
    const d = err.body.detail;
    return Array.isArray(d) ? d.join("; ") : String(d);
  }
  return fallback;
}

function makeLabeledRow(labelText, control, hintText = "") {
  const row = el("div", "field");
  const label = el("label", "", labelText);
  row.appendChild(label);
  row.appendChild(control);
  if (hintText) {
    row.appendChild(el("div", "muted", hintText));
  }
  return row;
}

function setButtonBusy(btn, busy, busyText) {
  if (!btn) return;
  if (busy) {
    btn.dataset.prevText = btn.textContent || "";
    btn.textContent = busyText;
    btn.disabled = true;
  } else {
    btn.textContent = btn.dataset.prevText || btn.textContent;
    btn.disabled = false;
  }
}

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  if (container.__voicePollId) {
    clearInterval(container.__voicePollId);
    container.__voicePollId = null;
  }

  container.innerHTML = "";
  container.classList.add("config-section");

  const root = el("div", "two-col-cards");
  const state = {
    health: null,
    config: null,
    voices: [],
    audio: null,
  };

  // CARD 1: status
  const statusCard = el("div", "admin-card");
  statusCard.appendChild(el("h3", "admin-card-title", "Status voice-service"));
  const statusLine = el("p", "muted", "Sprawdzam...");
  const statusMeta = el("pre", "config-diff-raw");
  statusMeta.style.maxHeight = "220px";
  statusMeta.style.overflow = "auto";
  const refreshHealthBtn = el("button", "secondary-btn", "Odśwież");
  refreshHealthBtn.type = "button";
  statusCard.appendChild(statusLine);
  statusCard.appendChild(refreshHealthBtn);
  statusCard.appendChild(statusMeta);

  // CARD 2: global toggles
  const globalCard = el("div", "admin-card");
  globalCard.appendChild(el("h3", "admin-card-title", "Globalne przełączniki"));
  const ttsGlobalToggle = document.createElement("input");
  ttsGlobalToggle.type = "checkbox";
  const sttGlobalToggle = document.createElement("input");
  sttGlobalToggle.type = "checkbox";
  globalCard.appendChild(makeLabeledRow("TTS (globalnie)", ttsGlobalToggle, "Czytaj odpowiedzi GM głosem"));
  globalCard.appendChild(makeLabeledRow("STT (globalnie)", sttGlobalToggle, "Umożliw graczom mówienie do mikrofonu"));

  const CLIENT_TTS_KEYS = {
    narrative: "ai-gm:tts:narrative",
    memory: "ai-gm:tts:memory",
    helpme: "ai-gm:tts:helpme",
    dice: "ai-gm:tts:dice",
    combat: "ai-gm:tts:combat",
  };

  const clientTtsCard = el("div", "admin-card");
  clientTtsCard.appendChild(el("h3", "admin-card-title", "Automatyczny odczyt — typ dymku (gra)"));
  clientTtsCard.appendChild(
    el(
      "p",
      "muted",
      "Zapis w localStorage tej przeglądarki (klucze ai-gm:tts:*). Dotyczy automatycznego TTS po wiadomościach w aplikacji gracza. Przycisk przy narracji czyta tekst po oczyszczeniu z bloków walki i rzutów."
    )
  );

  const clientTtsTable = document.createElement("table");
  clientTtsTable.className = "admin-table voice-client-tts-table";
  const clientThead = document.createElement("thead");
  const headTr = document.createElement("tr");
  const thOn = document.createElement("th");
  thOn.className = "admin-table-select-col";
  thOn.textContent = "";
  const thDesc = document.createElement("th");
  thDesc.textContent = "Rodzaj dymku";
  headTr.appendChild(thOn);
  headTr.appendChild(thDesc);
  clientThead.appendChild(headTr);

  const clientTbody = document.createElement("tbody");
  const clientTtsRows = [
    [CLIENT_TTS_KEYS.narrative, true, "Narracja GM", "route: narrative"],
    [CLIENT_TTS_KEYS.memory, false, "/mem — odpowiedź z pamięci podsumowania", "route: memory"],
    [CLIENT_TTS_KEYS.helpme, false, "/helpme — pomoc meta", "route: helpme"],
    [CLIENT_TTS_KEYS.dice, false, "Rzuty skill", "route: dice"],
    [CLIENT_TTS_KEYS.combat, false, "Mechanika walki w czacie", "route: combat"],
  ];

  function readClientTtsPref(storageKey, defaultBool) {
    try {
      const v = localStorage.getItem(storageKey);
      if (v === null) return defaultBool;
      return v === "1";
    } catch (_e) {
      return defaultBool;
    }
  }

  clientTtsRows.forEach(([storageKey, defaultBool, label, routeHint]) => {
    const tr = document.createElement("tr");
    const tdCb = document.createElement("td");
    tdCb.className = "admin-table-select-col";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = readClientTtsPref(storageKey, defaultBool);
    cb.addEventListener("change", () => {
      try {
        localStorage.setItem(storageKey, cb.checked ? "1" : "0");
      } catch (_e) {
        /* noop */
      }
    });
    tdCb.appendChild(cb);

    const tdLabel = document.createElement("td");
    const strong = el("span", "", label);
    tdLabel.appendChild(strong);
    tdLabel.appendChild(document.createTextNode(" "));
    const hint = el("code", "muted", routeHint);
    hint.style.fontSize = "0.85em";
    tdLabel.appendChild(hint);

    tr.appendChild(tdCb);
    tr.appendChild(tdLabel);
    clientTbody.appendChild(tr);
  });

  clientTtsTable.appendChild(clientThead);
  clientTtsTable.appendChild(clientTbody);
  clientTtsCard.appendChild(clientTtsTable);

  // CARD 3: TTS config + test
  const ttsCard = el("div", "admin-card");
  ttsCard.appendChild(el("h3", "admin-card-title", "Konfiguracja TTS (Piper)"));
  const voiceSelect = document.createElement("select");
  const speedInput = document.createElement("input");
  speedInput.type = "number";
  speedInput.min = "0.5";
  speedInput.max = "2.0";
  speedInput.step = "0.05";
  const noiseScaleInput = document.createElement("input");
  noiseScaleInput.type = "number";
  noiseScaleInput.min = "0.0";
  noiseScaleInput.max = "1.0";
  noiseScaleInput.step = "0.05";
  const noiseWInput = document.createElement("input");
  noiseWInput.type = "number";
  noiseWInput.min = "0.0";
  noiseWInput.max = "1.0";
  noiseWInput.step = "0.05";
  const saveTtsBtn = el("button", "primary-btn", "Zapisz TTS");
  saveTtsBtn.type = "button";
  ttsCard.appendChild(makeLabeledRow("Głos", voiceSelect));
  ttsCard.appendChild(makeLabeledRow("Szybkość (length_scale)", speedInput));
  ttsCard.appendChild(makeLabeledRow("Ekspresja (noise_scale)", noiseScaleInput));
  ttsCard.appendChild(makeLabeledRow("Wariancja (noise_w)", noiseWInput));
  ttsCard.appendChild(saveTtsBtn);

  ttsCard.appendChild(el("h3", "admin-card-title", "Test głosu"));
  const previewText = document.createElement("textarea");
  previewText.rows = 3;
  previewText.value = "Witaj, wedrowcze. Czego szukasz w tych mrokach?";
  const playTtsBtn = el("button", "secondary-btn", "▶ Odtworz glos GM");
  playTtsBtn.type = "button";
  ttsCard.appendChild(makeLabeledRow("Tekst testowy", previewText));
  ttsCard.appendChild(playTtsBtn);

  // CARD 4: STT + silence
  const sttCard = el("div", "admin-card");
  sttCard.appendChild(el("h3", "admin-card-title", "Konfiguracja STT (Whisper)"));
  const modelSelect = document.createElement("select");
  ["tiny", "small", "medium", "large-v2"].forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    modelSelect.appendChild(opt);
  });
  const langSelect = document.createElement("select");
  ["pl", "auto", "en"].forEach((l) => {
    const opt = document.createElement("option");
    opt.value = l;
    opt.textContent = l;
    langSelect.appendChild(opt);
  });
  const beamInput = document.createElement("input");
  beamInput.type = "number";
  beamInput.min = "1";
  beamInput.max = "10";
  beamInput.step = "1";
  const saveSttBtn = el("button", "primary-btn", "Zapisz STT");
  saveSttBtn.type = "button";

  sttCard.appendChild(makeLabeledRow("Model", modelSelect));
  sttCard.appendChild(makeLabeledRow("Jezyk", langSelect));
  sttCard.appendChild(makeLabeledRow("Beam size", beamInput));
  sttCard.appendChild(el("p", "muted", "Zmiana modelu Whisper moze chwile potrwac (~10s)."));
  sttCard.appendChild(saveSttBtn);

  sttCard.appendChild(el("h3", "admin-card-title", "Auto-stop ciszy STT"));
  const silenceMsInput = document.createElement("input");
  silenceMsInput.type = "number";
  silenceMsInput.min = "500";
  silenceMsInput.max = "10000";
  silenceMsInput.step = "100";
  const minRmsInput = document.createElement("input");
  minRmsInput.type = "number";
  minRmsInput.min = "0.001";
  minRmsInput.max = "0.2";
  minRmsInput.step = "0.001";
  const noiseMultInput = document.createElement("input");
  noiseMultInput.type = "number";
  noiseMultInput.min = "1.0";
  noiseMultInput.max = "5.0";
  noiseMultInput.step = "0.1";
  const saveSilenceBtn = el("button", "primary-btn", "Zapisz parametry ciszy");
  saveSilenceBtn.type = "button";
  sttCard.appendChild(makeLabeledRow("stt_silence_auto_stop_ms", silenceMsInput, "Czas ciszy po ktorym nasluch konczy sie automatycznie."));
  sttCard.appendChild(makeLabeledRow("stt_min_voice_rms_threshold", minRmsInput, "Minimalny poziom RMS traktowany jako mowa."));
  sttCard.appendChild(makeLabeledRow("stt_noise_multiplier", noiseMultInput, "Mnoznik progu wzgledem tla/szumu."));
  sttCard.appendChild(saveSilenceBtn);

  root.appendChild(statusCard);
  root.appendChild(globalCard);
  root.appendChild(clientTtsCard);
  root.appendChild(ttsCard);
  root.appendChild(sttCard);
  container.appendChild(root);

  function applyHealth(health) {
    state.health = health;
    if (!health || health.status !== "ok") {
      statusLine.textContent = "OFFLINE ❌";
      statusMeta.textContent = JSON.stringify(health || { status: "offline" }, null, 2);
      return;
    }
    const online = health.tts_loaded && health.stt_loaded;
    statusLine.textContent = online ? "ONLINE ✅" : "ONLINE ⚠️";
    statusMeta.textContent = JSON.stringify(
      {
        tts_loaded: !!health.tts_loaded,
        stt_loaded: !!health.stt_loaded,
        tts_voice: health.tts_voice,
        stt_model: health.stt_model,
        available_voices: health.available_voices || [],
      },
      null,
      2
    );
  }

  function applyConfig(cfg) {
    state.config = cfg || {};
    ttsGlobalToggle.checked = !!cfg.tts_enabled;
    sttGlobalToggle.checked = !!cfg.stt_enabled;
    speedInput.value = String(cfg.tts_speed ?? 1.0);
    noiseScaleInput.value = String(cfg.tts_noise_scale ?? 0.67);
    noiseWInput.value = String(cfg.tts_noise_w ?? 0.8);
    modelSelect.value = String(cfg.stt_model || "small");
    langSelect.value = String(cfg.stt_language || "pl");
    beamInput.value = String(cfg.stt_beam_size ?? 5);
    silenceMsInput.value = String(cfg.stt_silence_auto_stop_ms ?? 2000);
    minRmsInput.value = String(cfg.stt_min_voice_rms_threshold ?? 0.01);
    noiseMultInput.value = String(cfg.stt_noise_multiplier ?? 1.5);
  }

  function applyVoices(voices, selected) {
    state.voices = Array.isArray(voices) ? voices : [];
    voiceSelect.innerHTML = "";
    state.voices.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      voiceSelect.appendChild(opt);
    });
    if (selected && state.voices.includes(selected)) {
      voiceSelect.value = selected;
    }
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
      applyHealth({ status: "offline", error: parseApiError(err, "voice-service offline") });
      showToast(parseApiError(err, "Nie mozna zaladowac konfiguracji Voice."), "error");
    }
  }

  async function savePartial(payload, successText) {
    await adminFetch("/voice/config", { method: "POST", body: JSON.stringify(payload) });
    if (successText) showToast(successText, "success");
    await loadAll();
  }

  refreshHealthBtn.addEventListener("click", async () => {
    setButtonBusy(refreshHealthBtn, true, "Odswiezam...");
    try {
      const health = await adminFetch("/voice/healthz");
      applyHealth(health);
    } catch (err) {
      applyHealth({ status: "offline", error: parseApiError(err, "healthz failed") });
      showToast(parseApiError(err, "Voice health refresh failed."), "error");
    } finally {
      setButtonBusy(refreshHealthBtn, false);
    }
  });

  ttsGlobalToggle.addEventListener("change", async () => {
    try {
      await savePartial({ tts_enabled: !!ttsGlobalToggle.checked }, "Zapisano");
    } catch (err) {
      showToast(parseApiError(err, "Nie zapisano TTS."), "error");
      ttsGlobalToggle.checked = !ttsGlobalToggle.checked;
    }
  });

  sttGlobalToggle.addEventListener("change", async () => {
    try {
      await savePartial({ stt_enabled: !!sttGlobalToggle.checked }, "Zapisano");
    } catch (err) {
      showToast(parseApiError(err, "Nie zapisano STT."), "error");
      sttGlobalToggle.checked = !sttGlobalToggle.checked;
    }
  });

  saveTtsBtn.addEventListener("click", async () => {
    setButtonBusy(saveTtsBtn, true, "Zapis...");
    try {
      await savePartial(
        {
          tts_voice: voiceSelect.value,
          tts_speed: Number(speedInput.value),
          tts_noise_scale: Number(noiseScaleInput.value),
          tts_noise_w: Number(noiseWInput.value),
        },
        "TTS zapisane"
      );
    } catch (err) {
      showToast(parseApiError(err, "Nie zapisano TTS."), "error");
    } finally {
      setButtonBusy(saveTtsBtn, false);
    }
  });

  saveSttBtn.addEventListener("click", async () => {
    setButtonBusy(saveSttBtn, true, "Zapis...");
    try {
      await savePartial(
        {
          stt_model: modelSelect.value,
          stt_language: langSelect.value,
          stt_beam_size: Number(beamInput.value),
        },
        "STT zapisane"
      );
    } catch (err) {
      showToast(parseApiError(err, "Nie zapisano STT."), "error");
    } finally {
      setButtonBusy(saveSttBtn, false);
    }
  });

  saveSilenceBtn.addEventListener("click", async () => {
    setButtonBusy(saveSilenceBtn, true, "Zapis...");
    try {
      await savePartial(
        {
          stt_silence_auto_stop_ms: Number(silenceMsInput.value),
          stt_min_voice_rms_threshold: Number(minRmsInput.value),
          stt_noise_multiplier: Number(noiseMultInput.value),
        },
        "Parametry STT zapisane"
      );
    } catch (err) {
      showToast(parseApiError(err, "Nie zapisano parametrow ciszy."), "error");
    } finally {
      setButtonBusy(saveSilenceBtn, false);
    }
  });

  playTtsBtn.addEventListener("click", async () => {
    const text = String(previewText.value || "").trim();
    if (!text) {
      showToast("Podaj tekst do testu TTS.", "info");
      return;
    }
    setButtonBusy(playTtsBtn, true, "Ladowanie...");
    try {
      const query = new URLSearchParams({
        text,
        voice: voiceSelect.value,
        speed: String(Number(speedInput.value)),
      });
      const base = localStorage.getItem("aigm_admin_baseurl") || "";
      const normalizedBase = String(base).replace(/\/+$/, "");
      const url = `${normalizedBase}/voice/tts?${query.toString()}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      if (state.audio) {
        try {
          state.audio.pause();
        } catch (_e) {
          // noop
        }
      }
      const blobUrl = URL.createObjectURL(blob);
      const audio = new Audio(blobUrl);
      state.audio = audio;
      audio.onended = () => URL.revokeObjectURL(blobUrl);
      audio.onerror = () => URL.revokeObjectURL(blobUrl);
      await audio.play();
    } catch (err) {
      showToast(`Blad TTS: ${parseApiError(err, err?.message || "unknown")}`, "error");
    } finally {
      setButtonBusy(playTtsBtn, false);
    }
  });

  await loadAll();
  const pollId = setInterval(async () => {
    try {
      const health = await adminFetch("/voice/healthz");
      applyHealth(health);
    } catch (_err) {
      applyHealth({ status: "offline" });
    }
  }, 30000);
  container.__voicePollId = pollId;
}
