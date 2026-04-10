import os

import httpx


class OllamaServiceError(Exception):
    pass


class OllamaService:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT", "60"))

    def generate_narrative(
        self,
        *,
        model: str,
        system_prompt: str,
        user_text: str,
        character_id: int | None = None,
        campaign_id: int | None = None,
        game_id: int | None = None,
    ) -> str:
        url = f"{self.base_url}/v1/chat/completions"

        context_bits = []
        if campaign_id is not None:
            context_bits.append(f"Campaign ID: {campaign_id}")
        if character_id is not None:
            context_bits.append(f"Character ID: {character_id}")
        if game_id is not None:
            context_bits.append(f"Game ID: {game_id}")

        context_text = "\n".join(context_bits).strip()
        if not context_text:
            context_text = "No additional campaign context provided."

        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "system",
                    "content": f"Current game context:\n{context_text}",
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
            "temperature": 0.8,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer ollama",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaServiceError("Ollama request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaServiceError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaServiceError(f"Ollama request failed: {exc}") from exc

        data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OllamaServiceError(f"Unexpected Ollama response format: {data}") from exc

        content = (content or "").strip()
        if not content:
            raise OllamaServiceError("Ollama returned an empty response")

        return content