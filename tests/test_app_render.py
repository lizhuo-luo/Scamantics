"""Rendering helpers in app.py must escape input and reflect the result faithfully."""

import app
from scamantics.schema import AnalysisResult, EvidenceSpan, VerifiedTactic

MSG = "URGENT <b>act now</b> or your account will be closed. Don't tell anyone."


def _result() -> AnalysisResult:
    return AnalysisResult(
        message=MSG,
        is_suspicious=True,
        summary="Pressure & secrecy.",
        tactics=[
            VerifiedTactic(label="urgency", evidence=["act now"], explanation="deadline <script>", confidence=0.9),
            VerifiedTactic(label="isolation", evidence=["Don't tell anyone."], explanation="secrecy", confidence=None),
        ],
        spans=[
            EvidenceSpan(label="urgency", text="act now", start=MSG.index("act now"), end=MSG.index("act now") + 7),
            EvidenceSpan(label="isolation", text="Don't tell anyone.", start=MSG.index("Don't"), end=len(MSG)),
        ],
        provider="mock",
        model="m",
    )


def test_render_result_contains_sections_and_escapes_html():
    out = app.render_result(_result(), seconds=1.2)
    assert "2 manipulation tactics found" in out
    assert "&lt;b&gt;" in out and "&lt;/b&gt;" in out and "<b>" not in out  # user HTML escaped
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert out.count("<mark") == 2
    assert "Tactics in detail" in out
    assert "What you can do" in out
    assert "90%" in out
    assert "model mock:m" in out and "1.2s" in out


def test_render_benign_and_error():
    benign = AnalysisResult(message="hi", is_suspicious=False, summary="Ordinary.", tactics=[], spans=[])
    out = app.render_result(benign)
    assert "No strong manipulation tactic detected" in out
    assert "Tactics in detail" not in out and "verified to appear" not in out
    err = AnalysisResult(message="x", is_suspicious=False, summary="", tactics=[], spans=[], error="API <down>")
    out = app.render_result(err)
    assert "Could not analyse" in out and "API &lt;down&gt;" in out


def test_examples_and_labels_align():
    assert len(app.EXAMPLES) == len(app.EXAMPLE_LABELS)
    assert len(set(app.EXAMPLES)) == len(app.EXAMPLES)


def test_build_app_with_initial_message(monkeypatch):
    monkeypatch.setenv("SCAMANTICS_PROVIDER", "mock")
    app._analyzer = None
    demo = app.build_app(initial_message=app.EXAMPLES[0])
    assert demo is not None
    html, raw = app.analyse(app.EXAMPLES[0])
    assert raw["from_cache"] is True and "manipulation tactic" in html
