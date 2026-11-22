"""Workshop formats: the exercises (one sheet or card each) and the workshops that string them together.

    formats/exercises/<id>.json        one sheet or card: its code, its question, and the boxes people write in
    formats/workshops/<id>/
        workshop.json                  the agenda: which exercises, in what order, for how long, plus add-ons
        output.json                    what the finished page holds, and how verify checks each part
        rules.py                       (optional) checks particular to this workshop: check(data), verify(ctx)
        views.js                       the page's views, built from the shared components
        recipe.md                      how to write the page from the transcriptions (read by the writer)

The settings pick the workshop ("workshop": "round-tables") and can add folders to search ("formats": [...],
relative to the settings file), so another repository can keep its own formats beside this engine's. A folder
listed in the settings wins over the engine's own when both have an exercise or workshop with the same id.

Everything that used to name the round-table sheets directly (S1, S2, S3, SS) asks this module instead: the sheet
codes a table should have, the lists a transcription holds, the id pattern, the printed words on the paper, the
files in the kit.
"""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_FORMATS = ROOT / "formats"
VOICE = "V"   # voice notes are a source for every workshop, not an exercise


class Workshop:
    def __init__(self, data, folder, exercises):
        self.data = data
        self.id = data["id"]
        self.name = data.get("name", self.id)
        self.folder = folder
        self.group = data.get("group", "table")
        self.privacy = data.get("privacy", "public")
        self.exercises = exercises                      # agenda then add-ons, in order, each a dict
        self.output = _load_json(folder / "output.json") if (folder / "output.json").exists() else {"paths": []}
        self._rules = None

    # ------------------------------------------------------------ the exercises, by role

    def per_group(self):
        """Exercises every group fills in (sheets, in order): what `status` expects each table to have."""
        return [e for e in self.exercises if e.get("per", "group") == "group" and e.get("boxes")]

    def per_person(self):
        """Exercises each person fills in (cards), transcribed into one file for the whole room."""
        return [e for e in self.exercises if e.get("per") == "person" and e.get("boxes")]

    def by_code(self, code):
        return next((e for e in self.exercises if e.get("code") == code), None)

    def sheet_codes(self):
        return [e["code"] for e in self.per_group()]

    def sheet_names(self, capital=False):
        """Code -> how a person would name it: "Sheet 1", "side sheet". Voice notes are "V"."""
        names = {e["code"]: e.get("short", e["code"]) for e in self.per_group()}
        names[VOICE] = "voice note"
        if capital:
            names = {k: v[:1].upper() + v[1:] for k, v in names.items()}
        return names

    # ------------------------------------------------------------ what a transcription holds

    def raw_lists(self):
        """(sheet code, key) for every box that holds a list of items with ids, in order, then voice points."""
        out = []
        for e in self.per_group():
            for b in e["boxes"]:
                if b["type"] in ("list", "ranked", "row", "list+votes") and b.get("stem"):
                    out.append((e["code"], b["key"]))
        return out + [(VOICE, "points")]

    def raw_singles(self):
        """(sheet code, key) for boxes that hold one item with an id (like "the one we're tackling")."""
        return [(e["code"], b["key"]) for e in self.per_group() for b in e["boxes"] if b["type"] == "text" and b.get("stem")]

    def text_fields(self):
        """The fields an item's words can be in: "text", plus a row box's main field ("action" on the try-now sheet)."""
        out = ["text"]
        for e in self.exercises:
            for b in e.get("boxes", []):
                if b.get("text_field") and b["text_field"] not in out:
                    out.append(b["text_field"])
        return out

    def extra_fields(self):
        """Other written fields on an item, also read for names and shown to reviewers (who, needs, sticks...)."""
        out = []
        for e in self.exercises:
            for b in e.get("boxes", []):
                for f in b.get("fields", []):
                    if f["key"] not in out and f["key"] != b.get("text_field"):
                        out.append(f["key"])
        return out

    def card_sources(self):
        """(raw file, key, id prefix) for each per-person exercise: commitments.json / cards / C."""
        return [(e["raw_file"], e["key"], e["prefix"]) for e in self.per_person()]

    def id_re(self):
        """The pattern every transcribed id must match: T07.S1.challenge1, T07.V.point1, C.card12."""
        codes = "|".join(re.escape(c) for c in self.sheet_codes() + [VOICE])
        cards = "|".join(re.escape(p) + re.escape(e["stem"]) + r"\d+" for e in self.per_person() for p in [e["prefix"]])
        return re.compile(r"^(T(\d{2})\.(" + codes + r")\.[a-z]+\d*" + ("|" + cards if cards else "") + r")$")

    # ------------------------------------------------------------ the paper

    def printed(self):
        """Phrases printed on the paper kit, lower case, so the review app never mistakes a heading for writing."""
        out = []
        for e in self.exercises:
            for p in e.get("printed") or _phrases(e):
                if p not in out:
                    out.append(p)
        return out

    def kit_files(self):
        """The kit offered on the page's "Run your own" view: (folder, pattern, title, note, group), as build.py lists it."""
        out = [("slides/out", "*.html", "The slides", "Opens in any browser and works offline. Arrow keys move, T starts each question’s timer, N shows the facilitator notes.", "slides"),
               ("slides/out", "*.pdf", "The slides as a PDF", "One slide per page, without the notes.", "slides")]
        for kind in ("html", "print"):
            for e in self.exercises:
                k = e.get("kit") or (self._default_kit(e) if e.get("per", "group") == "group" and e.get("boxes") else {})
                if kind in k:
                    folder = "print/out/html" if kind == "html" else "print/out/paper"
                    out.append((folder, k[kind]["file"], k[kind].get("title", k.get("title", e.get("title", ""))), k[kind]["note"], kind))
        out.append(("print/out", "*.zip", "The whole paper kit", "All the print files in one zip.", "print"))
        return out

    # ------------------------------------------------------------ the page

    def page_items(self, data, order=None):
        """(path spec, label, owner, item) for every line on the page that verify checks, in page order.

        output.json lists the paths: "quotes[]" at the top level, or "challenges[].quotes[]" inside each challenge
        (all of a challenge's lines come together, in the order listed). `owner` is what the line belongs to, for
        people: a challenge's title, or the section's name. `order` (a list of paths) changes the order, as the
        review app does."""
        paths = self.output.get("paths", [])
        if order:
            rank = {p: i for i, p in enumerate(order)}
            paths = sorted((x for x in paths if x["path"] in rank), key=lambda x: rank[x["path"]])
        done = set()
        for spec in paths:
            whole = spec["path"]
            if "[]." in whole:
                parent = whole.split("[].", 1)[0]
                if parent in done:
                    continue
                done.add(parent)
                subs = [x for x in paths if x["path"].startswith(parent + "[].")]
                for item in data.get(parent, []):
                    for sub in subs:
                        child = sub["path"].split("[].", 1)[1][:-2] if sub["path"].endswith("[]") else sub["path"].split("[].", 1)[1]
                        for n, x in enumerate(item.get(child, []) or [], 1):
                            yield sub, sub["label"].format(parent=item.get("id", ""), n=n), item.get("title") or item.get("id", ""), x
            else:
                key = whole[:-2] if whole.endswith("[]") else whole
                for n, x in enumerate(data.get(key, []) or [], 1):
                    yield spec, spec["label"].format(n=n), spec.get("section", key), x

    def row_fields(self):
        """The fields of every row box (try-now: action, needs, sticks)."""
        return [f["key"] for e in self.exercises for b in e.get("boxes", []) if b["type"] == "row" for f in b.get("fields", [])]

    def name_fields(self):
        """The name lines on per-person cards (name, org)."""
        return [b["key"] for e in self.per_person() for b in e["boxes"] if b["type"] == "name"]

    def card_prefixes(self):
        return tuple(e["prefix"] for e in self.per_person())

    def row_box(self, code):
        """The row box on the sheet with this code, if it has one (for the review app's close-ups)."""
        e = self.by_code(code)
        return next((b for b in (e or {}).get("boxes", []) if b["type"] == "row"), None)

    def _default_kit(self, e):
        """Kit entries for a sheet that doesn't list its own: its fill-in page and its A1 poster."""
        return {"title": f"{e.get('short', e['code'])}: {e.get('title', '')}",
                "html": {"file": f"*sheet-{e['code']}*.html", "note": "Type into it, or print it on A4."},
                "print": {"file": f"*sheet-{e['code']}*.pdf", "note": f"A1 poster, one per {self.group}."}}

    # ------------------------------------------------------------ the workshop's own checks

    def rules(self):
        """The workshop's rules.py as a module (check, verify), or None."""
        if self._rules is None:
            f = self.folder / "rules.py"
            if f.exists():
                spec = importlib.util.spec_from_file_location(f"workshop_rules_{self.id.replace('-', '_')}", f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self._rules = mod
            else:
                self._rules = False
        return self._rules or None

    def views_js(self):
        f = self.folder / "views.js"
        return f.read_text() if f.exists() else ""

    def views_css(self):
        f = self.folder / "views.css"
        return f.read_text() if f.exists() else ""


def search_path(cfg=None):
    """Folders to look for formats in: the settings' own first, then the engine's."""
    dirs = []
    if cfg:
        base = Path(cfg.get("_dir") or ROOT)
        for d in cfg.get("formats") or []:
            p = Path(d) if Path(d).is_absolute() else base / d
            if p.exists():
                dirs.append(p)
    return dirs + [ENGINE_FORMATS]


def find(kind, name, cfg=None):
    """formats/exercises/<name>.json or formats/workshops/<name>/, from the first folder that has it."""
    for d in search_path(cfg):
        p = d / kind / (name + ".json" if kind == "exercises" else name)
        if p.exists():
            return p
    raise SystemExit(f"No {kind[:-1]} called {name!r} in: " + ", ".join(str(d) for d in search_path(cfg)))


def load(cfg=None, workshop=None):
    """The workshop the settings name (default round-tables), with its exercises resolved."""
    name = workshop or (cfg or {}).get("workshop") or "round-tables"
    folder = find("workshops", name, cfg)
    data = _load_json(folder / "workshop.json")
    exercises = []
    agenda = data.get("agenda", [])
    for i, item in enumerate(agenda + [{"exercise": a} if isinstance(a, str) else a for a in data.get("addons", [])], 1):
        e = _load_json(find("exercises", item["exercise"], cfg))
        if i <= len(agenda):
            # an exercise's place in the agenda names it on the paper, unless it names itself: Sheet 2, Question 2, S2
            e.setdefault("code", f"S{i}")
            e.setdefault("short", f"Sheet {i}")
            e.setdefault("label", f"Question {i}")
        e = dict(e, **{k: v for k, v in item.items() if k not in ("exercise",)})   # the agenda can override labels, minutes...
        exercises.append(e)
    return Workshop(data, folder, exercises)


def available(cfg=None):
    """Every workshop on the search path: {id: name}."""
    out = {}
    for d in reversed(search_path(cfg)):
        for w in sorted((d / "workshops").glob("*/workshop.json")) if (d / "workshops").exists() else []:
            out[w.parent.name] = _load_json(w).get("name", w.parent.name)
    return out


def _load_json(p):
    return json.loads(Path(p).read_text())


def _phrases(e):
    """Printed phrases for an exercise that doesn't list its own: its title, labels, hints and options, split at
    sentence breaks (OCR reads the paper a line at a time, so short phrases match better than whole sentences)."""
    texts = [e.get("title", ""), e.get("label", "")]
    for b in e.get("boxes", []):
        texts += [b.get("label", ""), b.get("hint", "")] + list(b.get("options", []))
        texts += [f.get("label", "") for f in b.get("fields", [])]
        for t in (b.get("ticks") or {}).get("options", []):
            texts.append(t[1] if isinstance(t, list) else t)
    out = []
    for t in texts:
        for part in re.split(r"(?<=[.?!:])\s+|…", t.lower()):
            part = part.strip(" .:")
            if len(part) > 3 and part not in out:
                out.append(part)
    return out
