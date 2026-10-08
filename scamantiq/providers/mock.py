from __future__ import annotations

import json

from .base import LLMProvider, ProviderError


class MockProvider(LLMProvider):
    """Offline provider for tests and demos.

    Answers come from a dict mapping message text -> JSON string (or dict). Unknown messages
    raise ProviderError so the analyzer falls back to the demo cache or reports the failure.
    """

    name = "mock"

    def __init__(self, settings, answers: dict[str, str | dict] | None = None):
        super().__init__(settings)
        self.answers: dict[str, str] = {}
        for k, v in (answers or {}).items():
            self.answers[k.strip()] = v if isinstance(v, str) else json.dumps(v)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        self.calls.append((system, user))
        for msg, ans in self.answers.items():
            if msg and msg in user:
                return ans
        raise ProviderError("mock provider has no answer for this message (offline mode)")

    def healthcheck(self) -> tuple[bool, str]:
        return True, "mock provider (offline, cached demo answers only)"
