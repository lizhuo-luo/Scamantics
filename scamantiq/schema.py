"""Pydantic models for the structured LLM output and the final verified result."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .taxonomy import LABELS, normalise_label

Label = Literal["urgency", "impersonation", "isolation", "reward", "threat"]


class TacticRecord(BaseModel):
    """One predicted tactic with its grounding evidence."""

    label: Label
    evidence: list[str] = Field(default_factory=list, description="Exact quotes copied verbatim from the message.")
    explanation: str = Field(default="", description="Plain-language explanation for a non-expert.")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("label", mode="before")
    @classmethod
    def _canonical_label(cls, v: str) -> str:
        canon = normalise_label(str(v))
        if canon is None:
            raise ValueError(f"unknown tactic label: {v!r}; expected one of {LABELS}")
        return canon

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v if str(x).strip()]

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        if v is None or v == "":
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f > 1.0 and f <= 100.0:  # model returned a percentage
            f = f / 100.0
        return max(0.0, min(1.0, f))


class LLMAnalysis(BaseModel):
    """The raw schema the LLM is asked to return."""

    is_suspicious: bool
    summary: str = ""
    tactics: list[TacticRecord] = Field(default_factory=list)


class EvidenceSpan(BaseModel):
    """A verified evidence quote located in the source text."""

    label: Label
    text: str
    start: int
    end: int


class VerifiedTactic(BaseModel):
    label: Label
    evidence: list[str]
    explanation: str
    confidence: float | None = None


class AnalysisResult(BaseModel):
    """The final, validator-checked result shown to the user."""

    message: str
    is_suspicious: bool
    summary: str
    tactics: list[VerifiedTactic]
    spans: list[EvidenceSpan]
    rejected_quotes: list[str] = Field(default_factory=list)
    attempts: int = 1
    provider: str = ""
    model: str = ""
    from_cache: bool = False
    error: str | None = None

    @property
    def labels(self) -> list[str]:
        return [t.label for t in self.tactics]


# JSON schema given to providers that support constrained decoding (Ollama, OpenAI, Gemini).
LLM_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "is_suspicious": {"type": "boolean"},
        "summary": {"type": "string"},
        "tactics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": list(LABELS)},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["label", "evidence", "explanation", "confidence"],
            },
        },
    },
    "required": ["is_suspicious", "summary", "tactics"],
}
