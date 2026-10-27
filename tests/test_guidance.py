import json
from datetime import date

import pytest

from core.extraction.claims import ExtractedClaim
from core.guidance.scoring import (
    add_months,
    classify_outcome,
    fiscal_quarter,
    fiscal_year_end_month,
    guided_period,
    score_guidance,
)

SOURCE = {"document_url": "https://www.sec.gov/Archives/edgar/data/1/2/pr.htm", "accession_number": "0001108524-26-000125"}


def make_fact(start, end, value, accession="0001-26-000001"):
    return {
        "canonical_concept": "revenue",
        "start_date": start,
        "end_date": end,
        "value": value,
        "filed_date": "2026-08-27",
        "accession_number": accession,
        "form": "10-Q",
        "raw_tag": "Revenues",
        "unit": "USD",
    }


FACTS = [
    make_fact("2026-02-01", "2026-04-30", 11133000000),
    make_fact("2025-02-01", "2025-04-30", 9829000000),
    make_fact("2026-05-01", "2026-07-31", 11345000000, accession="q2-fy27"),
    make_fact("2025-05-01", "2025-07-31", 10236000000, accession="q2-fy26"),
    make_fact("2026-02-01", "2026-07-31", 22478000000),
    make_fact("2025-02-01", "2026-01-31", 41525000000),
    make_fact("2024-02-01", "2025-01-31", 37895000000),
]


def make_guidance(quote, metric="revenue", low=11200000000, high=11300000000, basis="GAAP", **overrides):
    values = {
        "claim_quote": quote,
        "claim_type": "guidance",
        "metric": metric,
        "value_low": low,
        "value_high": high,
        "comparison_basis": basis,
        "basis_assumed": True,
        "source_start": 0,
        "source_end": len(quote),
        "extraction_confidence": 0.9,
    }
    values.update(overrides)
    return ExtractedClaim(**values)


Q2_QUOTE = "Initiates second quarter FY27 revenue guidance of $11.2 billion to $11.3 billion, up 10% - 11% Y/Y"


def test_add_months_keeps_month_ends():
    assert add_months(date(2026, 7, 31), 3) == date(2026, 10, 31)
    assert add_months(date(2026, 10, 31), 3) == date(2027, 1, 31)
    assert add_months(date(2027, 1, 31), 3) == date(2027, 4, 30)
    assert add_months(date(2027, 1, 31), -9) == date(2026, 4, 30)
    assert add_months(date(2026, 12, 31), 2) == date(2027, 2, 28)


def test_fiscal_quarter_for_a_january_year_end():
    assert [fiscal_quarter(date(2026, m, 28), 1) for m in (4, 7, 10)] == [1, 2, 3]
    assert fiscal_quarter(date(2027, 1, 31), 1) == 4


def test_fiscal_quarter_for_a_december_year_end():
    assert [fiscal_quarter(date(2026, m, 28), 12) for m in (3, 6, 9, 12)] == [1, 2, 3, 4]


def test_fiscal_year_end_month_is_read_from_annual_facts():
    assert fiscal_year_end_month(FACTS) == 1
    assert fiscal_year_end_month([]) is None


@pytest.mark.parametrize("quote, release_end, expected", [
    ("Initiates third quarter FY27 revenue guidance of $11.42 billion to $11.5 billion", "2026-07-31", ("quarter", "2026-10-31")),
    ("Raises full year FY27 revenue guidance to $46.1 billion to $46.4 billion", "2026-07-31", ("year", "2027-01-31")),
    ("Initiates first quarter FY27 revenue guidance of $11.0 billion", "2026-01-31", ("quarter", "2026-04-30")),
    ("Initiates full year FY27 revenue guidance of $45.8 billion to $46.2 billion", "2026-01-31", ("year", "2027-01-31")),
    ("Q3 revenue guidance of $11.4 billion", "2026-07-31", ("quarter", "2026-10-31")),
    ("Revenue guidance for the next quarter of $11.4 billion", "2026-07-31", ("quarter", "2026-10-31")),
    ("Full year revenue guidance of $46 billion", "2026-01-31", ("year", "2027-01-31")),
    ("Full year revenue guidance of $46 billion", "2026-07-31", ("year", "2027-01-31")),
    ("Revenue guidance of $11.4 billion", "2026-07-31", None),
    ("Revenue guidance for the first six months of $22 billion", "2026-07-31", None),
    ("we're well on our way to $63 billion in revenue in FY30", "2026-07-31", ("year", "2030-01-31")),
])
def test_guided_period_is_worked_out_from_the_quote_and_the_release(quote, release_end, expected):
    assert guided_period(make_guidance(quote), release_end, 1) == expected


def test_guided_period_needs_a_readable_release_date():
    assert guided_period(make_guidance(Q2_QUOTE), None, 1) is None
    assert guided_period(make_guidance(Q2_QUOTE), "not a date", 1) is None


def test_actual_inside_the_range_is_met():
    assert classify_outcome(11.2e9, 11.3e9, 11.25e9, "revenue") == ("met", 0.0)


def test_actual_above_the_range_is_exceeded_with_a_positive_gap():
    outcome, gap = classify_outcome(11.2e9, 11.3e9, 11.345e9, "revenue")

    assert outcome == "exceeded"
    assert gap == pytest.approx(0.003982, abs=1e-5)


def test_actual_below_the_range_is_missed_with_a_negative_gap():
    outcome, gap = classify_outcome(11.2e9, 11.3e9, 11.0e9, "revenue")

    assert outcome == "missed"
    assert gap < 0


def test_rounding_sized_overshoot_still_counts_as_met():
    assert classify_outcome(11.42e9, 11.5e9, 11.503e9, "revenue")[0] == "met"


def test_growth_within_half_a_point_of_the_range_is_met():
    assert classify_outcome(11, 12, 10.83, "revenue_growth")[0] == "met"
    assert classify_outcome(11, 12, 10.4, "revenue_growth")[0] == "missed"


def test_floor_only_guidance():
    assert classify_outcome(11e9, None, 11.5e9, "revenue")[0] == "met"
    assert classify_outcome(11e9, None, 10.5e9, "revenue")[0] == "missed"


def test_ceiling_only_guidance():
    assert classify_outcome(None, 11e9, 10.5e9, "revenue")[0] == "met"
    assert classify_outcome(None, 11e9, 11.5e9, "revenue")[0] == "exceeded"


def test_missing_or_inverted_range_cannot_be_classified():
    assert classify_outcome(None, None, 11e9, "revenue") is None
    assert classify_outcome(12e9, 11e9, 11.5e9, "revenue") is None


def test_past_guidance_is_scored_against_the_filed_actual():
    result = score_guidance(make_guidance(Q2_QUOTE), Q2_QUOTE, SOURCE, "2026-04-30", FACTS)

    assert result["outcome"] == "exceeded"
    assert result["difference"] == pytest.approx(0.003982, abs=1e-5)
    assert result["guidance"]["guided_period_end"] == "2026-07-31"
    assert result["actual"]["fact"]["accession_number"] == "q2-fy27"
    assert result["guidance_source"]["excerpt"] == Q2_QUOTE
    assert result["reason"] is None


def test_growth_guidance_is_scored_against_the_computed_actual_growth():
    claim = make_guidance(Q2_QUOTE, metric="revenue_growth", low=10, high=11)

    result = score_guidance(claim, Q2_QUOTE, SOURCE, "2026-04-30", FACTS)

    assert result["outcome"] == "met"
    assert result["actual"]["value"] == pytest.approx(10.834, abs=0.001)
    assert result["actual"]["prior_fact"]["accession_number"] == "q2-fy26"


def test_guidance_for_a_period_not_yet_reported_is_insufficient_evidence():
    quote = "Initiates third quarter FY27 revenue guidance of $11.42 billion to $11.5 billion"

    result = score_guidance(make_guidance(quote), quote, SOURCE, "2026-07-31", FACTS)

    assert result["outcome"] == "insufficient_evidence"
    assert "2026-10-31" in result["reason"]
    assert result["actual"] is None


def test_non_gaap_guidance_is_not_scored():
    result = score_guidance(make_guidance(Q2_QUOTE, basis="non-GAAP"), Q2_QUOTE, SOURCE, "2026-04-30", FACTS)

    assert result["outcome"] == "insufficient_evidence"
    assert "GAAP" in result["reason"]


def test_guidance_without_a_citation_is_not_scored():
    claim = make_guidance(Q2_QUOTE, source_start=None, source_end=None)

    result = score_guidance(claim, Q2_QUOTE, SOURCE, "2026-04-30", FACTS)

    assert result["outcome"] == "insufficient_evidence"
    assert "citation" in result["reason"]
    assert result["guidance_source"] is None


def test_guidance_with_no_readable_period_is_insufficient_evidence():
    quote = "Revenue guidance of $11.2 billion to $11.3 billion"

    result = score_guidance(make_guidance(quote), quote, SOURCE, "2026-04-30", FACTS)

    assert result["outcome"] == "insufficient_evidence"
    assert "which fiscal period" in result["reason"]


def test_reported_claims_are_refused():
    with pytest.raises(ValueError):
        score_guidance(make_guidance(Q2_QUOTE, claim_type="reported"), Q2_QUOTE, SOURCE, "2026-04-30", FACTS)


def test_scoring_result_is_json_serializable():
    result = score_guidance(make_guidance(Q2_QUOTE), Q2_QUOTE, SOURCE, "2026-04-30", FACTS)

    assert json.loads(json.dumps(result))["outcome"] == "exceeded"
