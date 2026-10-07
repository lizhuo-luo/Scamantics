from __future__ import annotations

import requests

from .base import LLMProvider, ProviderError


class OpenAICompatProvider(LLMProvider):
    """OpenAI chat-completions protocol. Works for OpenAI, Groq, OpenRouter, DeepSeek, Together,
    vLLM, LM Studio and Ollama's /v1 endpoint by changing `base_url`."""

    name = "openai"

    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        if not self.settings.api_key and "localhost" not in self.settings.base_url and "127.0.0.1" not in self.settings.base_url:
            raise ProviderError("no API key configured (set SCAMANTICS_API_KEY or the provider's *_API_KEY)")
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.api_key or 'none'}", "Content-Type": "application/json"}
        if "openrouter.ai" in url:
            headers["HTTP-Referer"] = "https://github.com/scamantics"
            headers["X-Title"] = "Scamantics"
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        r = self._post(url, headers, payload)
        if r.status_code == 400 and "response_format" in r.text:
            # backend does not support JSON mode; fall back to plain completion
            payload.pop("response_format", None)
            r = self._post(url, headers, payload)
        if r.status_code != 200:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected response shape: {str(data)[:300]}") from e

    def _post(self, url, headers, payload):
        try:
            return requests.post(url, json=payload, headers=headers, timeout=self.settings.timeout)
        except requests.RequestException as e:
            raise ProviderError(f"{self.name} request failed: {e}") from e

    def healthcheck(self) -> tuple[bool, str]:
        if not self.settings.api_key and "localhost" not in self.settings.base_url:
            return False, "no API key configured"
        return True, f"{self.name} configured ({self.settings.base_url}, {self.settings.model})"
