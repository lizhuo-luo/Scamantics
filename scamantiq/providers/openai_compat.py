from __future__ import annotations

from urllib.parse import urlparse

import requests

from .base import LLMProvider, ProviderError


def _is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host.startswith("192.168.") or host.startswith("10.")


class OpenAICompatProvider(LLMProvider):
    """OpenAI chat-completions protocol.

    Works for OpenAI, Groq, OpenRouter, DeepSeek, Together and for local servers such as SGLang,
    vLLM, LM Studio and Ollama's /v1 endpoint by changing `base_url`.

    Structured output is requested in the strongest form the server accepts, falling back
    step by step: `json_schema` (OpenAI, SGLang, vLLM) -> `json_object` -> none.
    """

    name = "openai"

    def __init__(self, settings):
        super().__init__(settings)
        self._resolved_model: str | None = None
        self._mode: str | None = None  # remembered response_format that worked: schema | object | none

    # -- model discovery ----------------------------------------------------------------
    @property
    def model(self) -> str:
        return self._resolved_model or self.settings.model

    def _served_models(self) -> list[str]:
        url = self.settings.base_url.rstrip("/") + "/models"
        r = requests.get(url, headers=self._headers(), timeout=5)
        if r.status_code != 200:
            raise ProviderError(f"{self.name} GET /models HTTP {r.status_code}: {r.text[:200]}")
        data = r.json().get("data", [])
        return [m.get("id", "") for m in data if m.get("id")]

    def _resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model
        if self.settings.model:
            self._resolved_model = self.settings.model
            return self._resolved_model
        try:
            served = self._served_models()
        except (requests.RequestException, ProviderError, ValueError) as e:
            raise ProviderError(f"no model configured and could not list models at {self.settings.base_url}: {e}") from e
        if not served:
            raise ProviderError(f"no model configured and server at {self.settings.base_url} serves none")
        self._resolved_model = served[0]
        return self._resolved_model

    # -- request --------------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.settings.api_key or 'none'}", "Content-Type": "application/json"}
        if "openrouter.ai" in self.settings.base_url:
            headers["HTTP-Referer"] = "https://github.com/scamantiq"
            headers["X-Title"] = "ScamantiQ"
        return headers

    def _response_format(self, mode: str, schema: dict | None) -> dict | None:
        if mode == "schema" and schema:
            return {"type": "json_schema", "json_schema": {"name": "scamantiq_analysis", "schema": schema}}
        if mode in ("schema", "object"):
            return {"type": "json_object"}
        return None

    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        if not self.settings.api_key and not _is_local(self.settings.base_url):
            raise ProviderError("no API key configured (set SCAMANTIQ_API_KEY or the provider's *_API_KEY)")
        model = self._resolve_model()
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        base_payload = {
            "model": model,
            "temperature": self.settings.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        modes = ["schema", "object", "none"]
        if self._mode:
            modes = modes[modes.index(self._mode) :]
        r = None
        for mode in modes:
            payload = dict(base_payload)
            fmt = self._response_format(mode, schema)
            if fmt:
                payload["response_format"] = fmt
            r = self._post(url, payload)
            rejected_format = r.status_code == 400 and ("response_format" in r.text or "json_schema" in r.text)
            if rejected_format and mode != "none":
                continue  # server rejected this response_format; try the next weaker one
            self._mode = mode
            break
        assert r is not None
        if r.status_code != 200:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected response shape: {str(data)[:300]}") from e

    def _post(self, url, payload):
        try:
            return requests.post(url, json=payload, headers=self._headers(), timeout=self.settings.timeout)
        except requests.RequestException as e:
            raise ProviderError(f"{self.name} request failed: {e}") from e

    # -- health ---------------------------------------------------------------------------
    def healthcheck(self) -> tuple[bool, str]:
        local = _is_local(self.settings.base_url)
        if not self.settings.api_key and not local:
            return False, "no API key configured"
        if local:
            try:
                served = self._served_models()
            except (requests.RequestException, ProviderError, ValueError) as e:
                return False, f"server not reachable at {self.settings.base_url}: {e}"
            if not self.settings.model:
                if not served:
                    return False, f"server at {self.settings.base_url} serves no model"
                self._resolved_model = served[0]
                return True, f"{self.settings.preset} ok, serving {served[0]}"
            if served and self.settings.model not in served:
                return False, f"model {self.settings.model!r} not served; available: {served}"
            return True, f"{self.settings.preset} ok, model {self.settings.model}"
        return True, f"{self.name} configured ({self.settings.base_url}, {self.settings.model})"
