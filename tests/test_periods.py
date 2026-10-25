import json

from core.extraction.claims import ExtractedClaim, extract_claims
from core.extraction.periods import release_period_end
from core.verification.evidence import build_evidence_card

QUOTE = "Revenue of $11.3 billion, up 11% Y/Y"
OPENING = (
    "Salesforce Delivers Record Second Quarter Fiscal 2027 Results SAN FRANCISCO, Calif. - August 26, 2026 - "
    "Salesforce today announced results for its second quarter fiscal 2027 ended July 31, 2026. "
    "Second Quarter Financial Highlights \u2022 " + QUOTE
)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


def claim_item(**overrides):
    base = {
        "claim_quote": QUOTE,
        "claim_type": "reported",
        "metric": "revenue",
        "value_low": 11300000000,
        "value_high": 11300000000,
        "period_end": None,
        "extraction_confidence": 0.95,
    }
    base.update(overrides)
    return base


def extract_one(monkeypatch, text=OPENING, **kwargs):
    item = claim_item(**{k: v for k, v in kwargs.items() if k != "period_end_arg"})
    monkeypatch.setattr(
        "core.extraction.claims.litellm.completion",
        lambda **_: FakeResponse(json.dumps([item])),
    )
    extra = {"period_end": kwargs["period_end_arg"]} if "period_end_arg" in kwargs else {}
    return extract_claims(text, **extra)[0]


def test_reads_the_period_end_from_the_opening_paragraph():
    assert release_period_end(OPENING) == "2026-07-31"


def test_period_end_reading_ignores_case_and_comma():
    assert release_period_end("results for the QUARTER ENDED JULY 31 2026.") == "2026-07-31"


def test_no_ended_date_gives_none():
    assert release_period_end("Salesforce today announced results.") is None


def test_dates_beyond_the_opening_are_ignored():
    assert release_period_end("x" * 3500 + " ended July 31, 2026") is None


def test_impossible_date_gives_none():
    assert release_period_end("quarter ended February 31, 2026") is None


def test_extract_claims_fills_the_period_for_reported_claims(monkeypatch):
    claim = extract_one(monkeypatch)

    assert claim.period_end == "2026-07-31"
    assert claim.period_from_release is True


def test_release_period_replaces_the_models_period(monkeypatch):
    claim = extract_one(monkeypatch, period_end="2026-04-30")

    assert claim.period_end == "2026-07-31"


def test_guidance_claims_keep_the_models_period(monkeypatch):
    claim = extract_one(monkeypatch, claim_type="guidance")

    assert claim.period_end is None
    assert claim.period_from_release is False


def test_explicit_period_end_argument_wins(monkeypatch):
    claim = extract_one(monkeypatch, period_end_arg="2026-01-31")

    assert claim.period_end == "2026-01-31"


def test_card_records_that_the_period_came_from_the_release():
    claim = ExtractedClaim(
        claim_quote=QUOTE, claim_type="reported", metric="revenue", value_low=11300000000,
        value_high=11300000000, period_end="2026-07-31", period_from_release=True,
        source_start=0, source_end=len(QUOTE), extraction_confidence=0.9,
    )
    fact = {"accession_number": "a", "form": "10-Q", "value": 1}

    card = build_evidence_card(
        claim, QUOTE, {"document_url": "u", "accession_number": "b"}, fact,
        verify=lambda c, f, prior_fact=None: {"verdict": "supported", "difference": 0.0, "abstention_reason": None},
    )

    assert "period end read from the release's opening paragraph" in card["rules_applied"]
