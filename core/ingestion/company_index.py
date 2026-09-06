from core.ingestion.sec_client import SECClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

def resolve_cik(ticker, client=None):
    client = client or SECClient()
    data = client.get(TICKERS_URL)
    ticker = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker:
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"ticker not found: {ticker}")