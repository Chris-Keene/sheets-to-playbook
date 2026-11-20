#!/usr/bin/env python3
"""Score the handwriting readers against the fixture's ground truth (the answer key is make_fixtures.py itself).

    python3 tests/fixtures/make_fixtures.py     # make the inbox
    ...run the ingest on tests/fixtures/inbox and let its readers write raw/T02.json, T05, T09 and commitments.json
    python3 tests/check_fixture.py [run folder]     # defaults to runs/latest
Exact match after normalising case and punctuation; near misses are printed for a human to judge.
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "fixtures"))
from make_fixtures import TABLES, STUBS

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("run", nargs="?", default=str(HERE.parent / "runs" / "latest"), help="ingest run folder (default runs/latest)")
run = Path(ap.parse_args().run)
needed = [run / "raw" / f"T{t:02d}.json" for t in TABLES] + [run / "raw" / "commitments.json"]
absent = [str(p.relative_to(run)) for p in needed if not p.exists()]
if absent:
    sys.exit(f"Nothing to score in {run}: missing {', '.join(absent)}.\n"
             "Make the inbox with python3 tests/fixtures/make_fixtures.py, run the ingest on tests/fixtures/inbox "
             "(see tests/README.md), then point this at that run.")

norm = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r"\[[^\]]*\]", "", (s or "").lower()))
text = lambda x: x.get("text", "") if isinstance(x, dict) else (x or "")
expected, got = [], []
for t, sheets in TABLES.items():
    raw = json.loads((run / "raw" / f"T{t:02d}.json").read_text())
    s1, s2, s3, ss = (raw.get(k) or {} for k in ("S1", "S2", "S3", "SS"))
    if "S1" in sheets:
        expected += [f"T{t} S1 {x}" for x in sheets["S1"]["challenges"] + sheets["S1"]["top3"] + [sheets["S1"]["pick"]]]
        got += [f"T{t} S1 {text(x)}" for x in (s1.get("challenges") or []) + (s1.get("top3") or []) + ([s1["pick"]] if s1.get("pick") else [])]
    expected += [f"T{t} S2 {a} ({b})" for k in ("helped", "hindered") for a, b in sheets["S2"][k]]
    got += [f"T{t} S2 {text(x)} ({x.get('who', '') if isinstance(x, dict) else ''})" for k in ("helped", "hindered") for x in s2.get(k) or []]
    if sheets["S2"]["lesson"]:
        expected.append(f"T{t} S2 {sheets['S2']['lesson']}")
    got += [f"T{t} S2 {text(x)}" for x in s2.get("lessons") or []]
    expected += [f"T{t} S3 {a} / {n} / {s} / {sorted(st)}" for a, n, s, st in sheets["S3"]]
    got += [f"T{t} S3 {x.get('action', '')} / {x.get('needs', '')} / {x.get('sticks', '')} / {sorted(x.get('stages') or [])}" for x in s3.get("actions") or []]
    expected += [f"T{t} SS {q} ({w})" for q, w in sheets["SS"]["quotes"]] + [f"T{t} SS {q}" for q in sheets["SS"]["questions"]]
    got += [f"T{t} SS {text(x)} ({x.get('who', '') if isinstance(x, dict) else ''})" for x in ss.get("quotes") or []] + \
           [f"T{t} SS {text(x)}" for x in ss.get("questions") or []]
cards = json.loads((run / "raw" / "commitments.json").read_text()).get("cards", [])
expected += [f"card {c}" for c in STUBS]
got += [f"card {text(c)}" for c in cards]
gn = {norm(g): g for g in got}
hits = [e for e in expected if norm(e) in gn]
print(f"{len(hits)} of {len(expected)} items transcribed exactly (case and punctuation ignored)")
for e in expected:
    if norm(e) not in gn:
        print("  expected:", e)
extra = [g for g in got if norm(g) not in {norm(e) for e in expected}]
for g in extra:
    print("  got:     ", g)
