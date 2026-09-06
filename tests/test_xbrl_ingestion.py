import httpx

from core.ingestion.company_index import resolve_cik
from core.ingestion.concepts import canonical_concept
from core.ingestion.sec_client import SECClient
from core.ingestion.xbrl import extract_revenue_facts

def test_resolve_cik_finds_matching_ticker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tickers = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1108524, "ticker": "CRM", "title": "SALESFORCE INC"},
    }

    def handler(request):
        return httpx.Response(200, json=tickers)

    client = SECClient(user_agent="Test test@example.com", transport=httpx.MockTransport(handler))
    assert resolve_cik("CRM", client=client) == "0001108524"

def test_resolve_cik_raises_on_unknown_ticker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def handler(request):
        return httpx.Response(200, json={"0": {"cik_str": 1, "ticker": "AAPL", "title": "Apple Inc."}})

    client = SECClient(user_agent="Test test@example.com", transport=httpx.MockTransport(handler))
    try:
        resolve_cik("NOTREAL", client=client)
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_canonical_concept_maps_known_revenue_tags():
    assert canonical_concept("Revenues") == "revenue"
    assert canonical_concept("RevenueFromContractWithCustomerExcludingAssessedTax") == "revenue"

def test_canonical_concept_returns_none_for_unknown_tag():
    assert canonical_concept("SomeRandomTag") is None

def test_extract_revenue_facts_handles_tag_drift():
    company_facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [
                        {"val": 1000, "start": "2016-01-01", "end": "2016-12-31",
                         "fy": 2016, "fp": "FY", "form": "10-K", "accn": "0001-16-000001"},
                    ]}
                },
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [
                        {"val": 2000, "start": "2019-01-01", "end": "2019-12-31",
                         "fy": 2019, "fp": "FY", "form": "10-K", "accn": "0001-19-000001"},
                    ]}
                },
                "SomeUnrelatedConcept": {
                    "units": {"USD": [
                        {"val": 999, "start": "2019-01-01", "end": "2019-12-31",
                         "fy": 2019, "fp": "FY", "form": "10-K", "accn": "0001-19-000002"},
                    ]}
                },
            }
        }
    }

    result = extract_revenue_facts(company_facts)

    assert len(result) == 2
    assert {r["canonical_concept"] for r in result} == {"revenue"}
    assert {r["raw_tag"] for r in result} == {
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    }
    assert all(r["gaap_basis"] == "GAAP" for r in result)