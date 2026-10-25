import re
from datetime import date, timedelta

QUARTER_DAYS = (80, 100)
YEAR_DAYS = (350, 380)
PRIOR_YEAR_WINDOW_DAYS = 14

FISCAL_LABEL = r"\b(?:fiscal\s+(?:year\s+)?|fy\s?)\d{2,4}"
QUARTER_WORDS = re.compile(r"quarter|\bq[1-4]\b", re.IGNORECASE)
QUARTER_LABELS = re.compile(
    rf"(?:quarter|\bq[1-4])\s*(?:of\s+)?{FISCAL_LABEL}"
    rf"|{FISCAL_LABEL}\s*(?:(?:first|second|third|fourth)\s+)?(?:quarter|q[1-4]\b)",
    re.IGNORECASE,
)
YEAR_WORDS = re.compile(
    rf"full[\s-]year|\bannual\b|year ended|for the year|fiscal[\s-]year|{FISCAL_LABEL}",
    re.IGNORECASE,
)
PARTIAL_WORDS = re.compile(r"six months|nine months|first half|second half|year[\s-]to[\s-]date|ytd", re.IGNORECASE)


def period_kind(claim):
    quote = claim.claim_quote
    if PARTIAL_WORDS.search(quote):
        return None
    has_quarter = bool(QUARTER_WORDS.search(quote))
    has_year = bool(YEAR_WORDS.search(QUARTER_LABELS.sub(" ", quote)))
    if has_quarter and has_year:
        return None
    return "year" if has_year else "quarter"


def match_facts(claim, facts):
    kind = period_kind(claim)
    if kind is None or not claim.period_end:
        return None, None
    try:
        target = date.fromisoformat(claim.period_end)
    except ValueError:
        return None, None

    days = QUARTER_DAYS if kind == "quarter" else YEAR_DAYS
    candidates = [f for f in facts if f.get("canonical_concept") == "revenue" and _in_length(f, days)]
    current = [f for f in candidates if _end(f) == target]
    prior_target = target - timedelta(days=365)
    prior = [f for f in candidates if abs((_end(f) - prior_target).days) <= PRIOR_YEAR_WINDOW_DAYS]
    return _earliest_filed(current), _closest(prior, prior_target)


def _end(fact):
    return date.fromisoformat(fact["end_date"])


def _in_length(fact, days):
    if not fact.get("start_date") or not fact.get("end_date"):
        return False
    length = (_end(fact) - date.fromisoformat(fact["start_date"])).days
    return days[0] <= length <= days[1]


def _earliest_filed(facts):
    if not facts:
        return None
    return min(facts, key=lambda f: f.get("filed_date") or "")


def _closest(facts, target):
    if not facts:
        return None
    return min(facts, key=lambda f: (abs((_end(f) - target).days), f.get("filed_date") or ""))
