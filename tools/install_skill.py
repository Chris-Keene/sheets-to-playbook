#!/usr/bin/env python3
"""Make the sheets-to-playbook skill available in every Claude Code session, not just inside this folder.

    python3 tools/install_skill.py            # writes ~/.claude/skills/sheets-to-playbook/SKILL.md
    python3 tools/install_skill.py --remove

Opening Claude Code inside the clone needs none of this: the skill in .claude/skills/ is picked up automatically.
The installed copy is the same file with this clone's location written in, so it can find the scripts from anywhere.
Run it again after pulling a new version.
"""
import argparse, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".claude" / "skills" / "sheets-to-playbook" / "SKILL.md"
DEST = Path.home() / ".claude" / "skills" / "sheets-to-playbook"
LINE = "Repo: the folder holding `ingest/ingest.py` (the current project, if Claude Code was opened in the clone)."

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--remove", action="store_true", help="delete the installed copy")
a = ap.parse_args()

if a.remove:
    if DEST.exists():
        shutil.rmtree(DEST)
        print(f"Removed {DEST}")
    else:
        print("Nothing installed.")
else:
    text = SRC.read_text()
    if LINE not in text:
        raise SystemExit(f"Couldn't find the Repo line in {SRC}: has the skill been edited? Update LINE in this script.")
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "SKILL.md").write_text(text.replace(LINE, f"Repo: `{ROOT}`."))
    print(f"Installed to {DEST / 'SKILL.md'} (repo: {ROOT}). Start a new Claude Code session to pick it up.")
