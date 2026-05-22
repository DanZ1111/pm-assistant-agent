import difflib

MATCH_THRESHOLD = 0.65


def find_best_match(candidate_name: str, projects: list) -> tuple:
    """Fuzzy-match candidate_name against a list of Project objects by name.
    Returns (best_project, score) or (None, 0.0) when no candidate or no projects.
    Score: 1.0 = exact, 0.85 = substring, 0.0–1.0 = difflib ratio.
    """
    if not candidate_name or not projects:
        return None, 0.0

    best_project = None
    best_score = 0.0
    c = candidate_name.lower().strip()

    for project in projects:
        p = (project.name or "").lower().strip()
        if not p:
            continue

        if c == p:
            return project, 1.0

        if c in p or p in c:
            score = 0.85
        else:
            score = difflib.SequenceMatcher(None, c, p).ratio()

        if score > best_score:
            best_score = score
            best_project = project

    return best_project, best_score
