"""Evaluation utilities: dataset loading, classification metrics, grounding and span F1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.preprocessing import MultiLabelBinarizer

from .schema import AnalysisResult
from .taxonomy import LABELS


@dataclass
class Example:
    id: str
    category: str
    message: str
    labels: list[str]
    evidence: dict[str, list[str]] = field(default_factory=dict)


def load_dataset(path: str | Path) -> list[Example]:
    rows: list[Example] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        rows.append(Example(d["id"], d["category"], d["message"], list(d.get("labels", [])), dict(d.get("evidence", {}))))
    return rows


def check_dataset(examples: list[Example]) -> list[str]:
    """Return a list of integrity problems (unknown labels, gold spans not in the message)."""
    problems = []
    ids = set()
    for ex in examples:
        if ex.id in ids:
            problems.append(f"{ex.id}: duplicate id")
        ids.add(ex.id)
        for lab in ex.labels:
            if lab not in LABELS:
                problems.append(f"{ex.id}: unknown label {lab!r}")
        for lab, spans in ex.evidence.items():
            if lab not in ex.labels:
                problems.append(f"{ex.id}: evidence for {lab!r} but label not in labels")
            for sp in spans:
                if sp not in ex.message:
                    problems.append(f"{ex.id}: gold span not in message: {sp!r}")
    return problems


# ---------------------------------------------------------------------------------------------
# metrics


def classification_metrics(gold: list[list[str]], pred: list[list[str]]) -> dict[str, float]:
    mlb = MultiLabelBinarizer(classes=list(LABELS))
    y_true = mlb.fit_transform(gold)
    y_pred = mlb.transform(pred)
    out = {
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "micro_f1": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "macro_precision": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
    }
    per_label = f1_score(y_true, y_pred, average=None, zero_division=0)
    for lab, f in zip(LABELS, per_label):
        out[f"f1_{lab}"] = float(f)
    return {k: float(v) for k, v in out.items()}


def detection_metrics(gold: list[list[str]], pred_susp: list[bool]) -> dict[str, float]:
    y_true = [1 if g else 0 for g in gold]
    y_pred = [1 if p else 0 for p in pred_susp]
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    acc = (tp + tn) / max(1, len(y_true))
    return {
        "detection_accuracy": acc,
        "detection_f1": f1_score(y_true, y_pred, zero_division=0),
        "false_positive_rate": fp / max(1, fp + tn),
        "false_negative_rate": fn / max(1, fn + tp),
    }


_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _token_positions(message: str, span: str) -> set[int]:
    """Character offsets of tokens covered by `span` inside `message` (first occurrence)."""
    start = message.find(span)
    if start == -1:
        return set()
    end = start + len(span)
    return {m.start() for m in _TOKEN.finditer(message) if start <= m.start() < end}


def span_f1(message: str, gold_spans: list[str], pred_spans: list[str]) -> float | None:
    """Token-level F1 between the union of gold spans and the union of predicted spans."""
    if not gold_spans:
        return None
    g: set[int] = set()
    for s in gold_spans:
        g |= _token_positions(message, s)
    p: set[int] = set()
    for s in pred_spans:
        p |= _token_positions(message, s)
    if not g:
        return None
    if not p:
        return 0.0
    tp = len(g & p)
    if tp == 0:
        return 0.0
    prec = tp / len(p)
    rec = tp / len(g)
    return 2 * prec * rec / (prec + rec)


def grounding_metrics(examples: list[Example], results: list[AnalysisResult]) -> dict[str, float]:
    """Exact-grounding rate of raw model quotes (before validation) and token span F1 per label."""
    total_quotes = 0
    exact_quotes = 0
    span_scores: list[float] = []
    for ex, res in zip(examples, results):
        accepted = [q for t in res.tactics for q in t.evidence]
        all_quotes = accepted + list(res.rejected_quotes)
        total_quotes += len(all_quotes)
        exact_quotes += sum(1 for q in all_quotes if q in ex.message)
        for lab, gold in ex.evidence.items():
            pred = next((t.evidence for t in res.tactics if t.label == lab), [])
            f = span_f1(ex.message, gold, pred)
            if f is not None:
                span_scores.append(f)
    return {
        "grounding_rate": exact_quotes / total_quotes if total_quotes else 1.0,
        "verified_evidence_rate": 1.0 if total_quotes == 0 else (total_quotes - sum(len(r.rejected_quotes) for r in results)) / total_quotes,
        "span_f1": sum(span_scores) / len(span_scores) if span_scores else 0.0,
        "n_quotes": float(total_quotes),
    }


def evaluate(examples: list[Example], results: list[AnalysisResult]) -> dict[str, dict[str, float]]:
    """Compute all metrics overall and per dataset category."""
    report: dict[str, dict[str, float]] = {}
    cats = ["all"] + sorted({e.category for e in examples})
    for cat in cats:
        pairs = [(e, r) for e, r in zip(examples, results) if cat == "all" or e.category == cat]
        if not pairs:
            continue
        ex, rs = zip(*pairs)
        gold = [e.labels for e in ex]
        pred = [r.labels for r in rs]
        m: dict[str, float] = {"n": float(len(pairs))}
        m.update(detection_metrics(gold, [r.is_suspicious for r in rs]))
        if any(gold):
            m.update(classification_metrics(gold, pred))
        m.update(grounding_metrics(list(ex), list(rs)))
        m["errors"] = float(sum(1 for r in rs if r.error))
        m["mean_attempts"] = sum(r.attempts for r in rs) / len(rs)
        report[cat] = m
    return report


def format_report(report: dict[str, dict[str, float]]) -> str:
    keys = [
        "n", "detection_accuracy", "detection_f1", "false_positive_rate", "macro_f1", "micro_f1",
        "grounding_rate", "span_f1", "mean_attempts", "errors",
    ]
    cats = list(report)
    w = 22
    lines = ["metric".ljust(w) + "".join(c.rjust(14) for c in cats)]
    for k in keys:
        row = k.ljust(w)
        for c in cats:
            v = report[c].get(k)
            row += ("-" if v is None else (f"{int(v)}" if k in ("n", "errors") else f"{v:.3f}")).rjust(14)
        lines.append(row)
    lines.append("")
    lines.append("per-label F1 (all):")
    for lab in LABELS:
        v = report.get("all", {}).get(f"f1_{lab}")
        lines.append(f"  {lab.ljust(14)} {'-' if v is None else f'{v:.3f}'}")
    return "\n".join(lines)
