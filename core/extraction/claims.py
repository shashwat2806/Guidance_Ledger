import json
import os
import time
from typing import Literal, Optional

import litellm
from pydantic import BaseModel, Field, model_validator

MIN_REVENUE_DOLLARS = 1_000_000

EXTRACTION_PROMPT = """Extract claims about TOTAL company revenue from this earnings press release excerpt. Ignore subscription and support revenue, remaining performance obligation, cRPO, margins, EPS, and cash flow.

Return a JSON array. For each claim, return an object with:
- claim_quote: the exact text of the claim
- claim_type: "reported" if it describes a period that has already ended, or "guidance" if it is a forward-looking outlook, expectation, raise, or initiation
- metric: "revenue" (a dollar amount) or "revenue_growth" (a percentage change)
- value_low, value_high: for revenue, FULL dollars as a plain number (write 11300000000, never 11.3 or 11,300). For revenue_growth, the percentage as a number (write 11.0 for 11%). Use the same number for both if it is a single figure.
- comparison_basis: "GAAP" or "non-GAAP" if stated, otherwise null
- period_end: the period-end date in YYYY-MM-DD format if stated, otherwise null
- extraction_confidence: your confidence this claim was extracted correctly, 0 to 1

If one sentence states both a dollar amount and a growth rate, return two separate claims, one per metric.

Return ONLY the JSON array, no other text.

Text:
{text}
"""


class ExtractedClaim(BaseModel):
    claim_quote: str
    claim_type: Literal["reported", "guidance"] = "reported"
    metric: Literal["revenue", "revenue_growth"]
    value_low: Optional[float] = None
    value_high: Optional[float] = None
    comparison_basis: Optional[Literal["GAAP", "non-GAAP"]] = None
    period_end: Optional[str] = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_at_least_one_value(self):
        if self.value_low is None and self.value_high is None:
            raise ValueError("claim must include at least one of value_low or value_high")
        return self


def extract_claims(text, model=None, max_retries=3):
    model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
    kwargs = {}
    if os.environ.get("LLM_API_KEY"):
        kwargs["api_key"] = os.environ["LLM_API_KEY"]
    if os.environ.get("OLLAMA_HOST"):
        kwargs["api_base"] = os.environ["OLLAMA_HOST"]
    if os.environ.get("LLM_REASONING_EFFORT"):
        kwargs["reasoning_effort"] = os.environ["LLM_REASONING_EFFORT"]
        kwargs["reasoning_format"] = "parsed"

    prompt = EXTRACTION_PROMPT.format(text=text)
    last_error = None
    validation_error = None
    backoff = 15

    for attempt in range(max_retries):
        message = prompt if validation_error is None else _retry_prompt(prompt, validation_error)
        try:
            response = litellm.completion(model=model, messages=[{"role": "user", "content": message}], **kwargs)
        except litellm.exceptions.RateLimitError as exc:
            last_error = str(exc)
            time.sleep(backoff)
            backoff *= 2
            continue

        raw = response.choices[0].message.content
        try:
            items = json.loads(raw)
            if isinstance(items, dict):
                items = items.get("claims", [items])
            claims = [ExtractedClaim(**item) for item in items]
            _check_extraction(items, claims)
            return claims
        except (ValueError, TypeError) as exc:
            last_error = validation_error = str(exc)
            continue

    raise RuntimeError(f"extraction failed after {max_retries} attempts: {last_error}")


def _check_extraction(items, claims):
    for item in items:
        if "claim_type" not in item:
            raise ValueError("every claim must include claim_type: reported or guidance")
    for claim in claims:
        values = [v for v in (claim.value_low, claim.value_high) if v is not None]
        if claim.metric == "revenue" and max(values) < MIN_REVENUE_DOLLARS:
            raise ValueError(
                f"revenue value {max(values)} is not in full dollars; write 11300000000, not 11.3"
            )


def _retry_prompt(original_prompt, error):
    return (
        f"{original_prompt}\n\nYour previous response failed validation: {error}\n"
        "Return ONLY a valid JSON array matching the schema, with no other text."
    )
