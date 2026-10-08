import json

from scamantiq.analyzer import Analyzer
from scamantiq.cache import DemoCache
from scamantiq.providers.mock import MockProvider

MSG = "Dear customer, your parcel is held at customs. Pay the $2.99 fee within 12 hours or it will be returned."


def _good():
    return {
        "is_suspicious": True,
        "summary": "Pressures you to pay quickly.",
        "tactics": [
            {"label": "urgency", "evidence": ["within 12 hours"], "explanation": "deadline", "confidence": 0.9},
            {"label": "threat", "evidence": ["or it will be returned"], "explanation": "penalty", "confidence": 0.7},
        ],
    }


def test_analyze_happy_path(settings):
    an = Analyzer(settings, provider=MockProvider(settings, {MSG: _good()}))
    res = an.analyze(MSG)
    assert res.error is None
    assert res.is_suspicious
    assert res.labels == ["urgency", "threat"]
    assert res.attempts == 1
    assert res.rejected_quotes == []
    assert [s.text for s in res.spans] == ["within 12 hours", "or it will be returned"]


def test_analyze_retries_on_bad_evidence(settings):
    bad = _good()
    bad["tactics"][0]["evidence"] = ["in twelve hours"]  # paraphrase -> rejected

    class Seq(MockProvider):
        def __init__(self, s):
            super().__init__(s)
            self.n = 0

        def complete_json(self, system, user, schema=None):
            self.calls.append((system, user))
            self.n += 1
            return json.dumps(bad if self.n == 1 else _good())

    p = Seq(settings)
    res = Analyzer(settings, provider=p).analyze(MSG)
    assert p.n == 2
    assert "REJECTED" in p.calls[1][1]
    assert "in twelve hours" in p.calls[1][1]
    assert res.attempts == 2
    assert res.labels == ["urgency", "threat"]


def test_analyze_gives_up_after_retries_and_keeps_valid_parts(settings):
    bad = _good()
    bad["tactics"][0]["evidence"] = ["in twelve hours"]
    res = Analyzer(settings, provider=MockProvider(settings, {MSG: bad})).analyze(MSG)
    assert res.attempts == 2
    assert res.labels == ["threat"]
    assert res.rejected_quotes == ["in twelve hours"]


def test_no_verified_evidence_means_not_suspicious(settings):
    ans = {"is_suspicious": True, "summary": "", "tactics": [{"label": "urgency", "evidence": ["nonsense"], "explanation": ""}]}
    res = Analyzer(settings, provider=MockProvider(settings, {MSG: ans})).analyze(MSG)
    assert res.is_suspicious is False
    assert res.tactics == []
    assert "No strong manipulation" in res.summary


def test_benign_message(settings):
    msg = "Hi Sam, running 10 min late, order me a flat white?"
    ans = {"is_suspicious": False, "summary": "Ordinary message.", "tactics": []}
    res = Analyzer(settings, provider=MockProvider(settings, {msg: ans})).analyze(msg)
    assert res.is_suspicious is False and res.tactics == [] and res.error is None


def test_empty_message(settings):
    res = Analyzer(settings, provider=MockProvider(settings)).analyze("   ")
    assert res.error


def test_provider_failure_falls_back_to_cache_then_error(settings, tmp_path):
    cache = DemoCache(tmp_path / "c.json")
    an = Analyzer(settings, provider=MockProvider(settings, {MSG: _good()}), cache=cache)
    first = an.analyze(MSG)
    cache.put(first)
    cache.save()

    offline = Analyzer(settings, provider=MockProvider(settings), cache=DemoCache(tmp_path / "c.json"))
    res = offline.analyze(MSG)
    assert res.from_cache and res.labels == ["urgency", "threat"]

    other = offline.analyze("something never seen")
    assert other.error and "unavailable" in other.error


def test_invalid_json_then_valid(settings):
    class Seq(MockProvider):
        n = 0

        def complete_json(self, system, user, schema=None):
            self.n += 1
            return "garbage" if self.n == 1 else json.dumps(_good())

    res = Analyzer(settings, provider=Seq(settings)).analyze(MSG)
    assert res.error is None and res.attempts == 2
