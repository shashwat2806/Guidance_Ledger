import re

from core.ingestion.sec_client import SECClient

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accn_no_dashes}/index.json"
EXHIBIT_99_PATTERN = re.compile(r"ex.*99", re.IGNORECASE)


def fetch_filings(cik, client=None):
    client = client or SECClient()
    url = SUBMISSIONS_URL.format(cik=cik)
    return client.get(url)


def list_8k_filings(submissions):
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    items = recent.get("items", [])
    result = []
    for i, form in enumerate(forms):
        if form != "8-K":
            continue
        result.append({
            "accession_number": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "primary_document": recent["primaryDocument"][i],
            "items": items[i] if i < len(items) else "",
        })
    return result


def is_earnings_related(filing):
    return "2.02" in filing.get("items", "")


def fetch_filing_documents(cik, accession_number, client=None):
    client = client or SECClient()
    cik_no_zeros = str(int(cik))
    accn_no_dashes = accession_number.replace("-", "")
    url = INDEX_URL.format(cik_no_zeros=cik_no_zeros, accn_no_dashes=accn_no_dashes)
    data = client.get(url)
    return data.get("directory", {}).get("item", [])


def find_press_release_exhibit(documents):
    candidates = [d for d in documents if EXHIBIT_99_PATTERN.search(d.get("name", ""))]
    if not candidates:
        return None
    largest = max(candidates, key=lambda d: int(d.get("size") or 0))
    return largest.get("name")