// F-72 (#1267) Głos w ŻAR — port protokołu z frontend/front/js/voice.js.
// „Nie przepisuj protokołu — owiń": zachowana logika TTS (GET /voice/tts, unlock
// audio z gestu, iOS WebKit decode), STT (WS /voice/stt + MediaRecorder + auto-stop
// na ciszy) oraz health/config. Różnica: zero DOM getElementById — stan wychodzi
// przez subskrypcję (React hook useVoice), a transkrypcja przez callback onTranscript.
//
// Endpointy głosu żyją pod /voice/* (poza /api) — nginx routuje je do backendu tak
// samo dla /graj/ jak dla starego frontu, więc używamy ścieżek względem hosta.

const LS_TTS = "voice_tts_enabled";
const LS_STT_AUTOSEND = "voice_stt_autosend";

const STT_SILENCE_AUTO_STOP_MS = 2000;
const STT_START_GRACE_MS = 800;
const STT_MIN_VOICE_RMS_THRESHOLD = 0.01;
const STT_NOISE_MULTIPLIER = 2.0;

export interface VoiceState {
  /** Usługa głosu online (healthz) i włączona globalnie (config admina). */
  available: boolean;
  /** Blokada z panelu admina — gracz nie może włączyć tego, co admin wyłączył. */
  ttsLocked: boolean;
  sttLocked: boolean;
  ttsEnabled: boolean;
  sttEnabled: boolean;
  /** Po transkrypcji od razu wyślij akcję (autosend). */
  autosend: boolean;
  /** TTS aktualnie czyta (overlay „Czytam…"). */
  playing: boolean;
  /** STT nagrywa (mic w composerze pulsuje). */
  recording: boolean;
  /** Krótki komunikat statusu (debug ciszy / błędy). */
  status: string;
}

type Listener = (s: VoiceState) => void;

function getFlag(key: string, def: boolean): boolean {
  const v = localStorage.getItem(key);
  if (v === null) return def;
  return v === "1";
}
function setFlag(key: string, value: boolean) {
  localStorage.setItem(key, value ? "1" : "0");
}
function isIosWebkit(): boolean {
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  const touchMac = platform === "MacIntel" && navigator.maxTouchPoints > 1;
  return /iPad|iPhone|iPod/i.test(ua) || touchMac;
}
function isHttps(): boolean {
  return window.location.protocol === "https:";
}
function wsUrl(): string {
  const proto = isHttps() ? "wss" : "ws";
  return `${proto}://${window.location.host}/voice/stt`;
}

// Tnij wiersze [ROLL:...] — narrator TTS nie ma czytać znaczników mechaniki.
function sanitizeGMText(text: string): string {
  return String(text || "")
    .split("\n")
    .filter((line) => !/^\s*\[ROLL:[^\]]*\]\s*$/i.test(line))
    .join("\n")
    .trim();
}

class VoiceController {
  private listeners = new Set<Listener>();
  private state: VoiceState = {
    available: true,
    ttsLocked: false,
    sttLocked: false,
    ttsEnabled: getFlag(LS_TTS, true),
    sttEnabled: false,
    autosend: getFlag(LS_STT_AUTOSEND, true),
    playing: false,
    recording: false,
    status: "",
  };

  /** Callback dostarczający transkrypcję do composera (ustawiany przez useVoice). */
  onTranscript: ((text: string, autosend: boolean) => void) | null = null;

  private initialized = false;
  // TTS
  private audio: HTMLAudioElement | null = null;
  private audioCtx: AudioContext | null = null;
  private activeBufferSource: AudioBufferSourceNode | null = null;
  private pendingSpeakText = "";
  private suppressAudioError = false;
  private audioUnlocked = false;
  private unlocking = false;
  // STT
  private mediaRecorder: MediaRecorder | null = null;
  private mediaStream: MediaStream | null = null;
  private ws: WebSocket | null = null;
  private sttCloseTimer: ReturnType<typeof setTimeout> | null = null;
  private sttResultPending = false;
  private monitorCtx: AudioContext | null = null;
  private monitorSource: MediaStreamAudioSourceNode | null = null;
  private monitorAnalyser: AnalyserNode | null = null;
  private monitorRaf = 0;
  private lastVoiceAt = 0;
  private startedAt = 0;
  private autoStopping = false;
  private noiseFloorRms = 0;
  private hadSpeech = false;
  private debugLastRenderAt = 0;

  // ── subskrypcja ────────────────────────────────────────────────────────────
  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    fn(this.state);
    return () => this.listeners.delete(fn);
  }
  getState(): VoiceState {
    return this.state;
  }
  private set(patch: Partial<VoiceState>) {
    this.state = { ...this.state, ...patch };
    for (const fn of this.listeners) fn(this.state);
  }
  private status(text: string) {
    this.set({ status: String(text || "") });
  }

  // ── TTS ──────────────────────────────────────────────────────────────────
  private ensureAudioContext(): AudioContext | null {
    if (this.audioCtx) return this.audioCtx;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    this.audioCtx = new Ctx();
    return this.audioCtx;
  }
  private ensureAudio(): HTMLAudioElement {
    if (this.audio) return this.audio;
    const a = new Audio();
    a.preload = "auto";
    a.setAttribute("playsinline", "true");
    a.onended = () => {
      this.set({ playing: false });
      this.stopPlayback();
    };
    a.onerror = () => {
      if (!this.state.playing || this.suppressAudioError) return;
      this.status("Błąd odtwarzania audio");
      this.stopPlayback();
    };
    this.audio = a;
    return a;
  }

  // Safari wymaga play() w synchronicznej ramce gestu — ta funkcja NIE jest async.
  private unlockAudioFromGesture() {
    const a = this.ensureAudio();
    a.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=";
    a.volume = 0;
    const playPromise = a.play();

    const ctx = this.ensureAudioContext();
    if (ctx && ctx.state !== "running") ctx.resume().catch(() => {});

    const onUnlocked = () => {
      try {
        a.pause();
        a.currentTime = 0;
      } catch {
        /* noop */
      }
      a.volume = 1;
      this.unlocking = false;
      this.audioUnlocked = true;
      if (this.pendingSpeakText) {
        const queued = this.pendingSpeakText;
        this.pendingSpeakText = "";
        void this.speak(queued);
      }
    };
    const onFailed = (err: unknown) => {
      a.volume = 1;
      this.unlocking = false;
      this.audioUnlocked = false;
      this.status(`Autoplay zablokowany — dotknij ekranu`);
      console.warn("voice tts unlock failed", err);
    };
    if (playPromise && typeof playPromise.then === "function") {
      playPromise.then(onUnlocked).catch(onFailed);
    } else {
      onUnlocked();
    }
  }
  /** Odblokuj audio z gestu użytkownika (dotyk/klik) — Safari autoplay policy. */
  unlockFromGesture() {
    if (!this.state.ttsEnabled || this.audioUnlocked || this.unlocking) return;
    this.unlocking = true;
    this.unlockAudioFromGesture();
  }

  stopPlayback() {
    if (this.activeBufferSource) {
      try {
        this.activeBufferSource.stop();
      } catch {
        /* noop */
      }
      this.activeBufferSource = null;
    }
    if (!this.audio) return;
    try {
      this.suppressAudioError = true;
      this.set({ playing: false });
      this.audio.pause();
      const blobUrl = this.audio.dataset.blobUrl;
      if (blobUrl && blobUrl.startsWith("blob:")) {
        setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
        this.audio.dataset.blobUrl = "";
      }
    } catch {
      /* noop */
    } finally {
      setTimeout(() => {
        this.suppressAudioError = false;
      }, 0);
    }
  }

  async speak(text: string) {
    if (!this.state.available || !this.state.ttsEnabled) return;
    const clean = sanitizeGMText(String(text || ""));
    if (!clean) return;
    try {
      if (!this.audioUnlocked) {
        this.pendingSpeakText = clean;
        this.status("Dotknij ekranu, aby odblokować audio");
        return;
      }
      this.pendingSpeakText = "";
      this.stopPlayback();
      const url = `/voice/tts?text=${encodeURIComponent(clean)}`;
      const resp = await fetch(url, { method: "GET" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      if (isIosWebkit()) {
        const ctx = this.ensureAudioContext();
        if (ctx) {
          if (ctx.state !== "running") await ctx.resume();
          const arr = await resp.arrayBuffer();
          const decoded = await ctx.decodeAudioData(arr.slice(0));
          const src = ctx.createBufferSource();
          src.buffer = decoded;
          src.connect(ctx.destination);
          src.onended = () => {
            this.set({ playing: false });
            this.activeBufferSource = null;
          };
          this.activeBufferSource = src;
          this.status("Czytam…");
          this.set({ playing: true });
          src.start(0);
          return;
        }
      }

      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = this.ensureAudio();
      a.muted = false;
      a.volume = 1;
      a.dataset.blobUrl = blobUrl;
      a.src = blobUrl;
      this.status("Czytam…");
      this.set({ playing: true });
      await a.play();
    } catch (err) {
      this.set({ playing: false });
      this.status(`Brak odtwarzania`);
      console.warn("voice tts failed", err);
      if (this.audio) {
        try {
          this.audio.muted = false;
          this.audio.volume = 1;
          this.audio.load();
        } catch {
          /* noop */
        }
      }
    }
  }

  setTtsEnabled(next: boolean, opts: { unlock?: boolean } = {}) {
    const enabled = !!next;
    this.set({ ttsEnabled: enabled });
    setFlag(LS_TTS, enabled);
    if (enabled && opts.unlock) {
      this.status("TTS włączone");
      this.unlockFromGesture();
    } else if (enabled) {
      this.status("TTS włączone");
    } else {
      this.stopPlayback();
      this.status("TTS wyłączone");
    }
  }
  setAutosend(next: boolean) {
    this.set({ autosend: !!next });
    setFlag(LS_STT_AUTOSEND, !!next);
  }

  // ── STT ──────────────────────────────────────────────────────────────────
  private clearSttCloseTimer() {
    if (this.sttCloseTimer) {
      clearTimeout(this.sttCloseTimer);
      this.sttCloseTimer = null;
    }
  }
  private scheduleSttWebSocketClose() {
    const socket = this.ws;
    if (!socket) return;
    this.clearSttCloseTimer();
    // Serwer dokleja bufory ~2 s po ostatnim chunku — nie zamykamy socketa od razu.
    this.sttCloseTimer = setTimeout(() => {
      this.sttCloseTimer = null;
      try {
        if (socket.readyState === WebSocket.OPEN) socket.close();
      } catch {
        /* noop */
      }
      if (this.ws === socket) this.ws = null;
      if (this.sttResultPending) {
        this.sttResultPending = false;
        this.status("STT timeout: brak odpowiedzi");
      }
    }, 30000);
  }
  private stopLevelMonitor() {
    if (this.monitorRaf) {
      cancelAnimationFrame(this.monitorRaf);
      this.monitorRaf = 0;
    }
    for (const node of [this.monitorSource, this.monitorAnalyser]) {
      try {
        node?.disconnect();
      } catch {
        /* noop */
      }
    }
    this.monitorSource = null;
    this.monitorAnalyser = null;
    if (this.monitorCtx) {
      try {
        this.monitorCtx.close();
      } catch {
        /* noop */
      }
      this.monitorCtx = null;
    }
  }
  private startLevelMonitor(stream: MediaStream) {
    this.stopLevelMonitor();
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    try {
      this.monitorCtx = new Ctx();
      this.monitorAnalyser = this.monitorCtx.createAnalyser();
      this.monitorAnalyser.fftSize = 2048;
      this.monitorSource = this.monitorCtx.createMediaStreamSource(stream);
      this.monitorSource.connect(this.monitorAnalyser);
      this.lastVoiceAt = Date.now();
      this.startedAt = this.lastVoiceAt;
      this.autoStopping = false;
      this.noiseFloorRms = 0.004;
      this.hadSpeech = false;
      this.debugLastRenderAt = 0;

      const buf = new Float32Array(this.monitorAnalyser.fftSize);
      const tick = () => {
        if (!this.mediaStream || !this.state.sttEnabled || this.autoStopping) return;
        this.monitorAnalyser!.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i += 1) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / buf.length);
        const now = Date.now();
        const adaptiveThreshold = Math.max(
          STT_MIN_VOICE_RMS_THRESHOLD,
          this.noiseFloorRms * STT_NOISE_MULTIPLIER,
        );
        const isSpeech = rms >= adaptiveThreshold;
        if (isSpeech) {
          this.lastVoiceAt = now;
          this.hadSpeech = true;
        } else {
          this.noiseFloorRms = this.noiseFloorRms * 0.92 + rms * 0.08;
        }
        const silenceMs = now - this.lastVoiceAt;
        const gracePassed = now - this.startedAt >= STT_START_GRACE_MS;
        if (gracePassed && this.hadSpeech && !isSpeech && silenceMs >= STT_SILENCE_AUTO_STOP_MS) {
          this.autoStopping = true;
          this.status("Cisza 2s — zatrzymuję nasłuch");
          this.set({ sttEnabled: false });
          this.stopRecording();
          return;
        }
        if (now - this.debugLastRenderAt >= 200) {
          this.debugLastRenderAt = now;
          const lvl = (rms * 100).toFixed(1);
          this.status(
            this.hadSpeech
              ? `Nagrywanie… (${lvl})`
              : `Nagrywanie… czekam na głos`,
          );
        }
        this.monitorRaf = requestAnimationFrame(tick);
      };
      this.monitorRaf = requestAnimationFrame(tick);
    } catch (err) {
      console.warn("voice stt monitor start failed", err);
      this.stopLevelMonitor();
    }
  }
  private attachSttHandlers() {
    if (!this.ws) return;
    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(String((event as MessageEvent).data) || "{}");
        const sock = this.ws;
        if (payload && payload.error) {
          this.sttResultPending = false;
          this.status(`STT error: ${payload.error}`);
          this.clearSttCloseTimer();
          setTimeout(() => {
            try {
              sock?.close();
            } catch {
              /* noop */
            }
            if (this.ws === sock) this.ws = null;
          }, 200);
          return;
        }
        if (payload && Object.prototype.hasOwnProperty.call(payload, "text")) {
          this.sttResultPending = false;
          const txt = String(payload.text || "").trim();
          if (txt) {
            this.onTranscript?.(txt, this.state.autosend);
            this.status("Transkrypcja gotowa");
          } else {
            this.status("STT: pusty wynik");
          }
          this.clearSttCloseTimer();
          setTimeout(() => {
            try {
              sock?.close();
            } catch {
              /* noop */
            }
            if (this.ws === sock) this.ws = null;
          }, 200);
        }
      } catch (err) {
        console.warn("voice stt parse failed", err);
      }
    };
  }

  private async startRecording() {
    if (!this.state.available || !this.state.sttEnabled) return;
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      this.set({ available: false });
      this.status("STT niedostępne w tej przeglądarce");
      return;
    }
    if (this.mediaRecorder) return;
    try {
      this.status("Łączę STT…");
      this.clearSttCloseTimer();
      if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
        try {
          this.ws.close();
        } catch {
          /* noop */
        }
        this.ws = null;
      }
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.startLevelMonitor(this.mediaStream);

      await new Promise<void>((resolve, reject) => {
        const socket = new WebSocket(wsUrl());
        this.ws = socket;
        const failTimer = setTimeout(() => reject(new Error("STT websocket timeout")), 15000);
        let opened = false;
        socket.onopen = () => {
          opened = true;
          clearTimeout(failTimer);
          resolve();
        };
        socket.onclose = () => {
          if (this.ws === socket) this.ws = null;
          if (this.sttResultPending) {
            this.sttResultPending = false;
            this.status("STT zakończone bez wyniku");
          }
        };
        socket.onerror = () => {
          clearTimeout(failTimer);
          if (!opened) reject(new Error("STT websocket error"));
          else {
            this.status("Błąd websocket STT");
            this.stopRecording();
          }
        };
        this.attachSttHandlers();
      });

      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac"];
      let mime: string | undefined;
      for (const c of mimeCandidates) {
        if (MediaRecorder.isTypeSupported(c)) {
          mime = c;
          break;
        }
      }
      this.mediaRecorder = mime
        ? new MediaRecorder(this.mediaStream, { mimeType: mime })
        : new MediaRecorder(this.mediaStream);
      this.mediaRecorder.ondataavailable = (evt) => {
        if (evt.data && evt.data.size > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(evt.data);
        }
      };
      this.mediaRecorder.start(350);
      this.set({ recording: true });
      this.status("Nagrywanie…");
    } catch (err) {
      console.warn("voice stt start failed", err);
      const msg = String((err as Error)?.message || err).includes("websocket")
        ? "Brak połączenia STT"
        : "Brak dostępu do mikrofonu";
      this.sttResultPending = false;
      this.stopLevelMonitor();
      this.clearSttCloseTimer();
      if (this.mediaRecorder) {
        try {
          this.mediaRecorder.stop();
        } catch {
          /* noop */
        }
      }
      this.mediaRecorder = null;
      this.mediaStream?.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
      try {
        this.ws?.close();
      } catch {
        /* noop */
      }
      this.ws = null;
      this.set({ sttEnabled: false, recording: false });
      this.status(msg);
    }
  }

  private stopRecording() {
    if (!this.state.sttEnabled) this.sttResultPending = false;
    this.stopLevelMonitor();
    this.autoStopping = false;

    const finish = () => {
      this.mediaStream?.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send("__end__");
        } catch {
          /* noop */
        }
      }
      this.sttResultPending = true;
      this.scheduleSttWebSocketClose();
      this.set({ recording: false });
      const waiting =
        !!this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING);
      this.status(waiting ? "Przetwarzanie STT…" : "Nasłuch wyłączony");
    };

    if (this.mediaRecorder) {
      const rec = this.mediaRecorder;
      this.mediaRecorder = null;
      try {
        if (rec.state !== "inactive") {
          rec.addEventListener("stop", () => finish(), { once: true });
          rec.requestData?.();
          rec.stop();
          return;
        }
      } catch {
        /* fall through */
      }
    }
    finish();
  }

  /** Przełącz nasłuch STT (mic w composerze / przycisk w menu). */
  async toggleStt() {
    if (this.state.sttLocked || !this.state.available) return;
    const next = !this.state.sttEnabled;
    this.set({ sttEnabled: next });
    if (next) {
      // Nie nagrywaj i nie czytaj jednocześnie.
      this.stopPlayback();
      this.pendingSpeakText = "";
      await this.startRecording();
    } else {
      this.stopRecording();
    }
  }

  // ── init (healthz + config admina) ─────────────────────────────────────────
  async init() {
    if (this.initialized) return;
    this.initialized = true;

    if (localStorage.getItem(LS_TTS) === null) setFlag(LS_TTS, true);
    if (localStorage.getItem(LS_STT_AUTOSEND) === null) setFlag(LS_STT_AUTOSEND, true);
    this.set({
      ttsEnabled: getFlag(LS_TTS, true),
      autosend: getFlag(LS_STT_AUTOSEND, true),
    });

    if (!navigator.mediaDevices || !window.MediaRecorder) {
      this.set({ sttLocked: true });
      this.status("STT niedostępne w tej przeglądarce");
    }

    // Odblokuj audio przy pierwszym geście (Safari autoplay).
    const onGesture = () => this.unlockFromGesture();
    document.addEventListener("touchend", onGesture, { passive: true });
    document.addEventListener("pointerup", onGesture, { passive: true });
    document.addEventListener("click", onGesture, { passive: true });

    try {
      const resp = await fetch("/voice/healthz");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this.set({ available: true });
    } catch {
      this.set({ available: false });
      this.status("Głos chwilowo niedostępny");
    }

    // Egzekwuj globalny on/off admina (fetch świeży za każdym init).
    try {
      const cfgResp = await fetch("/voice/config");
      if (cfgResp.ok) {
        const cfg = (await cfgResp.json()) as { tts_enabled?: boolean; stt_enabled?: boolean };
        const globalTts = cfg.tts_enabled !== false;
        const globalStt = cfg.stt_enabled !== false;
        if (!globalTts) this.set({ ttsEnabled: false, ttsLocked: true });
        if (!globalStt) this.set({ sttEnabled: false, sttLocked: true });
      }
    } catch {
      /* config nieosiągalny — zostaw preferencję lokalną */
    }
  }
}

export const voice = new VoiceController();
