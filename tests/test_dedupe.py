from core.ingestion.xbrl import dedupe_facts

def test_dedupe_keeps_earliest_filed_fact_for_each_period():
    facts = [
        {"canonical_concept": "revenue", "start_date": "2016-02-01", "end_date": "2017-01-31",
         "value": 8437000000, "filed_date": "2017-03-09", "accession_number": "0001108524-17-000009"},
        {"canonical_concept": "revenue", "start_date": "2016-02-01", "end_date": "2017-01-31",
         "value": 8437000000, "filed_date": "2018-03-08", "accession_number": "0001108524-18-000010"},
        {"canonical_concept": "revenue", "start_date": "2016-02-01", "end_date": "2017-01-31",
         "value": 8437000000, "filed_date": "2019-03-06", "accession_number": "0001108524-19-000009"},
    ]
    result = dedupe_facts(facts)
    assert len(result) == 1
    assert result[0]["filed_date"] == "2017-03-09"
    assert result[0]["accession_number"] == "0001108524-17-000009"

def test_dedupe_keeps_distinct_periods_separate():
    facts = [
        {"canonical_concept": "revenue", "start_date": "2016-02-01", "end_date": "2017-01-31",
         "value": 8437000000, "filed_date": "2017-03-09", "accession_number": "A"},
        {"canonical_concept": "revenue", "start_date": "2017-02-01", "end_date": "2018-01-31",
         "value": 10480000000, "filed_date": "2018-03-08", "accession_number": "B"},
    ]
    assert len(dedupe_facts(facts)) == 2

def test_dedupe_keeps_different_concepts_separate_even_with_same_period():
    facts = [
        {"canonical_concept": "revenue", "start_date": "2020-01-01", "end_date": "2020-12-31",
         "value": 100, "filed_date": "2021-02-01", "accession_number": "A"},
        {"canonical_concept": "operating_income", "start_date": "2020-01-01", "end_date": "2020-12-31",
         "value": 20, "filed_date": "2021-02-01", "accession_number": "B"},
    ]
    assert len(dedupe_facts(facts)) == 2