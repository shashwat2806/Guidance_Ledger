from core.ingestion.concepts import canonical_concept
from core.ingestion.sec_client import SECClient

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def fetch_company_facts(cik, client=None):
    client = client or SECClient()
    url = FACTS_URL.format(cik=cik)
    return client.get(url)

def extract_revenue_facts(company_facts):
    facts = []
    gaap = company_facts.get("facts", {}).get("us-gaap", {})
    for raw_tag, tag_data in gaap.items():
        concept = canonical_concept(raw_tag)
        if concept is None:
            continue
        for unit, entries in tag_data.get("units", {}).items():
            for entry in entries:
                facts.append({
                    "raw_tag": raw_tag,
                    "canonical_concept": concept,
                    "value": entry["val"],
                    "unit": unit,
                    "fiscal_year": entry.get("fy"),
                    "fiscal_period": entry.get("fp"),
                    "start_date": entry.get("start"),
                    "end_date": entry.get("end"),
                    "form": entry.get("form"),
                    "accession_number": entry.get("accn"),
                    "filed_date": entry.get("filed"),
                    "gaap_basis": "GAAP",
                })
    return facts

def dedupe_facts(facts):
    best = {}
    for fact in facts:
        key = (fact["canonical_concept"], fact["start_date"], fact["end_date"])
        current = best.get(key)
        if current is None or fact["filed_date"] < current["filed_date"]:
            best[key] = fact
    return list(best.values())