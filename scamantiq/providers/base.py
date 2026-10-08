from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from ..config import Settings


class ProviderError(RuntimeError):
    """Raised when the LLM backend cannot be reached or returns an unusable answer."""


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def model(self) -> str:
        return self.settings.model

    @abstractmethod
    def complete_json(self, system: str, user: str, schema: dict | None = None) -> str:
        """Return the model's raw text answer, expected to be a JSON object."""

    def healthcheck(self) -> tuple[bool, str]:
        return True, "not checked"


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json_object(text: str) -> dict:
    """Parse the first JSON object found in `text`, tolerating markdown fences and prose."""
    if not text or not text.strip():
        raise ProviderError("empty response from model")
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # find the outermost {...}
    start = cleaned.find("{")
    if start == -1:
        raise ProviderError(f"no JSON object in response: {text[:200]!r}")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError as e:
                    raise ProviderError(f"invalid JSON in response: {e}") from e
                if isinstance(obj, dict):
                    return obj
                break
    raise ProviderError(f"could not parse JSON object from response: {text[:200]!r}")
