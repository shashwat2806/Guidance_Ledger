import json

from core.extraction.claims import extract_claims
from core.extraction.spans import locate_quote

SOURCE = "Intro text. Revenue of $11.3 billion, up 11% Y/Y. More text follows here."
QUOTE = "Revenue of $11.3 billion, up 11% Y/Y"


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
        "period_end": "2026-07-31",
        "extraction_confidence": 0.95,
    }
    base.update(overrides)
    return base


def patch_completion(monkeypatch, item):
    monkeypatch.setattr(
        "core.extraction.claims.litellm.completion",
        lambda **kwargs: FakeResponse(json.dumps([item])),
    )


def test_exact_quote_returns_matching_offsets():
    start, end = locate_quote(SOURCE, QUOTE)

    assert SOURCE[start:end] == QUOTE


def test_match_ignores_case_and_returns_original_text():
    text = "Salesforce Raises full year FY27 revenue guidance to $46.1 billion today."

    start, end = locate_quote(text, "raises full year fy27 revenue guidance")

    assert text[start:end] == "Raises full year FY27 revenue guidance"


def test_match_ignores_whitespace_differences():
    text = "Revenue  of $11.3\nbillion,   up 11% Y/Y"

    start, end = locate_quote(text, "Revenue of $11.3 billion, up 11% Y/Y")

    assert text[start:end] == text


def test_match_ignores_curly_quotes_and_dashes():
    text = "Salesforce\u2019s revenue was up 11\u201312% this quarter"

    start, end = locate_quote(text, "Salesforce's revenue was up 11-12% this quarter")

    assert text[start:end] == text


def test_missing_quote_returns_none():
    assert locate_quote(SOURCE, "Revenue of $99 billion") is None


def test_empty_quote_returns_none():
    assert locate_quote(SOURCE, "   ") is None


def test_first_occurrence_wins():
    text = "Revenue grew 11%. Later: Revenue grew 11%."

    start, end = locate_quote(text, "Revenue grew 11%")

    assert start == 0


def test_offsets_use_original_coordinates_after_collapsed_whitespace():
    text = "a   b   Revenue grew"

    start, end = locate_quote(text, "Revenue grew")

    assert start == text.index("Revenue grew")
    assert text[start:end] == "Revenue grew"


def test_extract_claims_attaches_span_for_found_quote(monkeypatch):
    patch_completion(monkeypatch, claim_item())

    claim = extract_claims(SOURCE)[0]

    assert SOURCE[claim.source_start:claim.source_end] == QUOTE


def test_extract_claims_leaves_span_empty_when_quote_not_found(monkeypatch):
    patch_completion(monkeypatch, claim_item(claim_quote="Revenue of $99 billion"))

    claim = extract_claims(SOURCE)[0]

    assert claim.source_start is None
    assert claim.source_end is None


def test_span_from_a_prefix_matches_span_in_the_full_text(monkeypatch):
    patch_completion(monkeypatch, claim_item())

    from_prefix = extract_claims(SOURCE[:60])[0]
    from_full = extract_claims(SOURCE)[0]

    assert (from_prefix.source_start, from_prefix.source_end) == (from_full.source_start, from_full.source_end)
