"""Checks particular to the retro notes, used by build/build.py (check) and ingest/ingest.py verify (verify).

The generic checks (every line traced to a sheet, questions word for word, no unclear markers) run from output.json.
These cover what only a retro has: dot votes, which are numbers, and actions, whose owner and date are the team's
own words.
"""


def check(data):
    """Structural mistakes a hand-edit or an AI pass is most likely to make. Returns a list of problems."""
    problems = []
    meta = data.get("meta", {})
    status = meta.get("status")
    if status not in ("example", "template", "draft", "final"):
        problems.append(f"meta.status must be example, template, draft or final, not {status!r}")
    n = meta.get("tables")
    if not isinstance(n, int) or n < 1:
        problems.append("meta.tables must be how many teams there were (a number, at least 1)")
    for key in ("went_well", "got_in_way", "questions", "ideas", "actions"):
        if not isinstance(data.get(key, []), list):
            problems.append(f"{key} must be a list")
    for i, x in enumerate(data.get("ideas", []), 1):
        v = x.get("votes", 0) if isinstance(x, dict) else 0
        if not isinstance(v, int) or v < 0:
            problems.append(f"idea {i}: votes must be a whole number, 0 or more, not {v!r}")
    for i, a in enumerate(data.get("actions", []), 1):
        if not isinstance(a, dict) or not (a.get("what") or a.get("text")):
            problems.append(f"action {i}: needs `what`")
    if status == "final" and not data.get("actions"):
        problems.append("final: no actions (a retro's notes need at least one, or say so in meta.banner and publish as a draft)")
    for k in meta.get("table_names") or {}:
        if isinstance(n, int) and not (str(k).isdigit() and 1 <= int(k) <= n):
            problems.append(f"meta.table_names: {k!r} isn't a team number from 1 to {n}")
    return problems


def verify(v):
    """Votes must add up to the dots on the paper; an action's who and when must be what the sheet says."""
    data, items = v.data, v.items
    for i, x in enumerate(data.get("ideas", []), 1):
        if not isinstance(x, dict):
            continue
        srcs = [s for s in v.srcs(x) if s in items]
        if not srcs:
            continue
        # merged ideas carry every team's dots
        written = sum(int(items[s].get("votes") or 0) for s in srcs if str(items[s].get("votes") or 0).isdigit())
        if (x.get("votes") or 0) != written:
            v.errors.append(f"idea {i}: {x.get('votes', 0)} votes on the page, but the sheet{'s' if len(srcs) > 1 else ''} show{'' if len(srcs) > 1 else 's'} {written}")
    for i, a in enumerate(data.get("actions", []), 1):
        if not isinstance(a, dict):
            continue
        row = next((items[s] for s in v.srcs(a) if s in items), None)
        if not row:
            continue
        for field in ("who", "when"):
            if a.get(field) and v.similar(a[field], row.get(field, "")) < 0.8:
                v.errors.append(f"action {i}: {field} \"{a[field]}\" isn't what the sheet says (\"{row.get(field, '')}\")")
