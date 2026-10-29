from core.extraction.passages import score_passage, select_passages, split_passages

NARRATIVE = "Salesforce initiates third quarter revenue guidance of $11.42 billion to $11.5 billion, up 11% Y/Y. " * 3
TABLE = "Revenues: Subscription and support $ 10,812 $ 9,654 Professional services 533 582 Total revenues 11,345 10,236 " * 5
FILLER = "The company held a conference call to discuss the results with analysts and investors today. " * 6


def test_split_covers_the_whole_text_with_overlap():
    text = "x" * 7000

    passages = split_passages(text, size=3000, overlap=400)

    assert passages[0][0] == 0
    assert passages[-1][1] == 7000
    assert all(b[0] == a[1] - 400 for a, b in zip(passages, passages[1:]))


def test_short_text_is_a_single_passage():
    assert split_passages("short text", size=3000, overlap=400) == [(0, 10)]


def test_empty_text_has_no_passages():
    assert split_passages("") == []
    assert select_passages("") == []


def test_narrative_about_revenue_guidance_scores_above_filler():
    assert score_passage(NARRATIVE) > score_passage(FILLER)
    assert score_passage(FILLER) == 0


def test_number_heavy_tables_score_zero_even_when_they_say_revenue():
    assert score_passage(TABLE) == 0


def test_first_passage_is_always_selected():
    text = FILLER * 20 + NARRATIVE + FILLER * 20

    chosen = select_passages(text, top_k=1, size=1000, overlap=100)

    assert chosen[0][0] == 0


def test_high_scoring_passages_far_from_the_start_are_selected():
    text = FILLER * 20 + NARRATIVE + FILLER * 20
    position = text.index("Salesforce initiates")

    chosen = select_passages(text, top_k=2, size=1000, overlap=100)

    assert any(start <= position < end for start, end in chosen)


def test_zero_scoring_passages_are_not_selected():
    chosen = select_passages(FILLER * 20, top_k=3, size=1000, overlap=100)

    assert chosen == [(0, 1000)]


def test_top_k_limits_the_extra_passages():
    text = (NARRATIVE + FILLER * 5) * 8

    chosen = select_passages(text, top_k=2, size=1000, overlap=100)

    assert len(chosen) <= 3
    assert chosen == sorted(chosen)
