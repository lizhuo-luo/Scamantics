"""Demo cache: precomputed results so the demo works without network or an API key."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schema import AnalysisResult


def _key(message: str) -> str:
    return " ".join(message.split())


class DemoCache:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    def get(self, message: str) -> AnalysisResult | None:
        raw = self._data.get(_key(message))
        if raw is None:
            return None
        res = AnalysisResult.model_validate(raw)
        res.from_cache = True
        return res

    def put(self, result: AnalysisResult) -> None:
        self._data[_key(result.message)] = result.model_dump(exclude={"from_cache"})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._data)

    def messages(self) -> list[str]:
        return [v["message"] for v in self._data.values()]
