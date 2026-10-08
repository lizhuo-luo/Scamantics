"""Deterministic evidence validator.

Every quote the model returns must occur verbatim in the input message. Quotes that cannot be
located are rejected. A lenient second pass tolerates differences in whitespace, quote marks and
dashes: if that locates the quote, the span is *replaced by the exact source text*, so the final
evidence is always a true substring of the message.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .schema import EvidenceSpan, LLMAnalysis, VerifiedTactic

_PUNCT_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "“": "'",
        "”": "'",
        "„": "'",
        '"': "'",
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
        "…": "...",
    }
)


def _canon_char(ch: str) -> str:
    ch = ch.translate(_PUNCT_MAP)
    if ch.isspace():
        return " "
    return unicodedata.normalize("NFKC", ch).lower()


def _canonical_with_map(text: str) -> tuple[str, list[int]]:
    """Return a canonical string plus a map from canonical index -> original index.

    Runs of whitespace collapse to a single space.
    """
    out: list[str] = []
    idx_map: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        c = _canon_char(ch)
        if c == " ":
            if prev_space:
                continue
            prev_space = True
        else:
            prev_space = False
        for sub in c:  # NFKC may expand one char into several
            out.append(sub)
            idx_map.append(i)
    return "".join(out), idx_map


@dataclass
class Located:
    text: str
    start: int
    end: int


def locate(quote: str, message: str, used: list[tuple[int, int]] | None = None) -> Located | None:
    """Find `quote` in `message`.

    Exact substring match is tried first. If that fails a lenient match (case, whitespace,
    curly quotes, dashes) is tried; on success the returned text is the exact source slice.
    `used` lets callers prefer occurrences not already claimed by another span.
    """
    q = quote.strip()
    # Strip wrapping quote marks only when the quote is wrapped on both ends.
    _QM = "\"'“”‘’"
    while len(q) >= 2 and q[0] in _QM and q[-1] in _QM:
        q = q[1:-1].strip()
    if not q:
        return None

    def pick(candidates: list[tuple[int, int]]) -> tuple[int, int] | None:
        if not candidates:
            return None
        if used:
            for c in candidates:
                if not any(c[0] < u[1] and u[0] < c[1] for u in used):
                    return c
        return candidates[0]

    # 1. exact
    exact = [(m.start(), m.end()) for m in re.finditer(re.escape(q), message)]
    chosen = pick(exact)
    if chosen:
        return Located(message[chosen[0] : chosen[1]], chosen[0], chosen[1])

    # 2. lenient
    canon_msg, idx_map = _canonical_with_map(message)
    canon_q, _ = _canonical_with_map(q)
    canon_q = canon_q.strip()
    if not canon_q:
        return None
    lenient: list[tuple[int, int]] = []
    for m in re.finditer(re.escape(canon_q), canon_msg):
        start = idx_map[m.start()]
        end = idx_map[m.end() - 1] + 1
        lenient.append((start, end))
    chosen = pick(lenient)
    if chosen:
        return Located(message[chosen[0] : chosen[1]], chosen[0], chosen[1])
    return None


@dataclass
class ValidationOutcome:
    tactics: list[VerifiedTactic]
    spans: list[EvidenceSpan]
    rejected: list[str]
    dropped_labels: list[str]

    @property
    def ok(self) -> bool:
        return not self.rejected


def validate(analysis: LLMAnalysis, message: str) -> ValidationOutcome:
    """Check every evidence quote; drop invalid quotes and tactics left without evidence."""
    tactics: list[VerifiedTactic] = []
    spans: list[EvidenceSpan] = []
    rejected: list[str] = []
    dropped: list[str] = []
    used: list[tuple[int, int]] = []
    seen_labels: set[str] = set()

    for rec in analysis.tactics:
        if rec.label in seen_labels:
            # Merge duplicate labels into the first record.
            target = next(t for t in tactics if t.label == rec.label)
            for q in rec.evidence:
                loc = locate(q, message, used)
                if loc and loc.text not in target.evidence:
                    target.evidence.append(loc.text)
                    spans.append(EvidenceSpan(label=rec.label, text=loc.text, start=loc.start, end=loc.end))
                    used.append((loc.start, loc.end))
                elif not loc:
                    rejected.append(q)
            continue

        good: list[str] = []
        for q in rec.evidence:
            loc = locate(q, message, used)
            if loc is None:
                rejected.append(q)
                continue
            if loc.text in good:
                continue
            good.append(loc.text)
            spans.append(EvidenceSpan(label=rec.label, text=loc.text, start=loc.start, end=loc.end))
            used.append((loc.start, loc.end))
        if not good:
            dropped.append(rec.label)
            continue
        seen_labels.add(rec.label)
        tactics.append(
            VerifiedTactic(
                label=rec.label,
                evidence=good,
                explanation=rec.explanation.strip(),
                confidence=rec.confidence,
            )
        )

    spans.sort(key=lambda s: (s.start, s.end))
    return ValidationOutcome(tactics=tactics, spans=spans, rejected=rejected, dropped_labels=dropped)


def grounding_rate(quotes: list[str], message: str) -> float:
    """Fraction of quotes that are exact substrings of the message (strict, no lenient pass)."""
    if not quotes:
        return 1.0
    return sum(1 for q in quotes if q in message) / len(quotes)
