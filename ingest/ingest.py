#!/usr/bin/env python3
"""Turn a folder of worksheet photos (and any voice notes) into a draft playbook.

The mechanical steps live here. Reading handwriting and writing the playbook are done by Claude Code, following
the sheets-to-playbook skill (.claude/skills/sheets-to-playbook/SKILL.md) and ingest/RAW_FORMAT.md.

    python3 ingest/ingest.py prepare <folder>             # new run: normalise photos + audio, contact sheets, tiles
    python3 ingest/ingest.py prepare <folder> --into <run> # a later batch joins the same run
    python3 ingest/ingest.py transcribe                   # Whisper, locally, on any voice notes (optional)
    python3 ingest/ingest.py status                       # coverage and blur, once labels.json exists
    python3 ingest/ingest.py brief [--table 7]            # the workshop's sheets, ids and file shape, for the readers
    python3 ingest/ingest.py verify [--links]             # raw files + session.json: traceability, verbatim quotes, gaps, names
    python3 ingest/ingest.py review                       # review.html: every line next to its photos
    python3 ingest/ingest.py draft                        # the draft playbook, in the run folder
    python3 ingest/ingest.py publish [--links]            # final checks, then build playbook/index.html

Every command after `prepare` works on runs/latest unless --run is given. --config <file> picks a settings file
other than playbook.config.json; its "workshop" setting says which sheets to expect (round tables unless it
names another, see build/formats.py). History: CHANGELOG.md.
"""
import argparse, concurrent.futures, difflib, html, json, re, shutil, subprocess, sys, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
sys.path.insert(0, str(ROOT / "build"))
import config as _config  # noqa: E402
import formats  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff"}
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".amr", ".caf", ".aif", ".aiff", ".flac", ".mp4", ".mov", ".3gp"}
VIEW_EDGE = 1568      # roughly what a vision model sees of a whole image
WORK_EDGE = 3000      # kept for tiles, so small handwriting stays readable
WHISPER_MODEL = "small.en"   # downloaded to ~/.cache/whisper on first use; works offline after that
LOW_RES_EDGE = 2000   # a phone original is 3000 to 4000 px; WhatsApp and "small" exports come out around 1600

NUMBER_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                           "thirteen fourteen fifteen sixteen".split())}
# Whisper writes what it hears: "Table two" came back as "table too" in testing
NUMBER_WORDS.update({"too": 2, "to": 2, "for": 4, "fore": 4, "won": 1, "ate": 8})


# ---------------------------------------------------------------- helpers

def run_dir(arg):
    if arg:
        p = Path(arg).expanduser().resolve()
    else:
        p = (RUNS / "latest").resolve()
    if not (p / "manifest.json").exists():
        sys.exit(f"No run found at {p}. Start one with: ingest.py prepare <folder>")
    return p


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def save(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def tag(prefix, n):
    return f"{prefix}{n:03d}"


# ---------------------------------------------------------------- prepare

def prepare(args):
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    inbox = Path(args.inbox).expanduser().resolve()
    if not inbox.is_dir():
        sys.exit(f"{inbox} is not a folder")
    manifest = None
    if getattr(args, "into", None):
        # a second batch of photos joins an existing run: ids carry on, labels and raw files are kept
        into = Path(args.into).expanduser()
        run = run_dir(str(into if into.exists() else RUNS / args.into))
        manifest = load(run / "manifest.json")
        stamp = manifest["created"]
    else:
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        run = RUNS / stamp
    for sub in ("photos", "view", "tiles", "contact", "audio", "transcripts", "raw"):
        (run / sub).mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in inbox.rglob("*") if p.is_file() and not p.name.startswith("."))
    photos, audio, ignored = [], [], []
    for f in files:
        ext = f.suffix.lower()
        if ext in IMAGE_EXT:
            photos.append(f)
        elif ext in AUDIO_EXT:
            audio.append(f)
        else:
            ignored.append(str(f.relative_to(inbox)))

    skipped = []
    if manifest is None:
        manifest = {"created": stamp, "inbox": str(inbox), "photos": [], "audio": [], "ignored": ignored}
    else:
        # a re-download of the whole Drive folder would bring the first batch again: skip files already in the run
        seen = {Path(x["source"]).name for x in manifest["photos"] + manifest["audio"]}
        skipped = [f.name for f in photos + audio if f.name in seen]
        photos = [f for f in photos if f.name not in seen]
        audio = [f for f in audio if f.name not in seen]
        manifest.setdefault("batches", [manifest["inbox"]]).append(str(inbox))
        manifest["ignored"] += ignored
    first_new = len(manifest["photos"])

    for i, src in enumerate(photos, first_new + 1):
        pid = tag("P", i)
        work = run / "photos" / f"{pid}.jpg"
        if src.suffix.lower() in (".heic", ".heif"):
            # Pillow can't open HEIC on its own: pillow-heif can (any platform), and so can macOS's sips
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
                im = Image.open(src)
            except ImportError:
                if not shutil.which("sips"):
                    sys.exit(f"{src.name} is a HEIC photo: pip install pillow-heif to read it (or convert it to JPEG first).")
                subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(work)],
                               check=True, capture_output=True)
                im = Image.open(work)
        else:
            im = Image.open(src)
        taken = None
        try:
            taken = im.getexif().get_ifd(0x8769).get(0x9003) or im.getexif().get(0x0132)
        except Exception:
            pass
        im = ImageOps.exif_transpose(im).convert("RGB")   # phones store sideways pixels plus a rotate flag
        original = list(im.size)
        im.thumbnail((WORK_EDGE, WORK_EDGE))
        im.save(work, quality=90)
        view = im.copy()
        view.thumbnail((VIEW_EDGE, VIEW_EDGE))
        view.save(run / "view" / f"{pid}.jpg", quality=88)
        tiles = make_tiles(im, run / "tiles", pid)
        manifest["photos"].append({"id": pid, "source": str(src.relative_to(inbox)), "taken": taken,
                                   "size": list(im.size), "original": original, "low_res": max(original) < LOW_RES_EDGE,
                                   "sharpness": round(sharpness(im), 1), "brightness": round(brightness(im)), "tiles": tiles}
                                  | ({"inbox": str(inbox)} if first_new else {}))

    # Blur is relative: a photo much softer than the rest of the batch is the one to retake
    scores = sorted(p["sharpness"] for p in manifest["photos"])
    median = scores[len(scores) // 2] if scores else 0
    for p in manifest["photos"]:
        p["blurry"] = bool(median) and p["sharpness"] < 0.4 * median
    # Dark is relative too. The stress test read dim photos fine, so this is a nudge, not a retake
    lights = sorted(p["brightness"] for p in manifest["photos"])
    mid = lights[len(lights) // 2] if lights else 0
    for p in manifest["photos"]:
        p["dark"] = bool(mid) and p["brightness"] < 0.65 * mid

    for i, src in enumerate(audio, len(manifest["audio"]) + 1):
        aid = tag("A", i)
        wav = run / "audio" / f"{aid}.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)],
                           capture_output=True, text=True)
        entry = {"id": aid, "source": str(src.relative_to(inbox))}
        if r.returncode:
            entry["error"] = r.stderr.strip()[-300:]
        else:
            entry["seconds"] = round(duration(wav), 1)
        manifest["audio"].append(entry)

    contact_sheets(run, manifest)
    save(run / "manifest.json", manifest)
    if not (run / "labels.json").exists():
        save(run / "labels.json", {"photos": {}, "audio": {}})
    latest = RUNS / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(run.name)

    blurry = [p["id"] for p in manifest["photos"][first_new:] if p["blurry"]]
    low = [p["id"] for p in manifest["photos"][first_new:] if p["low_res"]]
    print(f"Run: {run}")
    if first_new:
        new = [x["id"] for x in manifest["photos"][first_new:]]
        print(f"  Added {len(new)} photos" + (f" ({new[0]} to {new[-1]})" if new else "") + f" to the {first_new} already here; labels and raw files kept")
        if skipped:
            print(f"  Skipped {len(skipped)} already in this run: {', '.join(skipped[:8])}{' ...' if len(skipped) > 8 else ''}")
    else:
        print(f"  {len(photos)} photos, {len(audio)} voice notes, {len(ignored)} other files ignored")
    if blurry:
        print(f"  Possibly blurry: {', '.join(blurry)} (check the contact sheets)")
    if low:
        print(f"  Low resolution, so no close-up tiles: {', '.join(low)} (sent over WhatsApp? Fine if the writing is big; ask for the original if it's small)")
    bad_audio = [a["id"] for a in manifest["audio"] if "error" in a]
    if bad_audio:
        print(f"  Audio that wouldn't convert: {', '.join(bad_audio)}")
    print(f"  Contact sheets: {run / 'contact'}")


def make_tiles(im, out, pid):
    """2x2 overlapping crops, so a reader can zoom into dense handwriting."""
    w, h = im.size
    if max(w, h) < 1800:
        return []
    ox, oy = int(w * 0.12), int(h * 0.12)
    names = []
    for row in range(2):
        for col in range(2):
            x0 = 0 if col == 0 else w // 2 - ox
            y0 = 0 if row == 0 else h // 2 - oy
            box = (x0, y0, min(w, x0 + w // 2 + ox), min(h, y0 + h // 2 + oy))
            name = f"{pid}-{'ab'[row]}{col + 1}.jpg"   # a1 top left ... b2 bottom right
            im.crop(box).save(out / name, quality=88)
            names.append(name)
    return names


def sharpness(im):
    """Variance of the Laplacian on a downsized greyscale copy, relative to the photo's own contrast: low means
    soft or shaken. Without the contrast step a dim but sharp photo scores as blurry (seen in the handwriting stress test)."""
    import numpy as np
    g = im.convert("L").copy()
    g.thumbnail((1200, 1200))
    a = np.asarray(g, dtype=np.float32)
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    spread = max(float(np.percentile(a, 95) - np.percentile(a, 5)), 1.0)
    return float(lap.var()) / spread ** 2 * 1000


def brightness(im):
    import numpy as np
    g = im.convert("L").copy()
    g.thumbnail((600, 600))
    return float(np.asarray(g, dtype=np.float32).mean())


def duration(wav):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def contact_sheets(run, manifest):
    from PIL import Image, ImageDraw, ImageFont
    cols, rows, cell = 4, 3, 480
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    per = cols * rows
    items = manifest["photos"]
    for page in range(0, len(items), per):
        sheet = Image.new("RGB", (cols * cell, rows * (cell + 40)), "white")
        d = ImageDraw.Draw(sheet)
        for k, p in enumerate(items[page:page + per]):
            im = Image.open(run / "view" / f"{p['id']}.jpg")
            im.thumbnail((cell - 12, cell - 12))
            x, y = (k % cols) * cell, (k // cols) * (cell + 40)
            sheet.paste(im, (x + (cell - im.width) // 2, y + 6))
            tags = [t for t, on in (("BLURRY?", p.get("blurry")), ("LOW-RES", p.get("low_res")), ("DARK", p.get("dark"))) if on]
            d.text((x + 8, y + cell + 6), "  ".join([p["id"]] + tags), fill="#b00020" if tags else "black", font=font)
        sheet.save(run / "contact" / f"sheet-{page // per + 1:02d}.jpg", quality=85)


# ---------------------------------------------------------------- transcribe

def transcribe(args):
    run = run_dir(args.run)
    m = load(run / "manifest.json")
    todo = [a for a in m["audio"] if "error" not in a and (args.force or not (run / "transcripts" / f"{a['id']}.txt").exists())]
    if not shutil.which("whisper"):
        sys.exit("Whisper isn't installed: pip install openai-whisper (or brew install openai-whisper on a Mac), plus ffmpeg.")

    def one(a):
        wav = run / "audio" / f"{a['id']}.wav"
        r = subprocess.run(["whisper", str(wav), "--model", args.model, "--language", "en", "--fp16", "False",
                            "--output_format", "json", "--output_dir", str(run / "transcripts")],
                           capture_output=True, text=True)
        return a["id"], r.returncode, r.stderr[-400:]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for aid, code, err in ex.map(one, todo):
            print(f"  {aid}: {'ok' if code == 0 else 'FAILED ' + err}")

    labels = load(run / "labels.json", {"photos": {}, "audio": {}})
    for a in m["audio"]:
        j = load(run / "transcripts" / f"{a['id']}.json")
        if not j:
            continue
        text = j.get("text", "").strip()
        (run / "transcripts" / f"{a['id']}.txt").write_text(text + "\n")
        a["table_guess"] = table_from_speech(text)
        a["words"] = len(text.split())
        # leads are asked to start with their table number; pre-fill it, Claude confirms
        if a["table_guess"] and a["id"] not in labels["audio"]:
            labels["audio"][a["id"]] = {"table": a["table_guess"], "by": "speech"}
    save(run / "manifest.json", m)
    save(run / "labels.json", labels)
    for a in m["audio"]:
        print(f"  {a['id']} {a['source']}: table {a.get('table_guess') or '?'}, {a.get('words', 0)} words")


def table_from_speech(text):
    head = " ".join(re.findall(r"[a-z0-9]+", text.lower())[:12])
    mm = re.search(r"\btable (?:number )?(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\b", head)
    if not mm:
        return None
    v = mm.group(1)
    if v in ("too", "to", "for", "fore", "won", "ate") and not head.startswith(("table", "hi table", "this is table")):
        return None   # a sound-alike only counts when the note opens with "Table ..."
    return int(v) if v.isdigit() else NUMBER_WORDS[v]


# ---------------------------------------------------------------- status

def label_sheets(lab):
    """A photo label's sheet codes as a list: "sheet" may be one code or a list when one photo shows two sheets."""
    sh = lab.get("sheet")
    return [s for s in (sh if isinstance(sh, list) else [sh]) if s]


def workshop(args=None):
    """The workshop the settings name: its sheets, lists and checks (build/formats.py)."""
    return formats.load(_config.load(getattr(args, "config", None)))


def status(args):
    run = run_dir(args.run)
    W = workshop(args)
    SHEETS, SHEET_NAMES = W.sheet_codes(), W.sheet_names()
    m = load(run / "manifest.json")
    labels = load(run / "labels.json", {"photos": {}, "audio": {}})
    tables = args.tables
    grid = {t: {s: [] for s in SHEETS} for t in range(1, tables + 1)}
    unlabelled, stubs, other = [], [], []
    for p in m["photos"]:
        lab = labels["photos"].get(p["id"])
        if not lab:
            unlabelled.append(p["id"])
        elif lab.get("kind") == "stubs":
            stubs.append(p["id"])
        elif lab.get("kind") == "other" or not lab.get("table"):
            other.append(p["id"])
        else:
            # one photo can hold two sheets pinned side by side: label it "sheet": ["S2", "S3"] (round 3 stress test)
            for sh in label_sheets(lab):
                grid.setdefault(lab["table"], {s: [] for s in SHEETS}).setdefault(sh, []).append(p)
    voice = {}
    for aid, lab in labels["audio"].items():
        voice.setdefault(lab.get("table"), []).append(aid)

    has_audio = bool(m.get("audio"))   # voice notes are optional: many sessions don't collect them
    print("Table  " + "  ".join(f"{s:<9}" for s in SHEETS) + ("  Voice" if has_audio else ""))
    gaps, empty, notes = [], [], []
    for t in sorted(grid):
        if not any(grid[t].values()) and not voice.get(t):
            # nothing at all usually means the table wasn't used; one line, not five
            empty.append(t)
            print(f"T{t:02d}    nothing yet")
            continue
        cells = []
        for s in SHEETS:
            ps = grid[t][s]
            sharp = [p for p in ps if not p["blurry"]]
            if not ps:
                cells.append("MISSING"); gaps.append(f"T{t:02d} {SHEET_NAMES[s]}: no photo")
            elif not sharp:
                cells.append("BLURRY"); gaps.append(f"T{t:02d} {SHEET_NAMES[s]}: only blurry photos ({', '.join(p['id'] for p in ps)})")
            else:
                cells.append(f"ok x{len(ps)}")
                if len(ps) > 1:
                    # seen with real photos: two different S1 sheets both said "22" and this line read "ok x2"
                    notes.append(f"T{t:02d} {SHEET_NAMES[s]}: {len(ps)} photos ({', '.join(p['id'] for p in ps)}). Fine if they're "
                                 "close-ups of one sheet; if they're different sheets, two tables used the same number (see the skill)")
                if all(p.get("low_res") for p in sharp):
                    notes.append(f"T{t:02d} {SHEET_NAMES[s]}: only a low-resolution copy ({', '.join(p['id'] for p in sharp)}); fine if the writing is big")
        v = voice.get(t, [])
        if has_audio and not v:
            gaps.append(f"T{t:02d}: no voice note")
        print(f"T{t:02d}    " + "  ".join(f"{c:<9}" for c in cells) + (f"  {'ok' if v else '-'}" if has_audio else ""))
    print(f"\nCard stub photos: {len(stubs)}   Not a sheet: {len(other)}   Not labelled yet: {len(unlabelled)}")
    if unlabelled:
        print("  Label these in labels.json: " + ", ".join(unlabelled))
    if empty:
        gaps.append("Nothing at all from table(s) " + ", ".join(str(t) for t in empty) + " (fine if they weren't used)")
    if gaps:
        print("\nRetake or chase while the sheets are still up:")
        for g in gaps:
            print("  - " + g)
    if notes:
        print("\nWorth a look, not urgent:")
        for n in notes:
            print("  - " + n)
    (run / "status.txt").write_text("\n".join(gaps) + "\n")


# ---------------------------------------------------------------- raw items

def raw_items(run, W=None):
    """Every transcribed item across all raw files, keyed by id. W is the workshop (default: from the settings)."""
    W = W or workshop()
    id_re, text_fields = W.id_re(), W.text_fields()
    items, problems = {}, []
    for f in sorted((run / "raw").glob("T*.json")):
        d = load(f)
        t = d.get("table")
        if not isinstance(t, int):
            problems.append(f"{f.name}: 'table' must be a number"); continue
        prefix = f"T{t:02d}."
        for sheet, key in W.raw_lists():
            for it in (d.get(sheet) or {}).get(key, []) or []:
                add_item(items, problems, f.name, it, prefix, f"{sheet}.{key}", id_re, text_fields)
        for sheet, key in W.raw_singles():
            one = (d.get(sheet) or {}).get(key)
            if one:
                add_item(items, problems, f.name, one, prefix, f"{sheet}.{key}", id_re, text_fields)
    for raw_file, key, prefix in W.card_sources():
        c = load(run / "raw" / raw_file)
        if c:
            for it in c.get(key, []):
                add_item(items, problems, raw_file, it, prefix, "card", id_re, text_fields)
    return items, problems


def add_item(items, problems, fname, it, prefix, kind, id_re, text_fields=("text",)):
    iid = it.get("id", "")
    if not id_re.match(iid) or not iid.startswith(prefix):
        problems.append(f"{fname}: bad id {iid!r} (expected {prefix}...)")
        return
    if iid in items:
        problems.append(f"{fname}: duplicate id {iid}")
    text = next((it.get(f) for f in text_fields if it.get(f)), "")
    if not text.strip():
        problems.append(f"{fname}: {iid} has no text")
    items[iid] = dict(it, _kind=kind, _file=fname)


def norm(s):
    s = re.sub(r"\[\?([^\]]*)\]", r"\1", s or "")
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("’", "'")).strip()


def similar(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b:
        return 1.0
    # compare against the best same-length window of the longer text
    if len(b) > len(a) * 1.3:
        words_b, n = b.split(), len(a.split())
        return max((difflib.SequenceMatcher(None, a, " ".join(words_b[i:i + n])).ratio()
                    for i in range(max(1, len(words_b) - n + 1))), default=0.0)
    return difflib.SequenceMatcher(None, a, b).ratio()


def srcs(x):
    s = x.get("src") if isinstance(x, dict) else None
    if not s:
        return []
    return s if isinstance(s, list) else [s]


# ---------------------------------------------------------------- verify

def page_items(data, W, order=None):
    """Every checked line on the page: see formats.Workshop.page_items."""
    return W.page_items(data, order)


class Checks:
    """What a workshop's rules.verify() gets: the page, the transcribed items, and somewhere to report."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def verify(args):
    run = run_dir(args.run)
    W = workshop(args)
    errors, warnings = [], []
    items, problems = raw_items(run, W)
    errors += problems
    transcripts = {p.stem: p.read_text() for p in (run / "transcripts").glob("*.txt")}

    data_path = Path(args.data) if args.data else run / "session.json"
    data = load(data_path)
    used = set()
    if data is None:
        warnings.append(f"No {data_path.name} yet: checked the raw files only")
    else:
        from build import check as build_check
        try:
            build_check(data, W)
        except SystemExit as e:
            errors.append(str(e))
        status_ = data["meta"].get("status")

        def walk(where, x, need_src=True, verbatim=None, min_ratio=0.86):
            ids = srcs(x)
            for i in ids:
                if i not in items:
                    errors.append(f"{where}: src {i} doesn't exist in the raw files")
                used.add(i)
            if need_src and not ids:
                (errors if status_ == "final" else warnings).append(f"{where}: no src, so it can't be traced to a sheet")
            if verbatim and ids:
                pool = [next((items[i].get(f) for f in W.text_fields() if items[i].get(f)), "") for i in ids if i in items]
                pool += [items[i].get("excerpt", "") for i in ids if i in items]
                pool += [transcripts.get(a, "") for a in transcripts]
                best = max((similar(verbatim, p) for p in pool if p), default=0)
                if best < min_ratio:
                    errors.append(f"{where}: text isn't close to what was written or said ({best:.0%} match): \"{verbatim[:70]}\"")
            text = json.dumps(x, ensure_ascii=False)
            if re.search(r"\[\?|\[illegible\]|\[unclear\]", text):
                warnings.append(f"{where}: still contains an unclear-reading marker")

        # every line the workshop's output.json lists: traced to a sheet, and word for word where it must be
        for spec, where, _owner, x in page_items(data, W):
            policy = spec.get("policy", "trace")
            plain = not isinstance(x, dict)
            need = policy != "optional" and not (plain and spec.get("strings_ok"))
            verbatim = x.get(spec.get("field", "text")) if policy == "verbatim" and not plain else None
            walk(where, {} if plain else x, need_src=need, verbatim=verbatim, min_ratio=spec.get("min", 0.86))

        # the checks particular to this workshop (round tables: themes match Sheet 1, one page per table, card names)
        rules = W.rules()
        if rules and hasattr(rules, "verify"):
            rules.verify(Checks(data=data, items=items, used=used, errors=errors, warnings=warnings, status=status_,
                                similar=similar, srcs=srcs, workshop=W))

        everything = json.dumps(data, ensure_ascii=False)
        for pat, what in [(r"[\w.+-]+@[\w-]+(?:\.[\w.]+)?", "email address"), (r"(?<![\w.+-])@\w{2,}", "social handle"),
                          (r"\b(?:\+44|0)\s?\d{3,4}\s?\d{3}\s?\d{3,4}\b", "phone number")]:
            for hit in set(re.findall(pat, everything)):
                # a private workshop's notes go to the people who were there, so these are worth a look, not a block
                (warnings if W.privacy == "private" else errors).append(f"Personal detail? {what}: {hit}")
        # Likely names: capitalised words in the middle of a raw sentence ("…said Sarah from Ofcom…").
        # Any that reach the page get flagged even if nobody put them on the scrub list.
        allow = {"I", "IT", "AI", "UK", "W3C", "WAI", "WCAG", "GOV", "ESG", "QA", "UX", "UI", "PM", "CEO", "CFO", "CTO",
                 "HR", "SEO", "PDF", "API", "OK"} | set("Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March "
                 "April May June July August September October November December".split())
        allow |= {w for w in _config.load(getattr(args, "config", None))["org"]["short"].split() if w}   # the org's own short name isn't a person
        candidates = set()
        fields = ["text", "excerpt"] + [f for f in W.text_fields() + W.extra_fields() if f != "text"]
        sources = [it.get(k, "") for it in items.values() for k in fields]
        sources += list(transcripts.values())
        for src_text in sources:
            for sentence in re.split(r"(?<=[.!?])\s+|\n", src_text or ""):
                words = re.findall(r"[A-Za-z][A-Za-z0-9'&.-]*", sentence)
                for w in words[1:]:
                    w = w.strip(".'")
                    if re.match(r"^[A-Z][a-zA-Z0-9&-]+$", w) and w not in allow:
                        candidates.add(w)
        page_text = " ".join(str(v) for v in json_strings(data))
        ok_file = run / "names-ok.txt"   # words a reviewer has confirmed aren't names, one per line
        ok_words = {l.strip() for l in ok_file.read_text().splitlines()} if ok_file.exists() else set()
        if W.privacy == "private":
            candidates = set()   # names are allowed in a private workshop's notes (an action's owner is a person)
        for w in sorted(candidates - ok_words):
            if re.search(r"\b" + re.escape(w) + r"\b", page_text):
                # a heuristic, so a warning while drafting; publishing needs it gone or listed in names-ok.txt
                (errors if status_ == "final" else warnings).append(f"Possible name on the page: \"{w}\" (capitalised mid-sentence in the raw notes); check it's not a person or organisation")
        names = run / "names-to-scrub.txt"
        if names.exists():
            for n in [l.strip() for l in names.read_text().splitlines() if l.strip() and not l.startswith("#")]:
                if re.search(r"\b" + re.escape(n) + r"\b", everything, re.I):
                    errors.append(f"Name or organisation on the scrub list appears: {n}")

        if args.links:
            for spec, _where, owner, r in page_items(data, W):
                if not spec.get("links") or not isinstance(r, dict) or not r.get("url"):
                    continue   # named without an address: listed as text, nothing to check
                ok, why = link_ok(r.get("url", ""))
                if not ok:
                    warnings.append(f"{spec.get('owner', owner)}: resource link {r.get('url')} {why}")

    skip = set(W.output.get("not_on_page", []))   # items that shape the page without being quoted (Sheet 1 feeds the themes)
    unused = sorted(i for i, it in items.items() if i not in used and it["_kind"] not in skip)
    if data is not None and unused:
        warnings.append(f"{len(unused)} transcribed items aren't used anywhere (fine if merged or off-topic): " + ", ".join(unused))

    report = {"errors": errors, "warnings": warnings, "raw_items": len(items), "used": len(used), "unused": unused}
    save(run / "verify.json", report)
    print(f"Raw items: {len(items)}   used in the playbook: {len(used)}")
    for e in errors:
        print("ERROR   " + e)
    for w in warnings:
        print("WARNING " + w)
    print("Clean." if not errors and not warnings else f"{len(errors)} errors, {len(warnings)} warnings (saved to verify.json)")
    if errors:
        sys.exit(1)


def json_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in ("src", "id", "url", "theme", "name", "org"):   # name/org are checked against the card instead
                yield from json_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from json_strings(v)


def link_ok(url):
    if not re.match(r"^https?://", url or ""):
        return False, "isn't a web address"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 sheets-to-playbook link check"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status < 400, f"returned {r.status}"
    except Exception as e:
        return False, f"failed: {e}"[:120]


# ---------------------------------------------------------------- review

def review(args):
    run = run_dir(args.run)
    m = load(run / "manifest.json")
    labels = load(run / "labels.json", {"photos": {}, "audio": {}})
    W = workshop(args)
    SHEET_NAMES = W.sheet_names()
    items, _ = raw_items(run, W)
    data = load(run / "session.json")
    rep = load(run / "verify.json", {"errors": [], "warnings": []})
    where_used = {}
    if data:
        for _spec, _where, owner, x in page_items(data, W):
            for s in srcs(x):
                where_used.setdefault(s, []).append(owner)
    roles = W.output.get("roles", {})
    row_fields, name_fields = W.row_fields(), W.name_fields()
    photos_by_table = {}
    for pid, lab in labels["photos"].items():
        photos_by_table.setdefault(lab.get("table") or lab.get("kind", "other"), []).append((pid, lab))
    e = html.escape

    def item_rows(prefix):
        rows = []
        for iid in sorted(i for i in items if i.startswith(prefix)):
            it = items[iid]
            txt = it.get("text") or " / ".join(filter(None, [it.get(f) for f in row_fields]))
            card_who = " · ".join(filter(None, [it.get(f) for f in name_fields]))
            extra = it.get("who") or it.get("url") or (f"Name and organisation lines: {card_who}" if card_who else "")
            used = where_used.get(iid)
            # some items shape the page without per-line sources (round tables: Sheet 1 feeds the themes and titles)
            role = roles.get(it["_kind"])
            unclear = "[?" in txt or "[illegible]" in txt
            rows.append(f'<tr class="{"unclear" if unclear else ""}"><th scope="row">{e(iid)}</th><td>{e(txt)}'
                        f'{"<br><small>" + e(extra) + "</small>" if extra else ""}</td>'
                        f'<td>{e(", ".join(sorted(set(used)))) if used else (e(role) if role else "<span class=unused>not used</span>")}</td></tr>')
        return "".join(rows)

    def reader_flags(raw):
        """The reader's unclear list and notes. Card files have them too, and the cards section used to drop both."""
        unclear = "".join(f"<li><b>{e(u.get('id', ''))}</b> ({e(u.get('photo', ''))}): {e(u.get('note', ''))}</li>" for u in raw.get("unclear", []))
        # readers explain their judgement calls here, so the reviewer needs to see them
        notes_html = f"<details open><summary>Reader's notes</summary><p>{e(raw['notes'])}</p></details>" if raw.get("notes") else ""
        return ("<h3>Flagged by the reader</h3><ul class=flag>" + unclear + "</ul>" if unclear else ""), notes_html

    sections = []
    tables = sorted({int(i[1:3]) for i in items if i.startswith("T")} | {k for k in photos_by_table if isinstance(k, int)})
    for t in tables:
        raw = load(run / "raw" / f"T{t:02d}.json", {})
        ph = "".join(f'<a href="photos/{pid}.jpg"><img src="view/{pid}.jpg" alt="{pid}: {e(" and ".join(SHEET_NAMES.get(sh, sh) for sh in label_sheets(lab)))}" loading="lazy"><span>{pid} {e(" + ".join(label_sheets(lab)))}</span></a>'
                     for pid, lab in sorted(photos_by_table.get(t, [])))
        aud = [aid for aid, lab in labels["audio"].items() if lab.get("table") == t]
        voice = "".join(f'<details><summary>Voice note {aid}</summary><p>{e((run / "transcripts" / f"{aid}.txt").read_text() if (run / "transcripts" / f"{aid}.txt").exists() else "(not transcribed)")}</p></details>' for aid in aud)
        flagged, notes_html = reader_flags(raw)
        room_html = ""
        for ex in W.per_group():
            for b in ex["boxes"]:
                if b["type"] != "tally":
                    continue
                room = (raw.get(ex["code"]) or {}).get(b["key"]) or {}
                tally = ", ".join(f"{k} {v}" for k, v in (room.get("tally") or {}).items() if v)
                line = (b.get("text_line") or "").lower()
                room_html += (f"<p><b>{e(b.get('review_label') or b['label'].rstrip('?'))}:</b> {e(tally or 'no tally')}"
                              f"{'; ' + e(line) + ': ' + e(room['countries']) if room.get('countries') and line else ''}</p>") if room else ""
        sections.append(f'<section><h2>Table {t}</h2><div class="photos">{ph or "<p>No photos labelled</p>"}</div>{voice}'
                        f'{flagged}{room_html}{notes_html}'
                        f'<table><thead><tr><th>Item</th><th>Transcribed</th><th>Used on</th></tr></thead><tbody>{item_rows(f"T{t:02d}.")}</tbody></table></section>')
    stub_ph = "".join(f'<a href="photos/{pid}.jpg"><img src="view/{pid}.jpg" alt="{pid}: card stubs" loading="lazy"><span>{pid}</span></a>' for pid, _ in photos_by_table.get("stubs", []))
    for ex in W.per_person():
        card_flags, card_notes = reader_flags(load(run / "raw" / ex["raw_file"], {}))
        title = ex.get("review_title") or (ex.get("short", "cards")[:1].upper() + ex.get("short", "cards")[1:] + "s")
        sections.append(f'<section><h2>{e(title)}</h2><div class="photos">{stub_ph}</div>{card_flags}{card_notes}<table><thead><tr><th>Item</th><th>Transcribed</th><th>Used on</th></tr></thead><tbody>{item_rows(ex["prefix"])}</tbody></table></section>')
    note = (data or {}).get("meta", {}).get("banner")
    banner = f'<p class="note-banner"><b>{e(note[0])}</b> {e(note[1])}</p>' if note else ""
    findings = "".join(f'<li class="err">{e(x)}</li>' for x in rep.get("errors", [])) + "".join(f"<li>{e(x)}</li>" for x in rep.get("warnings", []))
    page = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Playbook review</title><style>
body{{font:15px/1.5 -apple-system,Segoe UI,Arial,sans-serif;margin:0;padding:24px 20px;background:#fbf9fe;color:#1d1326}}
main{{max-width:1100px;margin:auto}} h1{{font-size:1.6rem;margin:0 0 4px}} h2{{margin:36px 0 10px;border-top:2px solid #57258c;padding-top:14px}}
.photos{{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}} .photos a{{display:grid;gap:2px;text-decoration:none;color:#57258c;font-size:.8rem;font-weight:600}}
.photos img{{width:150px;height:200px;object-fit:contain;border:1px solid #d9cfe6;border-radius:4px;background:#e9e5ef}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-top:10px}} th,td{{text-align:left;vertical-align:top;padding:7px 10px;border-bottom:1px solid #e2d9ee}}
thead th{{font-size:.8rem;color:#5b5168;text-transform:uppercase;letter-spacing:.04em}} tbody th{{font-weight:600;white-space:nowrap;font-size:.85rem}}
tr.unclear td{{background:#fff4cc}} .unused{{color:#9b2335;font-weight:600}} .err{{color:#9b2335;font-weight:600}}
.flag{{list-style:none;padding:0;display:grid;gap:6px}} .flag li{{background:#fff4cc;padding:8px 12px;border-radius:6px}} details{{margin:6px 0}} summary{{cursor:pointer;font-weight:600;color:#57258c}}
:focus-visible{{outline:3px solid #57258c;outline-offset:2px}} .note-banner{{background:#ffd35d;color:#1d1326;padding:12px 16px;border-radius:8px}}
</style></head><body><main><h1>Playbook review</h1>{banner}<p>Run {e(m['created'])}. Every transcribed item, the photo it came from, and where it's used in the draft. Yellow rows have words the reader wasn't sure of.</p>
<h2>Checks</h2><ul>{findings or "<li>No problems found.</li>"}</ul>{"".join(sections)}</main></body></html>"""
    (run / "review.html").write_text(page)
    print(run / "review.html")


# ---------------------------------------------------------------- brief

def brief_text(W, table=7):
    """The workshop's sheets for a reader: codes, headings, boxes, ids and the raw file's shape (Markdown)."""
    t = f"T{table:02d}"
    out = [f"# Reading the sheets: {W.name}", "",
           "What's on this workshop's paper, generated from its format files. Read it with ingest/RAW_FORMAT.md, which "
           f"holds the rules for every workshop. Examples use {W.group} {table}.", ""]
    example = {"table": table, "photos": ["P012", "P013"], "audio": []}
    for e in W.per_group():
        out.append(f"## {e['code']}: {e.get('title', '')}")
        out.append(f"{e.get('label', '')}{' · ' if e.get('label') else ''}{e.get('short', '')}. Section `{e['code']}` in raw/{t}.json.")
        if e.get("reader"):
            out += ["", e["reader"]]
        out.append("")
        section = {}
        for b in e["boxes"]:
            label = b.get("label", "").replace("{n}", "N")
            what = {"list": "a list of items", "ranked": f"a numbered list of {b.get('count', 3)}", "text": "one item",
                    "tally": "a tally (no id)", "row": "a list of rows, one per box", "name": "a name line",
                    "list+votes": "a list of items, each with its dot votes in `votes`"}.get(b["type"], b["type"])
            parts = [f"**{label}**{' (optional)' if b.get('optional') else ''}: `{b['key']}`, {what}."]
            if b["type"] in ("list", "ranked", "row", "list+votes"):
                parts.append(f"Ids `{t}.{e['code']}.{b['stem']}1`, `{t}.{e['code']}.{b['stem']}2` and so on.")
            elif b.get("stem"):
                parts.append(f"Id `{t}.{e['code']}.{b['stem']}`.")
            if b.get("hint"):
                parts.append(f"Printed hint: \u201c{b['hint']}\u201d")
            if b.get("fields"):
                parts.append("Fields: " + ", ".join(f"`{f['key']}` ({f['label']})" for f in b["fields"]) + ".")
            if b.get("ticks"):
                tk = b["ticks"]
                parts.append(f"Ticks under \u201c{tk.get('label', '').rstrip(':')}\u201d go in `{tk['key']}`: " + ", ".join(f"`{o[0]}` ({o[1]})" if isinstance(o, list) else f"`{o}`" for o in tk["options"]) + ".")
            if b.get("reader"):
                parts.append(b["reader"])
            line = "- " + " ".join(parts)
            out.append(line)
            # the example shape
            sid = f"{t}.{e['code']}.{b.get('stem', '')}"
            if b["type"] in ("list", "ranked", "list+votes"):
                item = {"id": sid + "1", "text": "..."}
                if b["type"] == "list+votes":
                    item["votes"] = 3
                section[b["key"]] = [item]
            elif b["type"] == "text" and b.get("stem"):
                section[b["key"]] = {"id": sid, "text": "..."}
            elif b["type"] == "row":
                row = {"id": sid + "1"}
                row.update({f["key"]: "..." for f in b.get("fields", [])})
                if b.get("ticks"):
                    row[b["ticks"]["key"]] = [b["ticks"]["options"][0][0] if isinstance(b["ticks"]["options"][0], list) else b["ticks"]["options"][0]]
                section[b["key"]] = [row]
            elif b["type"] == "tally":
                tally = {"tally": {o: 0 for o in b.get("options", [])[:2]}}
                if b.get("text_line"):
                    tally[b.get("fields_key", b["text_line"].lower())] = "..."
                section[b["key"]] = tally
        example[e["code"]] = section
        out.append("")
    example["V"] = {"points": [{"id": f"{t}.V.point1", "text": "...", "excerpt": "..."}]}
    example["unclear"] = [{"id": f"{t}.{W.sheet_codes()[0]}.{W.per_group()[0]['boxes'][0].get('stem', 'item')}1", "photo": "P013", "note": "..."}]
    example["notes"] = "..."
    out += [f"## The file: raw/{t}.json", "```json", json.dumps(example, indent=1, ensure_ascii=False), "```", ""]
    for e in W.per_person():
        out.append(f"## {e.get('short', 'cards')[:1].upper() + e.get('short', 'cards')[1:]}s: raw/{e['raw_file']}")
        out.append(f"One file for the whole room: `{e['key']}`, each with an id like `{e['prefix']}{e['stem']}1`. "
                   "Fields: " + ", ".join(f"`{b['key']}` ({b.get('label', '')})" for b in e["boxes"]) + ".")
        if e.get("reader"):
            out += ["", e["reader"]]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def brief(args):
    print(brief_text(workshop(args), args.table))


# ---------------------------------------------------------------- publish

def publish(args):
    run = run_dir(args.run)
    data = load(run / "session.json")
    if not data:
        sys.exit("No session.json in this run yet")
    if data["meta"].get("status") != "final":
        sys.exit("Set meta.status to \"final\" in session.json once the review is done, then run publish again")
    args.data = None
    verify(args)          # exits on errors
    (ROOT / "data").mkdir(exist_ok=True)
    shutil.copy(run / "session.json", ROOT / "data" / "session.json")
    subprocess.run([sys.executable, str(ROOT / "build" / "build.py"), str(ROOT / "data" / "session.json"),
                    "--out", str(ROOT / "playbook" / "index.html")] + config_args(args), check=True)


# ---------------------------------------------------------------- draft build

def draft(args):
    run = run_dir(args.run)
    subprocess.run([sys.executable, str(ROOT / "build" / "build.py"), str(run / "session.json"),
                    "--out", str(run / "playbook-draft.html")] + config_args(args), check=True)


def config_args(args):
    return ["--config", args.config] if getattr(args, "config", None) else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="normalise a folder of photos (and voice notes) into a new run, or --into an existing one", description="Normalise a folder of photos (and voice notes) into a new run, or --into an existing one."); p.add_argument("inbox")
    p.add_argument("--into", help="add these photos to an existing run (a second batch) instead of starting a new one")
    p.set_defaults(fn=prepare)
    p = sub.add_parser("transcribe", help="transcribe any voice notes locally with Whisper", description="Transcribe any voice notes locally with Whisper."); p.add_argument("--run", help="run folder (default: runs/latest)"); p.add_argument("--model", default=WHISPER_MODEL)
    p.add_argument("--jobs", type=int, default=3); p.add_argument("--force", action="store_true"); p.set_defaults(fn=transcribe)
    p = sub.add_parser("status", help="coverage and blur per table, once labels.json is written", description="Coverage and blur per table, once labels.json is written."); p.add_argument("--run", help="run folder (default: runs/latest)"); p.add_argument("--tables", type=int, default=12, help="how many tables to expect (default 12)"); p.add_argument("--config", help="settings file (default: playbook.config.json)"); p.set_defaults(fn=status)
    p = sub.add_parser("brief", help="the workshop's sheets, ids and file shape, for the readers", description="Print the workshop's sheets, boxes, ids and the raw file's shape, generated from its format files. Give it to each reader with RAW_FORMAT.md."); p.add_argument("--table", type=int, default=7, help="the table number the examples use (default 7)"); p.add_argument("--config", help="settings file (default: playbook.config.json)"); p.set_defaults(fn=brief)
    p = sub.add_parser("verify", help="check the raw files and session.json: traceability, verbatim quotes, gaps, names", description="Check the raw files and session.json: traceability, verbatim quotes, gaps, names."); p.add_argument("--run", help="run folder (default: runs/latest)"); p.add_argument("--data"); p.add_argument("--links", action="store_true")
    p.add_argument("--config", help="settings file (default: playbook.config.json)"); p.set_defaults(fn=verify)
    p = sub.add_parser("review", help="build review.html: every line next to its photos", description="Build review.html: every line next to its photos."); p.add_argument("--run", help="run folder (default: runs/latest)"); p.add_argument("--config", help="settings file (default: playbook.config.json)"); p.set_defaults(fn=review)
    p = sub.add_parser("draft", help="build the draft playbook in the run folder", description="Build the draft playbook in the run folder."); p.add_argument("--run", help="run folder (default: runs/latest)"); p.add_argument("--config", help="settings file (default: playbook.config.json)"); p.set_defaults(fn=draft)
    p = sub.add_parser("publish", help="final checks, then build playbook/index.html", description="Final checks, then build playbook/index.html."); p.add_argument("--run", help="run folder (default: runs/latest)"); p.add_argument("--links", action="store_true"); p.add_argument("--config", help="settings file (default: playbook.config.json)")
    p.set_defaults(fn=publish)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
