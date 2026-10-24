CHAR_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}


def normalize(text):
    chars = []
    index_map = []
    prev_space = False
    for i, ch in enumerate(text):
        ch = CHAR_MAP.get(ch, ch)
        if ch.isspace():
            if prev_space:
                continue
            prev_space = True
            chars.append(" ")
            index_map.append(i)
        else:
            prev_space = False
            for c in ch.lower():
                chars.append(c)
                index_map.append(i)
    return "".join(chars), index_map


def locate_quote(text, quote):
    norm_quote, _ = normalize(quote.strip())
    if not norm_quote:
        return None
    norm_text, index_map = normalize(text)
    pos = norm_text.find(norm_quote)
    if pos == -1:
        return None
    start = index_map[pos]
    end = index_map[pos + len(norm_quote) - 1] + 1
    return start, end
