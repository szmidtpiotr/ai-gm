import os
import re
import subprocess
import tempfile
from pathlib import Path

import requests

from config import load_config

MODELS_DIR = Path(os.getenv("VOICE_MODELS_DIR", "/app/models/tts"))
PIPER_BIN = os.getenv("PIPER_BIN", "piper")
PIPER_VOICES_BASE_URL = os.getenv(
    "PIPER_VOICES_BASE_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/pl",
)


def _clean_text(text: str) -> str:
    """Remove roll tags and keep safe length for TTS."""
    text = re.sub(r"\[ROLL:[^\]]*\]", "", text).strip()
    return text[:2000]


def synthesize(text: str, voice: str | None = None, speed: float | None = None) -> bytes:
    cfg = load_config()
    voice = voice or cfg["tts_voice"]
    speed = speed or cfg["tts_speed"]
    noise_scale = cfg["tts_noise_scale"]
    noise_w = cfg["tts_noise_w"]

    text = _clean_text(text)
    if not text:
        raise ValueError("Empty text after cleanup")

    model_path = MODELS_DIR / f"{voice}.onnx"
    if not model_path.exists():
        _download_voice_model(voice)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_f:
        out_path = out_f.name

    try:
        cmd = [
            PIPER_BIN,
            "--model",
            str(model_path),
            "--output_file",
            out_path,
            "--length_scale",
            str(1.0 / speed),  # Piper controls speed via inverse length scale
            "--noise_scale",
            str(noise_scale),
            "--noise_w",
            str(noise_w),
        ]
        result = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"Piper error: {result.stderr.decode()}")
        with open(out_path, "rb") as handle:
            return handle.read()
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)


def list_voices() -> list[str]:
    return [path.stem for path in MODELS_DIR.glob("*.onnx")]


def _download_voice_model(voice: str) -> None:
    """Download Piper voice files to runtime models volume if missing."""
    parts = voice.split("-")
    if len(parts) < 3:
        raise FileNotFoundError(f"Unsupported voice format: {voice}")
    locale, person, quality = parts[0], parts[1], parts[2]
    base = f"{PIPER_VOICES_BASE_URL}/{locale}/{person}/{quality}/{voice}.onnx"
    targets = [
        (base, MODELS_DIR / f"{voice}.onnx"),
        (f"{base}.json", MODELS_DIR / f"{voice}.onnx.json"),
    ]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for url, target in targets:
        if target.exists():
            continue
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with target.open("wb") as handle:
            handle.write(response.content)
