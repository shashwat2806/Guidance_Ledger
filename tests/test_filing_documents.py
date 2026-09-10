import httpx

from core.ingestion.filings import fetch_filing_documents, find_press_release_exhibit, is_earnings_related
from core.ingestion.sec_client import SECClient


def test_is_earnings_related_detects_item_202():
    assert is_earnings_related({"items": "2.02,9.01"}) is True
    assert is_earnings_related({"items": "5.02"}) is False
    assert is_earnings_related({"items": ""}) is False


def test_find_press_release_exhibit_picks_by_filename_pattern():
    documents = [
        {"name": "crm-20260826.htm", "type": "text.gif", "size": "29105"},
        {"name": "crm-20260826.xsd", "type": "text.gif", "size": "1860"},
        {"name": "crm-q2fy27xexhibit991.htm", "type": "text.gif", "size": "594133"},
        {"name": "FilingSummary.xml", "type": "text.gif", "size": "1693"},
    ]
    assert find_press_release_exhibit(documents) == "crm-q2fy27xexhibit991.htm"


def test_find_press_release_exhibit_returns_none_when_absent():
    documents = [
        {"name": "crm-20260902.htm", "type": "text.gif", "size": "28031"},
        {"name": "crm-20260902.xsd", "type": "text.gif", "size": "1860"},
    ]
    assert find_press_release_exhibit(documents) is None


def test_find_press_release_exhibit_picks_largest_when_multiple_match():
    documents = [
        {"name": "ex99-2-supplemental.htm", "type": "text.gif", "size": "5000"},
        {"name": "ex99-1-press-release.htm", "type": "text.gif", "size": "500000"},
    ]
    assert find_press_release_exhibit(documents) == "ex99-1-press-release.htm"


def test_fetch_filing_documents_parses_directory_item(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def handler(request):
        return httpx.Response(200, json={
            "directory": {
                "item": [
                    {"name": "crm-20260826.htm", "type": "text.gif", "size": "29105"},
                    {"name": "crm-q2fy27xexhibit991.htm", "type": "text.gif", "size": "594133"},
                ]
            }
        })

    client = SECClient(user_agent="Test test@example.com", transport=httpx.MockTransport(handler))
    docs = fetch_filing_documents("1108524", "0001108524-26-000187", client=client)
    assert len(docs) == 2
    assert docs[1]["name"] == "crm-q2fy27xexhibit991.htm"