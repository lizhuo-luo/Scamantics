"""Runtime configuration from environment variables (optionally loaded from a .env file).

Provider selection (SCAMANTICS_PROVIDER):
  ollama      - local Ollama server, free (default if reachable)
  openai      - OpenAI-compatible chat completions; also Groq, OpenRouter, DeepSeek, Together, vLLM
                via SCAMANTICS_BASE_URL
  anthropic   - Anthropic Messages API
  gemini      - Google Gemini generateContent API (free tier available)
  mock        - cached demonstration answers only, no network
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

PRESETS: dict[str, dict[str, str]] = {
    # name: {provider, base_url, model, key_env}
    "ollama": {"provider": "ollama", "base_url": "http://localhost:11434", "model": "gemma4:12b", "key_env": ""},
    "openai": {"provider": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY"},
    "groq": {"provider": "openai", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "key_env": "GROQ_API_KEY"},
    "openrouter": {"provider": "openai", "base_url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.3-70b-instruct:free", "key_env": "OPENROUTER_API_KEY"},
    "deepseek": {"provider": "openai", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "key_env": "DEEPSEEK_API_KEY"},
    "anthropic": {"provider": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude-haiku-4-5-20251001", "key_env": "ANTHROPIC_API_KEY"},
    "gemini": {"provider": "gemini", "base_url": "https://generativelanguage.googleapis.com", "model": "gemini-2.0-flash", "key_env": "GEMINI_API_KEY"},
    "mock": {"provider": "mock", "base_url": "", "model": "cached-demo", "key_env": ""},
}


@dataclass
class Settings:
    preset: str
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout: float = 120.0
    max_retries: int = 1  # regeneration attempts after a failed evidence check
    temperature: float = 0.0
    cache_path: str = "data/demo_cache.json"
    use_cache: bool = True

    @property
    def describe(self) -> str:
        return f"{self.provider}:{self.model}"


def load_settings(**overrides) -> Settings:
    preset_name = overrides.pop("preset", None) or os.getenv("SCAMANTICS_PROVIDER", "ollama").lower()
    preset = PRESETS.get(preset_name)
    if preset is None:
        # unknown name: treat it as a raw provider type
        preset = {"provider": preset_name, "base_url": "", "model": "", "key_env": ""}
    api_key = os.getenv("SCAMANTICS_API_KEY") or (os.getenv(preset["key_env"]) if preset["key_env"] else "") or ""
    s = Settings(
        preset=preset_name,
        provider=preset["provider"],
        base_url=os.getenv("SCAMANTICS_BASE_URL", preset["base_url"]),
        model=os.getenv("SCAMANTICS_MODEL", preset["model"]),
        api_key=api_key,
        timeout=float(os.getenv("SCAMANTICS_TIMEOUT", "120")),
        max_retries=int(os.getenv("SCAMANTICS_MAX_RETRIES", "1")),
        temperature=float(os.getenv("SCAMANTICS_TEMPERATURE", "0")),
        cache_path=os.getenv("SCAMANTICS_CACHE", "data/demo_cache.json"),
        use_cache=os.getenv("SCAMANTICS_USE_CACHE", "1") not in ("0", "false", "False"),
    )
    for k, v in overrides.items():
        if v is not None:
            setattr(s, k, v)
    return s
