REVENUE_TAGS = {
    "Revenues": "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "RevenueFromContractWithCustomerIncludingAssessedTax": "revenue",
    "SalesRevenueNet": "revenue",
}

def canonical_concept(raw_tag):
    return REVENUE_TAGS.get(raw_tag)