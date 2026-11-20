#!/usr/bin/env python3
"""Build the uncertainty review app for a run: one screen per uncertain line, with a close-up of the photo.

    python3 tools/review/make_review.py [--run <run folder>]     # then open <run>/review/index.html

Collects every line in the run's session.json that carries a [?word] or [illegible] marker and every card whose name
or organisation is unsure. Optional extra screens, written for this run, come from <run>/review/extra.json (see
tools/review/README.md): photo checks a reader asked for, and calls only a reviewer can make.

Close-ups come from Apple's Vision text recognition (macOS only; ocr.swift is compiled the first time it's needed):
each photo is turned the right way up, its lines are read, and the line that best matches the raw transcription is
cropped with its neighbours. When the match is weak the screen says so and shows a wider view. Without Vision (not on
a Mac, or no Swift compiler), every screen shows the whole photo instead. Results are cached in review/ocr/.
"""
import argparse, difflib, glob, json, re, shutil, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image

TOOL = Path(__file__).resolve().parent
ROOT = TOOL.parent.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--run", help="the run folder (default: runs/latest)")
ap.add_argument("--config", help="settings file, if not playbook.config.json (its names are ignored when matching text)")
ap.add_argument("--no-ocr", action="store_true", help="skip text recognition: every screen shows the whole photo")
A = ap.parse_args()
RUN = Path(A.run).expanduser().resolve() if A.run else (ROOT / "runs" / "latest").resolve()
if not (RUN / "session.json").exists():
    sys.exit(f"No session.json in {RUN}: write the draft playbook (stage 4) first.")
OUT = RUN / "review"
OCR_DIR, IMG_DIR = OUT / "ocr", OUT / "img"
OUT.mkdir(exist_ok=True)
CFG = config.load(A.config)
MK = re.compile(r"\[\?[^\]]*\]|\[illegible\]", re.I)
SEC_NAMES = {"quotes": "Quote", "helped": "Helped", "hindered": "Got in the way", "lessons": "If we did it again",
             "actions": "Action", "questions": "Question", "card": "Commitment card"}
SHEET_NAMES = {"S1": "Sheet 1", "S2": "Sheet 2", "S3": "Sheet 3", "SS": "Side sheet"}

session = json.loads((RUN / "session.json").read_text())
labels = json.loads((RUN / "labels.json").read_text())["photos"]
challenge_titles = {c["id"]: c["title"] for c in session["challenges"]}
EXTRA = json.loads((OUT / "extra.json").read_text()) if (OUT / "extra.json").exists() else {}


def ocr_binary():
    """The Vision command-line tool, compiled from ocr.swift on first use. None where Vision isn't available."""
    if A.no_ocr or sys.platform != "darwin":
        return None
    exe = TOOL / "ocr"
    if exe.exists() and exe.stat().st_mtime >= (TOOL / "ocr.swift").stat().st_mtime:
        return exe
    if not shutil.which("swiftc"):
        print("No Swift compiler (install Xcode's command line tools: xcode-select --install), so no close-ups.")
        return None
    print("Compiling the text recognition tool (once)...")
    r = subprocess.run(["swiftc", "-O", str(TOOL / "ocr.swift"), "-o", str(exe)], capture_output=True, text=True)
    if r.returncode:
        print("Couldn't compile ocr.swift, so no close-ups:\n" + r.stderr[-800:])
        return None
    return exe


OCR_BIN = ocr_binary()

# ---------------------------------------------------------------- raw items, reader notes and photos per id
raw, unclear = {}, {}
for f in sorted(glob.glob(str(RUN / "raw" / "T*.json"))):
    r = json.loads(Path(f).read_text())
    for sec in ("S1", "S2", "S3", "SS"):
        for v in (r.get(sec) or {}).values():
            for it in (v if isinstance(v, list) else [v] if isinstance(v, dict) else []):
                if isinstance(it, dict) and it.get("id"):
                    raw[it["id"]] = it
    for u in r.get("unclear", []):
        unclear.setdefault(u.get("id"), []).append(u)
card_photos = {}
# card stubs: raw/commitments.json, plus any cards-*.json sets when more than one agent read the cards
for f in sorted(glob.glob(str(RUN / "raw" / "cards-*.json"))) + [str(RUN / "raw" / "commitments.json")]:
    if not Path(f).exists():
        continue
    d = json.loads(Path(f).read_text())
    for c in d["cards"]:
        raw[c["id"]] = c
        card_photos[c["id"]] = c["photos"] if c.get("photos") else [c["photo"]] if c.get("photo") else d.get("photos", [])
    for u in d.get("unclear", []):
        if u not in unclear.get(u.get("id"), []):
            unclear.setdefault(u.get("id"), []).append(u)


def photos_for(src):
    if src.startswith("C."):
        return card_photos.get(src, [])
    table, sheet = int(src[1:3]), src.split(".")[1]
    named = [u["photo"] for u in unclear.get(src, []) if u.get("photo")]
    on_sheet = [pid for pid, lab in sorted(labels.items()) if lab.get("table") == table and
                sheet in (lab.get("sheet") if isinstance(lab.get("sheet"), list) else [lab.get("sheet")])]
    return list(dict.fromkeys(named + on_sheet))


def raw_text(src, field=None):
    it = raw.get(src, {})
    if field and field in it:
        return it[field]
    return it.get("text") or " ".join(str(it.get(k, "")) for k in ("action", "needs", "sticks") if it.get(k))


# notes added after the readers finished (extra.json "notes"), shown with theirs: say whose reading it is
EXTRA_NOTES = EXTRA.get("notes", {})


def notes_for(srcs):
    out = [EXTRA_NOTES[s] for s in srcs if s in EXTRA_NOTES]
    for s in srcs:
        for u in unclear.get(s, []):
            n = u.get("note") or u.get("what") or u.get("reason") or ""
            if n:
                out.append(n)
    return out


# ---------------------------------------------------------------- OCR, the right way up
def ocr(path):
    r = subprocess.run([str(OCR_BIN), str(path)], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout or "[]")


# the paper kit's printed text, so headings are never mistaken for handwriting
PRINTED = ["where does support get stuck", "who's at this table", "everyone puts one tally mark", "every challenge at this table",
           "write them all down", "budget, leadership, burnout", "our top three", "the one we're tackling", "copy it onto your table card",
           "what has helped, or not", "what happened, and why did it work", "got in the way", "what would you change or avoid",
           "if we did it again, we'd", "what could people try now", "and how does it stick", "what to try", "what you need",
           "how it sticks", "good for", "just starting", "established", "heard something good", "write it here",
           "exact words, no names", "things nobody could answer", "links, books, people, tools", "best thing said today",
           "the table lead writes it", "one thing i will try, adapt or explore", "name (optional)", "organisation (optional)",
           "add these only if you're happy", "public playbook", "all of this goes into the", "scan for the", "countries:"]
# and the names the settings print on the sheets and cards
PRINTED += [x.lower() for x in (CFG["playbook"]["name"], CFG["org"]["name"], urlparse(CFG["playbook"]["url"]).netloc) if x]
SHORT = re.escape(CFG["org"]["short"].lower()) if CFG["org"]["short"] else "(?!)"


def is_printed(t):
    t = t.lower().strip()
    if len(t) <= 2 or re.fullmatch(r"(table|question \d|action \d|helped|quotes|questions|resources|" + SHORT + r"|s\d\s*.\s*table.*)", t):
        return True
    return any(p in t or difflib.SequenceMatcher(None, p, t).ratio() > 0.8 for p in PRINTED)


def baseline_angle(lines, W, H):
    """Median direction of the text baselines, in degrees (0 = upright, 90 = reads bottom to top, 180 = upside down).
    Vision reads text at any angle and reports each line's corners, so this is exact where a word count is not."""
    import math
    ang = sorted(math.degrees(math.atan2((o["try"] - o["tly"]) * H, (o["trx"] - o["tlx"]) * W)) for o in lines if len(o["t"]) > 5)
    return ang[len(ang) // 2] if ang else 0.0


def photo_ocr(pid):
    """(rotation in degrees counter-clockwise, lines, rotated image). Cached."""
    OCR_DIR.mkdir(exist_ok=True)
    cache = OCR_DIR / f"{pid}.json"
    src = Image.open(RUN / "photos" / f"{pid}.jpg")
    if cache.exists():
        d = json.loads(cache.read_text())
        return d["rot"], d["lines"], src.rotate(d["rot"], expand=True)
    small = src.copy()
    small.thumbnail((1600, 1600))
    tmp = OCR_DIR / f"_{pid}_probe.jpg"
    small.save(tmp, quality=85)
    rot = int(-round(baseline_angle(ocr(tmp), *small.size) / 90) * 90) % 360   # turn the text back to level
    tmp.unlink()
    big = src.rotate(rot, expand=True)
    tmp = OCR_DIR / f"_{pid}.jpg"
    big.save(tmp, quality=92)
    lines = ocr(tmp)
    tmp.unlink()
    for o in lines:
        o["printed"] = is_printed(o["t"])
    cache.write_text(json.dumps({"rot": rot, "lines": lines}))
    return rot, lines, big


def words(s):
    s = MK.sub(lambda m: m.group(0)[2:-1] if m.group(0).startswith("[?") else " ", s or "")
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3]


def hit(w, line_words):
    return any(w == x or difflib.SequenceMatcher(None, w, x).ratio() >= 0.72 for x in line_words)


def locate(pid, target, card=False, s3=False):
    """Crop box (pixels, in the upright image) around the handwriting that matches `target`, plus how sure the match is.

    Every handwritten line is the centre of a small neighbourhood (a sticky note's worth of lines); the neighbourhood
    whose words best match the target, counting both how much of the target it covers and how little else it holds,
    wins. Printed headings are ignored."""
    if not OCR_BIN:
        return Image.open(RUN / "photos" / f"{pid}.jpg"), None, 0.0
    rot, lines, img = photo_ocr(pid)
    W, H = img.size
    tw = list(dict.fromkeys(words(target)))
    hand = [o for o in lines if not o.get("printed")]
    if not tw or not hand:
        return img, None, 0.0
    if card:
        found = locate_card(lines, hand, tw, W, H)
        if found:
            return img, found[0], found[1]
    lh = sorted(o["h"] for o in hand)[len(hand) // 2]
    for o in hand:
        o["w_"] = words(o["t"])
        o["hits"] = {w for w in tw if hit(w, o["w_"])}
        o["good"] = sum(1 for w in o["w_"] if hit(w, tw))
    best = None
    for c in hand:
        cy = c["y"] + c["h"] / 2
        hood = [o for o in hand if abs(o["y"] + o["h"] / 2 - cy) <= 3.5 * lh and o["x"] < c["x"] + c["w"] + 0.03 and o["x"] + o["w"] > c["x"] - 0.03]
        cov = set().union(*(o["hits"] for o in hood)) if hood else set()
        recall = len(cov) / len(tw)
        n_words = sum(len(o["w_"]) for o in hood) or 1
        precision = sum(o["good"] for o in hood) / n_words
        f = 2 * recall * precision / (recall + precision) if recall and precision else 0
        if not best or f > best[0]:
            best = (f, [o for o in hood if o["hits"]] or [c], recall)
    f, region, recall = best
    if f == 0:
        return img, None, 0.0
    x0 = min(o["x"] for o in region); x1 = max(o["x"] + o["w"] for o in region)
    y0 = min(o["y"] for o in region); y1 = max(o["y"] + o["h"] for o in region)
    printed = [o for o in lines if o.get("printed")]
    if card:
        # the whole card: from its printed heading down to the line under the Name and Organisation boxes
        heads = [o for o in printed if "thing" in o["t"].lower() and o["y"] < y0 + lh and o["x"] < x1 and o["x"] + o["w"] > x0 - 0.05]
        feet = [o for o in printed if re.search(r"playbook|these only", o["t"].lower()) and o["y"] > y1 and o["x"] < x1 + 0.05 and o["x"] + o["w"] > x0 - 0.08]
        if heads:
            # every card is the same shape, so its printed heading gives the whole card: the heading spans about 83% of
            # the card's width and sits about a fifth of the way down; the card is 1.41 times as tall as it is wide
            h = max(heads, key=lambda o: o["y"])
            cw = h["w"] * W / 0.83; ch = 1.41 * cw
            left, top = h["x"] * W - 0.08 * cw, h["y"] * H - 0.22 * ch
            box = (max(0, left - 0.03 * cw), max(0, top - 0.02 * ch), min(W, left + 1.05 * cw), min(H, top + 1.02 * ch))
            return img, box, round(min(f, recall), 2)
        if feet:
            ft = min(feet, key=lambda o: o["y"]); y1 = max(y1, ft["y"] + ft["h"]); x1 = max(x1, ft["x"] + ft["w"])
    if s3:
        # the whole action row, from its printed "Action N" heading down to its "Good for" tick boxes and across all
        # three columns, so the reviewer sees what to try, what you need, how it sticks and the ticks together
        ticks = [o for o in printed if re.search(r"good for|just starting|growing|established", o["t"].lower()) and o["y"] > y0 - lh]
        heads = [o for o in lines if re.fullmatch(r"\s*action\s*\d\s*", o["t"].lower()) and o["y"] < y0 + lh]
        if ticks:
            tk = min(ticks, key=lambda o: o["y"]); y1 = max(y1, tk["y"] + tk["h"])
        if heads:
            hd = max(heads, key=lambda o: o["y"]); y0 = min(y0, hd["y"])
        band = [o for o in lines if y0 - lh <= o["y"] <= y1]
        if band:
            x0 = min([x0] + [o["x"] for o in band]); x1 = max([x1] + [o["x"] + o["w"] for o in band])
    pad_y, pad_x = 1.4 * lh, 0.035
    box = [max(0, x0 - pad_x) * W, max(0, y0 - pad_y) * H, min(1, x1 + pad_x) * W, min(1, y1 + pad_y) * H]
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    w, h = max(box[2] - box[0], W * 0.22), max(box[3] - box[1], 5 * lh * H)
    box = (max(0, cx - w / 2), max(0, cy - h / 2), min(W, cx + w / 2), min(H, cy + h / 2))
    return img, box, round(min(f, recall), 2)


def locate_card(lines, hand, tw, W, H):
    """Whole-card matching for photos of many cards (line matching picked the wrong card when cards share words). Every card has the same printed heading and shape, so each heading gives one card's box; the card whose
    handwriting best matches the target (both covering the target and holding little else) wins."""
    heads = [o for o in lines if "thing" in o["t"].lower() and re.search(r"try|adapt|explore", o["t"].lower())]
    best = None
    for h in heads:
        cw = h["w"] * W / 0.83; ch = 1.41 * cw
        left, top = h["x"] * W - 0.08 * cw, h["y"] * H - 0.22 * ch
        box = (max(0, left - 0.03 * cw), max(0, top - 0.02 * ch), min(W, left + 1.05 * cw), min(H, top + 1.02 * ch))
        inside = [o for o in hand if box[0] <= (o["x"] + o["w"] / 2) * W <= box[2] and box[1] <= (o["y"] + o["h"] / 2) * H <= box[3]]
        got = [w for o in inside for w in words(o["t"])]
        if not got:
            continue
        recall = sum(1 for w in tw if hit(w, got)) / len(tw)
        precision = sum(1 for w in got if hit(w, tw)) / len(got)
        f = 2 * recall * precision / (recall + precision) if recall and precision else 0
        if not best or f > best[1]:
            best = (box, round(f, 2))
    return best


def save_webp(im, path, edge, q=82):
    im = im.convert("RGB")
    im.thumbnail((edge, edge), Image.LANCZOS)
    im.save(path, "WEBP", quality=q, method=5)
    return im.size


def picture(key, srcs, target, card=False):
    """Make the close-up and the whole upright photo for an item. Returns dict for the app."""
    IMG_DIR.mkdir(exist_ok=True)
    pids = list(dict.fromkeys(p for s in srcs for p in photos_for(s)))
    if not pids:
        return {"photos": []}
    best = None
    for pid in pids:
        img, box, conf = locate(pid, target, card, s3=any(".S3." in x for x in srcs))
        # a retake was sent because the first photo was poor: prefer it whenever it matches reasonably well
        score = conf + (0.3 if "retake" in (labels.get(pid, {}).get("note") or "") and conf >= 0.3 else 0)
        if not best or score > best[4]:
            best = (pid, box, conf, img, score)
    pid, box, conf, img, _ = best
    whole = IMG_DIR / f"{pid}.webp"
    if not whole.exists():
        save_webp(img, whole, 2000, 78)
    out = {"photo": pid, "photos": pids, "whole": f"img/{pid}.webp", "sure": round(conf, 2)}
    if box:
        crop = img.crop(tuple(int(v) for v in box))
        size = save_webp(crop, IMG_DIR / f"{key}.webp", 1500, 86)
        out.update(crop=f"img/{key}.webp", w=size[0], h=size[1])
    return out


# ---------------------------------------------------------------- the screens
items = []


def add(kind, key, where, srcs, **kw):
    items.append(dict(kind=kind, key=key, where=where, src=srcs, **kw))


def where_of(cid, sec, i):
    if cid == "commitments":
        return f"Commitments › card {i}"
    return f"{challenge_titles[cid]} › {SEC_NAMES[sec]} {i}"


for c in session["challenges"]:
    for sec in ("quotes", "helped", "hindered", "lessons", "actions", "questions"):
        for i, x in enumerate(c[sec], 1):
            if isinstance(x, str):
                continue
            fields = [k for k in ("text", "title", "what", "needs", "sticks") if isinstance(x.get(k), str) and MK.search(x[k])]
            if not fields:
                continue
            srcs = x["src"] if isinstance(x["src"], list) else [x["src"]]
            msrc = [s for s in srcs if MK.search(json.dumps(raw.get(s, {}), ensure_ascii=False))] or srcs
            key = f"{c['id']}-{sec}-{i}"
            target = " ".join(next((str(raw.get(s, {}).get(k)) for k in ("needs", "sticks", "action", "text")
                                    if MK.search(str(raw.get(s, {}).get(k, "")))), raw_text(s)) for s in msrc)
            add("reading", key, where_of(c["id"], sec, i), srcs,
                fields={k: x[k] for k in fields}, page={k: v for k, v in x.items() if isinstance(v, str) and k != "src"},
                raw=[f"{s}: {raw_text(s)}" for s in msrc], notes=notes_for(msrc),
                sheet=f"Table {msrc[0][1:3].lstrip('0')}, {SHEET_NAMES[msrc[0].split('.')[1]]}",
                **picture(key, msrc, target))
# general reading and "Heard on the day" live outside the challenges
for kind, label, lst in (("resources", "General reading", session.get("resources", [])), ("quotes", "Heard on the day", session.get("quotes", []))):
    for i, x in enumerate(lst, 1):
        fields = [k for k in ("text", "title", "source") if isinstance(x.get(k), str) and MK.search(x[k])]
        if not fields:
            continue
        srcs = x["src"] if isinstance(x["src"], list) else [x["src"]]
        key = f"{kind}-{srcs[0].replace('.', '-')}"
        add("reading", key, f"{label} › {i}", srcs, fields={k: x[k] for k in fields},
            page={k: v for k, v in x.items() if isinstance(v, str) and k != "src"},
            raw=[f"{s_}: {raw_text(s_)}" for s_ in srcs], notes=notes_for(srcs),
            sheet=f"Table {srcs[0][1:3].lstrip('0')}, {SHEET_NAMES[srcs[0].split('.')[1]]}",
            **picture(key, srcs, " ".join(raw_text(s_) for s_ in srcs)))
for i, m in enumerate(session["commitments"], 1):
    fields = [k for k in ("text", "name", "org") if isinstance(m.get(k), str) and MK.search(m[k])]
    if not fields:
        continue
    key = "card-" + re.sub(r"\W+", "-", m["src"])
    rc = raw.get(m["src"], {})
    add("reading", key, where_of("commitments", "card", i), [m["src"]],
        fields={k: m[k] for k in fields}, page={k: m[k] for k in ("text", "name", "org") if m.get(k)},
        raw=[f"{m['src']}: " + " · ".join(filter(None, [rc.get("text"), rc.get("name"), rc.get("org")]))],
        notes=notes_for([m["src"]]), sheet="Commitment card", published_name=bool(set(fields) & {"name", "org"}),
        **picture(key, [m["src"]], " ".join(filter(None, [rc.get("text"), rc.get("name")])), card=True))

def place_of(src):
    """Where a raw id ended up on the page, for a check's heading."""
    for c in session["challenges"]:
        for sec in ("quotes", "helped", "hindered", "lessons", "actions", "questions"):
            for x in c[sec]:
                s_ = x.get("src") if isinstance(x, dict) else None
                if src in (s_ if isinstance(s_, list) else [s_]):
                    return c["title"]
    for label, lst in (("General reading", session.get("resources", [])), ("Heard on the day", session.get("quotes", [])),
                       ("Commitments", session.get("commitments", []))):
        if any(src in (x.get("src") if isinstance(x.get("src"), list) else [x.get("src")]) for x in lst):
            return label
    return "Not on the page"


def sheet_of(src):
    return "Commitment card" if src.startswith("C.") else f"Table {src[1:3].lstrip('0')}, {SHEET_NAMES[src.split('.')[1]]}"


# photo checks the readers asked for: {"src": raw id, "note": the question}
for ch in EXTRA.get("checks", []):
    src = ch["src"]
    key = "check-" + re.sub(r"\W+", "-", src)
    add("check", key, f"{place_of(src)} · {src}", [src], raw=[f"{src}: {raw_text(src)}"], notes=[ch["note"]],
        sheet=sheet_of(src), **picture(key, [src], raw_text(src), card=src.startswith("C.")))

# calls only a reviewer can make: {"key", "src": [raw ids, may be empty], "text", "options": [two to four answers]}
for cl in EXTRA.get("calls", []):
    srcs = cl.get("src") or []
    key = "call-" + re.sub(r"\W+", "-", cl["key"])
    pic = picture(key, srcs, " ".join(raw_text(s_) for s_ in srcs), card=bool(srcs and srcs[0].startswith("C."))) if srcs else {"photos": []}
    add("call", key, "Your call", srcs, notes=[cl["text"]], options=cl["options"], **pic)

if not items:
    print("Nothing to review: no [?word] or [illegible] markers on the page, and no extra.json checks or calls.")
def themed_app():
    """The review app in the brand's accent, light and dark, wherever that keeps its contrast (else the app's own)."""
    page = (TOOL / "index.html").read_text()
    pal = config.palette(CFG)
    blocks = [m for m in re.finditer(r"--bg:#[0-9a-f]{6};\s*--panel:#[0-9a-f]{6};[^}]*", page)]
    for m, mode in zip(reversed(blocks), ("dark", "light")):
        block = m.group(0)
        bg, panel = re.search(r"--bg:(#[0-9a-f]{6})", block).group(1), re.search(r"--panel:(#[0-9a-f]{6})", block).group(1)
        acc = pal[mode]["--accent"] if mode == "light" else {**pal["light"], **pal["dark"]}["--accent"]
        on = "#ffffff" if config.contrast("#ffffff", acc) >= config.contrast(pal["light"]["--ink"], acc) else pal["light"]["--ink"]
        if mode == "dark":
            on = bg
        if min(config.contrast(acc, bg), config.contrast(acc, panel)) >= 4.5 and config.contrast(on, acc) >= 4.5:
            block = re.sub(r"--brand:#[0-9a-f]{6}", "--brand:" + acc, block)
            block = re.sub(r"--brand-ink:#[0-9a-f]{6}", "--brand-ink:" + on, block)
            page = page[:m.start()] + block + page[m.end():]
    return page


(OUT / "index.html").write_text(themed_app())
(OUT / "items.js").write_text("window.REVIEW = " + json.dumps({"run": RUN.name, "items": items}, ensure_ascii=False, indent=1) + ";\n")
weak = [i["key"] for i in items if i.get("photos") and i.get("sure", 1) < 0.34]
print(f"{len(items)} screens ({sum(i['kind'] == 'reading' for i in items)} readings, {sum(i['kind'] == 'check' for i in items)} checks, "
      f"{sum(i['kind'] == 'call' for i in items)} calls). Weak close-ups: {len(weak)} {weak}")
print(f"Open {OUT / 'index.html'}" + ("" if OCR_BIN else " (whole photos only: no text recognition here)"))
