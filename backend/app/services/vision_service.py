"""LLM Vision service — dungeon tile image → Polish room description."""
import base64
import json
import urllib.request
import urllib.error
from typing import Any


_VISION_PROMPT_TEMPLATE = """Jesteś asystentem GM do gry RPG. Opisz to pomieszczenie/kafelek lochu po polsku.

Kafelek: {label} (kategoria: {category})

Wygeneruj zwięzły opis atmosfery tego wnętrza (2-4 zdania). Opisz:
- Co widać w pomieszczeniu (meble, przedmioty, materiały, stan zniszczenia)
- Atmosferę i klimat (światło, zapachy, odgłosy)
- Czy widoczne są wyjścia/drzwi i gdzie się znajdują

Odpowiedz TYLKO opisem, bez nagłówków, bez wstępu."""


def build_vision_prompt(tile: dict[str, Any]) -> str:
    """Build Polish GM prompt for vision model."""
    label = tile.get("label") or "Nieznane pomieszczenie"
    category = tile.get("category_key") or "dungeon"
    return _VISION_PROMPT_TEMPLATE.format(label=label, category=category)


def describe_tile(
    image_bytes: bytes,
    ollama_url: str,
    model: str = "llava:7b",
) -> str:
    """Call Ollama vision API with image bytes, return generated description.

    ollama_url: base URL like 'http://192.168.1.170:11434'
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": model,
        "prompt": (
            "Opisz po polsku to pomieszczenie w lochu RPG. "
            "Podaj 2-4 zdania o atmosferze, wyglądzie, oświetleniu i klimacie. "
            "Odpowiedz TYLKO opisem, bez wstępu."
        ),
        "images": [image_b64],
        "stream": False,
    }
    url = ollama_url.rstrip("/") + "/api/generate"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("response", "").strip()
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama vision call failed ({url}): {e}") from e
