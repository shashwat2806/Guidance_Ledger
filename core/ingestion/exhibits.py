from bs4 import BeautifulSoup

from core.ingestion.sec_client import SECClient

ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accn_no_dashes}/{doc}"

def document_url(cik, accession_number, primary_document):
    cik_no_zeros = str(int(cik))
    accn_no_dashes = accession_number.replace("-", "")
    return ARCHIVES_URL.format(cik_no_zeros=cik_no_zeros, accn_no_dashes=accn_no_dashes, doc=primary_document)


def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)

def fetch_exhibit_text(url, client=None):
    client = client or SECClient()
    html = client.get_text(url)
    return extract_text(html)