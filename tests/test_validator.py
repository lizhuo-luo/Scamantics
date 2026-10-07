from scamantics.schema import LLMAnalysis
from scamantics.validator import grounding_rate, locate, validate

MSG = 'URGENT: Your account will be suspended in 24 hours. Click here now: http://bit.ly/x — "Bank of America" Security Team. Do not tell anyone.'


def test_locate_exact():
    loc = locate("suspended in 24 hours", MSG)
    assert loc is not None
    assert MSG[loc.start : loc.end] == "suspended in 24 hours"


def test_locate_strips_wrapping_quotes():
    loc = locate('"Click here now"', MSG)
    assert loc and loc.text == "Click here now"


def test_locate_lenient_case_and_quotes():
    # model used straight quotes and different case; source has straight quotes but we lower-case.
    loc = locate("'bank of america' security team", MSG)
    assert loc is not None
    assert loc.text == '"Bank of America" Security Team'
    assert MSG[loc.start : loc.end] == loc.text


def test_locate_lenient_whitespace():
    msg = "Please   send\nthe money today"
    loc = locate("send the money", msg)
    assert loc and loc.text == "send\nthe money"


def test_locate_rejects_paraphrase():
    assert locate("your account is going to be closed", MSG) is None


def test_locate_prefers_unused_occurrence():
    msg = "pay now pay now"
    first = locate("pay now", msg)
    second = locate("pay now", msg, used=[(first.start, first.end)])
    assert first.start == 0 and second.start == 8


def test_validate_drops_invalid_quotes_and_empty_tactics():
    analysis = LLMAnalysis(
        is_suspicious=True,
        summary="s",
        tactics=[
            {"label": "urgency", "evidence": ["suspended in 24 hours", "act within the hour"], "explanation": "e1"},
            {"label": "threat", "evidence": ["you will be arrested"], "explanation": "e2"},
            {"label": "isolation", "evidence": ["Do not tell anyone."], "explanation": "e3", "confidence": 0.9},
        ],
    )
    out = validate(analysis, MSG)
    assert [t.label for t in out.tactics] == ["urgency", "isolation"]
    assert out.tactics[0].evidence == ["suspended in 24 hours"]
    assert out.rejected == ["act within the hour", "you will be arrested"]
    assert out.dropped_labels == ["threat"]
    assert not out.ok
    assert [s.label for s in out.spans] == ["urgency", "isolation"]
    assert out.spans[0].start < out.spans[1].start


def test_validate_merges_duplicate_labels():
    analysis = LLMAnalysis(
        is_suspicious=True,
        tactics=[
            {"label": "urgency", "evidence": ["URGENT"], "explanation": "a"},
            {"label": "Urgency", "evidence": ["Click here now"], "explanation": "b"},
        ],
    )
    out = validate(analysis, MSG)
    assert len(out.tactics) == 1
    assert out.tactics[0].evidence == ["URGENT", "Click here now"]
    assert out.ok


def test_grounding_rate():
    assert grounding_rate(["URGENT", "nope"], MSG) == 0.5
    assert grounding_rate([], MSG) == 1.0
