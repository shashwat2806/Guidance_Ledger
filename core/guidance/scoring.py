import calendar
import re
from collections import Counter
from datetime import date
from decimal import Decimal

from core.verification.matching import YEAR_DAYS, find_facts, period_kind

ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
QUARTER_NUMBER = re.compile(r"\b(first|second|third|fourth)\s+quarter\b|\bq([1-4])\b", re.IGNORECASE)
NEXT_QUARTER = re.compile(r"\b(?:next|coming|following)\s+quarter\b", re.IGNORECASE)
FISCAL_YEAR_LABEL = re.compile(r"\bfy\s?(\d{2,4})\b|\bfiscal\s+(?:year\s+)?(\d{4})\b", re.IGNORECASE)

# guidance is rounded, so allow 0.1% on dollar ranges and half a point on growth ranges before calling a miss or a beat
SLACK = {
    "revenue": (Decimal("0.001"), Decimal("0")),
    "revenue_growth": (Decimal("0"), Decimal("0.5")),
}


def add_months(d, months):
    year, month_index = divmod(d.year * 12 + d.month - 1 + months, 12)
    month = month_index + 1
    last_day = calendar.monthrange(year, month)[1]
    if d.day == calendar.monthrange(d.year, d.month)[1]:
        return date(year, month, last_day)
    return date(year, month, min(d.day, last_day))


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def fiscal_quarter(end, fy_end_month):
    return ((end.month - fy_end_month - 1) % 12) // 3 + 1


def fiscal_year_end_month(facts):
    months = Counter()
    for fact in facts:
        if fact.get("canonical_concept") != "revenue" or not fact.get("start_date") or not fact.get("end_date"):
            continue
        end = date.fromisoformat(fact["end_date"])
        length = (end - date.fromisoformat(fact["start_date"])).days
        if YEAR_DAYS[0] <= length <= YEAR_DAYS[1]:
            months[end.month] += 1
    return months.most_common(1)[0][0] if months else None


def guided_period(claim, release_end, fy_end_month):
    kind = period_kind(claim)
    if kind is None or fy_end_month is None:
        return None
    try:
        release = date.fromisoformat(release_end)
    except (TypeError, ValueError):
        return None

    quote = claim.claim_quote
    label = _fiscal_year_label(quote)

    if kind == "year":
        if label is not None:
            return "year", month_end(label, fy_end_month).isoformat()
        end = month_end(release.year, fy_end_month)
        while end <= release:
            end = month_end(end.year + 1, fy_end_month)
        return "year", end.isoformat()

    if NEXT_QUARTER.search(quote):
        return "quarter", add_months(release, 3).isoformat()
    number = _quarter_number(quote)
    if number is None:
        return None
    if label is not None:
        year_end = month_end(label, fy_end_month)
        return "quarter", add_months(year_end, -(4 - number) * 3).isoformat()
    for k in range(1, 5):
        end = add_months(release, 3 * k)
        if fiscal_quarter(end, fy_end_month) == number:
            return "quarter", end.isoformat()
    return None


def classify_outcome(low, high, actual, metric):
    low = None if low is None else Decimal(str(low))
    high = None if high is None else Decimal(str(high))
    if low is None and high is None:
        return None
    if low is not None and high is not None and low > high:
        return None

    actual = Decimal(str(actual))
    relative, absolute = SLACK[metric]
    if low is not None and actual < low - abs(low) * relative - absolute:
        outcome, bound = "missed", low
    elif high is not None and actual > high + abs(high) * relative + absolute:
        outcome, bound = "exceeded", high
    else:
        return "met", 0.0

    gap = actual - bound
    if metric == "revenue" and bound != 0:
        gap = gap / abs(bound)
    return outcome, float(gap)


def score_guidance(claim, text, source, release_end, facts):
    if claim.claim_type != "guidance":
        raise ValueError("only guidance claims are scored here; reported claims are verified separately")

    record = {
        "guidance": {
            "quote": claim.claim_quote,
            "metric": claim.metric,
            "low": claim.value_low,
            "high": claim.value_high,
            "basis": claim.comparison_basis,
            "issued_in_period_ending": release_end,
            "guided_period_kind": None,
            "guided_period_end": None,
        },
        "guidance_source": None,
        "actual": None,
        "rules_applied": [],
    }
    if claim.basis_assumed:
        record["rules_applied"].append("basis not stated in the quote; assumed GAAP")

    if claim.source_start is None or claim.source_end is None:
        return {**_insufficient("guidance quote not found in source text, so there is no citation"), **record}
    record["guidance_source"] = {
        "document_url": source["document_url"],
        "accession_number": source["accession_number"],
        "start": claim.source_start,
        "end": claim.source_end,
        "excerpt": text[claim.source_start:claim.source_end],
    }

    if claim.comparison_basis != "GAAP":
        return {**_insufficient("guidance is not on a GAAP basis, so it cannot be compared with filed results"), **record}

    period = guided_period(claim, release_end, fiscal_year_end_month(facts))
    if period is None:
        return {**_insufficient("could not tell which fiscal period the guidance covers"), **record}
    kind, end = period
    record["guidance"]["guided_period_kind"] = kind
    record["guidance"]["guided_period_end"] = end

    fact, prior = find_facts(facts, end, kind)
    if fact is None:
        return {**_insufficient(f"no filed {kind} revenue figure for the period ending {end} yet"), **record}

    if claim.metric == "revenue":
        actual = Decimal(str(fact["value"]))
    else:
        if prior is None or not prior.get("value"):
            return {**_insufficient("no prior-year figure to compute the actual growth rate"), **record}
        prior_value = Decimal(str(prior["value"]))
        actual = (Decimal(str(fact["value"])) - prior_value) / prior_value * 100

    result = classify_outcome(claim.value_low, claim.value_high, actual, claim.metric)
    if result is None:
        return {**_insufficient("guided range is missing or inverted"), **record}
    outcome, difference = result

    record["actual"] = {
        "value": float(actual),
        "fact": _fact_summary(fact),
        "prior_fact": _fact_summary(prior) if claim.metric == "revenue_growth" else None,
    }
    return {"outcome": outcome, "difference": difference, "reason": None, **record}


def _fiscal_year_label(quote):
    match = FISCAL_YEAR_LABEL.search(quote)
    if match is None:
        return None
    year = int(match.group(1) or match.group(2))
    return year + 2000 if year < 100 else year


def _quarter_number(quote):
    match = QUARTER_NUMBER.search(quote)
    if match is None:
        return None
    word, digit = match.groups()
    return ORDINALS[word.lower()] if word else int(digit)


def _insufficient(reason):
    return {"outcome": "insufficient_evidence", "difference": None, "reason": reason}


def _fact_summary(fact):
    keys = ("accession_number", "form", "raw_tag", "value", "unit", "start_date", "end_date", "filed_date")
    return {key: fact.get(key) for key in keys}
