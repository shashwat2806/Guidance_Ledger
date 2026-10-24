import json

import pytest

from core.extraction.claims import ExtractedClaim
from core.verification.evidence import build_evidence_card

QUOTE = "Revenue of $11.3 billion, up 11% Y/Y"
TEXT = "Intro text. " + QUOTE + ". More text."
START = TEXT.index(QUOTE)
END = START + len(QUOTE)

SOURCE = {
    "document_url": "https://www.sec.gov/Archives/edgar/data/1108524/000110852426000187/pr.htm",
    "accession_number": "0001108524-26-000187",
}

FACT = {
    "accession_number": "0001108524-26-000190",
    "form": "10-Q",
    "raw_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "value": 11345000000,
    "unit": "USD",
    "start_date": "2026-05-01",
    "end_date": "2026-07-31",
    "filed_date": "2026-08-27",
}

PRIOR = {**FACT, "accession_number": "0001108524-25-000088", "value": 10236000000,
         "start_date": "2025-05-01", "end_date": "2025-07-31", "filed_date": "2025-09-04"}

SUPPORTED = {"verdict": "supported", "difference": 0.004, "abstention_reason": None}


def make_claim(**overrides):
    base = {
        "claim_quote": QUOTE,
        "claim_type": "reported",
        "metric": "revenue",
        "value_low": 11300000000,
        "value_high": 11300000000,
        "comparison_basis": "GAAP",
        "basis_assumed": False,
        "period_end": "2026-07-31",
        "source_start": START,
        "source_end": END,
        "extraction_confidence": 0.95,
    }
    base.update(overrides)
    return ExtractedClaim(**base)


def fake_verifier(result, calls=None):
    def verify(claim, fact, prior_fact=None):
        if calls is not None:
            calls.append((claim, fact, prior_fact))
        return result

    return verify


def test_card_carries_verifier_result_and_both_citations():
    card = build_evidence_card(make_claim(), TEXT, SOURCE, FACT, verify=fake_verifier(SUPPORTED))

    assert card["verdict"] == "supported"
    assert card["difference"] == 0.004
    assert card["claim_source"]["excerpt"] == QUOTE
    assert (card["claim_source"]["start"], card["claim_source"]["end"]) == (START, END)
    assert card["claim_source"]["accession_number"] == "0001108524-26-000187"
    assert card["claim_source"]["document_url"] == SOURCE["document_url"]
    assert card["filed_fact"]["accession_number"] == "0001108524-26-000190"
    assert card["filed_fact"]["form"] == "10-Q"


def test_claim_without_a_span_abstains_and_never_reaches_the_verifier():
    calls = []
    claim = make_claim(source_start=None, source_end=None)

    card = build_evidence_card(claim, TEXT, SOURCE, FACT, verify=fake_verifier(SUPPORTED, calls))

    assert card["verdict"] == "insufficient_evidence"
    assert "citation" in card["abstention_reason"]
    assert card["claim_source"] is None
    assert card["filed_fact"] is None
    assert calls == []


def test_verifier_abstention_passes_through_unchanged():
    result = {"verdict": "insufficient_evidence", "difference": None, "abstention_reason": "period mismatch"}

    card = build_evidence_card(make_claim(), TEXT, SOURCE, FACT, verify=fake_verifier(result))

    assert card["verdict"] == "insufficient_evidence"
    assert card["abstention_reason"] == "period mismatch"
    assert card["claim_source"] is not None


def test_assumed_basis_is_recorded_as_a_rule_applied():
    assumed = build_evidence_card(make_claim(basis_assumed=True), TEXT, SOURCE, FACT, verify=fake_verifier(SUPPORTED))
    stated = build_evidence_card(make_claim(basis_assumed=False), TEXT, SOURCE, FACT, verify=fake_verifier(SUPPORTED))

    assert assumed["rules_applied"] == ["basis not stated in the quote; assumed GAAP"]
    assert stated["rules_applied"] == []


def test_prior_fact_is_included_only_for_growth_claims():
    growth = make_claim(metric="revenue_growth", value_low=11.0, value_high=11.0)

    growth_card = build_evidence_card(growth, TEXT, SOURCE, FACT, prior_fact=PRIOR, verify=fake_verifier(SUPPORTED))
    revenue_card = build_evidence_card(make_claim(), TEXT, SOURCE, FACT, prior_fact=PRIOR, verify=fake_verifier(SUPPORTED))

    assert growth_card["prior_fact"]["accession_number"] == "0001108524-25-000088"
    assert revenue_card["prior_fact"] is None


def test_verifier_receives_the_claim_fact_and_prior_fact():
    calls = []
    claim = make_claim(metric="revenue_growth", value_low=11.0, value_high=11.0)

    build_evidence_card(claim, TEXT, SOURCE, FACT, prior_fact=PRIOR, verify=fake_verifier(SUPPORTED, calls))

    assert calls == [(claim, FACT, PRIOR)]


def test_guidance_claims_are_refused():
    with pytest.raises(ValueError):
        build_evidence_card(make_claim(claim_type="guidance"), TEXT, SOURCE, FACT, verify=fake_verifier(SUPPORTED))


def test_card_is_json_serializable():
    card = build_evidence_card(make_claim(basis_assumed=True), TEXT, SOURCE, FACT, verify=fake_verifier(SUPPORTED))

    assert json.loads(json.dumps(card))["verdict"] == "supported"
