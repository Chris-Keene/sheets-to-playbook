#!/usr/bin/env python3
"""Apply the decisions saved from the review app to a run.

    python3 tools/review/apply_review.py [decisions.json] [--run <run folder>]

With no file given, the newest ~/Downloads/review-decisions-<run>*.json is used. The file is copied to
<run>/review/decisions.json, so the readings can be applied again if session.json is rewritten.

  confirmed  each [?word] or [illegible] is replaced by the reviewed word, in the raw files (so verify still matches
             quotes and cards word for word) and in session.json. A blank [illegible] stays.
  edited     the reviewed line replaces the line in session.json; for a quote or a card it replaces the raw text too.
  keep       nothing changes: the word stays flagged.
  checks and calls need judgement, so they're listed in <run>/review/to-action.md rather than applied.
Then run ingest.py verify and ingest.py draft.
"""
import argparse, glob, json, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import formats  # noqa: E402


def replace_markers(s, pairs):
    """Replace each (marker, value) once, in order. Returns (new string, pairs not found)."""
    left = []
    for marker, value in pairs:
        if not value:
            continue
        if marker not in s:
            left.append((marker, value))
            continue
        s = s.replace(marker, value, 1)
    return s, left


def page_items(session, W):
    """Every line on the page that carries a src, with its path's settings from the workshop's output.json."""
    for spec, _label, _owner, x in W.page_items(session):
        if isinstance(x, dict):
            yield spec, x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions", nargs="?")
    ap.add_argument("--run", help="the run folder (default: runs/latest)")
    ap.add_argument("--config", help="settings file, if not playbook.config.json (it says which workshop the run is)")
    a = ap.parse_args()
    W = formats.load(config.load(a.config))
    raw_field = dict(W.output.get("raw_field_map", {}))   # a page field whose words live under another name in the raw file
    run = Path(a.run).expanduser().resolve() if a.run else (ROOT / "runs" / "latest").resolve()
    if not (run / "session.json").exists():
        sys.exit(f"No session.json in {run}.")
    src = Path(a.decisions).expanduser() if a.decisions else max(
        (Path(p) for p in glob.glob(str(Path.home() / "Downloads" / f"review-decisions-{run.name}*.json"))),
        key=lambda p: p.stat().st_mtime, default=None)
    if not src or not src.exists():
        sys.exit("No decisions file: save one from the review app first, or pass its path.")
    dec = json.loads(src.read_text())
    if dec.get("run") not in (run.name, None):
        sys.exit(f"That decisions file is for run {dec.get('run')}, not {run.name}.")
    review = run / "review"
    review.mkdir(exist_ok=True)
    if src.resolve() != (review / "decisions.json").resolve():
        shutil.copy(src, review / "decisions.json")

    # every raw file an id can live in: table files, card files and the merged commitments file
    files = {Path(p): json.loads(Path(p).read_text()) for p in glob.glob(str(run / "raw" / "*.json"))}
    index = {}
    for f, d in files.items():
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if isinstance(x.get("id"), str) and any(f in x for f in W.text_fields()):
                    index.setdefault(x["id"], []).append((f, x))
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    session_path = run / "session.json"
    session = json.loads(session_path.read_text())

    raw_changes, page_changes, missing, todo, changed = 0, 0, [], [], set()
    stamp = datetime.now().isoformat(timespec="minutes")
    for key, d in dec["items"].items():
        if d["kind"] in ("check", "call"):
            if d["status"] in ("change", "chosen"):
                todo.append((d["where"], d.get("option") or "", d.get("note") or "", d["src"]))
            continue
        if d["status"] not in ("confirmed", "edited"):
            continue
        for field, v in (d.get("fields") or {}).items():
            pairs = [(m, val) for m, val in zip(v["markers"], v["values"]) if val]
            resolved = set()
            # raw files: an id can live in several files (a card set's file and the merged commitments.json), and
            # every copy gets the same fix, each starting from the full list of readings
            for sid in d["src"]:
                for f, item in index.get(sid, []):
                    rf = raw_field.get(field, field)
                    todo_pairs = list(pairs)
                    for k in [rf] + [k for k, val in item.items() if isinstance(val, str) and k not in (rf, "id", "photo")]:
                        if not todo_pairs or not isinstance(item.get(k), str):
                            continue
                        new, left = replace_markers(item[k], todo_pairs)
                        resolved |= {pr for pr in todo_pairs if pr not in left}
                        if new != item[k]:
                            item[k] = new; changed.add(f); raw_changes += 1
                        todo_pairs = left
            # the page: the line whose src matches this screen's
            for _spec, x in page_items(session, W):
                s = x.get("src")
                if set(s if isinstance(s, list) else [s]) != set(d["src"]) or not isinstance(x.get(field), str):
                    continue
                new, left = replace_markers(x[field], pairs)
                resolved |= {pr for pr in pairs if pr not in left}
                if new != x[field]:
                    x[field] = new; page_changes += 1
            unresolved = [pr for pr in pairs if pr not in resolved]
            if unresolved and d["status"] == "confirmed":
                missing.append((key, unresolved))
        if d["status"] == "edited" and d.get("line"):
            first = next(iter(d.get("fields") or {"text": None}))
            word_for_word = False
            for spec, x in page_items(session, W):
                s = x.get("src")
                if set(s if isinstance(s, list) else [s]) == set(d["src"]):
                    word_for_word |= spec.get("policy") == "verbatim"
                    if x.get(first) != d["line"]:
                        x[first] = d["line"]; page_changes += 1
            if word_for_word:
                # quotes and cards are checked word for word against the raw text, so the raw text takes the edit
                # too (wherever the quote was written: a quote taken from Sheet 2 used to keep its old raw text)
                for f, item in index.get(d["src"][0], []):
                    rf = raw_field.get(first, first)
                    if item.get(rf) != d["line"]:
                        item[rf] = d["line"]; changed.add(f); raw_changes += 1
        # leave a trail in the readers' unclear lists
        for sid in d["src"]:
            for f, dd in files.items():
                for u in dd.get("unclear", []) if isinstance(dd, dict) else []:
                    if u.get("id") == sid and u.get("reviewed", {}).get("status") != d["status"]:
                        u["reviewed"] = {"status": d["status"], "at": stamp}; changed.add(f)

    for f in changed:
        f.write_text(json.dumps(files[f], ensure_ascii=False, indent=2) + "\n")
    if page_changes:
        session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n")
    lines = [f"# To action from the review ({stamp})", "",
             "Checks marked as needing a change, and the calls made. These need judgement, so they aren't applied automatically.", ""]
    for where, option, note, srcs in todo:
        lines.append(f"- **{where}** ({', '.join(srcs) or 'no source'}): " + "; ".join(filter(None, [option, note])))
    (review / "to-action.md").write_text("\n".join(lines) + "\n")
    print(f"Applied {raw_changes} change(s) to {len(changed)} raw file(s) and {page_changes} to session.json. "
          f"{len(todo)} item(s) listed in {review / 'to-action.md'}.")
    for key, pairs in missing:
        print(f"  not found in the raw files or on the page (already applied?): {key} {pairs}")
    print("Next: python3 ingest/ingest.py verify, then ingest/ingest.py draft.")


if __name__ == "__main__":
    main()
