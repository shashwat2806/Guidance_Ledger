from core.verification.matching import period_kind
from core.verification.verifier import verify_claim


def build_evidence_card(claim, text, source, fact, prior_fact=None, verify=verify_claim):
    if claim.claim_type != "reported":
        raise ValueError("only reported claims are checked against filed results; guidance is tracked separately")

    card = {
        "claim": _claim_summary(claim),
        "claim_source": None,
        "filed_fact": None,
        "prior_fact": None,
        "rules_applied": [],
    }
    if claim.basis_assumed:
        card["rules_applied"].append("basis not stated in the quote; assumed GAAP")

    if claim.source_start is None or claim.source_end is None:
        return {**_abstain("claim quote not found in source text, so there is no citation"), **card}

    card["claim_source"] = {
        "document_url": source["document_url"],
        "accession_number": source["accession_number"],
        "start": claim.source_start,
        "end": claim.source_end,
        "excerpt": text[claim.source_start:claim.source_end],
    }

    if fact is None:
        return {**_abstain(_no_fact_reason(claim)), **card}

    card["filed_fact"] = _fact_summary(fact)
    if claim.metric == "revenue_growth" and prior_fact is not None:
        card["prior_fact"] = _fact_summary(prior_fact)

    result = verify(claim, fact, prior_fact=prior_fact)
    return {**result, **card}


def _abstain(reason):
    return {"verdict": "insufficient_evidence", "difference": None, "abstention_reason": reason}


def _no_fact_reason(claim):
    kind = period_kind(claim)
    if kind is None:
        return "claim's period is ambiguous or partial, so no filed figure can be matched"
    if not claim.period_end:
        return "claim states no period, so no filed figure can be matched"
    return f"no filed {kind} revenue figure found for the period ending {claim.period_end}"


def _claim_summary(claim):
    return {
        "quote": claim.claim_quote,
        "claim_type": claim.claim_type,
        "metric": claim.metric,
        "value_low": claim.value_low,
        "value_high": claim.value_high,
        "basis": claim.comparison_basis,
        "basis_assumed": claim.basis_assumed,
        "period_end": claim.period_end,
    }


def _fact_summary(fact):
    keys = ("accession_number", "form", "raw_tag", "value", "unit", "start_date", "end_date", "filed_date")
    return {key: fact.get(key) for key in keys}
