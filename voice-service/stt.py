import os
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from config import load_config

MODELS_DIR = Path(os.getenv("VOICE_MODELS_DIR_STT", "/app/models/stt"))
_model_cache: dict[str, WhisperModel] = {}


def _suffix_for_media_audio(data: bytes) -> str:
    """Rozszerzenie pliku dla ffmpeg (MediaRecorder często wysyła webm lub mp4, nie WAV)."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return ".m4a"
    if len(data) >= 4:
        if data[:4] == b"RIFF":
            return ".wav"
        if data[:4] == b"fLaC":
            return ".flac"
        if data[:4] == b"\x1a\x45\xdf\xa3":
            return ".webm"
        if data[:2] in (b"\xff\xf1", b"\xff\xf9"):
            return ".aac"
    return ".audio"


def get_model(model_name: str | None = None) -> WhisperModel:
    cfg = load_config()
    name = model_name or cfg["stt_model"]
    if name not in _model_cache:
        _model_cache[name] = WhisperModel(
            name,
            device="cpu",
            compute_type="int8",
            download_root=str(MODELS_DIR),
        )
    return _model_cache[name]


def transcribe(audio_bytes: bytes) -> dict[str, str | float]:
    cfg = load_config()
    model = get_model(cfg["stt_model"])
    suffix = _suffix_for_media_audio(audio_bytes)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
        audio_file.write(audio_bytes)
        audio_path = audio_file.name
    try:
        segments, info = model.transcribe(
            audio_path,
            language=cfg["stt_language"] if cfg["stt_language"] != "auto" else None,
            beam_size=cfg["stt_beam_size"],
            vad_filter=cfg["vad_filter"],
        )
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return {
        "text": text,
        "language": info.language,
        "confidence": round(info.language_probability, 3),
    }


def reload_model() -> None:
    """Clear model cache after STT config changes."""
    _model_cache.clear()
