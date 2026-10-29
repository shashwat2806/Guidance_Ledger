from core.extraction.claims import ExtractedClaim
from core.extraction.release import extract_release_claims
from core.extraction.spans import locate_quote

FILLER = "The company held a conference call to discuss the results with analysts and investors today. " * 6
Q3 = "Initiates third quarter FY27 revenue guidance of $11.42 billion to $11.5 billion, up 11% - 12% Y/Y"
FY = "Raises full year FY27 revenue guidance to $46.1 billion to $46.4 billion, up 11% - 12% Y/Y"
OPENING = "Salesforce results for its second quarter fiscal 2027 ended July 31, 2026. "
TEXT = OPENING + FILLER * 15 + Q3 + ". " + FILLER * 15 + FY + ". " + FILLER * 15


def make_claim(window, quote, metric="revenue", low=11420000000, high=11500000000, claim_type="guidance"):
    span = locate_quote(window, quote)
    if span is None:
        return None
    return ExtractedClaim(
        claim_quote=quote, claim_type=claim_type, metric=metric, value_low=low, value_high=high,
        source_start=span[0], source_end=span[1], extraction_confidence=0.9,
    )


def fake_extractor(calls=None):
    def extract(window, period_end=None):
        if calls is not None:
            calls.append((window, period_end))
        found = [
            make_claim(window, Q3),
            make_claim(window, FY, low=46100000000, high=46400000000),
        ]
        return [c for c in found if c is not None]

    return extract


def test_spans_are_shifted_into_whole_release_coordinates():
    claims = extract_release_claims(TEXT, extractor=fake_extractor())

    for claim in claims:
        assert TEXT[claim.source_start:claim.source_end] == claim.claim_quote


def test_claims_far_from_the_start_are_found():
    claims = extract_release_claims(TEXT, extractor=fake_extractor())

    assert {c.value_high for c in claims} == {11500000000, 46400000000}
    assert max(c.source_start for c in claims) > 5000


def test_a_sentence_seen_in_overlapping_windows_is_kept_once():
    claims = extract_release_claims(TEXT, extractor=fake_extractor())

    assert len(claims) == 2


def test_distinct_sentences_with_equal_values_are_not_merged():
    same_growth = ExtractedClaim(
        claim_quote="x", claim_type="guidance", metric="revenue_growth", value_low=11, value_high=12,
        source_start=10, source_end=40, extraction_confidence=0.9,
    )
    other = same_growth.model_copy(update={"claim_quote": "y", "source_start": 9000, "source_end": 9030})
    results = iter([[same_growth], [other]])

    claims = extract_release_claims(TEXT, extractor=lambda window, period_end=None: next(results, []))

    assert len(claims) == 2


def test_the_release_period_end_is_passed_to_every_window():
    calls = []

    extract_release_claims(TEXT, extractor=fake_extractor(calls))

    assert len(calls) > 1
    assert {period_end for _, period_end in calls} == {"2026-07-31"}


def test_an_explicit_period_end_overrides_the_one_in_the_text():
    calls = []

    extract_release_claims(TEXT, period_end="2026-01-31", extractor=fake_extractor(calls))

    assert {period_end for _, period_end in calls} == {"2026-01-31"}


def test_claims_come_back_in_reading_order():
    claims = extract_release_claims(TEXT, extractor=fake_extractor())

    starts = [c.source_start for c in claims]
    assert starts == sorted(starts)


def test_claims_without_a_span_are_deduplicated_by_their_quote():
    unlocated = ExtractedClaim(
        claim_quote="same words", claim_type="reported", metric="revenue", value_low=1e9, value_high=1e9,
        extraction_confidence=0.5,
    )

    claims = extract_release_claims(TEXT, extractor=lambda window, period_end=None: [unlocated])

    assert len(claims) == 1
    assert claims[0].source_start is None
