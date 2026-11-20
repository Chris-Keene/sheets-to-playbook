#!/usr/bin/env python3
"""Golden snapshot test: proves a change didn't alter what the kit produces, except where you meant it to.

    python3 tests/golden.py              # build everything and compare with the saved snapshots
    python3 tests/golden.py --update     # accept what's built now as the new baseline
    python3 tests/golden.py --keep       # leave the built files in tests/golden/work/ to look at

For each settings file in CONFIGS it builds the A1 sheets and cards, the fill-in HTML sheets, the slides, and the
playbook from three session files (the example, the blank template and four tables). It also runs `verify` and
`draft` on a run made from fake sheets (tests/fixtures/run-golden).

Two kinds of snapshot:
  - tests/golden/snapshots/ (committed): the text of every PDF, the text and accessibility tree of every HTML page,
    slide and playbook view, and the verify report. These are the same on every machine.
  - tests/golden/local/ (git-ignored): low-resolution pictures of every PDF page and screenshots of every page and
    view. Font rendering differs between machines, so a fresh clone runs --update once to make its own.

Needs poppler (pdftoppm, pdftotext), Node.js and Playwright with Chromium: set PW to the Playwright folder
(.../node_modules/playwright), as for the slides PDF. The builders' own output folders (print/out, slides/out) are
moved aside while it runs and put back afterwards.
"""
import argparse, difflib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "tests" / "golden"
SNAP = GOLD / "snapshots"
LOCAL = GOLD / "local"
FIXTURE = ROOT / "tests" / "fixtures" / "run-golden"
PY = sys.executable

CONFIGS = {
    "default": "playbook.config.json",
    "can": "examples/can/playbook.config.json",
}
SESSIONS = {
    "example": "examples/example-playbook.json",
    "template": "examples/session-template.json",
    "four": "tests/four-tables.json",
}
PAGES = ["overview", "commitments", "about", "kit"]   # the playbook's fixed views; challenge pages are added per session
BUILD_OUTPUTS = ["print/out", "slides/out"]
PIXEL_TOLERANCE = 0.002   # share of pixels allowed to differ (anti-aliasing noise), per picture


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"Failed: {' '.join(str(c) for c in cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def routes(session_file):
    data = json.loads(Path(session_file).read_text())
    return PAGES + [c["id"] for c in data.get("challenges", [])]


def safe(key):
    return re.sub(r"[^A-Za-z0-9._-]+", "__", key)


def build(work):
    """Build every output into work/, returning the jobs to snapshot."""
    jobs, pdfs = [], []
    for cname, cfg in CONFIGS.items():
        for d in BUILD_OUTPUTS:
            shutil.rmtree(ROOT / d, ignore_errors=True)
        run([PY, "print/build_paper.py", "--config", cfg])
        run([PY, "print/build_sheets_html.py", "--config", cfg])
        run([PY, "slides/build_slides.py", "--config", cfg])
        dest = work / cname
        for f in sorted((ROOT / "print/out/paper").glob("*.pdf")):
            (dest / "paper").mkdir(parents=True, exist_ok=True)
            pdfs.append((f"{cname}/paper/{f.name}", shutil.copy2(f, dest / "paper" / f.name)))
        for f in sorted((ROOT / "print/out/html").glob("*.html")):
            (dest / "sheets").mkdir(parents=True, exist_ok=True)
            jobs.append({"key": f"{cname}/sheets/{f.name}", "file": str(shutil.copy2(f, dest / "sheets" / f.name)), "kind": "page"})
        for f in sorted((ROOT / "slides/out").glob("*.html")):
            (dest / "slides").mkdir(parents=True, exist_ok=True)
            jobs.append({"key": f"{cname}/slides/{f.name}", "file": str(shutil.copy2(f, dest / "slides" / f.name)), "kind": "slides"})
        for sname, sfile in SESSIONS.items():
            out = dest / f"playbook-{sname}" / "index.html"
            run([PY, "build/build.py", sfile, "--out", out, "--config", cfg])
            jobs.append({"key": f"{cname}/playbook-{sname}", "file": str(out), "kind": "playbook", "routes": routes(ROOT / sfile)})
    # verify and draft on the fake run (a copy, so the fixture folder stays clean)
    rc = work / "run"
    shutil.copytree(FIXTURE, rc)
    run([PY, "ingest/ingest.py", "verify", "--run", rc])
    report = json.loads((rc / "verify.json").read_text())
    run([PY, "ingest/ingest.py", "draft", "--run", rc])
    jobs.append({"key": "run/draft", "file": str(rc / "playbook-draft.html"), "kind": "playbook", "routes": routes(rc / "session.json")})
    return jobs, pdfs, report


def snapshot_pdfs(pdfs, shots):
    out = {}
    for key, f in pdfs:
        text = run(["pdftotext", f, "-"])
        out[key] = "## text\n" + norm(text)
        prefix = shots / safe(key)
        run(["pdftoppm", "-r", "10", "-png", f, prefix])
    return out


def snapshot_pages(jobs, shots, work):
    pw = os.environ.get("PW", "playwright")
    spec = work / "jobs.json"
    spec.write_text(json.dumps({"jobs": jobs, "shots": str(shots)}))
    result = work / "result.json"
    env = dict(os.environ, PW=pw)
    r = subprocess.run(["node", str(GOLD / "snap.js"), str(spec), str(result)], capture_output=True, text=True, env=env)
    if r.returncode:
        sys.exit("The page snapshots failed. They need Node and Playwright with Chromium: set PW to the Playwright "
                 "folder (.../node_modules/playwright).\n" + r.stderr[-2000:])
    out = {}
    for key, snap in json.loads(result.read_text()).items():
        out[key] = "## text\n" + norm(snap["text"]) + "\n## accessibility tree\n" + snap["ax"]
    return out


def norm(text):
    # file sizes change by a byte or two whenever a PDF is rebuilt; what matters is that a size is shown
    text = re.sub(r"\b\d+(?:\.\d+)? ?(KB|MB)\b", r"N \1", text)
    return "\n".join(line.rstrip() for line in text.replace("\r", "").split("\n")).strip() + "\n"


def compare_pictures(old_dir, new_dir):
    from PIL import Image, ImageChops
    problems = []
    old = {p.name: p for p in old_dir.glob("*.png")} if old_dir.exists() else {}
    new = {p.name: p for p in new_dir.glob("*.png")}
    if not old:
        return ["no local pictures to compare yet: run with --update once on this machine"]
    for name in sorted(set(old) | set(new)):
        if name not in new:
            problems.append(f"picture gone: {name}")
        elif name not in old:
            problems.append(f"new picture: {name}")
        else:
            a, b = Image.open(old[name]).convert("RGB"), Image.open(new[name]).convert("RGB")
            if a.size != b.size:
                problems.append(f"picture changed size: {name} {a.size} -> {b.size}")
                continue
            diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 24 else 0)
            share = sum(diff.histogram()[255:]) / (a.size[0] * a.size[1])
            if share > PIXEL_TOLERANCE:
                problems.append(f"picture differs: {name} ({share:.2%} of pixels)")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--update", action="store_true", help="save what's built now as the baseline")
    ap.add_argument("--keep", action="store_true", help="keep the built files in tests/golden/work/")
    a = ap.parse_args()

    work = GOLD / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    saved = Path(tempfile.mkdtemp(prefix="golden-saved-"))
    for d in BUILD_OUTPUTS:   # keep the user's own builds safe
        if (ROOT / d).exists():
            shutil.move(str(ROOT / d), str(saved / d.replace("/", "__")))
    try:
        jobs, pdfs, report = build(work)
        shots = work / "pictures"
        shots.mkdir()
        snaps = snapshot_pdfs(pdfs, shots)
        snaps.update(snapshot_pages(jobs, shots, work))
        snaps["run/verify"] = json.dumps({k: report[k] for k in ("errors", "warnings", "raw_items", "used", "unused")}, indent=1) + "\n"
    finally:
        for d in BUILD_OUTPUTS:
            shutil.rmtree(ROOT / d, ignore_errors=True)
            if (saved / d.replace("/", "__")).exists():
                shutil.move(str(saved / d.replace("/", "__")), str(ROOT / d))
        shutil.rmtree(saved, ignore_errors=True)

    if a.update:
        shutil.rmtree(SNAP, ignore_errors=True)
        SNAP.mkdir(parents=True)
        for key, text in snaps.items():
            (SNAP / (safe(key) + ".txt")).write_text(text)
        shutil.rmtree(LOCAL, ignore_errors=True)
        shutil.copytree(shots, LOCAL)
        print(f"Baseline saved: {len(snaps)} snapshots, {len(list(LOCAL.glob('*.png')))} pictures.")
    else:
        problems = []
        old = {p.stem: p.read_text() for p in SNAP.glob("*.txt")}
        new = {safe(k): v for k, v in snaps.items()}
        if not old:
            sys.exit("No baseline yet: run with --update first.")
        for key in sorted(set(old) | set(new)):
            if key not in new:
                problems.append(f"GONE     {key}")
            elif key not in old:
                problems.append(f"NEW      {key}")
            elif old[key] != new[key]:
                diff = list(difflib.unified_diff(old[key].splitlines(), new[key].splitlines(), "before", "now", lineterm="", n=1))
                problems.append(f"CHANGED  {key}\n    " + "\n    ".join(diff[2:40]) + ("\n    ..." if len(diff) > 40 else ""))
        pictures = compare_pictures(LOCAL, shots)
        for p in problems:
            print(p)
        for p in pictures:
            print("PICTURE  " + p)
        print(f"{len(new)} snapshots: {len(problems)} differ. Pictures: {len(pictures)} differ.")
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
        sys.exit(1 if problems or pictures else 0)
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
