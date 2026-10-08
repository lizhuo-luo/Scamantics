import pytest

from scamantiq.analyzer import parse_llm_output
from scamantiq.providers.base import ProviderError, extract_json_object
from scamantiq.schema import TacticRecord
from scamantiq.taxonomy import LABELS, normalise_label


def test_taxonomy_has_five_labels():
    assert LABELS == ("urgency", "impersonation", "isolation", "reward", "threat")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Urgency", "urgency"),
        ("impersonation or authority", "impersonation"),
        ("Threat/Penalty", "threat"),
        ("reward_or_incentive", "reward"),
        ("Isolation / Secrecy", "isolation"),
        ("banana", None),
    ],
)
def test_normalise_label(raw, expected):
    assert normalise_label(raw) == expected


def test_tactic_record_coercions():
    r = TacticRecord(label="Threat / Penalty", evidence="single quote", confidence="85")
    assert r.label == "threat"
    assert r.evidence == ["single quote"]
    assert r.confidence == 0.85


def test_extract_json_with_fences_and_prose():
    text = 'Sure! Here you go:\n```json\n{"is_suspicious": true, "tactics": []}\n```\nHope this helps.'
    assert extract_json_object(text) == {"is_suspicious": True, "tactics": []}


def test_extract_json_nested_braces_in_strings():
    text = '{"summary": "has } brace", "tactics": [{"label": "urgency"}]}'
    assert extract_json_object(text)["summary"] == "has } brace"


def test_extract_json_failure():
    with pytest.raises(ProviderError):
        extract_json_object("no json here")


def test_parse_drops_unknown_labels_and_coerces_bool():
    raw = '{"is_suspicious": "yes", "summary": "x", "tactics": [{"label": "flattery", "evidence": ["a"]}, {"label": "urgency", "evidence": ["now"]}]}'
    a = parse_llm_output(raw)
    assert a.is_suspicious is True
    assert [t.label for t in a.tactics] == ["urgency"]
