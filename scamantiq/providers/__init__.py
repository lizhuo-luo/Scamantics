"""LLM provider adapters. All share the `LLMProvider.complete_json` interface."""

from __future__ import annotations

from ..config import Settings
from .base import LLMProvider, ProviderError
from .mock import MockProvider


def build_provider(settings: Settings) -> LLMProvider:
    p = settings.provider
    if p == "ollama":
        from .ollama import OllamaProvider

        return OllamaProvider(settings)
    if p == "openai":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(settings)
    if p == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(settings)
    if p == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(settings)
    if p == "mock":
        return MockProvider(settings)
    raise ProviderError(f"unknown provider {p!r}")


__all__ = ["LLMProvider", "ProviderError", "MockProvider", "build_provider"]
