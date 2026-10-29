from core.extraction.claims import extract_claims
from core.extraction.passages import select_passages
from core.extraction.periods import release_period_end


def extract_release_claims(text, period_end=None, top_k=3, extractor=extract_claims):
    release_end = period_end or release_period_end(text)
    claims = []
    for start, end in select_passages(text, top_k=top_k):
        for claim in extractor(text[start:end], period_end=release_end):
            claims.append(_shift(claim, start))
    return _dedupe(claims)


def _shift(claim, offset):
    if claim.source_start is None:
        return claim
    return claim.model_copy(update={
        "source_start": claim.source_start + offset,
        "source_end": claim.source_end + offset,
    })


def _dedupe(claims):
    kept = []
    for claim in sorted(claims, key=lambda c: (c.source_start is None, c.source_start or 0)):
        if not any(_same_claim(claim, other) for other in kept):
            kept.append(claim)
    return kept


def _same_claim(a, b):
    if (a.claim_type, a.metric, a.value_low, a.value_high) != (b.claim_type, b.metric, b.value_low, b.value_high):
        return False
    if a.source_start is None or b.source_start is None:
        return a.claim_quote == b.claim_quote
    return a.source_start < b.source_end and b.source_start < a.source_end
