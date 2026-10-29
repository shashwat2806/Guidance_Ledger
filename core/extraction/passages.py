import re

SIGNALS = (
    (re.compile(r"revenue[^.]{0,80}\$\s?\d", re.IGNORECASE), 3),
    (re.compile(r"guidance", re.IGNORECASE), 1),
    (re.compile(r"\bY/Y\b|year-over-year", re.IGNORECASE), 1),
    (re.compile(r"\b(?:expects?|initiates|raises)\b", re.IGNORECASE), 1),
)
TABLE_DIGIT_RATIO = 0.2


def split_passages(text, size=3000, overlap=400):
    passages = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        passages.append((start, end))
        if end == len(text):
            break
        start = end - overlap
    return passages


def score_passage(passage):
    letters = sum(c.isalpha() for c in passage)
    digits = sum(c.isdigit() for c in passage)
    if digits > TABLE_DIGIT_RATIO * max(letters, 1):
        return 0
    return sum(weight * len(pattern.findall(passage)) for pattern, weight in SIGNALS)


def select_passages(text, top_k=3, size=3000, overlap=400):
    passages = split_passages(text, size, overlap)
    if not passages:
        return []
    ranked = sorted(passages[1:], key=lambda p: score_passage(text[p[0]:p[1]]), reverse=True)
    chosen = [passages[0]] + [p for p in ranked[:top_k] if score_passage(text[p[0]:p[1]]) > 0]
    return sorted(chosen)
