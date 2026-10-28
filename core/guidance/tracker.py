from collections import defaultdict


def track_guidance(results):
    groups = defaultdict(list)
    tracked = []
    for result in results:
        key = _group_key(result)
        if key is None:
            tracked.append({**result, "individual_outcome": result["outcome"], "is_final": None, "superseded_by": None})
        else:
            groups[key].append(result)

    for statements in groups.values():
        tracked.extend(_resolve(statements))
    return sorted(tracked, key=_sort_key)


def _group_key(result):
    guidance = result["guidance"]
    if result["guidance_source"] is None or guidance["guided_period_end"] is None:
        return None
    return guidance["guided_period_kind"], guidance["guided_period_end"], guidance["metric"]


def _resolve(statements):
    by_release = {}
    for statement in statements:
        by_release.setdefault(statement["guidance"]["issued_in_period_ending"], statement)
    ordered = [by_release[issued] for issued in sorted(by_release)]

    resolved = []
    for i, statement in enumerate(ordered):
        later = ordered[i + 1] if i + 1 < len(ordered) else None
        if later is None:
            resolved.append({**statement, "individual_outcome": statement["outcome"], "is_final": True, "superseded_by": None})
            continue
        accession = later["guidance_source"]["accession_number"]
        issued = later["guidance"]["issued_in_period_ending"]
        resolved.append({
            **statement,
            "outcome": "withdrawn_superseded",
            "difference": None,
            "reason": f"replaced by later guidance for the same period, issued with the results for the period ending {issued} ({accession})",
            "individual_outcome": statement["outcome"],
            "is_final": False,
            "superseded_by": accession,
        })
    return resolved


def _sort_key(result):
    guidance = result["guidance"]
    return (guidance["guided_period_end"] or "", guidance["metric"], guidance["issued_in_period_ending"] or "")
