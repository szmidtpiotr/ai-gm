(function () {
  const LS_TTS = "voice_tts_enabled";
  const LS_STT = "voice_stt_enabled";
  const LS_STT_AUTOSEND = "voice_stt_autosend";

  let available = true;
  let mediaRecorder = null;
  let mediaStream = null;
  let ws = null;
  let sttCloseTimer = null;
  let sttResultPending = false;
  let sttMonitorCtx = null;
  let sttMonitorSource = null;
  let sttMonitorAnalyser = null;
  let sttMonitorRaf = 0;
  let sttLastVoiceAt = 0;
  let sttAutoStopping = false;
  let sttNoiseFloorRms = 0;
  let sttHadSpeech = false;
  let sttStartedAt = 0;
  let sttHardStopTimer = null;
  let audio = null;
  let audioCtx = null;
  let activeBufferSource = null;
  let pendingSpeakText = "";
  let isPlaying = false;
  let suppressAudioError = false;
  let audioUnlocked = false;
  let ttsEnabled = true;
  let sttEnabled = false;
  let initialized = false;
  const STT_SILENCE_AUTO_STOP_MS = 2000;
  const STT_MIN_VOICE_RMS_THRESHOLD = 0.03;
  const STT_NOISE_MULTIPLIER = 4.0;
  const STT_MAX_RECORDING_MS = 14000;

  function _el(id) {
    return document.getElementById(id);
  }

  function _status(text) {
    const statusEl = _el("voice-status");
    if (statusEl) statusEl.textContent = text || "";
    window.dispatchEvent(
      new CustomEvent("voice-debug-status", {
        detail: { text: String(text || "") },
      })
    );
  }

  function _isIosWebkit() {
    const ua = navigator.userAgent || "";
    const platform = navigator.platform || "";
    const touchMac = platform === "MacIntel" && navigator.maxTouchPoints > 1;
    return /iPad|iPhone|iPod/i.test(ua) || touchMac;
  }

  function _ensureAudioContext() {
    if (audioCtx) return audioCtx;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audioCtx = new Ctx();
    return audioCtx;
  }

  function _ensureAudio() {
    if (audio) return audio;
    audio = new Audio();
    audio.preload = "auto";
    audio.setAttribute("playsinline", "true");
    audio.onended = () => {
      isPlaying = false;
      stopPlayback();
    };
    audio.onerror = () => {
      if (!isPlaying) return;
      if (suppressAudioError) return;
      _status("Blad odtwarzania audio");
      stopPlayback();
    };
    return audio;
  }

  async function _unlockAudioFromGesture() {
    const a = _ensureAudio();
    const ctx = _ensureAudioContext();
    let ctxReady = false;
    try {
      if (ctx && ctx.state !== "running") {
        await ctx.resume();
      }
      ctxReady = !!ctx && ctx.state === "running";
      // Minimalny „unlock” pod user gesture (Safari/Chrome autoplay policy).
      a.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=";
      a.volume = 0;
      await a.play();
      a.pause();
      a.currentTime = 0;
      a.volume = 1;
      audioUnlocked = true;
      _status("TTS gotowe");
    } catch (err) {
      // iOS WebKit often rejects HTMLAudio unlock, but WebAudio context may already be usable.
      if (ctxReady) {
        audioUnlocked = true;
        _status("TTS gotowe");
        console.warn("voice html audio unlock failed; using webaudio", err);
      } else {
        audioUnlocked = false;
        _status(`Autoplay blocked (${err?.name || "error"}) - kliknij TTS ponownie`);
        console.warn("voice tts unlock failed", err);
      }
    }
  }

  async function _tryUnlockFromUserGesture() {
    if (!ttsEnabled || audioUnlocked) return;
    await _unlockAudioFromGesture();
    if (audioUnlocked && pendingSpeakText) {
      const queued = pendingSpeakText;
      pendingSpeakText = "";
      await speakGMText(queued);
    }
  }

  function _isHttps() {
    return window.location.protocol === "https:";
  }

  function _voiceEndpoint(path) {
    return path.startsWith("/") ? path : `/${path}`;
  }

  function _wsUrl() {
    const proto = _isHttps() ? "wss" : "ws";
    return `${proto}://${window.location.host}/voice/stt`;
  }

  function _getFlag(key, defaultValue) {
    const val = localStorage.getItem(key);
    if (val === null) return defaultValue;
    return val === "1";
  }

  function _setFlag(key, value) {
    localStorage.setItem(key, value ? "1" : "0");
  }

  function _emitTtsState() {
    window.dispatchEvent(
      new CustomEvent("voice-tts-state", {
        detail: { enabled: !!ttsEnabled },
      })
    );
  }

  function sanitizeGMText(text) {
    return String(text || "")
      .split("\n")
      .filter((line) => !/^\s*\[ROLL:[^\]]*\]\s*$/i.test(line))
      .join("\n")
      .trim();
  }

  function _syncUiState() {
    const ttsBtn = _el("tts-toggle");
    const sttBtn = _el("stt-toggle");
    const sttInputMicBtn = _el("stt-input-mic");
    if (!ttsBtn) return;

    ttsBtn.classList.toggle("is-active", ttsEnabled);
    ttsBtn.setAttribute("aria-pressed", ttsEnabled ? "true" : "false");
    if (sttBtn) {
      sttBtn.classList.toggle("is-active", sttEnabled);
      sttBtn.setAttribute("aria-pressed", sttEnabled ? "true" : "false");
    }
    if (sttInputMicBtn) {
      sttInputMicBtn.classList.toggle("is-active", sttEnabled);
      sttInputMicBtn.setAttribute("aria-pressed", sttEnabled ? "true" : "false");
    }
  }

  function setAvailability(enabled, reason = "") {
    available = !!enabled;
    const ttsBtn = _el("tts-toggle");
    const sttBtn = _el("stt-toggle");
    const sttInputMicBtn = _el("stt-input-mic");
    if (ttsBtn) ttsBtn.disabled = !available;
    if (sttBtn) sttBtn.disabled = !available;
    if (sttInputMicBtn) sttInputMicBtn.disabled = !available;
    _status(available ? "" : reason || "Glos chwilowo niedostepny");
  }

  function stopPlayback() {
    if (activeBufferSource) {
      try {
        activeBufferSource.stop();
      } catch (_e) {
        // noop
      }
      activeBufferSource = null;
    }
    if (!audio) return;
    try {
      suppressAudioError = true;
      isPlaying = false;
      audio.pause();
      if (audio.dataset.blobUrl && audio.dataset.blobUrl.startsWith("blob:")) {
        URL.revokeObjectURL(audio.dataset.blobUrl);
        audio.dataset.blobUrl = "";
      }
      audio.src = "";
    } catch (_e) {
      // noop
    } finally {
      // Keep the element; we only reset its source.
      setTimeout(() => {
        suppressAudioError = false;
      }, 0);
    }
  }

  async function speakGMText(text) {
    if (!available || !ttsEnabled) return;
    const clean = sanitizeGMText(text);
    if (!clean) return;

    try {
      if (!audioUnlocked) {
        pendingSpeakText = clean;
        _status("Tapnij ekran, aby odblokowac audio");
        return;
      }
      pendingSpeakText = "";
      stopPlayback();
      const url = `${_voiceEndpoint("/voice/tts")}?text=${encodeURIComponent(clean)}`;
      const resp = await fetch(url, { method: "GET" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      if (_isIosWebkit()) {
        const ctx = _ensureAudioContext();
        if (ctx) {
          if (ctx.state !== "running") await ctx.resume();
          const arr = await resp.arrayBuffer();
          const decoded = await ctx.decodeAudioData(arr.slice(0));
          const src = ctx.createBufferSource();
          src.buffer = decoded;
          src.connect(ctx.destination);
          src.onended = () => {
            isPlaying = false;
            activeBufferSource = null;
          };
          activeBufferSource = src;
          _status("Czytam...");
          isPlaying = true;
          src.start(0);
          return;
        }
      }

      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = _ensureAudio();
      a.dataset.blobUrl = blobUrl;
      a.src = blobUrl;
      _status("Czytam...");
      isPlaying = true;
      await a.play();
    } catch (err) {
      isPlaying = false;
      _status(`Brak odtwarzania (${err?.name || "error"})`);
      console.warn("voice tts failed", err);
    }
  }

  async function setTtsEnabled(next, opts = {}) {
    const enabled = !!next;
    const unlock = !!opts.unlock;
    ttsEnabled = enabled;
    _setFlag(LS_TTS, enabled);
    _syncUiState();
    _emitTtsState();
    if (enabled && unlock) {
      _status("TTS wlaczone");
      await _tryUnlockFromUserGesture();
    } else if (enabled) {
      _status("TTS wlaczone");
    }
    if (!enabled) {
      stopPlayback();
      _status("TTS wylaczone");
    }
  }

  function isTtsEnabled() {
    return !!ttsEnabled;
  }

  function getPlaybackState() {
    return { isPlaying: !!isPlaying };
  }

  async function speakNowFromUserGesture(text) {
    if (!ttsEnabled) {
      await setTtsEnabled(true, { unlock: true });
    } else if (!audioUnlocked) {
      await _unlockAudioFromGesture();
    }
    await speakGMText(text);
  }

  function _clearSttCloseTimer() {
    if (sttCloseTimer) {
      clearTimeout(sttCloseTimer);
      sttCloseTimer = null;
    }
  }

  function _scheduleSttWebSocketClose() {
    const socket = ws;
    if (!socket) return;
    _clearSttCloseTimer();
    // Serwer dokleja bufory ~2 s po ostatnim chunku — nie zamykamy socketa od razu
    // i nie zerujemy `ws`, żeby `onmessage` mogło przyjąć JSON z transkrypcją.
    sttCloseTimer = setTimeout(() => {
      sttCloseTimer = null;
      try {
        if (socket.readyState === WebSocket.OPEN) {
          socket.close();
        }
      } catch (_e) {
        /* noop */
      }
      if (ws === socket) ws = null;
      if (sttResultPending) {
        sttResultPending = false;
        _status("STT timeout: brak odpowiedzi");
      }
    }, 30000);
  }

  function _stopSttLevelMonitor() {
    if (sttMonitorRaf) {
      cancelAnimationFrame(sttMonitorRaf);
      sttMonitorRaf = 0;
    }
    if (sttMonitorSource) {
      try {
        sttMonitorSource.disconnect();
      } catch (_e) {
        // noop
      }
      sttMonitorSource = null;
    }
    if (sttMonitorAnalyser) {
      try {
        sttMonitorAnalyser.disconnect();
      } catch (_e) {
        // noop
      }
      sttMonitorAnalyser = null;
    }
    if (sttMonitorCtx) {
      try {
        sttMonitorCtx.close();
      } catch (_e) {
        // noop
      }
      sttMonitorCtx = null;
    }
  }

  function _clearSttHardStopTimer() {
    if (sttHardStopTimer) {
      clearTimeout(sttHardStopTimer);
      sttHardStopTimer = null;
    }
  }

  function _startSttLevelMonitor(stream) {
    _stopSttLevelMonitor();
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    try {
      sttMonitorCtx = new Ctx();
      sttMonitorAnalyser = sttMonitorCtx.createAnalyser();
      sttMonitorAnalyser.fftSize = 2048;
      sttMonitorSource = sttMonitorCtx.createMediaStreamSource(stream);
      sttMonitorSource.connect(sttMonitorAnalyser);
      sttLastVoiceAt = Date.now();
      sttStartedAt = sttLastVoiceAt;
      sttAutoStopping = false;
      sttNoiseFloorRms = 0.004;
      sttHadSpeech = false;

      const buf = new Float32Array(sttMonitorAnalyser.fftSize);
      const tick = () => {
        if (!mediaRecorder || !sttEnabled || sttAutoStopping) return;
        sttMonitorAnalyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i += 1) {
          sum += buf[i] * buf[i];
        }
        const rms = Math.sqrt(sum / buf.length);
        const now = Date.now();
        const adaptiveThreshold = Math.max(
          STT_MIN_VOICE_RMS_THRESHOLD,
          sttNoiseFloorRms * STT_NOISE_MULTIPLIER
        );
        const isSpeech = rms >= adaptiveThreshold;
        if (isSpeech) {
          sttLastVoiceAt = now;
          sttHadSpeech = true;
        } else {
          // Aktualizujemy tło tylko gdy nie wykryto mowy.
          sttNoiseFloorRms = sttNoiseFloorRms * 0.92 + rms * 0.08;
        }

        // Auto-stop dopiero po realnym wykryciu mowy (nie od samego startu nagrywania).
        if (sttHadSpeech && !isSpeech && now - sttLastVoiceAt >= STT_SILENCE_AUTO_STOP_MS) {
          sttAutoStopping = true;
          _status("Cisza 2s - zatrzymuje nasluch");
          sttEnabled = false;
          _setFlag(LS_STT, false);
          _syncUiState();
          stopRecording();
          return;
        }

        // Fallback: jeśli szum otoczenia stale wygląda jak "mowa", zamknij po czasie.
        if (now - sttStartedAt >= STT_MAX_RECORDING_MS) {
          sttAutoStopping = true;
          _status("Auto-stop po limicie czasu");
          sttEnabled = false;
          _setFlag(LS_STT, false);
          _syncUiState();
          stopRecording();
          return;
        }
        sttMonitorRaf = requestAnimationFrame(tick);
      };
      sttMonitorRaf = requestAnimationFrame(tick);
    } catch (err) {
      console.warn("voice stt monitor start failed", err);
      _stopSttLevelMonitor();
    }
  }

  function _attachSttWebSocketHandlers() {
    if (!ws) return;
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        const sock = ws;
        if (payload && payload.error) {
          sttResultPending = false;
          _status(`STT error: ${payload.error}`);
          _clearSttCloseTimer();
          setTimeout(() => {
            try {
              sock?.close();
            } catch (_e) {
              /* noop */
            }
            if (ws === sock) ws = null;
          }, 200);
          return;
        }
        if (payload && Object.prototype.hasOwnProperty.call(payload, "text")) {
          sttResultPending = false;
          const txt = String(payload.text || "").trim();
          if (txt) {
            handleTranscript(txt);
            _status("Transkrypcja gotowa");
          } else {
            _status("STT: pusty wynik (glosniej / inny mikrofon?)");
          }
          _clearSttCloseTimer();
          setTimeout(() => {
            try {
              sock?.close();
            } catch (_e) {
              /* noop */
            }
            if (ws === sock) ws = null;
          }, 200);
        }
      } catch (err) {
        console.warn("voice stt parse failed", err);
      }
    };
  }

  function handleTranscript(text) {
    const inputEl = _el("input");
    if (!inputEl) return;
    const value = String(text || "").trim();
    if (!value) return;
    inputEl.value = value;
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
    inputEl.focus();

    _el("send-btn")?.click();
  }

  async function startRecording() {
    if (!available) return;
    const sttBtn = _el("stt-toggle");
    const sttInputMicBtn = _el("stt-input-mic");
    if (!sttEnabled) return;
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      setAvailability(false, "STT niedostepne w tej przegladarce");
      return;
    }
    if (mediaRecorder) return;

    try {
      _clearSttCloseTimer();
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        try {
          ws.close();
        } catch (_e) {
          /* noop */
        }
        ws = null;
      }

      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _startSttLevelMonitor(mediaStream);
      _clearSttHardStopTimer();
      // Hard fallback for browsers where analyser-based silence detection is unreliable.
      sttHardStopTimer = setTimeout(() => {
        if (!mediaRecorder || !sttEnabled) return;
        sttAutoStopping = true;
        _status("Auto-stop po limicie czasu");
        sttEnabled = false;
        _setFlag(LS_STT, false);
        _syncUiState();
        stopRecording();
      }, STT_MAX_RECORDING_MS);

      await new Promise((resolve, reject) => {
        const socket = new WebSocket(_wsUrl());
        ws = socket;
        const failTimer = setTimeout(() => reject(new Error("STT websocket timeout")), 15000);
        let opened = false;
        socket.onopen = () => {
          opened = true;
          clearTimeout(failTimer);
          resolve();
        };
        socket.onclose = () => {
          if (ws === socket) ws = null;
          if (sttResultPending) {
            sttResultPending = false;
            _status("STT zakonczone bez wyniku");
          }
        };
        socket.onerror = () => {
          clearTimeout(failTimer);
          if (!opened) reject(new Error("STT websocket error"));
          else {
            _status("Blad websocket STT");
            stopRecording();
          }
        };
        _attachSttWebSocketHandlers();
      });

      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac"];
      let mime;
      for (let i = 0; i < mimeCandidates.length; i += 1) {
        if (MediaRecorder.isTypeSupported(mimeCandidates[i])) {
          mime = mimeCandidates[i];
          break;
        }
      }
      mediaRecorder = mime
        ? new MediaRecorder(mediaStream, { mimeType: mime })
        : new MediaRecorder(mediaStream);
      mediaRecorder.ondataavailable = (evt) => {
        if (evt.data && evt.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(evt.data);
        }
      };
      mediaRecorder.start(350);
      sttBtn?.classList.add("is-recording");
      sttInputMicBtn?.classList.add("is-recording");
      _status("Nagrywanie...");
    } catch (err) {
      console.warn("voice stt start failed", err);
      sttResultPending = false;
      _clearSttCloseTimer();
      try {
        ws?.close();
      } catch (_e) {
        /* noop */
      }
      ws = null;
      if (String(err?.message || err).includes("websocket")) {
        _status("Brak polaczenia STT (websocket)");
      } else {
        _status("Brak dostepu do mikrofonu");
      }
      stopRecording();
    }
  }

  function stopRecording() {
    const sttBtn = _el("stt-toggle");
    const sttInputMicBtn = _el("stt-input-mic");
    if (!sttEnabled) sttResultPending = false;

    _stopSttLevelMonitor();
    _clearSttHardStopTimer();
    sttAutoStopping = false;

    const afterRecorderFullyStopped = () => {
      if (mediaStream) {
        mediaStream.getTracks().forEach((t) => t.stop());
        mediaStream = null;
      }
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          // Tell backend to flush buffered chunks immediately instead of waiting for timeout.
          ws.send("__end__");
        } catch (_e) {
          /* noop */
        }
      }
      sttResultPending = true;
      _scheduleSttWebSocketClose();
      sttBtn?.classList.remove("is-recording");
      sttInputMicBtn?.classList.remove("is-recording");
      const waitingForResult =
        !!ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING);
      if (waitingForResult) {
        _status("Przetwarzanie STT...");
      } else if (sttEnabled) {
        _status("Gotowe");
      } else {
        _status("Nasluch wylaczony");
      }
    };

    if (mediaRecorder) {
      const rec = mediaRecorder;
      mediaRecorder = null;
      try {
        if (rec.state !== "inactive") {
          rec.addEventListener(
            "stop",
            () => {
              afterRecorderFullyStopped();
            },
            { once: true }
          );
          rec.requestData?.();
          rec.stop();
          return;
        }
      } catch (_e) {
        /* fall through — zatrzymaj jak resztę bez nagrywania */
      }
    }

    afterRecorderFullyStopped();
  }

  function _patchAddMessageHook() {
    if (window.__voiceAddMessagePatched) return;
    const original = window.addMessage;
    if (typeof original !== "function") return;

    window.addMessage = function patchedAddMessage(message, ...rest) {
      const result = original.call(this, message, ...rest);
      try {
        const role = String(message?.role || "").toLowerCase();
        const text = message?.content || message?.text || "";
        if (role === "assistant" || role === "gm") {
          speakGMText(text);
        }
      } catch (err) {
        console.warn("voice hook failed", err);
      }
      return result;
    };
    window.__voiceAddMessagePatched = true;
  }

  async function init() {
    if (initialized) return;
    initialized = true;

    const ttsBtn = _el("tts-toggle");
    const sttBtn = _el("stt-toggle");
    const sttInputMicBtn = _el("stt-input-mic");
    if (!ttsBtn || !_el("input")) return;

    if (localStorage.getItem(LS_TTS) === null) _setFlag(LS_TTS, true);
    if (localStorage.getItem(LS_STT) === null) _setFlag(LS_STT, false);
    if (localStorage.getItem(LS_STT_AUTOSEND) === null) _setFlag(LS_STT_AUTOSEND, true);
    ttsEnabled = _getFlag(LS_TTS, true);
    sttEnabled = _getFlag(LS_STT, false);
    _syncUiState();

    if (!navigator.mediaDevices || !window.MediaRecorder) {
      if (sttBtn) sttBtn.disabled = true;
      if (sttInputMicBtn) sttInputMicBtn.disabled = true;
      _status("STT niedostepne w tej przegladarce");
    }

    ttsBtn.addEventListener("click", () => {
      const next = !ttsEnabled;
      void setTtsEnabled(next, { unlock: next });
    });

    const onAnyGesture = () => {
      void _tryUnlockFromUserGesture();
    };
    document.addEventListener("touchend", onAnyGesture, { passive: true });
    document.addEventListener("pointerup", onAnyGesture, { passive: true });
    document.addEventListener("click", onAnyGesture, { passive: true });

    const toggleStt = async () => {
      const next = !sttEnabled;
      sttEnabled = next;
      _setFlag(LS_STT, next);
      _syncUiState();
      if (next) await startRecording();
      else stopRecording();
    };
    if (sttBtn) {
      sttBtn.addEventListener("click", () => {
        void toggleStt();
      });
    }
    if (sttInputMicBtn) {
      sttInputMicBtn.addEventListener("click", () => {
        void toggleStt();
      });
    }

    _patchAddMessageHook();

    try {
      const resp = await fetch(_voiceEndpoint("/voice/healthz"));
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setAvailability(true);
    } catch (_err) {
      setAvailability(false, "Glos chwilowo niedostepny");
    }
  }

  window.voiceUI = {
    init,
    speakGMText,
    speakNowFromUserGesture,
    stopPlayback,
    startRecording,
    stopRecording,
    setAvailability,
    setTtsEnabled,
    isTtsEnabled,
    getPlaybackState,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.voiceUI.init());
  } else {
    window.voiceUI.init();
  }
})();
