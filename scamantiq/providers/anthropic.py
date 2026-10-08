from __future__ import annotations

import requests

from .base import LLMProvider, ProviderError


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        if not self.settings.api_key:
            raise ProviderError("no API key configured (set ANTHROPIC_API_KEY)")
        url = self.settings.base_url.rstrip("/") + "/v1/messages"
        headers = {
            "x-api-key": self.settings.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.settings.model,
            "max_tokens": 1500,
            "temperature": self.settings.temperature,
            "system": system,
            "messages": [
                {"role": "user", "content": user},
                # Prefill forces the answer to start as a JSON object.
                {"role": "assistant", "content": "{"},
            ],
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=self.settings.timeout)
        except requests.RequestException as e:
            raise ProviderError(f"anthropic request failed: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"anthropic HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return "{" + text

    def healthcheck(self) -> tuple[bool, str]:
        if not self.settings.api_key:
            return False, "no API key configured"
        return True, f"anthropic configured ({self.settings.model})"
