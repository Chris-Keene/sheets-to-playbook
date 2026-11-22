"""Checks particular to the round-tables page, used by build/build.py (check) and ingest/ingest.py verify (verify).

The generic checks (every line traced to a sheet, quotes word for word, no personal details, no unclear markers)
run for every workshop from output.json. These are the ones that only make sense for this page's shape: themes,
challenges, tables and commitment cards.
"""
import re

STAGES = {"starting", "growing", "established"}
PAGES = ("overview", "commitments", "resources", "about", "kit", "challenges")


def check(data):
    """Structural mistakes a hand-edit or an AI pass is most likely to make. Returns a list of problems."""
    ids = {c["id"] for c in data["challenges"]}
    themes = {t["id"] for t in data["themes"]}
    n = data["meta"]["tables"]
    status = data["meta"]["status"]
    problems = []
    if status not in ("example", "template", "draft", "final"):
        problems.append(f"meta.status must be example, template, draft or final, not {status!r}")
    if status == "final":
        # nothing half-filled goes live: these are the parts every challenge page leans on
        if not data["themes"]:
            problems.append("final: no themes")
        for c in data["challenges"]:
            for field in ("title", "summary", "theme"):
                if not c.get(field):
                    problems.append(f'final: {c["id"]} has no {field}')
            if not c["actions"]:
                problems.append(f'final: {c["id"]} has no actions')
        if len(ids) != len(data["challenges"]):
            problems.append("duplicate challenge ids")
    for c in data["challenges"]:
        if c["theme"] and c["theme"] not in themes:
            problems.append(f'{c["id"]}: unknown theme {c["theme"]}')
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", c["id"]):
            problems.append(f'{c["id"]}: id must be lowercase letters, digits and hyphens (used as the URL #anchor)')
        if c["id"] in PAGES:
            problems.append(f'{c["id"]}: id clashes with a page name')
        for a in c["actions"]:
            bad = set(a.get("stages", [])) - STAGES
            if bad:
                problems.append(f'{c["id"]}: unknown stage {bad}')
    for t in data["themes"] + data["challenges"]:
        out = [x for x in t["tables"] if not 1 <= x <= n]
        if out:
            problems.append(f'{t.get("id")}: table numbers outside 1-{n}: {out}')
    for q in data.get("quotes", []):
        if q.get("challenge") and q["challenge"] not in ids:
            problems.append(f'quote links unknown challenge {q["challenge"]}')
        out = [x for x in q.get("tables", []) if not 1 <= x <= n]
        if out:
            problems.append(f'quote "{q.get("text", "")[:40]}": table numbers outside 1-{n}: {out}')
    for k in data["meta"].get("table_names") or {}:
        if not (str(k).isdigit() and 1 <= int(k) <= n):
            problems.append(f"meta.table_names: {k!r} isn't a table number from 1 to {n}")
    for m in data["commitments"]:
        if m.get("challenge") and m["challenge"] not in ids:
            problems.append(f'commitment links unknown challenge {m["challenge"]}')
    return problems


def verify(v):
    """Cross-checks between the page and the transcriptions. v has data, items, errors, warnings, similar, srcs."""
    data, items = v.data, v.items
    for c in data["challenges"]:
        # the tables credited must be the ones whose items the page actually uses
        used_tables = {int(s[1:3]) for x in c.get("helped", []) + c.get("hindered", []) + c.get("actions", []) + c.get("quotes", [])
                       for s in v.srcs(x) if s.startswith("T")}
        extra = used_tables - set(c["tables"])
        if extra:
            v.warnings.append(f"{c['id']}: uses items from table(s) {sorted(extra)} that aren't in its tables list")
    for i, m in enumerate(data.get("commitments", []), 1):
        # a name goes on the page only if that person wrote it in the card's Name or Organisation line
        card = next((items[s_] for s_ in v.srcs(m) if s_ in items), {})
        for field in ("name", "org"):
            if m.get(field) and v.similar(m[field], card.get(field, "")) < 0.85:
                v.errors.append(f"commitment {i}: {field} \"{m[field]}\" isn't what the card's own {field} line says")

    # theme phrases are meant to be copied from Sheet 1, so each should match something written there
    s1 = [it.get("text", "") for i, it in items.items() if it["_kind"].startswith("S1.")]
    for t in data.get("themes", []):
        for h in t.get("heard", []):
            if s1 and max(v.similar(h, x) for x in s1) < 0.8:
                v.warnings.append(f"theme {t['id']}: \"{h}\" doesn't match anything written on a Sheet 1")
        stray = set(t["tables"]) - {int(i[1:3]) for i, it in items.items() if it["_kind"].startswith("S1.")}
        if stray:
            v.warnings.append(f"theme {t['id']}: tables {sorted(stray)} have no transcribed Sheet 1")

    # every table that worked on a challenge should land on exactly one page
    raw_tables = sorted({int(i[1:3]) for i in items if i.startswith("T")})
    homes = {}
    for c in data["challenges"]:
        for t in c["tables"]:
            homes.setdefault(t, []).append(c["id"])
    for t in raw_tables:
        if t not in homes:
            v.warnings.append(f"Table {t} has transcribed sheets but no challenge page")
        elif len(homes[t]) > 1:
            v.warnings.append(f"Table {t} appears on more than one challenge page: {homes[t]}")
