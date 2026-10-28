import json

from core.guidance.tracker import track_guidance


def result(end, issued, accession, kind="year", metric="revenue", outcome="insufficient_evidence", cited=True):
    return {
        "outcome": outcome,
        "difference": 0.01 if outcome in ("exceeded", "missed") else None,
        "reason": "no filed figure yet" if outcome == "insufficient_evidence" else None,
        "guidance": {
            "quote": "some guidance",
            "metric": metric,
            "low": 1,
            "high": 2,
            "basis": "GAAP",
            "issued_in_period_ending": issued,
            "guided_period_kind": kind,
            "guided_period_end": end,
        },
        "guidance_source": {"accession_number": accession} if cited else None,
        "actual": None,
        "rules_applied": [],
    }


def three_statements():
    return [
        result("2027-01-31", "2026-07-31", "aug"),
        result("2027-01-31", "2026-01-31", "feb"),
        result("2027-01-31", "2026-04-30", "may"),
    ]


def test_only_the_latest_statement_for_a_period_is_final():
    tracked = track_guidance(three_statements())

    assert [r["guidance_source"]["accession_number"] for r in tracked] == ["feb", "may", "aug"]
    assert [r["is_final"] for r in tracked] == [False, False, True]


def test_earlier_statements_are_marked_superseded_and_point_to_their_replacement():
    tracked = track_guidance(three_statements())

    assert [r["outcome"] for r in tracked[:2]] == ["withdrawn_superseded", "withdrawn_superseded"]
    assert [r["superseded_by"] for r in tracked] == ["may", "aug", None]
    assert "may" in tracked[0]["reason"]


def test_the_final_statement_keeps_its_scored_outcome():
    statements = three_statements()
    statements[0] = result("2027-01-31", "2026-07-31", "aug", outcome="met")

    tracked = track_guidance(statements)

    assert tracked[-1]["outcome"] == "met"
    assert tracked[-1]["individual_outcome"] == "met"


def test_superseded_statements_keep_their_own_comparison_in_individual_outcome():
    statements = [
        result("2026-01-31", "2025-04-30", "early", outcome="exceeded"),
        result("2026-01-31", "2025-10-31", "late", outcome="met"),
    ]

    tracked = track_guidance(statements)

    assert tracked[0]["outcome"] == "withdrawn_superseded"
    assert tracked[0]["individual_outcome"] == "exceeded"
    assert tracked[0]["difference"] is None


def test_different_periods_do_not_supersede_each_other():
    tracked = track_guidance([
        result("2026-10-31", "2026-07-31", "q3", kind="quarter"),
        result("2026-07-31", "2026-04-30", "q2", kind="quarter"),
    ])

    assert [r["is_final"] for r in tracked] == [True, True]


def test_different_metrics_do_not_supersede_each_other():
    tracked = track_guidance([
        result("2027-01-31", "2026-04-30", "may", metric="revenue"),
        result("2027-01-31", "2026-07-31", "aug", metric="revenue_growth"),
    ])

    assert [r["is_final"] for r in tracked] == [True, True]


def test_an_uncited_statement_cannot_supersede_a_cited_one():
    tracked = track_guidance([
        result("2027-01-31", "2026-04-30", "may"),
        result("2027-01-31", "2026-07-31", "aug", cited=False),
    ])

    cited = [r for r in tracked if r["guidance_source"] is not None][0]
    uncited = [r for r in tracked if r["guidance_source"] is None][0]
    assert cited["is_final"] is True
    assert cited["outcome"] == "insufficient_evidence"
    assert uncited["is_final"] is None
    assert uncited["superseded_by"] is None


def test_statements_with_no_guided_period_pass_through_untouched():
    tracked = track_guidance([result(None, "2026-07-31", "x", kind=None)])

    assert tracked[0]["is_final"] is None
    assert tracked[0]["outcome"] == "insufficient_evidence"


def test_duplicates_from_the_same_release_do_not_supersede_each_other():
    tracked = track_guidance([
        result("2027-01-31", "2026-07-31", "first-copy"),
        result("2027-01-31", "2026-07-31", "second-copy"),
    ])

    assert len(tracked) == 1
    assert tracked[0]["guidance_source"]["accession_number"] == "first-copy"
    assert tracked[0]["is_final"] is True


def test_output_is_sorted_by_period_then_metric_then_issue_date():
    tracked = track_guidance([
        result("2027-01-31", "2026-07-31", "d", metric="revenue_growth"),
        result("2026-10-31", "2026-07-31", "c", kind="quarter"),
        result("2027-01-31", "2026-07-31", "b", metric="revenue"),
        result("2026-07-31", "2026-04-30", "a", kind="quarter"),
    ])

    assert [r["guidance_source"]["accession_number"] for r in tracked] == ["a", "c", "b", "d"]


def test_input_results_are_not_modified():
    statements = three_statements()

    track_guidance(statements)

    assert all(s["outcome"] == "insufficient_evidence" and "is_final" not in s for s in statements)


def test_no_results_gives_no_tracking():
    assert track_guidance([]) == []


def test_tracked_output_is_json_serializable():
    tracked = track_guidance(three_statements())

    assert json.loads(json.dumps(tracked))[0]["outcome"] == "withdrawn_superseded"
