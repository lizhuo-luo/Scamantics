"""Orchestrates one analysis: prompt -> LLM -> parse -> verify -> (retry) -> result."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from .cache import DemoCache
from .config import Settings, load_settings
from .prompt import retry_prompt, system_prompt, user_prompt
from .providers import LLMProvider, ProviderError, build_provider
from .providers.base import extract_json_object
from .schema import LLM_JSON_SCHEMA, AnalysisResult, LLMAnalysis
from .validator import validate

log = logging.getLogger("scamantics")

MAX_MESSAGE_CHARS = 4000


def parse_llm_output(text: str) -> LLMAnalysis:
    """Turn raw model text into an LLMAnalysis, dropping tactic records with unknown labels."""
    obj = extract_json_object(text)
    tactics_raw = obj.get("tactics") or []
    if not isinstance(tactics_raw, list):
        tactics_raw = []
    clean: list[dict] = []
    for rec in tactics_raw:
        if not isinstance(rec, dict):
            continue
        try:
            LLMAnalysis.model_validate({"is_suspicious": True, "tactics": [rec]})
        except ValidationError as e:
            log.warning("dropping tactic record %r: %s", rec, e.errors()[0].get("msg"))
            continue
        clean.append(rec)
    is_susp = obj.get("is_suspicious")
    if isinstance(is_susp, str):
        is_susp = is_susp.strip().lower() in ("true", "yes", "1")
    return LLMAnalysis(
        is_suspicious=bool(is_susp) if is_susp is not None else bool(clean),
        summary=str(obj.get("summary") or ""),
        tactics=clean,
    )


class Analyzer:
    def __init__(self, settings: Settings | None = None, provider: LLMProvider | None = None, cache: DemoCache | None = None):
        self.settings = settings or load_settings()
        self.provider = provider or build_provider(self.settings)
        self.cache = cache if cache is not None else (DemoCache(self.settings.cache_path) if self.settings.use_cache else None)
        self._system = system_prompt()

    # -- public ---------------------------------------------------------------------------
    def analyze(self, message: str, use_cache: bool | None = None) -> AnalysisResult:
        message = (message or "").strip()
        if not message:
            return self._error_result(message, "Please paste a message to analyse.")
        if len(message) > MAX_MESSAGE_CHARS:
            message = message[:MAX_MESSAGE_CHARS]

        use_cache = self.settings.use_cache if use_cache is None else use_cache
        if use_cache and self.cache is not None:
            hit = self.cache.get(message)
            if hit is not None:
                return hit

        try:
            return self._run(message)
        except ProviderError as e:
            log.error("provider failure: %s", e)
            if self.cache is not None:
                hit = self.cache.get(message)
                if hit is not None:
                    return hit
            return self._error_result(message, f"The analysis service is unavailable: {e}")

    # -- internals ------------------------------------------------------------------------
    def _run(self, message: str) -> AnalysisResult:
        prompt = user_prompt(message)
        attempts = 0
        last_outcome = None
        last_analysis = None
        raw = ""
        while True:
            attempts += 1
            raw = self.provider.complete_json(self._system, prompt, LLM_JSON_SCHEMA)
            try:
                analysis = parse_llm_output(raw)
            except ProviderError:
                if attempts > self.settings.max_retries:
                    raise
                prompt = user_prompt(message) + "\n\nYour previous reply was not valid JSON. Return only the JSON object."
                continue
            outcome = validate(analysis, message)
            last_outcome, last_analysis = outcome, analysis
            if outcome.ok or attempts > self.settings.max_retries:
                break
            log.info("retrying: %d rejected quotes", len(outcome.rejected))
            prompt = retry_prompt(message, json.dumps(analysis.model_dump(), ensure_ascii=False), outcome.rejected)

        assert last_outcome is not None and last_analysis is not None
        is_susp = last_analysis.is_suspicious or bool(last_outcome.tactics)
        if not last_outcome.tactics:
            # Without verified evidence we never flag the message as suspicious.
            is_susp = False
        return AnalysisResult(
            message=message,
            is_suspicious=is_susp,
            summary=last_analysis.summary.strip() or self._default_summary(is_susp),
            tactics=last_outcome.tactics,
            spans=last_outcome.spans,
            rejected_quotes=last_outcome.rejected,
            attempts=attempts,
            provider=self.provider.name,
            model=self.provider.model,
        )

    @staticmethod
    def _default_summary(is_susp: bool) -> str:
        if is_susp:
            return "This message contains phrases that match known manipulation tactics."
        return "No strong manipulation tactic was detected in this message."

    def _error_result(self, message: str, error: str) -> AnalysisResult:
        return AnalysisResult(
            message=message,
            is_suspicious=False,
            summary="",
            tactics=[],
            spans=[],
            provider=self.provider.name,
            model=self.provider.model,
            error=error,
        )
