import httpx

from core.ingestion.exhibits import document_url, extract_text, fetch_exhibit_text
from core.ingestion.filings import list_8k_filings
from core.ingestion.sec_client import SECClient

def test_list_8k_filings_filters_out_other_forms():
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K", "8-K", "10-K"],
                "accessionNumber": ["0001-24-01", "0001-24-02", "0001-24-03", "0001-24-04"],
                "filingDate": ["2024-05-01", "2024-08-28", "2024-11-15", "2025-02-01"],
                "primaryDocument": ["q1.htm", "pr1.htm", "pr2.htm", "annual.htm"],
                "items": ["", "2.02,9.01", "5.02", ""],
            }
        }
    }

    result = list_8k_filings(submissions)

    assert len(result) == 2
    assert result[0]["accession_number"] == "0001-24-02"
    assert result[0]["filing_date"] == "2024-08-28"
    assert result[0]["items"] == "2.02,9.01"
    assert result[1]["accession_number"] == "0001-24-03"


def test_document_url_strips_leading_zeros_and_dashes():
    url = document_url("0001108524", "0001108524-24-000123", "crm-20240828.htm")
    assert url == "https://www.sec.gov/Archives/edgar/data/1108524/000110852424000123/crm-20240828.htm"


def test_extract_text_strips_tags_scripts_and_styles():
    html = (
        "<html><head><style>.a{color:red}</style></head>"
        "<body><script>var x=1;</script>"
        "<p>Revenue grew <b>20%</b> this quarter.</p></body></html>"
    )
    text = extract_text(html)
    assert "var x=1" not in text
    assert "color:red" not in text
    assert "Revenue grew 20% this quarter." in text

def test_fetch_exhibit_text_uses_client_and_extracts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def handler(request):
        return httpx.Response(200, text="<p>We grew revenue 20% year over year.</p>")

    client = SECClient(user_agent="Test test@example.com", transport=httpx.MockTransport(handler))
    text = fetch_exhibit_text("https://www.sec.gov/Archives/edgar/data/1/1/pr.htm", client=client)
    assert text == "We grew revenue 20% year over year."