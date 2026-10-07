from __future__ import annotations

import copy

import requests

from .base import LLMProvider, ProviderError


def _gemini_schema(schema: dict) -> dict:
    """Gemini's response schema is a subset of JSON schema; strip unsupported keys."""
    s = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            node.pop("additionalProperties", None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(s)
    return s


class GeminiProvider(LLMProvider):
    name = "gemini"

    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        if not self.settings.api_key:
            raise ProviderError("no API key configured (set GEMINI_API_KEY)")
        url = (
            self.settings.base_url.rstrip("/")
            + f"/v1beta/models/{self.settings.model}:generateContent?key={self.settings.api_key}"
        )
        gen_cfg: dict = {"temperature": self.settings.temperature, "responseMimeType": "application/json"}
        if schema:
            gen_cfg["responseSchema"] = _gemini_schema(schema)
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        try:
            r = requests.post(url, json=payload, timeout=self.settings.timeout)
        except requests.RequestException as e:
            raise ProviderError(f"gemini request failed: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"gemini HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected gemini response: {str(data)[:300]}") from e
        return "".join(p.get("text", "") for p in parts)

    def healthcheck(self) -> tuple[bool, str]:
        if not self.settings.api_key:
            return False, "no API key configured"
        return True, f"gemini configured ({self.settings.model})"
