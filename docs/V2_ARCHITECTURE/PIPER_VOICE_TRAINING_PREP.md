# Piper Voice Training — Desktop Prep Guide

**Goal of this doc:** get a recording-quality Polish speech dataset of YOUR voice on your Ubuntu desktop (Ryzen 7700 / 64GB / RTX 3060), ready to hand off to Piper training.

**This doc only covers PHASE A (recording).** Once you have the dataset, we'll do PHASE B (training) on the same machine in a follow-up doc.

**Time budget:**
- Reading + setup: 2–3 hours
- Recording: 30 min minimum, 1–2 hours sweet spot, split over several sittings

---

## 0. The single most important thing to know

There is a purpose-built tool called **piper-recording-studio** made by the same team that builds Piper. It is a small local web app that:

- Shows you Polish prompts one at a time in your browser
- Records each one via your mic at the correct sample rate
- Saves each clip with the right filename
- Generates the `metadata.csv` Piper training needs

This replaces the entire "open Audacity, save WAV, rename it, paste sentence into spreadsheet" loop. **You should use it.** Almost everything below is built around it.

Repo: https://github.com/rhasspy/piper-recording-studio

---

## 1. Required reading (in this order, ~90 min total)

Do this BEFORE you touch the mic. Most failures in voice cloning come from skipping the theory.

### 1.1 — Piper training overview (30 min)
**URL:** https://github.com/rhasspy/piper/blob/master/TRAINING.md
**What to look for:**
- Dataset format (LJSpeech-style: `metadata.csv` + `wavs/` folder)
- Sample rate (22050 Hz for "medium" quality — our target)
- Fine-tuning vs from-scratch (we're fine-tuning)
- The two checkpoint files: `.ckpt` (training) vs `.onnx` (runtime)

### 1.2 — piper-recording-studio README (15 min)
**URL:** https://github.com/rhasspy/piper-recording-studio
**What to look for:**
- Install steps
- How prompts are served
- Output directory structure (you need to understand this — it's where your dataset lives)
- How to export to LJSpeech format at the end

### 1.3 — Available Piper voices, to pick your base model (15 min)
**URL:** https://github.com/rhasspy/piper/blob/master/VOICES.md
Scroll to `pl_PL`. Two Polish voices exist:
- `pl_PL-gosia-medium` (female)
- `pl_PL-darkman-medium` (male)
**Action:** play the samples (links in the table) and pick the one closer to your gender + pitch range. You'll fine-tune on top of it. Write your choice on a sticky note now.

### 1.4 — Background on what VITS is actually doing (30 min, optional but useful)
**URL:** https://github.com/coqui-ai/TTS/blob/dev/docs/source/models/vits.md
Just skim. You don't need the math. The point is to understand:
- The model learns the mapping from **phonemes** (sound units) to **mel-spectrograms** (audio in frequency form)
- Polish phonemes are derived from your text by **espeak-ng** automatically
- That's why your recordings must match the text exactly — every "uh" you say but didn't write throws the alignment off

### 1.5 — Recording technique primer (10 min)
**URL:** https://www.neumann.com/en-en/discover/recording-tutorials/4-tips-for-recording-voice-overs/
(or any VO recording guide — the key concepts are universal)
**What to look for:** mic distance, plosives, room treatment basics.

---

## 2. Ubuntu setup

All on your desktop (192.168.1.170 — your physical box).

### 2.1 System packages

```bash
sudo apt update
sudo apt install -y \
    git python3 python3-venv python3-pip \
    audacity \
    pulseaudio-utils pavucontrol \
    sox libsox-fmt-all \
    ffmpeg \
    espeak-ng
```

What each is for:
- **audacity** — QC tool. We'll only use it to inspect recordings, not record.
- **pavucontrol** — GUI mixer to confirm your mic is the default input and not clipping.
- **sox / ffmpeg** — audio processing utilities (used in post).
- **espeak-ng** — phonemizer; the recording studio doesn't need it but Piper training will.

### 2.2 Folder structure on your desktop

Create one root project folder. Pick a path with no spaces.

```bash
mkdir -p ~/voice-training/{recordings,exported_dataset,reference,checkpoints}
cd ~/voice-training
```

What goes where:
- `recordings/` — raw output from piper-recording-studio (one folder per session)
- `exported_dataset/` — final LJSpeech-format dataset (created in step 5)
- `reference/` — base voice checkpoint (downloaded later)
- `checkpoints/` — where training output will go (used in Phase B, not yet)

### 2.3 Install piper-recording-studio

```bash
cd ~/voice-training
git clone https://github.com/rhasspy/piper-recording-studio.git
cd piper-recording-studio
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
```

Run it:
```bash
python -m piper_recording_studio
```

Open your browser to `http://localhost:8000`. You should see a language picker. **Choose Polish (pl).** It will start serving you prompts.

If the language picker is missing Polish prompts, the studio bundles prompt files in `prompts/`. Polish should be there as `pl.txt`. If for any reason it isn't, drop one in yourself — one prompt per line, plain UTF-8.

### 2.4 Mic configuration (do this BEFORE first recording)

Open `pavucontrol`. Go to the **Input Devices** tab.
1. Confirm your microphone (USB / XLR-interface / whatever) is the active input.
2. **Unlock the L/R channel slider** (click the chain icon) so you can set mono level cleanly.
3. Speak at your normal recording distance and volume. The bar should peak around the middle, never touching the right edge (red = clipping).
4. In the **Configuration** tab, set your interface to **mono** if it's a single mic. Stereo wastes space and we'll downmix anyway.
5. Disable any system-level "noise suppression" or "echo cancel" effects. They distort the source.

Then in your browser:
1. piper-recording-studio will prompt the browser for mic permission — allow it.
2. Record a test clip ("test test 1 2 3") and play it back. If volume is too low or too high, fix in pavucontrol, not in the browser.

---

## 3. Recording environment (15 min one-time setup)

The cheapest big wins:

| What | Why | How |
|---|---|---|
| Quiet room | Fans, fridges, HVAC, traffic all bake noise into your dataset | Record at night, kill the PC fans if possible, mute notifications |
| Soft surroundings | Hard walls = reverb = the model learns the room, not your voice | Close curtains, put a duvet behind you, throw a thick towel under the mic |
| Consistent mic distance | If distance changes between clips, the model gets confused | Mark the distance with tape on the desk, ~15–20 cm from mouth |
| Pop filter or fabric in front of mic | Removes "p" and "b" plosives | DIY: pantyhose stretched over a coat-hanger ring works |
| Closed window, phone in another room | Random thumps ruin clips | Self-explanatory |

Don't bother with: aggressive noise suppression software, EQ, compression. Clean source > processed source — the model learns artifacts.

---

## 4. Recording sessions

### 4.1 Performance rules

- **Tone:** neutral game narrator. Imagine you're reading audiobook prose, not acting out characters.
- **Pace:** slightly slower than conversational. Each sentence should feel deliberate.
- **Energy:** consistent across ALL clips. Don't start strong and fade by clip 200. Match every session to the first one.
- **Read what's on screen.** If you flub a word, **re-record** the clip. Do not "fix it later" — the text→audio alignment must be exact.
- **No mouth noises.** Sip water between clips, not during. Don't lick lips right before hitting record.
- **Breathe before** starting a clip, not during. Long mid-sentence breaths confuse the aligner.

### 4.2 Session structure

Suggested rhythm:
- 30–45 min sessions max. Your voice changes when you're tired (drier, more nasal, slower).
- Take 2–3 sessions over different days. Variety in fatigue/mood actually helps generalization, as long as each session is internally consistent.
- Target counts:
  - **Minimum viable**: 300 clips (~25 min usable audio) — voice will sound like you, with rough edges.
  - **Sweet spot**: 800–1200 clips (~60–90 min usable audio) — confident output, robust on rare words.
  - **Maxing out**: 2000+ clips (~2.5 h) — diminishing returns, but the result is solid.

### 4.3 What piper-recording-studio creates

The studio saves into `~/voice-training/piper-recording-studio/output/pl/`:
```
output/
  pl/
    <session_id>/
      0001.webm           ← raw browser recording
      0001.txt            ← prompt text
      0002.webm
      0002.txt
      ...
```

You don't rename anything. Don't touch the filenames. Don't move files between sessions. The export step in section 5 reads this structure verbatim.

### 4.4 Mid-session checks

Every ~50 clips:
1. Pick 3 clips at random from your latest session
2. Open each in Audacity, look at the waveform
3. Check for: clipping (flat tops on peaks), background noise floor higher than ~-60 dB, dropouts, weird thumps
4. If something's wrong, fix the cause (move closer/farther, fix room noise) and re-record the affected clips

### 4.5 If you stop and resume later

Just relaunch:
```bash
cd ~/voice-training/piper-recording-studio
source .venv/bin/activate
python -m piper_recording_studio
```
It remembers your progress through the prompt list.

---

## 5. Export to LJSpeech format

When you've hit your target clip count:

### 5.1 Run the studio's exporter

The repo includes an export script. From the recording-studio folder:

```bash
cd ~/voice-training/piper-recording-studio
source .venv/bin/activate

python -m export_dataset \
    --language pl \
    --output-dir ~/voice-training/exported_dataset/piotr
```

(Confirm the exact command name from the README — it has been renamed in the past. The README in section 1.2 is the authoritative source.)

Result:
```
~/voice-training/exported_dataset/piotr/
  wavs/
    0001.wav
    0002.wav
    ...
  metadata.csv      ← format: <id>|<prompt text>
```

### 5.2 Verify the export

```bash
cd ~/voice-training/exported_dataset/piotr
ls wavs | wc -l                              # → should match your clip count
wc -l metadata.csv                           # → same number
head metadata.csv                            # → spot-check pipes + Polish text intact
soxi wavs/0001.wav                           # → confirm 22050 Hz, 16-bit, mono
```

If `soxi` shows anything other than `Sample Rate: 22050` and `Channels: 1`, do a batch conversion:
```bash
mkdir wavs_fixed
for f in wavs/*.wav; do
    sox "$f" -r 22050 -c 1 -b 16 "wavs_fixed/$(basename $f)"
done
mv wavs wavs_orig && mv wavs_fixed wavs
```

### 5.3 Final loudness normalization (optional but recommended)

```bash
mkdir wavs_norm
for f in wavs/*.wav; do
    ffmpeg -i "$f" -af "loudnorm=I=-23:LRA=7:TP=-2" -ar 22050 -ac 1 \
           "wavs_norm/$(basename $f)" -y -loglevel error
done
mv wavs wavs_preloudnorm && mv wavs_norm wavs
```

This makes every clip the same perceived loudness, which helps training stability.

### 5.4 Snapshot

Back up the exported dataset folder to an external drive or a different disk **before training touches it**. Re-recording is expensive; re-training is cheap.

```bash
tar czf ~/piotr-dataset-$(date +%Y%m%d).tar.gz \
    -C ~/voice-training/exported_dataset piotr
```

---

## 6. Hand-off checklist

Before we start training (Phase B), you should have:

- [ ] `~/voice-training/exported_dataset/piotr/wavs/` containing N×WAV files at 22050 Hz mono 16-bit
- [ ] `~/voice-training/exported_dataset/piotr/metadata.csv` with N lines, pipe-separated
- [ ] Spot-checked 5 random clips: clean, no clipping, no background hum, text matches audio exactly
- [ ] Backed up the dataset
- [ ] Chosen + noted your base voice (`gosia` or `darkman`)
- [ ] At least 300 clips (ideally 800+)

When all boxes are ticked, ping me and we'll write the Phase B (training) doc — environment setup with PyTorch + CUDA 12, downloading the base checkpoint, the actual `piper_train` command line tuned for your 3060, monitoring loss curves, and exporting the final `.onnx` for our voice service.

---

## 7. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Trained voice sounds robotic / monotone | Recordings were all the same intonation pattern | Vary sentence types: questions, statements, exclamations |
| Sibilance ("sssss") harsh | Mic too close, or pointed straight at mouth | Move to 20 cm, angle slightly off-axis |
| Background "shhh" in output | Room noise floor too high | Re-record in a quieter time/place; do NOT denoise — re-record |
| Voice drifts in pitch over training | Clips inconsistent across sessions | Match energy/posture every session; warm up your voice first |
| Random clipping in one session | Got louder partway through, didn't recheck levels | The mid-session check in 4.4 catches this |
| Polish diacritics garbled in metadata.csv | Wrong encoding | Ensure UTF-8 everywhere; piper-recording-studio defaults to it |

---

## 8. Reading list — bookmark for reference

Save these to your browser bookmarks:

1. **Piper TRAINING.md** — https://github.com/rhasspy/piper/blob/master/TRAINING.md
2. **piper-recording-studio README** — https://github.com/rhasspy/piper-recording-studio
3. **Piper VOICES.md** — https://github.com/rhasspy/piper/blob/master/VOICES.md
4. **Coqui VITS overview** — https://github.com/coqui-ai/TTS/blob/dev/docs/source/models/vits.md
5. **espeak-ng Polish phoneme reference** — https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md (search "Polish")

---

## 9. TL;DR — the actual sequence

1. Read sections 1.1, 1.2, 1.3 (~60 min)
2. `sudo apt install` block from 2.1
3. Create folders from 2.2
4. Install + launch piper-recording-studio (2.3)
5. Configure mic in pavucontrol (2.4)
6. Set up your recording corner (section 3)
7. Open `http://localhost:8000`, pick Polish, record 30–45 min sessions until you hit your target
8. Export to LJSpeech (section 5)
9. Verify + back up
10. Tell me you're done — we move to training

Good luck. The recording quality is THE thing that decides how good the cloned voice will be. Take your time on section 3 + section 4.1, and don't be afraid to throw out a session that doesn't sound right.
