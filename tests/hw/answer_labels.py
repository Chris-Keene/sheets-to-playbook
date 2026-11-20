#!/usr/bin/env python3
"""Write a run's labels.json from a handwriting test's answer key, so the readers can be scored on reading alone.

    python3 tests/hw/answer_labels.py runs/<run>                                      # rounds 1 and 2
    python3 tests/hw/answer_labels.py runs/<run> --truth tests/hw/round3/truth.json   # round 3

Use it after `ingest.py prepare` and before the readers start. Labelling and reading are separate skills: in the
scored rounds the readers worked from correct labels made this way, while a blind labeller wrote labels-blind.json
in the same format without seeing them, and score.py scores that file separately. If you're testing a blind
labeller, run `ingest.py status` only after it has finished: status prints what's in labels.json.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def label(want):
    if want["sheet"] == "stubs":
        return {"kind": "stubs", "note": want["kind"]}
    sheet = want["sheet"].split("+") if "+" in want["sheet"] else want["sheet"]   # "S2+S3": two sheets, one photo
    out = {"table": want["table"], "sheet": sheet}
    notes = [] if want["kind"] == "whole" else [want["kind"]]
    if int(want["table"]) >= 91:
        notes.append("spare number: this table wrote the same number as another table")
    if notes:
        out["note"] = "; ".join(notes)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="the ingest run folder (made by ingest.py prepare from this test's inbox)")
    ap.add_argument("--truth", default=str(HERE / "truth.json"), help="answer key (default tests/hw/truth.json)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing labels.json")
    a = ap.parse_args()
    run, truth_path = Path(a.run), Path(a.truth)
    if not truth_path.exists():
        sys.exit(f"No answer key at {truth_path}: make it with make_hw_tests.py or make_round3.py first.")
    if not (run / "manifest.json").exists():
        sys.exit(f"No manifest.json in {run}: run python3 ingest/ingest.py prepare on the test's inbox first.")
    out = run / "labels.json"
    if out.exists() and not a.force:
        sys.exit(f"{out} already exists; add --force to replace it.")
    photos = json.loads(truth_path.read_text())["photos"]
    manifest = json.loads((run / "manifest.json").read_text())
    labels, unknown = {}, []
    for p in manifest["photos"]:
        src = Path(p["source"])
        want = photos.get(src.name) or photos.get(src.with_suffix(".HEIC").name)
        if want is None:
            unknown.append(src.name)
            continue
        labels[p["id"]] = label(want)
    out.write_text(json.dumps({"photos": labels, "audio": {}}, indent=1, ensure_ascii=False) + "\n")
    print(f"Labelled {len(labels)} of {len(manifest['photos'])} photos from {truth_path.name} into {out}")
    if unknown:
        print(f"Not in the answer key, so left unlabelled: {', '.join(unknown)} (is this run from the right inbox?)")


if __name__ == "__main__":
    main()
