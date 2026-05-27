# Voice Service — GPU Host Deployment (.16 / GTX 1660)

**Goal of this doc:** record how the AI-GM voice service (Piper TTS + faster-whisper STT) was deployed as a **standalone GPU instance** on host `192.168.1.16`, the host-recovery work it required, and exactly how to rebuild / verify / cut over to it later.

**Status (2026-05-26):** Deployed and verified standalone. **No cutover performed** — the game on `.61`/`.63` still uses its own voice instance. `.61` and `.63` were left untouched.

---

## 0. TL;DR

- Host `192.168.1.16` has a **GTX 1660 (6 GB)**. It now runs container **`ai-gm-voice-gpu`** on port **8300**, `restart: unless-stopped`, with **Whisper STT on CUDA** and **Piper TTS on CPU**.
- Build context lives on `.16` at `~/voice-service-gpu/` (source copy on the Claude VM at `/tmp/voice-gpu/`).
- Verified end-to-end: TTS produces a valid Polish WAV; Whisper transcribes it back on the GPU (`CT2_DEVICE: cuda`, `language: pl`, confidence 1.0).
- **Two host landmines were fixed and must stay fixed** (see §3): the kernel is **pinned to `6.17.0-23-generic`** (the `-29` kernel breaks the NIC), and NVIDIA modules are now built via **DKMS** (userspace `535.309.01`).

---

## 1. Why a separate GPU host

The game's existing voice service (on `.61`) runs Whisper STT on **CPU** (`device="cpu", compute_type="int8"`). `.16` has a spare GTX 1660, so STT can run on the GPU for much faster transcription. The intent is to eventually point the game at `.16`, but the first milestone was a **standalone, verified** instance with **no cutover** — zero risk to the running game.

---

## 2. Host access (NOT in the standard machine matrix)

| Field | Value |
|---|---|
| Host | `192.168.1.16` |
| User / pass | `piotrszmidt` / `Mousy66/temp` |
| SSH keys | **Not deployed** — use `sshpass -p 'Mousy66/temp' ssh ...` |
| sudo | Works with the same password (`echo 'Mousy66/temp' \| sudo -S ...`) |
| Other roles on box | Also runs tdarr / frigate / ollama (`:11434`) + a local `ai-gm` backend on `:8000`. Port **8300 was free**. |

`.16` is a multi-purpose box — treat changes conservatively.

---

## 3. Host recovery that this deployment required

Bringing the GPU online surfaced two **pre-existing** problems on `.16`. Both are now fixed; the notes below exist so a future kernel update or reinstall doesn't reintroduce them.

### 3.1 Broken `-29` kernel → kernel pinned to `-23`

`6.17.0-29-generic` is broken on this box in two ways:
- Its **`r8169` NIC driver fails to load** → the wired NIC (`enp34s0`, Realtek RTL8168) disappears and the host loses network on boot.
- Its **kernel headers are incomplete** (`/usr/src/linux-headers-6.17.0-29-generic/scripts/module.lds` missing) → out-of-tree module builds for `-29` fail.

**Fix — GRUB pinned to the known-good `-23`:**
```
# /etc/default/grub
GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-23-generic"
# then:
sudo update-grub
```
Verified: the box auto-boots `6.17.0-23-generic` and the NIC comes up unattended.
**Do not unpin** or let `-29` become default until that kernel's NIC + headers are fixed.

### 3.2 NVIDIA driver/library mismatch → switched to DKMS

After an apt upgrade, **userspace libs were `535.309.01`** but the **prebuilt kernel module was `535.288.01`** (`linux-modules-nvidia-535-<kernel>` lagged, and the old `535.288.01` userspace was already gone from the repo, so a downgrade was impossible). `nvidia-smi` reported *"Driver/library version mismatch."*

**Fix — build the module from source via DKMS so it matches userspace and auto-rebuilds on future kernels:**
```
sudo apt-get install -y dkms nvidia-dkms-535        # builds 535.309.01 for the running kernel
# remove the broken/redundant prebuilt -29 module packages to clean dpkg state:
sudo apt-get remove -y linux-modules-nvidia-535-6.17.0-29-generic \
                       linux-modules-nvidia-535-generic-hwe-24.04
sudo reboot                                          # loads the freshly built module
```
After reboot: `nvidia-smi` → `NVIDIA GeForce GTX 1660, 535.309.01, 6144 MiB`. ✅
DKMS now owns the nvidia module (`/lib/modules/<kernel>/updates/dkms/`), which takes precedence over any prebuilt package and rebuilds automatically on kernel updates.

---

## 4. The GPU image

Build context: `~/voice-service-gpu/` on `.16` (7 files: `Dockerfile`, `docker-compose.yml`, `config.json`, `main.py`, `tts.py`, `stt.py`, `config.py`). Only `stt.py`, the `Dockerfile`, and the compose file differ from the `.61` service.

**Key compatibility decisions (the GTX 1660 / sm_75 + cuDNN8 constraint):**

| Choice | Value | Why |
|---|---|---|
| Base image | `nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04` | Matches the host's NVIDIA 535 driver (native CUDA 12.2) and ships **cuDNN 8**. |
| CTranslate2 | `ctranslate2==4.4.0` | **Last 4.x line built against cuDNN 8** (4.5+ requires cuDNN 9). |
| faster-whisper | `1.0.3` | Accepts CT2 4.4.0. |
| STT compute type | `int8_float16` | Good speed/quality on the 6 GB sm_75 card. |
| Piper TTS | CPU (prebuilt `2023.11.14-2` x86_64 binary) | Upstream binary is CPU-only and fast enough. |

**`stt.py` GPU-awareness** (the one behavioral change vs `.61`): device is chosen by env (`STT_DEVICE`, default `cuda`; `STT_COMPUTE_TYPE`, default `int8_float16`). `_load_model()` **tries CUDA and falls back to CPU** on any init exception, so a driver issue degrades gracefully instead of hard-crashing.

**Models are baked into the image** (Whisper `small`+`tiny`, Polish Piper voices `darkman-medium`, `gosia-medium`, `bass-high`). Only `config.json` is bind-mounted (so `/voice/config` edits persist); host model dirs are intentionally **not** mounted, or they'd shadow the baked-in models.

`config.json` on this host uses `stt_model="small"` and `vad_filter=true` (vs `tiny`/false on `.61`).

---

## 5. Build / run / verify

```bash
# on .16, in ~/voice-service-gpu
docker compose build           # pulls CUDA base, pip-installs, prefetches all models
docker compose up -d

# health + GPU passthrough
docker ps --filter name=ai-gm-voice-gpu                    # → Up (healthy)
docker exec ai-gm-voice-gpu nvidia-smi --query-gpu=name,driver_version --format=csv,noheader

# TTS (note: URL-encode Polish text; use curl -G --data-urlencode)
curl -s -G http://localhost:8300/voice/tts \
  --data-urlencode "text=Witaj w świecie przygody, bohaterze" \
  --data-urlencode "voice=pl_PL-darkman-medium" -o /tmp/tts_ok.wav
file /tmp/tts_ok.wav            # → RIFF ... WAVE audio, 16 bit, mono 22050 Hz

# STT on GPU (decisive check)
docker cp /tmp/tts_ok.wav ai-gm-voice-gpu:/tmp/test.wav
docker exec ai-gm-voice-gpu python3 -c "
import stt
print('CT2_DEVICE:', stt.get_model().model.device)        # must print: cuda
print(stt.transcribe(open('/tmp/test.wav','rb').read()))   # → Polish transcript
"
```

**Verified result (2026-05-26):** `CT2_DEVICE: cuda`, transcript `'Witaj w świecie przygody, bohaterze.'`, `language: pl`, confidence 1.0.
(The `onnxruntime ... device_discovery` warning is harmless — inference uses CTranslate2/CUDA, not onnxruntime.)

### 5.1 Web test console

The service serves a self-contained test page at **`GET /voice/test`** (open `http://192.168.1.16:8300/voice/test` from any LAN browser). It's a single `test.html` baked into the image; `main.py` also enables permissive CORS (acceptable here — standalone LAN test host, not the game service).

The console covers:
- **Piper TTS** — Polish text box, voice dropdown (auto-filled from `/voice/voices`), speed slider; synthesizes + plays inline, shows latency/size, offers a WAV download. Quick A/B of voices and speeds by ear.
- **Whisper STT** — mic recorder that streams audio over the `/voice/stt` WebSocket to the GPU and shows transcript + language + confidence + round-trip time.
- **Runtime config** — live-edit `noise_scale` / `noise_w` (Piper timbre), Whisper model, and VAD → `POST /voice/config`.

> **Mic caveat:** browsers grant `getUserMedia` only in a secure context. TTS works over plain `http://<ip>:8300/voice/test`, but the STT recorder is blocked there. To use the mic, tunnel and open via localhost:
> ```
> ssh -L 8300:localhost:8300 piotrszmidt@192.168.1.16   # then open http://localhost:8300/voice/test
> ```

Scoped to the `.16` build context only (`~/voice-service-gpu/` + the `/tmp/voice-gpu` source); the `.61` game service and the committed repo are untouched.

### 5.2 HTTPS access via NPM (required for the mic)

Browsers grant `getUserMedia` only in a **secure context**, so the STT recorder needs HTTPS. Instead of a self-signed cert, front the service with **Nginx Proxy Manager** (`192.168.1.4`).

**NPM → Proxy Hosts → Add Proxy Host:**

| Tab | Field | Value |
|---|---|---|
| Details | Domain Names | e.g. `voice-gpu.studio-colorbox.com` (add DNS → NPM, like `aigm-dev`) |
| Details | Scheme | `http` |
| Details | Forward Hostname / IP | `192.168.1.16` |
| Details | Forward Port | `8300` |
| Details | **Websockets Support** | **ON** — required, the STT stream uses `/voice/stt` (WS) |
| Details | Block Common Exploits | on |
| SSL | SSL Certificate | Request a new Let's Encrypt cert |
| SSL | **Force SSL** | **ON** — this provides the secure context for the mic |

Leave the **Advanced** tab empty — the service already lives under `/voice/*`.

Then open **`https://voice-gpu.studio-colorbox.com/voice/test`**. The page derives `wss://<domain>/voice/stt` from its own URL, so the secure WebSocket works through NPM with no HTML change.

**Gotchas:** the subdomain must resolve to NPM (add to split-DNS if used); and NPM must reach the backend — verify from `.4`:
```
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.1.16:8300/voice/healthz   # expect 200
```

---

## 6. Cutover — DONE (2026-05-26), now runtime-swappable from the admin panel

The cutover was performed, but **not** by hardcoding the nginx target as originally
sketched. Voice routing is now **backend-mediated and swappable at runtime**:

- **`voice_hosts` table** (admin DB, via `migrations_admin.py`) holds each voice
  backend (`label`, `base_url`, `kind`, `is_active`). Seeded with
  `Lokalny (.61, CPU) → http://voice-service:8300` and
  `GPU (.16, GTX 1660) → http://192.168.1.16:8300`. Exactly one row is active.
- **`backend/app/routers/voice_proxy.py`** reverse-proxies `/voice/*` to the active
  host — HTTP via httpx (tts, config, voices, healthz) and the `/voice/stt` WebSocket
  via a `websockets` bidirectional pump. `GET/POST/PATCH/DELETE /api/admin/voice/hosts`
  manage hosts (with live per-host `/voice/healthz` probes) and set the active one.
- **`frontend/nginx.conf`** — `location /voice/stt` and `/voice/` now point at
  `http://backend:8000` (was `voice-service:8300`). nginx no longer knows the target;
  the backend resolves it from the table on every request.
- **Admin panel → Głos** has a "Serwer głosu" card to switch the active host (instant,
  no restart), per-host health + model status, and a TTS/STT test console.

Switching hosts = one PATCH (or one click in the panel); no nginx edit, no restart.
The active host as of cutover is **GPU (.16)**. To revert: activate `Lokalny (.61)`.
Verified end-to-end through the public domain: TTS WAV + WSS `/voice/stt` transcript.

⚠️ **Single-file bind-mount gotcha:** `nginx.conf` is mounted as a single file
(`./frontend/nginx.conf:/etc/nginx/conf.d/default.conf`). Editing it over sshfs
replaces the inode, so the running container keeps serving the *old* file and
`nginx -s reload` is not enough. After changing `nginx.conf`, **force-recreate** the
frontend: `docker compose -f docker-compose.dev.yml up -d --force-recreate frontend`.

---

## 7. Endpoints (same surface as the `.61` service)

| Method | Path | Notes |
|---|---|---|
| GET | `/voice/healthz` | liveness |
| GET | `/voice/test` | self-contained web test console (HTML) |
| GET | `/voice/tts?text=&voice=&speed=` | returns `audio/wav` |
| GET | `/voice/voices` | lists installed Piper voices |
| GET/POST | `/voice/config` | read/update runtime config |
| WS | `/voice/stt` | buffers audio, flushes on 2.5 s silence or `__end__`/`eof`/`end` |
