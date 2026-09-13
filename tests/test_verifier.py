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