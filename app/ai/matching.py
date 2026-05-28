import difflib

MATCH_THRESHOLD = 0.65


def find_best_match(candidate_name: str, items: list, key=None) -> tuple:
    """Fuzzy-match candidate_name against a list of objects by some name field.
    Returns (best_item, score) or (None, 0.0) when no candidate or no items.
    Score: 1.0 = exact, 0.85 = substring, 0.0–1.0 = difflib ratio.

    By default matches on item.name. Pass key=lambda x: x.something to match a different field.
    """
    if not candidate_name or not items:
        return None, 0.0

    if key is None:
        key = lambda x: x.name

    best_item = None
    best_score = 0.0
    c = candidate_name.lower().strip()

    for item in items:
        p = (key(item) or "").lower().strip()
        if not p:
            continue

        if c == p:
            return item, 1.0

        if c in p or p in c:
            score = 0.85
        else:
            score = difflib.SequenceMatcher(None, c, p).ratio()

        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score
