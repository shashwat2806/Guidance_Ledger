from core.extraction.claims import ExtractedClaim
from core.verification.evidence import build_evidence_card
from core.verification.matching import match_facts, period_kind

QUOTE = "Revenue of $11.3 billion, up 11% Y/Y"


def make_fact(start, end, value, filed="2026-08-27", accession="0001-26-000001"):
    return {
        "canonical_concept": "revenue",
        "start_date": start,
        "end_date": end,
        "value": value,
        "filed_date": filed,
        "accession_number": accession,
    }


FACTS = [
    make_fact("2026-05-01", "2026-07-31", 11345000000),
    make_fact("2026-02-01", "2026-07-31", 22478000000),
    make_fact("2025-05-01", "2025-07-31", 10236000000),
    make_fact("2025-02-01", "2025-07-31", 20000000000),
    make_fact("2025-02-01", "2026-01-31", 41500000000),
    make_fact("2024-02-01", "2025-01-31", 37900000000),
]


def make_claim(quote=QUOTE, period_end="2026-07-31"):
    return ExtractedClaim(
        claim_quote=quote,
        claim_type="reported",
        metric="revenue",
        value_low=11300000000,
        value_high=11300000000,
        period_end=period_end,
        source_start=0,
        source_end=len(quote),
        extraction_confidence=0.9,
    )


def fake_verifier(calls):
    def verify(claim, fact, prior_fact=None):
        calls.append(fact)
        return {"verdict": "supported", "difference": 0.0, "abstention_reason": None}

    return verify


def test_quarter_claim_matches_the_three_month_fact_not_the_year_to_date_one():
    fact, prior = match_facts(make_claim(), FACTS)

    assert fact["value"] == 11345000000
    assert prior["value"] == 10236000000


def test_year_claim_matches_the_fiscal_year_fact_and_the_prior_fiscal_year():
    claim = make_claim("Full year fiscal 2026 revenue of $41.5 billion", period_end="2026-01-31")

    fact, prior = match_facts(claim, FACTS)

    assert fact["value"] == 41500000000
    assert prior["value"] == 37900000000


def test_partial_period_claims_are_not_matched():
    claim = make_claim("Revenue for the first six months was $22.5 billion")

    assert match_facts(claim, FACTS) == (None, None)


def test_claim_without_a_period_end_is_not_matched():
    assert match_facts(make_claim(period_end=None), FACTS) == (None, None)


def test_malformed_period_end_is_not_matched():
    assert match_facts(make_claim(period_end="July 2026"), FACTS) == (None, None)


def test_period_with_no_filed_fact_is_not_matched():
    assert match_facts(make_claim(period_end="2027-01-31"), FACTS) == (None, None)


def test_prior_year_match_tolerates_a_few_days_of_calendar_drift():
    facts = [
        make_fact("2026-05-03", "2026-08-01", 100),
        make_fact("2025-05-04", "2025-08-02", 90),
    ]

    fact, prior = match_facts(make_claim(period_end="2026-08-01"), facts)

    assert fact["value"] == 100
    assert prior["value"] == 90


def test_earliest_filed_fact_wins_when_a_period_is_reported_twice():
    facts = [
        make_fact("2026-05-01", "2026-07-31", 111, filed="2026-09-30", accession="later"),
        make_fact("2026-05-01", "2026-07-31", 100, filed="2026-08-27", accession="first"),
    ]

    fact, _ = match_facts(make_claim(), facts)

    assert fact["accession_number"] == "first"


def test_quarter_wording_wins_over_fiscal_year_wording():
    claim = make_claim("Second quarter fiscal year 2027 revenue of $11.3 billion")

    assert period_kind(claim) == "quarter"


def test_unlabeled_quote_defaults_to_quarter():
    assert period_kind(make_claim("Revenue of $11.3 billion")) == "quarter"


def test_full_year_wording_is_a_year():
    assert period_kind(make_claim("Full year revenue of $41.5 billion")) == "year"


def test_card_abstains_but_keeps_the_citation_when_no_fact_matches():
    calls = []
    claim = make_claim()

    card = build_evidence_card(claim, QUOTE, {"document_url": "u", "accession_number": "a"}, None,
                               verify=fake_verifier(calls))

    assert card["verdict"] == "insufficient_evidence"
    assert "2026-07-31" in card["abstention_reason"]
    assert card["claim_source"]["excerpt"] == QUOTE
    assert card["filed_fact"] is None
    assert calls == []


def test_card_says_so_when_the_claim_has_no_period():
    card = build_evidence_card(make_claim(period_end=None), QUOTE, {"document_url": "u", "accession_number": "a"},
                               None, verify=fake_verifier([]))

    assert "no period" in card["abstention_reason"]


def test_fy_abbreviation_without_a_quarter_word_is_a_year():
    assert period_kind(make_claim("FY26 revenue of $41.5 billion, up 10% Y/Y")) == "year"


def test_quarter_with_fiscal_label_is_a_quarter():
    for quote in (
        "Second quarter fiscal 2027 revenue of $11.3 billion",
        "Q2 FY27 revenue of $11.3 billion",
        "FY27 second quarter revenue of $11.3 billion",
        "Revenue of $11.3 billion for the fourth quarter of fiscal 2026",
    ):
        assert period_kind(make_claim(quote)) == "quarter", quote


def test_conflicting_quarter_and_year_wording_is_ambiguous():
    for quote in (
        "We delivered a phenomenal quarter to close out a record fiscal 2026, delivering $41.5 billion in revenue",
        "Fourth quarter and full year revenue of $11.2 billion and $41.5 billion",
    ):
        assert period_kind(make_claim(quote)) is None, quote


def test_card_explains_when_the_period_is_ambiguous():
    quote = "We delivered a phenomenal quarter to close out a record fiscal 2026, delivering $41.5 billion in revenue"

    card = build_evidence_card(make_claim(quote), quote, {"document_url": "u", "accession_number": "a"},
                               None, verify=fake_verifier([]))

    assert "ambiguous" in card["abstention_reason"]


def test_card_names_the_kind_of_period_it_searched_for():
    quote = "FY26 revenue of $41.5 billion"

    card = build_evidence_card(make_claim(quote, period_end="2026-01-31"), quote,
                               {"document_url": "u", "accession_number": "a"}, None, verify=fake_verifier([]))

    assert "year revenue figure" in card["abstention_reason"]
