from scamantiq.evaluation import (
    check_dataset,
    classification_metrics,
    detection_metrics,
    evaluate,
    format_report,
    load_dataset,
    span_f1,
)
from scamantiq.schema import AnalysisResult, VerifiedTactic


def test_dataset_integrity():
    ex = load_dataset("data/test_set.jsonl")
    assert len(ex) >= 90
    assert check_dataset(ex) == []
    cats = {e.category for e in ex}
    assert cats == {"familiar", "paraphrased", "benign", "hard_benign", "subtle_scam"}
    assert all(e.labels == [] for e in ex if e.category in ("benign", "hard_benign"))
    assert all(e.labels for e in ex if e.category in ("familiar", "paraphrased"))


def test_classification_metrics_perfect_and_empty():
    gold = [["urgency"], ["threat", "reward"], []]
    m = classification_metrics(gold, gold)
    assert m["micro_f1"] == 1.0
    m2 = classification_metrics(gold, [[], [], []])
    assert m2["micro_f1"] == 0.0


def test_detection_metrics():
    m = detection_metrics([["urgency"], [], []], [True, True, False])
    assert m["detection_accuracy"] == 2 / 3
    assert m["false_positive_rate"] == 0.5


def test_span_f1():
    msg = "Pay now or your account will be closed today."
    assert span_f1(msg, ["Pay now"], ["Pay now"]) == 1.0
    assert span_f1(msg, ["Pay now"], ["closed today"]) == 0.0
    partial = span_f1(msg, ["your account will be closed"], ["will be closed today"])
    assert 0 < partial < 1
    assert span_f1(msg, [], ["Pay now"]) is None


def test_evaluate_report_shape():
    ex = load_dataset("data/test_set.jsonl")[:3]
    results = []
    for e in ex:
        tactics = [VerifiedTactic(label=l, evidence=e.evidence.get(l, []), explanation="x") for l in e.labels]
        results.append(AnalysisResult(message=e.message, is_suspicious=bool(e.labels), summary="", tactics=tactics, spans=[]))
    rep = evaluate(ex, results)
    assert rep["all"]["micro_f1"] == 1.0
    assert rep["all"]["grounding_rate"] == 1.0
    assert rep["all"]["span_f1"] == 1.0
    txt = format_report(rep)
    assert "macro_f1" in txt
