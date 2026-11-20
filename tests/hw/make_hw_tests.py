#!/usr/bin/env python3
"""Handwriting stress test for the ingest readers: fake-but-hard handwriting on the REAL printed sheets.

    python3 tests/hw/get_fonts.py            # once: the handwriting fonts aren't in the repo
    python3 print/build_paper.py             # once: the printed sheets the handwriting goes on
    python3 tests/hw/make_hw_tests.py        # writes tests/hw/inbox/ (photos) and tests/hw/truth.json

Rounds 1 and 2: ten test tables, each pushing on one thing (see PROFILES), plus two photos of commitment-card
halves. The sheets are rasterised from print/out/paper, so the layout is exactly what's on the tables on the day.
Handwriting comes from 20 handwriting fonts (tests/hw/fonts, OFL/Apache, each based on real handwriting), each
"writer" warped with a smooth random displacement field, wobbly baselines and their own slant, size and ink.
That is still kinder than real handwriting (letterforms repeat), so treat the scores as a ceiling: photos of
real people's handwriting on the printed sheets are the true test.
ALL CONTENT IS SYNTHETIC TEST DATA. Names and organisations in it are invented.
"""
import json, random, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PAPER = ROOT / "print" / "out" / "paper"
FONTS = HERE / "fonts"
OUT = HERE / "inbox"
PX = 4.04                      # pixels per mm on the rendered A1 sheet (2400 px across the trim)
BLEED = 3

# ---------------------------------------------------------------- geometry, in mm from the trim's top left
# taken from print/build_paper.py by recording its zone/checkbox/line calls (v1.3.0, proposed boxes on);
# v1.4.0 changed colours and wording but no box positions. Add a version here once you've checked its boxes.
GEO_VERSIONS = ("1.3.0", "1.4.0")
GEO = {
    "circle": (485, 112),              # where the table number goes, inside the circle under "Table"
    "footer": (524, 800),              # the "S1 · Table ____" line
    "S1": {"tally_boxes": [(48 + i * 63, 267.5, 57, 40) for i in range(8)],
           "countries": (103, 330), "challenges": (48, 425, 498, 165),
           "top3": [(70, 671), (70, 703), (70, 735)], "pick": [(352, 692), (352, 720), (352, 748)]},
    "S2": {"helped": (46, 262, 230, 312), "hindered": (318, 262, 230, 312), "lessons": (46, 645, 502, 118)},
    "S3": {"rows": [210.1, 403.0, 596.0], "row_h": 175.0, "cols": [(48, 214), (280, 124), (420, 124)],
           "ticks": [96.8, 177.2, 240.5]},
    "SS": {"quotes": (44, 262, 146, 318), "questions": (225, 262, 146, 318), "resources": (405, 262, 146, 318),
           "best": (46, 657, 502, 108)},
    "card": {"lines": [(116, 49 + 9 * i) for i in range(6)], "name": (143, 116), "org": (153, 126)},
}
SIZE_BOOST = 1.0          # set per sheet or card in main(); the numbers in T are the em size in mm
SECTORS = ["Public sector", "Finance", "Retail", "Tech", "Education", "Charity", "Health", "Other"]

INKS = {"black": (22, 20, 28), "blue": (28, 52, 150), "red": (176, 32, 38), "green": (24, 110, 60),
        "biro": (32, 44, 120), "faint": (120, 118, 126), "pencil": (105, 105, 110)}
FONT_FILES = {
    "patrick": "PatrickHand-Regular.ttf", "kalam": "Kalam-Regular.ttf", "indie": "IndieFlower-Regular.ttf",
    "shadows": "ShadowsIntoLight.ttf", "gochi": "GochiHand-Regular.ttf", "architect": "ArchitectsDaughter-Regular.ttf",
    "marker": "PermanentMarker-Regular.ttf", "rocksalt": "RockSalt-Regular.ttf", "reenie": "ReenieBeanie.ttf",
    "nothing": "NothingYouCouldDo.ttf", "zeyada": "Zeyada.ttf", "homemade": "HomemadeApple-Regular.ttf",
    "aurore": "LaBelleAurore.ttf", "grace": "CoveredByYourGrace.ttf", "justme": "JustMeAgainDownHere.ttf",
    "sueellen": "SueEllenFrancisco-Regular.ttf", "sunrise": "WaitingfortheSunrise.ttf", "gloria": "GloriaHallelujah.ttf",
    "dawning": "DawningofaNewDay.ttf", "caveat": "Caveat.ttf",
}
# fonts whose letters are much smaller than their em size, scaled up so they're written at a similar height
FONT_SCALE = {"reenie": 1.35, "zeyada": 1.3, "justme": 1.35, "sueellen": 1.35, "dawning": 1.15, "sunrise": 1.2,
              "aurore": 1.0, "homemade": 0.8, "rocksalt": 0.8, "nothing": 1.05, "caveat": 1.15, "shadows": 1.1}


class Writer:
    """One person's handwriting: a font plus their own size, slant, wobble, pen and ink."""
    def __init__(self, font, size=17, ink="black", pen="marker", slant=0.0, wobble=1.0, seed=0):
        self.font_key, self.size, self.ink, self.pen, self.slant, self.wobble = font, size, ink, pen, slant, wobble
        self.rng = np.random.default_rng(seed)
        px = int(size * PX * FONT_SCALE.get(font, 1.0) * SIZE_BOOST)
        self.font = ImageFont.truetype(str(FONTS / FONT_FILES[font]), px)
        self.stroke = {"marker": max(1, px // 28), "fat": max(2, px // 16), "biro": 0, "pencil": 0}[pen]

    def line_image(self, text):
        """The text as one RGBA strip, warped like a real hand. Returns (image, word x-spans)."""
        f, rng = self.font, self.rng
        words = text.split(" ")
        # size the strip from the font's real ink box: some hands (Rock Salt, Homemade Apple) reach far below the em box
        tops, bots = zip(*[(f.getbbox(w, stroke_width=self.stroke)[1], f.getbbox(w, stroke_width=self.stroke)[3]) for w in words if w] or [(0, f.size)])
        pad = int(f.size * 0.35)
        base_y = pad - min(0, min(tops))
        h = int(base_y + max(bots) + pad + f.size * 0.1)
        gaps = [f.getlength(" ") * rng.uniform(0.8, 1.5) for _ in words]
        width = int(sum(f.getlength(w) for w in words) + sum(gaps) + f.size)
        layer = Image.new("L", (width, h), 0)
        d = ImageDraw.Draw(layer)
        x, spans = f.size * 0.2, []
        drift = rng.uniform(-0.04, 0.04)          # the line climbs or sags a little
        for w, g in zip(words, gaps):
            y = base_y + drift * x + rng.normal(0, f.size * 0.04 * self.wobble)
            d.text((x, y), w, font=f, fill=255, stroke_width=self.stroke, stroke_fill=255)
            wl = f.getlength(w)
            spans.append((x, x + wl))
            x += wl + g
        a = np.asarray(layer, dtype=np.float32)
        # elastic warp: a smooth random displacement field, so letterforms vary like a hand rather than a font
        alpha, sigma = f.size * 0.075 * self.wobble, f.size * 0.18
        dx = gaussian_filter(rng.uniform(-1, 1, a.shape), sigma) * alpha * 40
        dy = gaussian_filter(rng.uniform(-1, 1, a.shape), sigma) * alpha * 40
        yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
        xx = xx + dx + self.slant * (yy - h * 0.6)   # slant as a shear
        a = map_coordinates(a, [yy + dy, xx], order=1, mode="constant")
        if self.pen in ("biro", "pencil"):
            a = a * rng.uniform(0.75, 0.95)
        alpha_img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        if self.pen == "pencil":
            alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(0.6))
        ink = Image.new("RGBA", alpha_img.size, INKS[self.ink] + (0,))
        ink.putalpha(alpha_img)
        a = np.asarray(alpha_img)
        boxed = []
        for x0, x1 in spans:
            rows = np.where(a[:, max(0, int(x0)):int(x1) + 1].max(axis=1) > 60)[0]
            top, bot = (rows.min(), rows.max()) if len(rows) else (h * 0.3, h * 0.7)
            boxed.append((x0, x1, top, bot))
        return ink, boxed


class Sheet:
    def __init__(self, base):
        self.img = base.copy().convert("RGBA")
        self.marks = []          # word boxes we may need later, for strike-throughs and scribbles

    def paste(self, strip, x_mm, y_mm, angle=0.0):
        """Paste a strip with its text baseline roughly at y_mm. Returns the strip's box in pixels."""
        if angle:
            strip = strip.rotate(angle, resample=Image.BICUBIC, expand=True)
        x, y = int(x_mm * PX), int(y_mm * PX - strip.height * 0.62)
        self.img.alpha_composite(strip, (max(0, x), max(0, y)))
        return (x, y, x + strip.width, y + strip.height)

    def write(self, text, writer, x_mm, y_mm, width_mm, max_lines=99, angle=0.0, line_gap=1.28):
        """Wrap and write. Returns (y below the text in mm, [(word, box px)])."""
        while True:   # never drop words: if it won't fit in max_lines, the writer writes smaller, as people do
            f = writer.font
            lines, cur = [], ""
            for w in text.split(" "):
                t = (cur + " " + w).strip()
                if f.getlength(t) * 1.12 > width_mm * PX and cur:
                    lines.append(cur); cur = w
                else:
                    cur = t
            lines.append(cur)
            too_wide = max(f.getlength(w) for w in text.split(" ")) * 1.12 > width_mm * PX
            if (len(lines) <= max_lines and not too_wide) or writer.size < 4:
                break
            writer = Writer(writer.font_key, writer.size * 0.85, writer.ink, writer.pen, writer.slant, writer.wobble,
                            seed=int(writer.rng.integers(1e6)))
        if len(lines) > max_lines:
            print(f"  warning: '{text}' needs {len(lines)} lines, allowed {max_lines}")
        boxes, y = [], y_mm
        for ln in lines:
            strip, spans = writer.line_image(ln)
            bx = self.paste(strip, x_mm + writer.rng.uniform(-2, 2), y + writer.rng.uniform(-1, 1), angle)
            for w, (a, b, t, bt) in zip(ln.split(" "), spans):
                boxes.append((w, (bx[0] + a, bx[1] + t, bx[0] + b, bx[1] + bt)))
            y += writer.size * line_gap
        return y, boxes

    def strike(self, box, ink="black", rng=None):
        d = ImageDraw.Draw(self.img)
        x0, y0, x1, y1 = box
        ym = (y0 + y1) / 2
        d.line([(x0 - 6, ym + 4), ((x0 + x1) / 2, ym - 3), (x1 + 6, ym + 2)], fill=INKS[ink] + (255,), width=9)

    def scribble(self, box, ink="black", cover=0.6, rng=None):
        """Zigzag over part of a word, the way people half-correct a mistake."""
        d = ImageDraw.Draw(self.img)
        x0, y0, x1, y1 = box
        x1 = x0 + (x1 - x0) * cover
        pts, x, up = [], x0, True
        while x < x1:
            pts.append((x, y0 if up else y1)); x += 11; up = not up
        d.line(pts, fill=INKS[ink] + (255,), width=6)

    def circle(self, box, ink="black"):
        x0, y0, x1, y1 = box
        ImageDraw.Draw(self.img).ellipse((x0 - 30, y0 - 25, x1 + 30, y1 + 20), outline=INKS[ink] + (255,), width=7)

    def arrow(self, a, b, ink="black"):
        d = ImageDraw.Draw(self.img)
        d.line([a, b], fill=INKS[ink] + (255,), width=7)
        v = np.array(b, float) - np.array(a, float); v /= np.linalg.norm(v); n = np.array([-v[1], v[0]])
        tip = np.array(b, float)
        d.polygon([tuple(tip), tuple(tip - v * 40 + n * 18), tuple(tip - v * 40 - n * 18)], fill=INKS[ink] + (255,))

    def tick(self, x_mm, y_mm, kind="tick", ink="black"):
        d = ImageDraw.Draw(self.img)
        x, y, s = x_mm * PX, y_mm * PX, 9 * PX
        c = INKS[ink] + (255,)
        if kind == "tick":
            d.line([(x + s * 0.1, y + s * 0.5), (x + s * 0.4, y + s * 0.9), (x + s * 1.1, y - s * 0.2)], fill=c, width=10)
        elif kind == "cross":
            d.line([(x, y), (x + s, y + s)], fill=c, width=9); d.line([(x + s, y), (x, y + s)], fill=c, width=9)
        elif kind == "fill":
            d.rectangle((x + 4, y + 4, x + s - 4, y + s - 4), fill=c)
        elif kind == "straddle":     # one tick across two boxes: genuinely ambiguous
            d.line([(x - s * 0.2, y + s * 0.5), (x + s * 0.6, y + s * 1.0), (x + s * 3.2, y - s * 0.4)], fill=c, width=10)

    def sticky(self, x_mm, y_mm, w_mm, h_mm, angle):
        note = Image.new("RGBA", (int(w_mm * PX), int(h_mm * PX)), (255, 236, 120, 255))
        sh = Image.new("RGBA", note.size, (0, 0, 0, 60)).filter(ImageFilter.GaussianBlur(8))
        self.img.alpha_composite(sh.rotate(angle, expand=True), (int(x_mm * PX) + 10, int(y_mm * PX) + 14))
        self.img.alpha_composite(note.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0)), (int(x_mm * PX), int(y_mm * PX)))


def render_pdf(pdf, width_px):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-png", "-singlefile", "-scale-to-x", str(width_px), "-scale-to-y", "-1",
                        str(pdf), f"{tmp}/p"], check=True)
        im = Image.open(f"{tmp}/p.png").convert("RGB")
        im.load()
        return im


# print/build_paper.py's output, matched on the end of the file name so a change of prefix doesn't break it
PAPER_FILES = {"S1": "sheet-S1-A1.pdf", "S2": "sheet-S2-A1.pdf", "S3": "sheet-S3-A1.pdf", "SS": "sheet-SS-A1.pdf",
               "card": "commitment-card-A5-perforated.pdf"}


def paper_pdf(key):
    hits = sorted(PAPER.glob("*" + PAPER_FILES[key]), key=lambda p: p.stat().st_mtime)
    return hits[-1] if hits else None     # the newest, if an old build with another prefix is still lying around


def preflight():
    """Stop before any work if something a fresh clone doesn't have yet is missing, and say how to get it."""
    def rel(p):
        return p.relative_to(ROOT)
    missing = [f for f in FONT_FILES.values() if not (FONTS / f).exists()]
    if missing:
        sys.exit(f"{len(missing)} of {len(FONT_FILES)} handwriting fonts are missing from {rel(FONTS)}/ "
                 f"({', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}).\n"
                 "Run python3 tests/hw/get_fonts.py first.")
    if not shutil.which("pdftoppm"):
        sys.exit("pdftoppm isn't installed (it rasterises the printed sheets). It comes with poppler:\n"
                 "  macOS: brew install poppler    Debian/Ubuntu: sudo apt install poppler-utils")
    absent = [PAPER_FILES[k] for k in PAPER_FILES if not paper_pdf(k)]
    if absent:
        sys.exit(f"The printed sheets aren't built yet: no {', '.join(absent)} in {rel(PAPER)}/.\n"
                 "Run python3 print/build_paper.py first.")
    if shutil.which("pdfinfo"):     # GEO was measured on one version of the sheets: say if they've moved on
        info = subprocess.run(["pdfinfo", str(paper_pdf("S1"))], capture_output=True, text=True).stdout
        v = re.search(r"^Title:.*\bv(\d+\.\d+\.\d+)", info, re.M)
        if v and v.group(1) not in GEO_VERSIONS:
            print(f"note: the printed sheets are v{v.group(1)}, but the handwriting positions (GEO) were checked "
                  f"on v{' and v'.join(GEO_VERSIONS)}.\n      Fine if no box has moved; look at a photo or two to be sure.")


def save_heic(im, path, quality=92):
    """Save as an iPhone would. Returns the HEIC path, or None when this machine can't write HEIC: that needs
    macOS's sips or the pillow-heif package (the same two the ingest uses to read it)."""
    target = path.with_suffix(".HEIC")
    if shutil.which("sips"):
        tmp = path.with_suffix(".tmp.jpg"); im.save(tmp, quality=quality)
        subprocess.run(["sips", "-s", "format", "heic", str(tmp), "--out", str(target)], check=True, capture_output=True)
        tmp.unlink()
        return target
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        im.save(target, format="HEIF", quality=quality)
        return target
    except Exception:          # not installed, or no HEIF encoder in this build
        target.unlink(missing_ok=True)
        return None


def base_sheets():
    """The four A1 sheets and the card, rendered and trimmed (no bleed)."""
    out = {}
    for code in ("S1", "S2", "S3", "SS"):
        im = render_pdf(paper_pdf(code), int(600 * PX))
        b = int(BLEED * PX)
        out[code] = im.crop((b, b, im.width - b, im.height - b))
    im = render_pdf(paper_pdf("card"), int(216 * PX * 2))
    b = int(BLEED * PX * 2)
    out["card"] = im.crop((b, b, im.width - b, im.height - b))
    return out


# ---------------------------------------------------------------- the test tables
# Each item: text as it should be transcribed, plus optional effects. GT is what a perfect reader writes.
#   strike=k   word k (0-based) crossed out: GT drops it        scribble=k  word k half scribbled: correct or flagged
#   insert=(k, "words")  caret before word k, words written small above: GT includes them
#   upside / vertical / circle / sticky / ink / pen / over   presentation only
#   gone=True  the whole item is crossed out: must NOT appear anywhere

PROFILES = {
    1: "Control: tidy marker, two writers, a good photo",
    2: "Hard hands: four messy and cursive handwriting styles, good photos",
    3: "Bad light: dim room, glare hotspot, phone shadow, steep angle",
    4: "Far and squashed: sheet small in the frame, then sent over WhatsApp (1600 px, heavy JPEG)",
    5: "Dense biro: small blue pen writing, lots of items crammed in",
    6: "Editing marks: crossings-out, scribbles, carets, arrows, circles, upside-down and sideways writing",
    7: "Jargon, numbers and names: WCAG refs, acronyms, money, URLs, an email, people and employers",
    8: "Colour and clutter: red, blue and green pens, sticky notes, a dried-out marker",
    9: "Photo coverage traps: table numbers disagree, a sheet in two halves, a duplicate, a missing sheet, sideways and HEIC files",
    10: "Day-like mix: several writers, moderate everything, empty boxes and an ambiguous tick",
}

T = {}

T[1] = dict(writers=[("patrick", 18, "black", "marker", 0.05), ("architect", 16, "black", "marker", -0.05)],
    tally={"Finance": 2, "Retail": 1, "Public sector": 2, "Tech": 1}, countries="UK, Ireland",
    S1=dict(challenges=["Accessibility seen as the a11y team's job only", "No budget until there's a complaint",
                        "Champions burn out", "Hard to prove impact to leadership", "Training doesn't stick"],
            top3=["No budget until a complaint", "Champions burn out", "Proving impact"],
            pick="Getting leaders to fund it before a complaint"),
    S2=dict(helped=["Showed a video of a real customer using a screen reader", "Tied it to our existing risk register"],
            hindered=["One big launch event then silence", dict(text="Audit reports nobody read", raw="Audit reports nobody ever read", strike=3)],
            lessons=["Start with one team that wants it, not the whole org"]),
    S3=[dict(action="Record 3 short customer videos", needs="Consent forms and a camera", sticks="Show one at every quarterly review", stages=["starting", "growing"]),
        dict(action="Add accessibility to the risk register", needs="Risk team contact", sticks="Reviewed with other risks each quarter", stages=["growing"])],
    SS=dict(quotes=["Nobody argues with a customer on video"], questions=["Who should own accessibility budget?"],
            resources=["W3C business case w3.org/WAI/business-case"], best="Show the customer, not the report"))

T[2] = dict(writers=[("reenie", 15, "black", "marker", 0.12), ("zeyada", 14, "black", "marker", -0.08),
                     ("nothing", 12, "black", "marker", 0.18), ("dawning", 13, "black", "marker", 0.0)],
    tally={"Tech": 3, "Health": 1, "Charity": 1}, countries="UK, Netherlands, Spain",
    S1=dict(challenges=["Designers think it limits creativity", "Developers fix the same bugs every sprint",
                        "Product owners deprioritise it", "No time for testing with disabled people",
                        "Leadership churn every year"],
            top3=["Same bugs every sprint", "Product owners deprioritise", "Leadership churn"],
            pick="Stopping the same bugs coming back every sprint"),
    S2=dict(helped=["Accessible components in the design system", "Pairing devs with a screen reader user"],
            hindered=["Linting rules switched off because they were noisy", "Fixing bugs without telling the team why"],
            lessons=["Fix it once in the component, not fifty times in the product"]),
    S3=[dict(action="Make the design system the default", needs="Buy-in from the platform team", sticks="Block merges that bypass it", stages=["growing", "established"]),
        dict(action="Monthly bug review with designers", needs="An hour and the bug list", sticks="Track repeat bugs on a chart", stages=["starting"]),
        dict(action="Turn the linting back on slowly", needs="One rule at a time", sticks="Add a rule each sprint", stages=["growing"])],
    SS=dict(quotes=["Every bug we fix in a component is fixed for good"], questions=["How do you stop people turning off lint rules?"],
            resources=["Fixing It Once book by Rowan Hale"], best="Fix it once in the component"))

T[3] = dict(writers=[("indie", 17, "black", "marker", 0.04), ("gochi", 18, "black", "marker", -0.06), ("shadows", 18, "black", "marker", 0.08)],
    tally={"Public sector": 4, "Education": 1}, countries="UK",
    S1=dict(challenges=["Procurement buys inaccessible software", "Suppliers say they're compliant but aren't",
                        "No one checks the VPAT", "Legacy systems nobody can change"],
            top3=["Procurement buys inaccessible software", "Suppliers overclaim", "Legacy systems"],
            pick="Making procurement check accessibility before buying"),
    S2=dict(helped=["Asked suppliers to demo with a keyboard only", "Put accessibility in the contract with penalties"],
            hindered=["Procurement saw it as a tick box", "Checking too late after the contract was signed"],
            lessons=["Get into procurement before the tender goes out"]),
    S3=[dict(action="Keyboard demo in every supplier pitch", needs="A short script for buyers", sticks="Make it part of the scoring", stages=["starting", "growing"]),
        dict(action="Accessibility clause in standard contracts", needs="Legal to agree wording", sticks="It's in the template so it's automatic", stages=["established"])],
    SS=dict(quotes=["If they can't demo it with a keyboard, they can't sell it to us"], questions=["Can we fail a supplier on accessibility alone?"],
            resources=["GOV.UK accessible procurement guidance"], best="Ask for a keyboard-only demo"))

T[4] = dict(writers=[("kalam", 17, "black", "marker", 0.0), ("caveat", 18, "black", "marker", 0.06)],
    tally={"Retail": 3, "Finance": 1, "Other": 1}, countries="UK, France",
    S1=dict(challenges=["Marketing campaigns launch with no checks", "Agencies don't know accessibility",
                        "Videos without captions", "Social media posts are images of text"],
            top3=["Campaigns launch unchecked", "Agencies", "No captions"],
            pick="Getting marketing to check before they launch"),
    S2=dict(helped=["A one page checklist for campaign sign-off", "Agency briefs that include accessibility"],
            hindered=["Deadlines always win", "Checklist too long so people skipped it"],
            lessons=["Keep the checklist to five items"]),
    S3=[dict(action="Five item launch checklist", needs="Marketing director to sign it off", sticks="No launch without it", stages=["starting"]),
        dict(action="Captions as default in the video brief", needs="Update the brief template", sticks="Agencies quote for it every time", stages=["starting", "growing"])],
    SS=dict(quotes=["Deadlines always win unless it's in the sign-off"], questions=["Who audits the agencies?"],
            resources=["Scope for Business marketing guide"], best="Five items or nobody reads it"))

T[5] = dict(writers=[("grace", 9, "biro", "biro", 0.05), ("justme", 9, "biro", "biro", 0.1), ("caveat", 8, "biro", "biro", -0.02)],
    tally={"Finance": 5, "Tech": 2, "Retail": 1}, countries="UK, Germany, Poland, India",
    S1=dict(challenges=["Release cadence too fast to test", "Testers not trained in assistive tech",
                        "Offshore teams have no context", "Automated tools miss half the issues",
                        "Bugs logged as low priority", "No definition of done for accessibility",
                        "Mobile apps behind web", "Third party widgets we can't fix",
                        "PDF statements inaccessible", "Chatbot vendor won't fix things",
                        "Leadership only care about the EAA", "Champions have no time allocated"],
            top3=["No definition of done", "Bugs logged as low priority", "Testers not trained"],
            pick="Adding accessibility to the definition of done"),
    S2=dict(helped=["Severity guide that maps to customer impact", "Accessibility in acceptance criteria templates",
                    dict(text="Weekly office hours with the specialist", raw="Weekly office hours with the main specialist", strike=5), "Showing bug ageing on a dashboard",
                    "Training testers with real assistive tech", "Shadowing a customer support call"],
            hindered=["Bugs downgraded to get releases out", "Criteria too vague to test",
                      "Specialist is a bottleneck", "Tools without training",
                      "Offshore team not invited to demos", "Too many tools at once"],
            lessons=["Write criteria a tester can actually check", "Agree severity before the release crunch"]),
    S3=[dict(action="Accessibility acceptance criteria in every story", needs="Story template change and examples", sticks="Refinement checks it before sprint", stages=["starting", "growing"]),
        dict(action="Severity guide based on customer impact", needs="Agreement from product and QA leads", sticks="Used in bug triage every week", stages=["growing"]),
        dict(action="Office hours twice a week", needs="Specialist time protected", sticks="Recorded and shared with offshore teams", stages=["growing", "established"])],
    SS=dict(quotes=["Low priority means never", "If a tester can't check it, it isn't a criterion"],
            questions=["How do you train offshore testers?", "Should accessibility bugs ever be low?"],
            resources=["Deque University", "Gov.uk service manual testing for accessibility"], best="Low priority means never"))

T[6] = dict(writers=[("gloria", 12, "black", "marker", 0.0), ("sueellen", 14, "black", "marker", 0.1), ("rocksalt", 11, "black", "marker", -0.04)],
    tally={"Charity": 2, "Public sector": 2, "Health": 2}, countries="UK, Ireland",
    S1=dict(challenges=[
        dict(text="Senior leaders say yes but do nothing"),
        dict(text="Accessibility really only in one team", raw="Accessibility only in one team", insert=(1, "really")),
        dict(text="We have no money for audits", gone=True),
        dict(text="No money for external audits"),
        dict(text="Staff with disabilities not asked", strike=4, raw="Staff with disabilities not ever asked"),
        dict(text="Our website CMS fights us", upside=True),
        dict(text="Burnout", circle=True)],
        top3=["Leaders say yes do nothing", "No money for audits", "Staff not asked"],
        pick="Turning senior yes into real action"),
    S2=dict(helped=[dict(text="Exec sponsor with a named objective"), dict(text="Staff network led the work", scribble=1)],
            hindered=[dict(text="Sponsor moved jobs and nobody replaced them"), dict(text="Objectives too vague", over=True)],
            lessons=[dict(text="Write the objective into the sponsor's appraisal")]),
    S3=[dict(action="Named sponsor objective", needs="HR and the exec's line manager", sticks="Checked in the annual appraisal", stages=["growing"], strike_needs=2, raw_needs="HR and also the exec's line manager"),
        dict(action="Disabled staff network sets priorities", needs="Budget for the network chair's time", sticks="They report to the board twice a year", stages=["starting", "growing", "established"])],
    SS=dict(quotes=["A yes without a deadline is a no"], questions=["What happens when the sponsor leaves?"],
            resources=[dict(text="Business Disability Forum", vertical=True)], best="A yes without a deadline is a no"),
    arrows=[("S1", 0, 6)], arrow_note="arrow from 'Senior leaders say yes but do nothing' to 'Burnout'")

T[7] = dict(writers=[("marker", 13, "black", "marker", 0.0), ("caveat", 17, "black", "marker", 0.05), ("homemade", 11, "black", "marker", 0.15)],
    tally={"Finance": 3, "Tech": 2}, countries="UK, USA, Israel",
    S1=dict(challenges=["EAA deadline June 2025 already passed", "WCAG 2.2 AA vs 2.1 AA confusion",
                        dict(text="ARIA misused everywhere", raw="ARIA misused almost everywhere", strike=2), "VPATs out of date", "SC 1.4.3 contrast fails in brand colours",
                        "Only 3 of 40 squads have a champion"],
            top3=["Brand colours fail 1.4.3", "ARIA misuse", "3 of 40 squads"],
            pick="Brand colours that fail WCAG contrast"),
    S2=dict(helped=["Brand team got a 4.5:1 palette approved", "Priya at Halcyon Bank ran the design token change",
                    "Saved 15% of design QA time"],
            hindered=["£40k rebrand already printed", "Marketing overrode the tokens"],
            lessons=["Fix colours in tokens, not per page"]),
    S3=[dict(action="Contrast-safe token set", needs="Brand sign-off and 2 sprints", sticks="Tokens are the only source of colour", stages=["growing", "established"]),
        dict(action="Run axe-core in CI on every PR", needs="DevOps 1 day", sticks="Build fails on new contrast issues", stages=["starting", "growing"])],
    SS=dict(quotes=["We spent £40k printing a palette that fails AA"],
            questions=["Does the EAA cover our B2B portal?"],
            resources=["webaim.org/resources/contrastchecker", "email tom.okafor@meridianlabs.example for the token repo"],
            best="Fix it in the tokens"))

T[8] = dict(writers=[("sunrise", 17, "red", "marker", 0.05), ("aurore", 15, "blue", "marker", 0.12),
                     ("indie", 17, "green", "marker", -0.03), ("patrick", 18, "faint", "fat", 0.0)],
    tally={"Education": 3, "Public sector": 1, "Charity": 1}, countries="UK, Scotland, Wales",
    S1=dict(challenges=["Lecturers make inaccessible slides", dict(text="Captions on lecture recordings are poor", raw="Captions on lecture recordings are really poor", strike=5),
                        "Students have to ask for adjustments every term", "Virtual learning environment is a maze"],
            top3=["Inaccessible slides", "Asking every term", "VLE maze"],
            pick="Students having to ask for the same adjustments every term"),
    S2=dict(helped=[dict(text="Adjustments passport that follows the student"), dict(text="Template slide decks with good contrast", sticky=True)],
            hindered=[dict(text="Each department has its own process"), dict(text="Passport not shared with exam office", sticky=True)],
            lessons=["Agree one process before buying a system"]),
    S3=[dict(action="Adjustments passport pilot", needs="Student services and two departments", sticks="Renewed automatically each year", stages=["starting"]),
        dict(action="Accessible slide template for all staff", needs="Comms team design time", sticks="Default in PowerPoint for everyone", stages=["starting", "growing"])],
    SS=dict(quotes=[dict(text="I spend the first week of every term proving I'm still disabled", sticky=True)],
            questions=["Who owns the passport data?"], resources=["Jisc accessibility guidance"],
            best="Tell us once"))

T[9] = dict(writers=[("kalam", 17, "black", "marker", 0.0), ("shadows", 18, "black", "marker", 0.05)],
    number_circle=9, number_footer=8,          # the lead wrote 8 in the footer by mistake
    tally={"Health": 4, "Public sector": 1}, countries="UK",
    S1=dict(challenges=["Patient letters not in accessible formats", "Clinicians too busy for training",
                        "Booking system fails screen readers", "Easy read takes months"],
            top3=["Patient letters", "Booking system", "Easy read"],
            pick="Getting patient letters into accessible formats"),
    S2=dict(helped=["Flag on the patient record for format needs", "Partnered with a local easy read group",
                    "Large print as a default option"],
            hindered=["Flags ignored by agency staff", "Printing done by a different trust"],
            lessons=["Fix the record first, then the letters"]),
    S3=[dict(action="Format flag on every patient record", needs="IT change request", sticks="Audit 20 letters a month", stages=["growing"]),
        dict(action="Easy read partnership", needs="Small budget and a contract", sticks="Annual renewal with the group", stages=["starting"])],
    SS=dict(quotes=["The letter about your appointment is the appointment if you can't read it"],
            questions=["Does the Accessible Information Standard have teeth?"],
            resources=["NHS Accessible Information Standard"], best="Fix the record first"))

T[10] = dict(writers=[("patrick", 17, "black", "marker", 0.06), ("gochi", 18, "black", "marker", -0.05),
                      ("reenie", 19, "black", "marker", 0.1), ("kalam", 16, "blue", "marker", 0.0)],
    tally={"Tech": 2, "Retail": 2, "Finance": 1, "Other": 1}, countries="UK, Sweden",
    S1=dict(challenges=["Accessibility is someone's side job", "No metrics leadership cares about",
                        "We test too late", "Teams don't know where to start"],
            top3=["Side job", "No metrics", "Test too late"],
            pick="Making accessibility someone's actual job"),
    S2=dict(helped=["Got a role written into the org chart"], hindered=["Volunteers only", "Job description too broad"],
            lessons=[]),
    S3=[dict(action="Write a one page role proposal", needs="Examples from other companies", sticks="Review it at budget planning", stages=["starting"], tick="straddle")],
    SS=dict(quotes=["Side jobs get side effort"], questions=[], resources=[], best=""))

CARDS = [
    dict(text="Run a keyboard-only test on our checkout this month", name="Sam Patel", org="Brightway Retail", font="patrick"),
    dict(text="Ask procurement to add a keyboard demo to supplier pitches", font="kalam"),
    dict(text="Share one customer video with my director", name="Aoife", font="indie"),
    dict(text="Turn on one lint rule a sprint", org="Northgate Insurance", font="gochi"),
    dict(text="Book a session with our disabled staff network", font="reenie"),
    dict(text="Put accessibility in our definition of done", name="Jo Mbeki", org="Fernhollow Telecom", font="caveat", pen="biro", ink="biro", size=6),
    dict(text="Ask Dan in legal about contract clauses", font="shadows", note="a name inside the commitment is not consent: keep it in raw, verify flags it later"),
    dict(text="Fix our brand colours in the design tokens", name="Priya R", font="zeyada"),
    dict(text="Stop calling it a nice to have", font="marker", size=7),
    dict(text="Pilot an adjustments passport with two departments", org="University of Eastmoor", font="homemade", size=6),
    dict(text="Make a five item launch checklist", font="sueellen", strike_word=2, raw="Make a short five item launch checklist"),
    dict(text="Talk to my manager about time for being a champion", name="Rhys", font="sunrise"),
    dict(text="Present one fix at the all hands", font="rocksalt", size=6),
    dict(text="Find out who owns the accessibility budget", font="grace"),
    dict(text="Ask for captions in every video brief", name="M. Okonkwo", org="Lark & Finch Agency", font="gloria"),
    dict(text="Test our app with VoiceOver for an hour", font="aurore", ink="blue"),
]


# ---------------------------------------------------------------- writing one table's sheets

def as_item(x):
    return x if isinstance(x, dict) else dict(text=x)


def number(sheet, n_circle, n_footer, w):
    sheet.write(str(n_circle), Writer(w.font_key, 40, w.ink, "fat", 0, 0.6, seed=n_circle), GEO["circle"][0] - 9, GEO["circle"][1] + 18, 60)
    sheet.write(str(n_footer), Writer(w.font_key, 12, w.ink, "marker", 0, 0.5, seed=n_footer + 50), GEO["footer"][0] + 4, GEO["footer"][1] - 2, 30)


def write_items(sheet, items, writers, x, y, w, bottom, rng, truth, key, effects_log):
    for i, raw in enumerate(items):
        it = as_item(raw)
        wr = writers[i % len(writers)]
        if it.get("ink"):
            wr = Writer(wr.font_key, wr.size, it["ink"], wr.pen, wr.slant, wr.wobble, seed=i + 99)
        shown = it.get("raw", it["text"])
        if it.get("sticky"):
            sx, sw = x + rng.uniform(0, 12), min(w - 14, 120)
            small = Writer(wr.font_key, wr.size * 0.6, wr.ink, wr.pen, wr.slant, seed=i + 77)
            n_lines = int(small.font.getlength(shown) * 1.25 // ((sw - 12) * PX)) + 1
            sh_h = max(70, n_lines * small.size * 1.28 + 22)
            sheet.sticky(sx, y - 6, sw, sh_h, rng.uniform(-3, 3))
            yy, boxes = sheet.write(shown, small, sx + 5, y + 12, sw - 12)
            y = max(yy, y - 6 + sh_h) + 10
            effects_log.append(f"{key}: sticky note '{it['text']}'")
        elif it.get("upside"):
            strip, _ = wr.line_image(shown)
            sheet.paste(strip, x + 20, y + 6, angle=180 + rng.uniform(-3, 3))
            y += wr.size * 1.5
            effects_log.append(f"{key}: written upside down '{it['text']}'")
            boxes = []
        elif it.get("vertical"):
            strip, _ = wr.line_image(shown)
            sheet.paste(strip, x + w - 12, y + 150, angle=90)
            effects_log.append(f"{key}: written sideways up the box '{it['text']}'")
            boxes = []
        else:
            xx = x + (w * 0.55 if it.get("over") else 0)
            yy, boxes = sheet.write(("- " if key.startswith("S1.ch") else "") + shown, wr, xx, y, w + (60 if it.get("over") else 0))
            y = yy + 5
        words = boxes[1:] if key.startswith("S1.ch") and boxes else boxes
        if it.get("copied"):   # round 3: people copy the printed prompt into the box (seen in real photos)
            truth.setdefault("copied", []).append(shown)
            effects_log.append(f"{key}: printed prompt copied into the box '{shown}' (not an item)")
            continue
        if it.get("ink") in ("yellow", "highlighter", "orange"):
            truth["flag_ok"].append(it["text"])
            effects_log.append(f"{key}: written in {it['ink']} '{it['text']}' (correct or flagged)")
        if it.get("gone") and words:
            for _, b in words:
                sheet.strike(b, wr.ink)
            effects_log.append(f"{key}: whole item crossed out '{shown}' (must not appear)")
            truth["gone"].append(shown)
            continue
        if "strike" in it and words:
            sheet.strike(words[it["strike"]][1], wr.ink)
            effects_log.append(f"{key}: word crossed out in '{shown}'")
        if "scribble" in it and words:
            sheet.scribble(words[it["scribble"]][1], wr.ink)
            truth["flag_ok"].append(it["text"])
            effects_log.append(f"{key}: word half scribbled in '{it['text']}' (correct or flagged)")
        if "insert" in it and words:
            k, ins = it["insert"]
            bx = words[k][1]
            d = ImageDraw.Draw(sheet.img)
            cx, by = bx[0] - 12, bx[3] + 8
            d.line([(cx - 18, by + 18), (cx, by - 8), (cx + 18, by + 18)], fill=INKS[wr.ink] + (255,), width=6)
            small = Writer(wr.font_key, wr.size * 0.7, wr.ink, wr.pen, wr.slant, seed=7)
            strip, _ = small.line_image(ins)
            sheet.img.alpha_composite(strip, (int(cx - strip.width / 2), int(bx[1] - strip.height * 0.75)))
            effects_log.append(f"{key}: caret insertion '{ins}' in '{it['text']}'")
        if it.get("circle") and words:
            sheet.circle((words[0][1][0], words[0][1][1], words[-1][1][2], words[-1][1][3]), wr.ink)
            effects_log.append(f"{key}: circled '{it['text']}'")
        if it.get("over"):
            effects_log.append(f"{key}: runs over the box edge '{it['text']}'")
        if y > bottom + 4:
            print(f"  warning: table {truth['table']} {key} runs {y - bottom:.0f} mm past its box")
        truth.setdefault(key, []).append(it["text"])
        if words:
            truth["_boxes"].setdefault(key, []).append((words[0][1], words[-1][1]))
    return y


def make_table(n, spec, bases, rng):
    global SIZE_BOOST
    SIZE_BOOST = 1.45
    writers = [Writer(f, s, ink, pen, sl, seed=n * 10 + i) for i, (f, s, ink, pen, sl) in enumerate(spec["writers"])]
    truth = {"table": n, "profile": PROFILES[n], "gone": [], "flag_ok": [], "effects": [], "_boxes": {}}
    sheets = {}
    nc, nf = spec.get("number_circle", n), spec.get("number_footer", n)
    if nc != nf:
        truth["effects"].append(f"table number written as {nc} in the circle but {nf} in the footer (should be noted)")

    # S1
    s = Sheet(bases["S1"]); number(s, nc, nf, writers[0])
    tally_inks = spec.get("tally_inks", ["black"])   # round 3: several pens, gates drawn through other people's strokes
    for si, (sec, k) in enumerate(spec["tally"].items()):
        bx, by, bw, bh = GEO["S1"]["tally_boxes"][SECTORS.index(sec)]
        d = ImageDraw.Draw(s.img)
        for j in range(k):
            ink = INKS[tally_inks[(j + si) % len(tally_inks)]] + (255,)
            if j == 4:
                d.line([((bx + 4) * PX, (by + 30) * PX), ((bx + 6 + 4 * 5) * PX, (by + 10) * PX)], fill=ink, width=7)
            else:
                x0 = (bx + 6 + j * 5) * PX
                d.line([(x0, (by + 8) * PX), (x0 + rng.uniform(-6, 6), (by + 32) * PX)], fill=ink, width=7)
    s.write(spec["countries"], writers[0], *GEO["S1"]["countries"], 440)
    truth["tally"], truth["countries"] = spec["tally"], spec["countries"]
    x, y, w, h = GEO["S1"]["challenges"]
    # two columns when the list is long, the way people use a wide box
    items = spec["S1"]["challenges"]
    if len(items) > 4:
        half = (len(items) + 1) // 2
        write_items(s, items[:half], writers, x, y, w / 2 - 10, y + h, rng, truth, "S1.challenges", truth["effects"])
        write_items(s, items[half:], writers[1:] + writers[:1], x + w / 2, y, w / 2 - 10, y + h, rng, truth, "S1.challenges", truth["effects"])
    else:
        write_items(s, items, writers, x, y, w, y + h, rng, truth, "S1.challenges", truth["effects"])
    for i, t3 in enumerate(spec["S1"]["top3"]):
        tx, ty = GEO["S1"]["top3"][i]
        s.write(t3, writers[(i + 1) % len(writers)], tx, ty - 6, 230, max_lines=1)
    truth["S1.top3"] = spec["S1"]["top3"]
    px, py = GEO["S1"]["pick"][0]
    s.write(spec["S1"]["pick"], writers[0], px, py - 6, 190, line_gap=1.7)
    truth["S1.pick"] = "" if spec["S1"].get("pick_copied") else spec["S1"]["pick"]
    if spec["S1"].get("pick_copied"):
        truth["effects"].append(f"S1 pick box holds the copied heading '{spec['S1']['pick']}' (no pick)")
    if spec.get("arrows"):   # from the first challenge to the last one written (Burnout)
        bx = truth["_boxes"]["S1.challenges"]
        s.arrow((bx[0][1][2] + 20, bx[0][1][3] - 10), (bx[-1][0][0] - 40, bx[-1][0][1] + 20))
        truth["effects"].append(spec["arrow_note"] + " (should be noted)")
    sheets["S1"] = s

    # S2
    s = Sheet(bases["S2"]); number(s, nc, nf, writers[0])
    for key in ("helped", "hindered", "lessons"):
        x, y, w, h = GEO["S2"][key]
        write_items(s, spec["S2"][key], writers if key != "hindered" else writers[1:] + writers[:1], x, y, w, y + h, rng, truth, f"S2.{key}", truth["effects"])
    sheets["S2"] = s

    # S3
    s = Sheet(bases["S3"]); number(s, nc, nf, writers[0])
    truth["S3.actions"] = []
    for i, act in enumerate(spec["S3"]):
        top = GEO["S3"]["rows"][i]
        wr = writers[i % len(writers)]
        (cx0, cw0), (cx1, cw1), (cx2, cw2) = GEO["S3"]["cols"]
        s.write(act["action"], wr, cx0, top + 60, cw0, max_lines=4)
        _, nb = s.write(act.get("raw_needs", act["needs"]), wr, cx1, top + 60, cw1, max_lines=5)
        if "strike_needs" in act:
            s.strike(nb[act["strike_needs"]][1], wr.ink)
            truth["effects"].append(f"S3: word crossed out in needs '{act['raw_needs']}'")
        s.write(act["sticks"], wr, cx2, top + 60, cw2, max_lines=5)
        if act.get("copied"):
            truth.setdefault("copied", []).extend([act["action"], act["needs"], act["sticks"]])
            truth["effects"].append(f"S3 row {i + 1}: printed prompts copied into the row (not an action)")
            continue
        names = {"starting": 0, "growing": 1, "established": 2}
        tick_top = top + GEO["S3"]["row_h"] - 25
        if act.get("tick") == "straddle":
            s.tick(GEO["S3"]["ticks"][0], tick_top, "straddle", wr.ink)
            truth["effects"].append("S3 action 1: one tick drawn across 'Just starting' and 'Growing' (should be flagged)")
        else:
            kinds = ["tick", "cross", "fill"]
            for st in act["stages"]:
                s.tick(GEO["S3"]["ticks"][names[st]], tick_top, kinds[(n + i) % 3], wr.ink)
        truth["S3.actions"].append({k: act[k] for k in ("action", "needs", "sticks", "stages")} | {"ambiguous_tick": act.get("tick") == "straddle"})
    sheets["S3"] = s

    # SS
    s = Sheet(bases["SS"]); number(s, nc, nf, writers[0])
    for key in ("quotes", "questions", "resources"):
        x, y, w, h = GEO["SS"][key]
        items = [as_item(q) for q in spec["SS"][key]]
        if key == "quotes":
            items = [dict(it, raw="“" + it["text"] + "”") if not it.get("sticky") else it for it in items]
        write_items(s, items, writers[["quotes", "questions", "resources"].index(key) % len(writers):] + writers, x, y, w, y + h, rng, truth, f"SS.{key}", truth["effects"])
    if spec["SS"]["best"]:
        x, y, w, h = GEO["SS"]["best"]
        s.write(spec["SS"]["best"], writers[-1], x, y + 10, w, max_lines=2)
    truth["SS.best"] = spec["SS"]["best"]
    sheets["SS"] = s
    truth.pop("_boxes")
    return sheets, truth


def make_cards(base, rng):
    """Right halves only (the half people hand in), eight to a photo on a table top."""
    global SIZE_BOOST
    SIZE_BOOST = 1.15
    W_, H_ = base.size
    half = base.crop((W_ // 2, 0, W_, H_)).convert("RGBA")
    k = 2 * PX / PX   # card rendered at 2x PX per mm
    cards, truth = [], []
    for i, c in enumerate(CARDS):
        im = half.copy()
        sheet = Sheet(im)
        wr = Writer(c["font"], c.get("size", 6), c.get("ink", "black"), c.get("pen", "marker"), rng.uniform(-0.05, 0.12), seed=300 + i)
        # card coordinates are mm from the card's left edge; the half starts at 105 mm, and the card is at 2x scale
        def at(x_mm, y_mm):
            return (x_mm - 105) * 2, y_mm * 2
        wr2 = Writer(wr.font_key, wr.size * 2, wr.ink, wr.pen, wr.slant, seed=300 + i)
        x, y = at(*GEO["card"]["lines"][0])
        _, boxes = sheet.write(c.get("raw", c["text"]), wr2, x, y - 2, 2 * 85, line_gap=9 / wr.size)
        if "strike_word" in c:
            sheet.strike(boxes[c["strike_word"]][1], wr.ink)
        if c.get("name"):
            sheet.write(c["name"], wr2, *at(GEO["card"]["name"][0], GEO["card"]["name"][1] - 1), 2 * 55, max_lines=1)
        if c.get("org"):
            sheet.write(c["org"], wr2, *at(GEO["card"]["org"][0], GEO["card"]["org"][1] - 1), 2 * 46, max_lines=1)
        cards.append(sheet.img.convert("RGB"))
        truth.append({k: c[k] for k in ("text", "name", "org", "note") if k in c})
    return cards, truth


# ---------------------------------------------------------------- photographing

def photograph(img, rng, wall=(196, 192, 184), fill=0.84, keystone=0.035, light=1.0, glare=0.0, shadow=0.0,
               blur=0.7, motion=0, noise=4.5, size=(3024, 4032), crop=None, rot=2.5):
    """Pin a sheet to the wall and take a phone photo of it, with whatever went wrong this time."""
    img = img.convert("RGB")
    if crop:
        w, h = img.size
        img = img.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    bw, bh = size
    if img.width > img.height and bw < bh:
        bw, bh = bh, bw
    scale = min(bw * fill / img.width, bh * fill / img.height)
    sw, sh = int(img.width * scale), int(img.height * scale)
    s = img.resize((sw, sh), Image.LANCZOS)
    j = lambda: rng.uniform(-keystone, keystone) * sw
    quad = (j(), j(), j(), sh + j(), sw + j(), sh + j(), sw + j(), j())
    s = s.transform((sw, sh), Image.QUAD, quad, Image.BICUBIC, fillcolor=wall)
    bg = Image.new("RGB", (bw, bh), wall)
    ox, oy = (bw - sw) // 2 + int(rng.uniform(-50, 50)), (bh - sh) // 2 + int(rng.uniform(-60, 60))
    bg.paste(s, (ox, oy))
    bg = bg.rotate(rng.uniform(-rot, rot), resample=Image.BICUBIC, fillcolor=wall)
    a = np.asarray(bg).astype(np.float32)
    yy, xx = np.mgrid[0:bh, 0:bw]
    lmap = 0.86 + 0.18 * (1 - ((xx - bw * rng.uniform(0.3, 0.7)) ** 2 + (yy - bh * 0.35) ** 2) / (bw ** 2 + bh ** 2))
    lmap *= light
    if shadow:   # the phone's own shadow, a soft dark band across part of the sheet
        band = np.clip(1 - np.abs((xx * 0.4 + yy) - bh * rng.uniform(0.4, 0.6)) / (bh * 0.18), 0, 1)
        lmap *= 1 - shadow * band
    a = a * lmap[..., None]
    if glare:    # overhead light reflecting off the paper
        gx, gy = bw * rng.uniform(0.3, 0.7), bh * rng.uniform(0.25, 0.5)
        g = np.exp(-(((xx - gx) / (bw * 0.12)) ** 2 + ((yy - gy) / (bh * 0.07)) ** 2))
        a = a + glare * 255 * g[..., None]
    a = a + rng.normal(0, noise, a.shape)
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if motion:
        from scipy.ndimage import uniform_filter1d
        out = Image.fromarray(uniform_filter1d(np.asarray(out), motion, axis=1))
    return out.filter(ImageFilter.GaussianBlur(blur)) if blur else out


SHOTS = {   # per-table photo conditions
    1: {}, 2: {}, 6: {}, 7: {}, 10: dict(keystone=0.05, light=0.92),
    3: dict(light=0.55, glare=0.55, shadow=0.45, keystone=0.09, noise=9, rot=5),
    4: dict(fill=0.5, whatsapp=True),
    5: dict(fill=0.88),
    8: dict(light=0.85, keystone=0.05),
    9: {},
}


def save(im, path, quality=88, exif_rotate=False, heic=False):
    """Returns the file actually written: a HEIC request falls back to JPEG where HEIC can't be made."""
    if exif_rotate:
        exif = Image.Exif(); exif[0x0112] = 6
        im.rotate(90, expand=True).save(path, quality=quality, exif=exif)
        return path
    if heic:
        written = save_heic(im, path)
        if written:
            return written
        print(f"  note: can't write HEIC here (needs macOS or pip install pillow-heif), so {path.name} is a JPEG "
              "and the HEIC trap is skipped")
    im.save(path, quality=quality)
    return path


def main():
    preflight()
    rng = np.random.default_rng(13112026)   # fixed seeds: every run makes the same photos and answer key
    random.seed(13112026)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    bases = base_sheets()
    truth = {"tables": {}, "cards": [], "photos": {}, "expect": {}}
    n_img = 7100
    shots = []
    for n, spec in T.items():
        sheets, tt = make_table(n, spec, bases, rng)
        truth["tables"][n] = tt
        cond = dict(SHOTS[n])
        whatsapp = cond.pop("whatsapp", False)
        for code, sh in sheets.items():
            if n == 9 and code == "S1":
                truth["expect"]["missing"] = ["T09 S1"]
                continue                      # never photographed
            if n == 9 and code == "S2":       # only two overlapping halves, no whole shot
                for part, box in (("top", (0, 0, 1, 0.58)), ("bottom", (0, 0.42, 1, 1))):
                    shots.append(dict(im=photograph(sh.img, rng, crop=box), table=n, sheet=code, kind=f"half ({part})"))
                continue
            im = photograph(sh.img, rng, **cond)
            if whatsapp:
                im.thumbnail((1600, 1600))
            shots.append(dict(im=im, table=n, sheet=code, kind="whole", whatsapp=whatsapp,
                              exif=(n == 9 and code == "SS"), heic=(n == 9 and code == "S3")))
            if n == 9 and code == "S3":       # plus a close-up of the top half
                shots.append(dict(im=photograph(sh.img, rng, crop=(0, 0, 1, 0.5)), table=n, sheet=code, kind="close-up"))
            if n == 3 and code == "S2":       # a shaky retake alongside the good one
                shots.append(dict(im=photograph(sh.img, rng, motion=31, **cond), table=n, sheet=code, kind="shaky duplicate"))
                truth["expect"]["blurry"] = "the T03 S2 shaky duplicate"
    cards, ct = make_cards(bases["card"], rng)
    truth["cards"] = ct
    for g in range(2):
        table_top = Image.new("RGB", (4032, 3024), (128, 94, 64))
        for k, c in enumerate(cards[g * 8:(g + 1) * 8]):
            c = c.copy(); c.thumbnail((880, 1240))
            c = c.rotate(rng.uniform(-8, 8), expand=True, fillcolor=(128, 94, 64))
            table_top.paste(c, (60 + (k % 4) * 990, 120 + (k // 4) * 1450))
        a = np.asarray(table_top).astype(np.float32) + rng.normal(0, 4, (3024, 4032, 3))
        shots.append(dict(im=Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), table=None, sheet="stubs",
                          kind=f"cards {g * 8 + 1} to {g * 8 + 8}"))
    random.shuffle(shots)
    for sh in shots:
        n_img += 1
        written = save(sh["im"], OUT / f"IMG_{n_img}.JPG", quality=55 if sh.get("whatsapp") else 88,
                       exif_rotate=sh.get("exif", False), heic=sh.get("heic", False))
        name, heic = written.name, written.suffix == ".HEIC"
        truth["photos"][name] = {k: v for k, v in sh.items() if k in ("table", "sheet", "kind")} | (
            {"whatsapp": True} if sh.get("whatsapp") else {}) | ({"exif_rotated": True} if sh.get("exif") else {}) | ({"heic": True} if heic else {})
    truth["profiles"] = PROFILES
    (HERE / "truth.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False))
    print(f"{len(shots)} photos in {OUT.relative_to(ROOT)}/, answer key in {(HERE / 'truth.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
