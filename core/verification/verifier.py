from decimal import Decimal
VALUE_TOLERANCE = Decimal("0.02")  # 2% relative tolerance on absolute dollar figures
GROWTH_TOLERANCE = Decimal("1.0")  # 1 percentage point tolerance on growth-rate claims

def verify_claim(claim, fact, prior_fact=None):
    basis_check = _check_basis(claim, fact)
    if basis_check:
        return basis_check

    period_check = _check_period(claim, fact)
    if period_check:
        return period_check

    if claim["metric"] == "revenue":
        return _verify_absolute_value(claim, fact)

    if claim["metric"] == "revenue_growth":
        return _verify_growth_rate(claim, fact, prior_fact)

    return _insufficient(f"unsupported metric: {claim['metric']}")


def _check_basis(claim, fact):
    basis = claim.get("comparison_basis")
    if basis and basis.upper() != fact["gaap_basis"].upper():
        return _insufficient(f"claim basis ({basis}) does not match filed fact basis ({fact['gaap_basis']})")
    return None


def _check_period(claim, fact):
    period = claim.get("period")
    if period and period != f"{fact['start_date']}:{fact['end_date']}":
        return _insufficient("claim period does not match filed fact period")
    return None


def _claim_midpoint(claim):
    low, high = claim.get("value_low"), claim.get("value_high")
    if low is None and high is None:
        return None
    if low is None:
        return Decimal(str(high))
    if high is None:
        return Decimal(str(low))
    return (Decimal(str(low)) + Decimal(str(high))) / 2


def _verify_absolute_value(claim, fact):
    claimed = _claim_midpoint(claim)
    if claimed is None:
        return _insufficient("claim has no comparable value")
    fact_value = Decimal(str(fact["value"]))
    diff = abs(claimed - fact_value) / fact_value
    verdict = "supported" if diff <= VALUE_TOLERANCE else "contradicted"
    return _verdict(verdict, diff)

def _verify_growth_rate(claim, fact, prior_fact):
    if prior_fact is None:
        return _insufficient("no comparable prior-year fact to compute growth from")
    fact_value = Decimal(str(fact["value"]))
    prior_value = Decimal(str(prior_fact["value"]))
    actual_growth_pct = (fact_value - prior_value) / prior_value * 100
    claimed_pct = _claim_midpoint(claim)
    if claimed_pct is None:
        return _insufficient("claim has no comparable growth value")
    diff = abs(claimed_pct - actual_growth_pct)
    verdict = "supported" if diff <= GROWTH_TOLERANCE else "contradicted"
    return _verdict(verdict, diff)

def _verdict(verdict, difference):
    return {"verdict": verdict, "difference": float(difference), "abstention_reason": None}

def _insufficient(reason):
    return {"verdict": "insufficient_evidence", "difference": None, "abstention_reason": reason}