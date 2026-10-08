from __future__ import annotations

import requests

from .base import LLMProvider, ProviderError


class OllamaProvider(LLMProvider):
    """Local Ollama server via its native /api/chat endpoint with schema-constrained output."""

    name = "ollama"

    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        url = self.settings.base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.settings.model,
            "stream": False,
            "format": schema or "json",
            "think": False,
            "options": {"temperature": self.settings.temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            r = requests.post(url, json=payload, timeout=self.settings.timeout)
        except requests.RequestException as e:
            raise ProviderError(f"Ollama request failed: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        return data.get("message", {}).get("content", "")

    def healthcheck(self) -> tuple[bool, str]:
        try:
            r = requests.get(self.settings.base_url.rstrip("/") + "/api/tags", timeout=3)
            names = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            return False, f"Ollama not reachable at {self.settings.base_url}: {e}"
        if self.settings.model not in names and self.settings.model.split(":")[0] not in [n.split(":")[0] for n in names]:
            return False, f"model {self.settings.model!r} not pulled; available: {names}"
        return True, f"Ollama ok, model {self.settings.model}"
