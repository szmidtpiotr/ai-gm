import json
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(os.getenv("VOICE_CONFIG_PATH", "/app/config.json"))

DEFAULTS: dict[str, Any] = {
    "tts_enabled": True,
    "stt_enabled": True,
    "tts_voice": "pl_PL-darkman-medium",
    "tts_speed": 1.0,
    "tts_noise_scale": 0.667,
    "tts_noise_w": 0.8,
    "stt_model": "small",
    "stt_language": "pl",
    "stt_beam_size": 5,
    "vad_filter": True,
    "stt_silence_auto_stop_ms": 2000,
    "stt_min_voice_rms_threshold": 0.01,
    "stt_noise_multiplier": 1.5,
}


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return {**DEFAULTS, **data}
    return DEFAULTS.copy()


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    cfg.update(updates)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(cfg, handle, indent=2)
    return cfg
