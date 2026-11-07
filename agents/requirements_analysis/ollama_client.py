import json
import re
import httpx

from app.core.config import settings


class OllamaError(RuntimeError):
    pass


def chat_json(prompt: str) -> dict:
    """Call Ollama's local chat API and parse its JSON response."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {
            "temperature": 0.1,
            "num_ctx": 4096,
            "num_predict": 1024
        },
    }

    try:
        timeout = httpx.Timeout(
            connect=10.0,
            read=settings.ollama_timeout_seconds,
            write=30.0,
            pool=10.0
        )

        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise OllamaError("Ollama returned a response that was not valid JSON.")
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise OllamaError("Ollama response must be a JSON object.")
        return parsed
    except httpx.HTTPError as exc:
        raise OllamaError(f"Cannot reach Ollama at {url}: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise OllamaError(f"Could not parse Ollama response: {exc}") from exc
