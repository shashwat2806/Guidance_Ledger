from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

VALUE_TOLERANCE = Decimal("0.02")  # 2% relative tolerance for reported revenue
GROWTH_TOLERANCE = Decimal("1.0")  # 1 percentage point for reported growth


def verify_claim(claim, fact, prior_fact=None):
    """Compare one normalized claim to an XBRL fact without guessing.

    ``claim`` may be an ``ExtractedClaim`` Pydantic model or a mapping. A
    partial claim period is checked against the corresponding filed boundary;
    claims without any period remain verifiable but should be treated as lower
    confidence by a caller.
    """
    claim = _to_mapping(claim)
    fact = _to_mapping(fact)
    if claim is None or fact is None:
        return _insufficient("claim and filed fact must be mappings or Pydantic models")

    metric = claim.get("metric")
    if metric not in {"revenue", "revenue_growth"}:
        return _insufficient(f"unsupported metric: {metric}")

    basis_check = _check_basis(claim, fact)
    if basis_check:
        return basis_check

    period_check = _check_period(claim, fact)
    if period_check:
        return period_check

    if metric == "revenue":
        return _verify_absolute_value(claim, fact)
    return _verify_growth_rate(claim, fact, prior_fact)


def _to_mapping(value):
    if isinstance(value, Mapping):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump()
    return None


def _check_basis(claim, fact):
    claim_basis = claim.get("comparison_basis")
    fact_basis = fact.get("gaap_basis")
    if fact_basis and not claim_basis:
        return _insufficient("claim accounting basis is unknown; cannot compare safely")
    if claim_basis and not fact_basis:
        return _insufficient("filed fact is missing its accounting basis")
    if claim_basis and str(claim_basis).casefold() != str(fact_basis).casefold():
        return _insufficient(
            f"claim basis ({claim_basis}) does not match filed fact basis ({fact_basis})"
        )
    return None


def _check_period(claim, fact):
    period_start = claim.get("period_start")
    period_end = claim.get("period_end")
    legacy_period = claim.get("period")

    # Accept the original verifier contract during migration, but normalize it
    # to the shared period_start / period_end representation.
    if legacy_period is not None:
        if not isinstance(legacy_period, str) or legacy_period.count(":") != 1:
            return _insufficient("claim period must use YYYY-MM-DD:YYYY-MM-DD")
        legacy_start, legacy_end = legacy_period.split(":", maxsplit=1)
        if period_start is not None and _date_text(period_start) != legacy_start:
            return _insufficient("claim contains conflicting period_start values")
        if period_end is not None and _date_text(period_end) != legacy_end:
            return _insufficient("claim contains conflicting period_end values")
        period_start = period_start or legacy_start
        period_end = period_end or legacy_end

    if period_start is None and period_end is None:
        return _insufficient("claim period is missing; cannot compare with a filed period safely")

    if period_start is not None and period_end is not None:
        if _date_text(period_start) > _date_text(period_end):
            return _insufficient("claim period_start is after period_end")

    for claim_key, fact_key in (("period_start", "start_date"), ("period_end", "end_date")):
        claim_date = period_start if claim_key == "period_start" else period_end
        if claim_date is None:
            continue
        filed_date = fact.get(fact_key)
        if filed_date is None:
            return _insufficient(f"filed fact is missing {fact_key} for period comparison")
        if _date_text(claim_date) != _date_text(filed_date):
            return _insufficient("claim period does not match filed fact period")
    return None


def _date_text(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _claim_bounds(claim):
    raw_low = claim.get("value_low")
    raw_high = claim.get("value_high")
    low = _decimal(raw_low)
    high = _decimal(raw_high)
    if raw_low is not None and low is None or raw_high is not None and high is None:
        return None
    if low is None and high is None:
        return None
    if low is None:
        low = high
    if high is None:
        high = low
    if low > high:
        return None
    return low, high


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() else None


def _verify_absolute_value(claim, fact):
    fact_value = _decimal(fact.get("value"))
    bounds = _claim_bounds(claim)
    if fact_value is None:
        return _insufficient("filed fact has no finite numeric value")
    if bounds is None:
        return _insufficient("claim has no valid comparable value range")
    if fact_value < 0:
        return _insufficient("negative filed revenue is outside this verifier's supported scope")

    low, high = bounds
    if low < 0:
        return _insufficient("revenue claim range cannot be negative")
    unit = fact.get("unit")
    if unit and str(unit).casefold() != "usd":
        return _insufficient("filed revenue fact is not denominated in USD")
    if low <= fact_value <= high:
        return _verdict("supported", Decimal(0))

    # A zero filed value has no meaningful relative-error denominator. We
    # abstain instead of manufacturing an infinite percentage difference.
    if fact_value == 0:
        return _insufficient("relative comparison is undefined for zero filed revenue")

    nearest_bound = low if fact_value < low else high
    difference = abs(nearest_bound - fact_value) / abs(fact_value)
    verdict = "supported" if difference <= VALUE_TOLERANCE else "contradicted"
    return _verdict(verdict, difference)


def _verify_growth_rate(claim, fact, prior_fact):
    if prior_fact is None:
        return _insufficient("no comparable prior-year fact to compute growth from")
    prior_fact = _to_mapping(prior_fact)
    if prior_fact is None:
        return _insufficient("prior-year fact must be a mapping or Pydantic model")

    current_basis = fact.get("gaap_basis")
    prior_basis = prior_fact.get("gaap_basis")
    if bool(current_basis) != bool(prior_basis):
        return _insufficient("current or prior-year fact is missing its accounting basis")
    if (
        current_basis
        and prior_basis
        and str(current_basis).casefold() != str(prior_basis).casefold()
    ):
        return _insufficient("current and prior-year facts use different accounting bases")
    current_unit = fact.get("unit")
    prior_unit = prior_fact.get("unit")
    if bool(current_unit) != bool(prior_unit):
        return _insufficient("current or prior-year fact is missing its unit")
    if current_unit and prior_unit and str(current_unit).casefold() != str(prior_unit).casefold():
        return _insufficient("current and prior-year facts use different units")

    period_check = _check_prior_year_period(fact, prior_fact)
    if period_check:
        return period_check

    fact_value = _decimal(fact.get("value"))
    prior_value = _decimal(prior_fact.get("value"))
    bounds = _claim_bounds(claim)
    if fact_value is None or prior_value is None:
        return _insufficient("current or prior-year fact has no finite numeric value")
    if prior_value <= 0:
        return _insufficient("prior-year revenue must be positive to compute a growth rate")
    if fact_value < 0:
        return _insufficient("negative current revenue is outside this verifier's supported scope")
    if bounds is None:
        return _insufficient("claim has no valid comparable growth range")

    actual_growth_pct = (fact_value - prior_value) / prior_value * 100
    low, high = bounds
    if low <= actual_growth_pct <= high:
        return _verdict("supported", Decimal(0))

    nearest_bound = low if actual_growth_pct < low else high
    difference = abs(nearest_bound - actual_growth_pct)
    verdict = "supported" if difference <= GROWTH_TOLERANCE else "contradicted"
    return _verdict(verdict, difference)


def _check_prior_year_period(fact, prior_fact):
    current_start = _parse_date(fact.get("start_date"))
    current_end = _parse_date(fact.get("end_date"))
    prior_start = _parse_date(prior_fact.get("start_date"))
    prior_end = _parse_date(prior_fact.get("end_date"))
    if not all((current_start, current_end, prior_start, prior_end)):
        return _insufficient(
            "current and prior-year fact periods are required for growth comparison"
        )

    if prior_end >= current_start:
        return _insufficient("prior-year fact does not precede the current fact period")
    current_duration = (current_end - current_start).days
    prior_duration = (prior_end - prior_start).days
    if abs(current_duration - prior_duration) > 7:
        return _insufficient("current and prior-year facts cover different period lengths")
    year_gap = (current_end - prior_end).days
    if not 350 <= year_gap <= 380:
        return _insufficient("prior-year fact is not from a comparable year-earlier period")

    current_fiscal_period = fact.get("fiscal_period")
    prior_fiscal_period = prior_fact.get("fiscal_period")
    if (
        current_fiscal_period
        and prior_fiscal_period
        and str(current_fiscal_period).casefold() != str(prior_fiscal_period).casefold()
    ):
        return _insufficient("current and prior-year facts use different fiscal periods")

    current_fiscal_year = fact.get("fiscal_year")
    prior_fiscal_year = prior_fact.get("fiscal_year")
    if current_fiscal_year is not None and prior_fiscal_year is not None:
        try:
            consecutive_years = int(current_fiscal_year) - int(prior_fiscal_year) == 1
        except (TypeError, ValueError):
            return _insufficient("fiscal-year metadata is invalid")
        if not consecutive_years:
            return _insufficient("current and prior-year facts are not in consecutive fiscal years")
    return None


def _parse_date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(_date_text(value))
    except (TypeError, ValueError):
        return None


def _verdict(verdict, difference):
    return {"verdict": verdict, "difference": float(difference), "abstention_reason": None}


def _insufficient(reason):
    return {"verdict": "insufficient_evidence", "difference": None, "abstention_reason": reason}
