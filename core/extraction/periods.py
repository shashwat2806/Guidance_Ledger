import re
from datetime import datetime

OPENING_CHARS = 3000
ENDED_DATE = re.compile(
    r"ended\s+(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)


def release_period_end(text):
    match = ENDED_DATE.search(text[:OPENING_CHARS])
    if match is None:
        return None
    month, day, year = match.groups()
    try:
        return datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date().isoformat()
    except ValueError:
        return None
