#!/usr/bin/env python3
"""Set up an event: pick a workshop, get a settings file for it, and the commands that make its kit.

    python3 tools/new_event.py                       # list the workshops
    python3 tools/new_event.py retro events/q4-retro # a settings file for a retro in events/q4-retro/

The new settings start from your current playbook.config.json (your names, colours, logo and font), with the
workshop set and the playbook's name and address left for you to fill in. Every builder takes it with --config.
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import formats  # noqa: E402


def describe(cfg):
    for wid, name in formats.available(cfg).items():
        w = formats.load(cfg, wid)
        minutes = sum(e.get("minutes", 0) for e in w.exercises[:len(w.data.get("agenda", []))])
        sheets = ", ".join(f"{e['code']} {e['title']}" for e in w.per_group())
        print(f"{wid}\n  {name}: {w.data.get('description', '')}\n  About {minutes} minutes on the sheets, "
              f"one set per {w.group}; {w.privacy}. Sheets: {sheets}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("workshop", nargs="?", help="the workshop's id (leave out to list them)")
    ap.add_argument("folder", nargs="?", help="where to put the event's settings (default events/<workshop>)")
    ap.add_argument("--config", help="settings to start from (default playbook.config.json)")
    a = ap.parse_args()
    base_file = Path(a.config) if a.config else ROOT / "playbook.config.json"
    cfg = config.load(str(base_file) if base_file.exists() else None)
    if not a.workshop:
        describe(cfg)
        return
    formats.load(cfg, a.workshop)        # stops with the list of folders searched if there's no such workshop
    folder = Path(a.folder or ROOT / "events" / a.workshop)
    out = folder / "playbook.config.json"
    if out.exists():
        sys.exit(f"{out} already exists: edit it, or pick another folder")
    folder.mkdir(parents=True, exist_ok=True)
    mine = json.loads(base_file.read_text()) if base_file.exists() else {}
    mine.pop("_note", None)
    mine["workshop"] = a.workshop
    mine.setdefault("playbook", {})
    mine["playbook"]["url"] = ""
    # paths in the settings are relative to the settings file, so point them back at where they were
    import os

    def rel(p):
        src = Path(p) if Path(p).is_absolute() else base_file.parent / p
        if not src.exists():
            src = ROOT / p              # a default, which resolves from the repo
        src, here = src.resolve(), folder.resolve()
        # relative when the two share a folder (a repo, a project); absolute when they only share the disk
        return str(src) if Path(os.path.commonpath([src, here])) == Path(src.anchor) else os.path.relpath(src, here)
    for key in ("primary", "secondary", "mark", "primary_dark", "secondary_dark", "mark_dark"):
        if (mine.get("brand") or {}).get("logo", {}).get(key):
            mine["brand"]["logo"][key] = rel(mine["brand"]["logo"][key])
    for weight, f in ((mine.get("brand") or {}).get("font") or {}).get("files", {}).items():
        mine["brand"]["font"]["files"][weight] = rel(f)
    if mine.get("formats"):
        mine["formats"] = [rel(f) for f in mine["formats"]]
    out.write_text(json.dumps(mine, indent=2, ensure_ascii=False) + "\n")
    c = out.resolve().relative_to(ROOT) if out.resolve().is_relative_to(ROOT) else out.resolve()
    print(f"Wrote {c}. Set playbook.name (and playbook.url if it will be online), then:\n"
          f"  python3 print/build_paper.py --config {c}          # the A1 sheets\n"
          f"  python3 print/build_sheets_html.py --config {c}    # fill-in versions of the sheets\n"
          f"  python3 slides/build_slides.py --config {c}        # the slides, with a timer per question\n"
          f"On the day, give Claude Code the photos; the skill reads this file's workshop (or pass --config to each ingest command).")


if __name__ == "__main__":
    main()
