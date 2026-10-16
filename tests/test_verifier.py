from core.extraction.claims import ExtractedClaim
from core.verification.verifier import verify_claim
FACT = {
    "value": 11_300_000_000,
    "gaap_basis": "GAAP",
    "start_date": "2026-05-01",
    "end_date": "2026-07-31",
}
PRIOR_FACT = {
    "value": 10_180_000_000,
    "gaap_basis": "GAAP",
    "start_date": "2025-05-01",
    "end_date": "2025-07-31",
}

def test_absolute_value_supported_within_tolerance():
    claim = {
        "metric": "revenue", "value_low": 11_300_000_000, "value_high": 11_300_000_000,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT)
    assert result["verdict"] == "supported"
    assert result["difference"] < 0.001

def test_absolute_value_contradicted_outside_tolerance():
    claim = {
        "metric": "revenue", "value_low": 13_000_000_000, "value_high": 13_000_000_000,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT)
    assert result["verdict"] == "contradicted"
    assert result["difference"] > 0.02

def test_growth_rate_supported_within_tolerance():
    claim = {
        "metric": "revenue_growth", "value_low": 11.0, "value_high": 11.0,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT, prior_fact=PRIOR_FACT)
    assert result["verdict"] == "supported"

def test_growth_rate_contradicted_outside_tolerance():
    claim = {
        "metric": "revenue_growth", "value_low": 20.0, "value_high": 20.0,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT, prior_fact=PRIOR_FACT)
    assert result["verdict"] == "contradicted"

def test_growth_rate_insufficient_without_prior_fact():
    claim = {
        "metric": "revenue_growth", "value_low": 11.0, "value_high": 11.0,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT, prior_fact=None)
    assert result["verdict"] == "insufficient_evidence"
    assert "prior-year" in result["abstention_reason"]

def test_basis_mismatch_is_insufficient_not_silently_scored():
    claim = {
        "metric": "revenue", "value_low": 11_300_000_000, "value_high": 11_300_000_000,
        "comparison_basis": "non-GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT)
    assert result["verdict"] == "insufficient_evidence"
    assert "basis" in result["abstention_reason"]

def test_period_mismatch_is_insufficient():
    claim = {
        "metric": "revenue", "value_low": 11_300_000_000, "value_high": 11_300_000_000,
        "comparison_basis": "GAAP", "period": "2025-05-01:2025-07-31",
    }
    result = verify_claim(claim, FACT)
    assert result["verdict"] == "insufficient_evidence"
    assert "period" in result["abstention_reason"]

def test_missing_claim_value_is_insufficient():
    claim = {
        "metric": "revenue", "value_low": None, "value_high": None,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT)
    assert result["verdict"] == "insufficient_evidence"

def test_unsupported_metric_is_insufficient():
    claim = {
        "metric": "operating_margin", "value_low": 20.5, "value_high": 20.5,
        "comparison_basis": "GAAP", "period": "2026-05-01:2026-07-31",
    }
    result = verify_claim(claim, FACT)
    assert result["verdict"] == "insufficient_evidence"


def test_extracted_claim_model_can_be_passed_directly_to_verifier():
    claim = ExtractedClaim(
        claim_quote="Revenue was $11.3 billion.",
        metric="revenue",
        value_low=11_300_000_000,
        value_high=11_300_000_000,
        comparison_basis="GAAP",
        period_start="2026-05-01",
        period_end="2026-07-31",
        extraction_confidence=0.95,
    )

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "supported"


def test_partial_extracted_period_checks_quarter_end():
    claim = {
        "metric": "revenue", "value_low": 11_300_000_000,
        "comparison_basis": "GAAP", "period_end": "2026-06-30",
    }

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "insufficient_evidence"
    assert "period" in result["abstention_reason"]


def test_missing_claim_period_abstains():
    claim = {
        "metric": "revenue", "value_low": 11_300_000_000,
        "comparison_basis": "GAAP",
    }

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "insufficient_evidence"
    assert "period is missing" in result["abstention_reason"]


def test_revenue_range_containing_fact_is_supported_not_midpoint_scored():
    claim = {
        "metric": "revenue", "value_low": 11_300_000_000,
        "value_high": 12_500_000_000, "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "supported"
    assert result["difference"] == 0


def test_revenue_range_outside_fact_uses_nearest_bound():
    claim = {
        "metric": "revenue", "value_low": 12_500_000_000,
        "value_high": 13_000_000_000, "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "contradicted"
    assert result["difference"] == (12_500_000_000 - FACT["value"]) / FACT["value"]


def test_zero_filed_revenue_and_zero_point_claim_are_supported():
    claim = {
        "metric": "revenue", "value_low": 0, "value_high": 0,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }
    fact = {**FACT, "value": 0}

    result = verify_claim(claim, fact)

    assert result["verdict"] == "supported"
    assert result["difference"] == 0


def test_nonzero_claim_against_zero_filed_revenue_abstains_safely():
    claim = {
        "metric": "revenue", "value_low": 1, "value_high": 1,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }
    fact = {**FACT, "value": 0}

    result = verify_claim(claim, fact)

    assert result["verdict"] == "insufficient_evidence"
    assert "zero" in result["abstention_reason"]


def test_growth_rate_abstains_when_prior_revenue_is_zero():
    claim = {
        "metric": "revenue_growth", "value_low": 10, "value_high": 10,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }
    prior_fact = {**PRIOR_FACT, "value": 0}

    result = verify_claim(claim, FACT, prior_fact=prior_fact)

    assert result["verdict"] == "insufficient_evidence"
    assert "positive" in result["abstention_reason"]


def test_growth_rate_range_containing_actual_growth_is_supported():
    claim = {
        "metric": "revenue_growth", "value_low": 10.5, "value_high": 11.5,
        "comparison_basis": "GAAP", "period_start": "2026-05-01",
        "period_end": "2026-07-31",
    }

    result = verify_claim(claim, FACT, prior_fact=PRIOR_FACT)

    assert result["verdict"] == "supported"
    assert result["difference"] == 0


def test_growth_rate_abstains_for_incompatible_prior_fact_basis():
    claim = {
        "metric": "revenue_growth", "value_low": 11, "value_high": 11,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }
    prior_fact = {**PRIOR_FACT, "gaap_basis": "non-GAAP"}

    result = verify_claim(claim, FACT, prior_fact=prior_fact)

    assert result["verdict"] == "insufficient_evidence"
    assert "different accounting bases" in result["abstention_reason"]


def test_growth_rate_abstains_for_incompatible_prior_fact_unit():
    claim = {
        "metric": "revenue_growth", "value_low": 11, "value_high": 11,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }
    fact = {**FACT, "unit": "USD"}
    prior_fact = {**PRIOR_FACT, "unit": "shares"}

    result = verify_claim(claim, fact, prior_fact=prior_fact)

    assert result["verdict"] == "insufficient_evidence"
    assert "different units" in result["abstention_reason"]


def test_invalid_raw_mapping_range_abstains_instead_of_crashing():
    claim = {
        "metric": "revenue", "value_low": 13, "value_high": 11,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "insufficient_evidence"
    assert "valid comparable value range" in result["abstention_reason"]


def test_missing_fact_numeric_value_abstains_instead_of_crashing():
    result = verify_claim(
        {
            "metric": "revenue", "value_low": 11, "comparison_basis": "GAAP",
            "period_start": "2026-05-01", "period_end": "2026-07-31",
        },
        {**FACT, "value": None},
    )

    assert result["verdict"] == "insufficient_evidence"
    assert "finite numeric value" in result["abstention_reason"]


def test_missing_claim_basis_abstains_instead_of_assuming_gaap():
    claim = {"metric": "revenue", "value_low": 11_300_000_000}

    result = verify_claim(claim, FACT)

    assert result["verdict"] == "insufficient_evidence"
    assert "basis is unknown" in result["abstention_reason"]


def test_growth_rate_abstains_for_non_comparable_prior_period():
    claim = {
        "metric": "revenue_growth", "value_low": 11, "value_high": 11,
        "comparison_basis": "GAAP",
        "period_start": "2026-05-01", "period_end": "2026-07-31",
    }
    prior_fact = {**PRIOR_FACT, "start_date": "2025-06-01", "end_date": "2025-07-30"}

    result = verify_claim(claim, FACT, prior_fact=prior_fact)

    assert result["verdict"] == "insufficient_evidence"
    assert "period lengths" in result["abstention_reason"]
