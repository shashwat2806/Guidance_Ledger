import json

import litellm
import pytest
from pydantic import ValidationError

from core.extraction.claims import ExtractedClaim, extract_claims


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


def claim_json(**overrides):
    base = {
        "claim_quote": "Revenue of $11.3 billion",
        "claim_type": "reported",
        "metric": "revenue",
        "value_low": 11300000000,
        "value_high": 11300000000,
        "comparison_basis": "GAAP",
        "period_end": "2026-07-31",
        "extraction_confidence": 0.95,
    }
    base.update(overrides)
    return base


VALID_CLAIM_JSON = json.dumps([claim_json()])


def patch_completion(monkeypatch, responses):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return FakeResponse(responses[min(len(calls) - 1, len(responses) - 1)])

    monkeypatch.setattr("core.extraction.claims.litellm.completion", fake_completion)
    return calls


def test_extracted_claim_requires_at_least_one_value():
    with pytest.raises(ValidationError):
        ExtractedClaim(claim_quote="some claim", metric="revenue", extraction_confidence=0.9)


def test_extracted_claim_rejects_unknown_metric():
    with pytest.raises(ValidationError):
        ExtractedClaim(claim_quote="some claim", metric="operating_margin", value_low=1, extraction_confidence=0.9)


def test_extracted_claim_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        ExtractedClaim(claim_quote="some claim", metric="revenue", value_low=1, extraction_confidence=1.5)


def test_extract_claims_succeeds_on_first_valid_response(monkeypatch):
    patch_completion(monkeypatch, [VALID_CLAIM_JSON])

    claims = extract_claims("some press release text")

    assert len(claims) == 1
    assert claims[0].metric == "revenue"
    assert claims[0].value_low == 11300000000


def test_extract_claims_retries_after_malformed_response(monkeypatch):
    calls = patch_completion(monkeypatch, ["not valid json at all", VALID_CLAIM_JSON])

    claims = extract_claims("some press release text")

    assert len(calls) == 2
    assert len(claims) == 1
    assert "failed validation" in calls[1]["messages"][0]["content"]


def test_extract_claims_raises_after_exhausting_retries(monkeypatch):
    patch_completion(monkeypatch, ["still not valid json"])

    with pytest.raises(RuntimeError):
        extract_claims("some press release text", max_retries=2)


def test_extract_claims_waits_and_retries_on_rate_limit(monkeypatch):
    calls = []
    sleeps = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise litellm.exceptions.RateLimitError(
                message="rate limited", llm_provider="groq", model="test-model"
            )
        return FakeResponse(VALID_CLAIM_JSON)

    monkeypatch.setattr("core.extraction.claims.litellm.completion", fake_completion)
    monkeypatch.setattr("core.extraction.claims.time.sleep", lambda s: sleeps.append(s))

    claims = extract_claims("some press release text")

    assert len(calls) == 2
    assert len(sleeps) == 1
    assert len(claims) == 1
    assert "failed validation" not in calls[1]["messages"][0]["content"]


def test_extract_claims_passes_reasoning_effort_when_configured(monkeypatch):
    seen = {}

    def fake_completion(**kwargs):
        seen.update(kwargs)
        return FakeResponse(VALID_CLAIM_JSON)

    monkeypatch.setattr("core.extraction.claims.litellm.completion", fake_completion)
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")

    extract_claims("some press release text")

    assert seen["reasoning_effort"] == "low"
    assert seen["reasoning_format"] == "parsed"


def test_extract_claims_omits_reasoning_params_when_not_configured(monkeypatch):
    seen = {}

    def fake_completion(**kwargs):
        seen.update(kwargs)
        return FakeResponse(VALID_CLAIM_JSON)

    monkeypatch.setattr("core.extraction.claims.litellm.completion", fake_completion)
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)

    extract_claims("some press release text")

    assert "reasoning_effort" not in seen


def test_extract_claims_rejects_revenue_not_in_full_dollars_and_retries(monkeypatch):
    wrong_scale = json.dumps([claim_json(value_low=11.3, value_high=11.3)])
    calls = patch_completion(monkeypatch, [wrong_scale, VALID_CLAIM_JSON])

    claims = extract_claims("some press release text")

    assert len(calls) == 2
    assert "full dollars" in calls[1]["messages"][0]["content"]
    assert claims[0].value_low == 11300000000


def test_extract_claims_requires_claim_type_and_retries(monkeypatch):
    item = claim_json()
    del item["claim_type"]
    calls = patch_completion(monkeypatch, [json.dumps([item]), VALID_CLAIM_JSON])

    claims = extract_claims("some press release text")

    assert len(calls) == 2
    assert "claim_type" in calls[1]["messages"][0]["content"]
    assert claims[0].claim_type == "reported"


def test_extract_claims_keeps_guidance_separate_from_reported(monkeypatch):
    mixed = json.dumps([
        claim_json(),
        claim_json(
            claim_quote="Raises full year revenue guidance to $46.1 billion to $46.4 billion",
            claim_type="guidance",
            value_low=46100000000,
            value_high=46400000000,
            period_end=None,
        ),
    ])
    patch_completion(monkeypatch, [mixed])

    claims = extract_claims("some press release text")

    assert [c.claim_type for c in claims] == ["reported", "guidance"]


def test_extract_claims_retries_on_pydantic_validation_error(monkeypatch):
    bad_metric = json.dumps([claim_json(metric="operating_margin")])
    calls = patch_completion(monkeypatch, [bad_metric, VALID_CLAIM_JSON])

    claims = extract_claims("some press release text")

    assert len(calls) == 2
    assert len(claims) == 1


def test_growth_claims_are_not_subject_to_the_dollar_check(monkeypatch):
    growth = json.dumps([claim_json(
        claim_quote="up 11% Y/Y", metric="revenue_growth", value_low=11.0, value_high=11.0,
    )])
    calls = patch_completion(monkeypatch, [growth])

    claims = extract_claims("some press release text")

    assert len(calls) == 1
    assert claims[0].metric == "revenue_growth"
    assert claims[0].value_low == 11.0
