#!/usr/bin/env python3
"""Print-ready paper kit: four A1 sheets, an A5 commitment card and A4 table cards that fold into A5 tents.

    python3 print/build_paper.py                          # writes print/out/paper/ and the zip in print/out/
    python3 print/build_paper.py --config my.config.json  # another settings file (see build/config.py)
    python3 print/build_paper.py --tables 8               # table cards for tables 1 to 8
    python3 print/build_paper.py --no-qr                  # a "Your QR code here" box instead of a QR code
    python3 print/build_paper.py --no-optional            # leaves out the tally strip (S1) and best-thing box (SS)

Names, colours, logo and the QR code's address come from the settings file. Design choices worth keeping:
the commitment card is A5 and perforated, with room for an optional name and organisation; the table card has
"Table" above the number; the A1 sheets have the table number written on by hand, so one print run covers every
table. Table cards are A4, printed one side and folded in half into an A5 tent, with the logo in the bottom-left
corner of both faces. The wording matches the fill-in HTML versions in build_sheets_html.py: change both together.
"""
import argparse, sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from pdfkit import BLACK, MM, WHITE, Page, svg_paths, write
import pdfkit  # noqa: E402  use_fonts, cap_height

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import formats  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "paper"
VERSION = "1.4.0"
BLEED = 3
HINT = (0, 0, 0, 0.72)     # 72% black: clearly secondary, but far darker than the usual 50% grey hint
RULE = (0, 0, 0, 0.45)     # write-on lines and fold marks

# Output file names, shared with build_sheets_html.py (its "Print-ready PDF" links) and build/build.py (the kit list)
SHEET_PDF = "sheet-{code}-A1.pdf"
CARD_PDF = "commitment-card-A5-perforated.pdf"
TABLES_PDF = "table-cards-A4-fold-to-A5-tables-1-to-{n}.pdf"
SHEET_LAYOUT = "sheet-{code}-A1.layout.json"
ZIP = "paper-kit-print-files-v{version}.zip"


# ---------------------------------------------------------------- settings

def readable(fg, bg, need=4.5):
    """fg if it reads on bg; otherwise fg pushed toward black or white (whichever bg suits) until it does."""
    if config.contrast(fg, bg) >= need:
        return fg
    target = "#000000" if config.contrast("#000000", bg) >= config.contrast("#ffffff", bg) else "#ffffff"
    return config.toward(fg, target, bg, need)


def address(url):
    """The playbook's address as people would type it: no scheme, no trailing slash, the path kept if there is one."""
    u = urlparse(url if "://" in url else "https://" + url)
    return (u.netloc + u.path).rstrip("/")


def kit_settings(cfg, qr_url, W=None):
    """Everything the artwork needs from the settings: colours as CMYK, the logo or wordmark, names and the QR.
    W is the workshop: what a group is called on the sheets ("Table", "Team") and whether names are kept off them."""
    b = cfg["brand"]
    acc, hi = b["accent"], b["highlight"]
    # an optional brand.cmyk {"accent": [c, m, y, k], "highlight": [...]} keeps values a printer has already proofed
    exact = b.get("cmyk") or {}
    ink = lambda name, hexval: tuple(exact[name]) if exact.get(name) else config.hex_to_cmyk(hexval)
    k = SimpleNamespace(warnings=[])
    k.accent = ink("accent", acc)                         # header band, circle, logo
    k.highlight = ink("highlight", hi)                    # the commitment card
    k.tint = config.hex_to_cmyk(config.mix(acc, "#ffffff", 0.93))   # pale fill for the optional boxes
    on_band = max(("#ffffff", "#000000"), key=lambda c: config.contrast(c, acc))
    k.on_band = config.hex_to_cmyk(on_band)
    k.band_label = k.highlight if config.contrast(hi, acc) >= 4.5 else k.on_band
    # text in the brand colour, darkened only if the accent is too light to read on white paper
    acc_text = readable(acc, "#ffffff")
    k.accent_text = k.accent if acc_text == acc else config.hex_to_cmyk(acc_text)
    card_prompt = readable(acc, hi)
    k.card_prompt = k.accent if card_prompt == acc else config.hex_to_cmyk(card_prompt)
    # the dashed box edges: a grey with a hint of the brand, at least 3:1 against both white and the tint
    k.dash = config.hex_to_cmyk(readable(config.mix(acc, "#808080", 0.55), config.mix(acc, "#ffffff", 0.93), 3.0))
    # the card's small print is black, unless the highlight is too dark for it (then no ink: the paper shows through)
    k.card_ink = BLACK if config.contrast("#000000", hi) >= 4.5 else WHITE
    k.logo = config.logo_path(cfg, "secondary") or config.logo_path(cfg, "primary")
    # a logo in its own colours keeps them on paper too (each shape's fill, converted to CMYK); otherwise it's
    # printed in the accent colour
    k.logo_colours = config.hex_to_cmyk if (cfg["brand"].get("logo") or {}).get("keep_colours") else None
    if k.logo and k.logo.suffix.lower() != ".svg":
        k.warnings.append(f"{k.logo.name} isn't an SVG, and the print kit draws logos as vector shapes, so the wordmark stands in")
        k.logo = None
    if k.logo:
        try:
            svg_paths(k.logo)
        except (OSError, ValueError) as err:
            k.warnings.append(f"can't draw the logo ({err}), so the wordmark stands in")
            k.logo = None
    k.wordmark = cfg["org"]["short"] or cfg["playbook"]["name"]
    k.name = cfg["playbook"]["name"]
    k.qr_url = qr_url
    k.qr_text = address(qr_url) if qr_url else ""    # printed beside the code for anyone who can't scan it
    k.group = (W.group if W else "table").capitalize()
    k.public = (W.privacy if W else "public") == "public"
    return k


# ---------------------------------------------------------------- shared pieces

def logo(p, k, x, y, h, max_w, baseline=None, colour=None):
    """The logo file in the accent colour (or its own colours, with brand.logo.keep_colours), or the wordmark in its
    place: the org's short name (or the playbook's name) in the brand font's Bold, sized to the same box. `colour` is the wordmark's, for a background other than white.
    Returns the width used."""
    if k.logo:
        vb, _ = svg_paths(k.logo)
        w = min(h * vb[2] / vb[3], max_w)
        return p.svg("art", k.logo, x, y, w=w, fill=k.accent, colours=k.logo_colours)[0]
    cap = pdfkit.cap_height("Bold")      # the brand font's capital height, as a share of the font size (Poppins: 0.7)
    size_mm = 0.5 * h / cap              # capitals half the logo's height, like the lettering in a logo lockup
    size_mm = min(size_mm, size_mm * max_w / p.text_width(k.wordmark, size_mm * MM, "Bold"))
    if baseline is None:
        baseline = y + h / 2 + size_mm * cap / 2       # capitals centred in the box
    return p.text("art", k.wordmark, x, baseline, size_mm * MM, "Bold", colour or k.accent_text)


def checkbox(p, x, y, size, label, pt, gap=3):
    """A drawn tick box (Poppins has no ☐ glyph) with its label; returns the x after the label."""
    p.rrect("art", x, y - size, size, size, size * 0.12, stroke=BLACK, width=0.5)
    return x + size + gap + p.text("art", label, x + size + gap, y - size * 0.12, pt, "Regular", BLACK)


def write_lines(p, x0, x1, y, n, gap):
    for i in range(n):
        p.line("art", x0, y + i * gap, x1, y + i * gap, stroke=RULE, width=0.5)


# ---------------------------------------------------------------- A1 sheets

A1 = (594, 841)
M = 34                     # outer margin


def zone(p, k, x, y, w, h, title, hint=None, tint=False, title_pt=44, hint_pt=26, box=None, n=None):
    """A dashed write-in box with a heading. Returns the y below its heading and hint, where writing starts.
    The box is recorded on the page (p.zones), so its position can be saved beside the PDF for the tests."""
    if tint:
        p.rrect("art", x, y, w, h, 7, fill=k.tint)
    p.rrect("art", x, y, w, h, 7, stroke=k.dash, width=1.1, dash=(5, 3))
    pad = 14
    ty = y + pad + title_pt / 2.835 * 0.78
    p.text("art", title, x + pad, ty, title_pt, "SemiBold", BLACK)
    if hint:
        ty = p.para("art", hint, x + pad, ty + hint_pt / 2.835 * 1.35, hint_pt, w - 2 * pad, "Regular", HINT,
                    leading=1.3) - hint_pt / 2.835 * 1.3
    if hasattr(p, "zones"):
        p.zones.append({"box": box, "n": n, "title": title, "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2),
                        "write_from": round(ty + 12, 2)})
    return ty + 12


def sheet_frame(k, label, question, code):
    """Header band, the table circle to write in, and the footer. Returns (page, y where the boxes start, y where they end)."""
    p = Page(*A1, BLEED)
    p.zones = []
    W, H = A1
    circle = 150
    band_w = W - 2 * M - circle - 22
    pad = 22
    q_pt = 76
    lines = p.wrap(question, q_pt, band_w - 2 * pad, "Bold")
    lh = q_pt / 2.835 * 1.12
    band_h = max(circle, pad + 16 + 10 + len(lines) * lh + pad - 6)
    p.rrect("art", M, M, band_w, band_h, 9, fill=k.accent)
    p.text("art", label, M + pad, M + pad + 13, 40, "SemiBold", k.band_label)
    for i, ln in enumerate(lines):
        p.text("art", ln, M + pad, M + pad + 16 + 12 + (i + 0.78) * lh, q_pt, "Bold", k.on_band)
    cx, cy = W - M - circle / 2, M + band_h / 2
    p.circle("art", cx, cy, circle / 2, stroke=k.accent, width=2.2)
    p.text("art", k.group, cx, cy - circle / 2 + 40, 44, "SemiBold", k.accent_text, align="center")
    # footer: logo, a reminder, and the sheet code with a second place for the table number,
    # so close-up photos of any corner can still be matched to their table
    fy = H - M
    lw = logo(p, k, M, fy - 20, h=20, max_w=110, baseline=fy - 6.5)
    note = f"All of this goes into the {k.name}." + (" No names, please." if k.public else "")
    note_x = M + lw + 16
    code_x = W - M
    p.line("art", code_x - 38, fy - 5, code_x, fy - 5, stroke=BLACK, width=0.6)
    code_w = p.text("art", f"{code} · {k.group}", code_x - 41, fy - 6.5, 24, "SemiBold", BLACK, align="right")
    room = code_x - 41 - code_w - 12 - note_x
    # a long playbook name wraps the note upwards from the baseline the code sits on
    note_lines = p.wrap(note, 20, room, "Regular")
    nlh = 20 / 2.835 * 1.3
    if len(note_lines) > 3 or max(p.text_width(ln, 20, "Regular") for ln in note_lines) > room:
        raise SystemExit(f"The playbook name {k.name!r} is too long for the sheet footer: shorten playbook.name in the settings.")
    for i, ln in enumerate(note_lines):
        p.text("art", ln, note_x, fy - 6.5 - (len(note_lines) - 1 - i) * nlh, 20, "Regular", HINT)
    return p, M + band_h + 22, fy - 36


def sheet1(k, optional):
    p, top, bottom = sheet_frame(k, "Question 1", "Where does support get stuck?", "S1")
    W = A1[0]
    x, w = M, W - 2 * M
    y = top
    if optional:
        h = 146
        ty = zone(p, k, x, y, w, h, "Who's at this table?",
                  "Everyone puts one tally mark against their sector, and writes their country.", tint=True)
        sectors = ["Public sector", "Finance", "Retail", "Tech", "Education", "Charity", "Health", "Other"]
        bw = (w - 28 - 7 * 6) / 8
        for i, s in enumerate(sectors):
            bx = x + 14 + i * (bw + 6)
            p.text("art", s, bx + bw / 2, ty + 6, 22, "Medium", BLACK, align="center")
            p.rrect("art", bx, ty + 11, bw, 40, 4, stroke=RULE, width=0.6)
        cy = ty + 11 + 40 + 22
        lw = p.text("art", "Countries:", x + 14, cy, 26, "Medium", BLACK)
        p.line("art", x + 14 + lw + 6, cy + 1, x + w - 14, cy + 1, stroke=RULE, width=0.5)
        y += h + 18
    # the challenge list is the main event, so it gets whatever height is left; the picks share one row
    row_h = 158
    grow_h = bottom - y - row_h - 18
    zone(p, k, x, y, w, grow_h, "Every challenge at this table",
         "Write them all down. Budget, leadership, burnout, proving impact…")
    y += grow_h + 18
    lw_ = (w - 18) * 0.56
    rw = w - 18 - lw_
    ty = zone(p, k, x, y, lw_, row_h, "Our top three")
    for i in range(3):
        ly = ty + 20 + i * 32
        p.text("art", f"{i + 1}.", x + 14, ly, 28, "SemiBold", BLACK)
        p.line("art", x + 34, ly + 1, x + lw_ - 14, ly + 1, stroke=RULE, width=0.5)
    rx = x + lw_ + 18
    ty = zone(p, k, rx, y, rw, row_h, "The one we're tackling", "Copy it onto your table card too.")
    write_lines(p, rx + 14, rx + rw - 14, ty + 30, 3, 28)
    return p


def sheet2(k, optional):
    p, top, bottom = sheet_frame(k, "Question 2", "What has helped, or not?", "S2")
    W = A1[0]
    gap = 18
    lesson_h = 170
    col_h = bottom - top - lesson_h - gap
    cw = (W - 2 * M - gap) / 2
    zone(p, k, M, top, cw, col_h, "Helped", "What happened, and why did it work?")
    zone(p, k, M + cw + gap, top, cw, col_h, "Got in the way", "What would you change or avoid?")
    zone(p, k, M, top + col_h + gap, W - 2 * M, lesson_h, "If we did it again, we'd…")
    return p


def sheet3(k, optional):
    p, top, bottom = sheet_frame(k, "Question 3", "What could people try now, and how does it stick?", "S3")
    W = A1[0]
    gap = 18
    rh = (bottom - top - 2 * gap) / 3
    x, w = M, W - 2 * M
    for i in range(3):
        y = top + i * (rh + gap)
        ty = zone(p, k, x, y, w, rh, f"Action {i + 1}")
        # three labelled parts, so the reader knows what each bit of writing is
        parts = [("What to try", 0.46), ("What you need", 0.27), ("How it sticks", 0.27)]
        px = x + 14
        inner = w - 28 - 2 * 12
        for j, (label, share) in enumerate(parts):
            pw = inner * share
            p.text("art", label, px, ty + 6, 24, "Medium", HINT)
            if j:
                p.line("art", px - 6, ty - 2, px - 6, y + rh - 46, stroke=RULE, width=0.4)
            px += pw + 12
        tick_y = y + rh - 16
        tx = p.text("art", "Good for:", x + 14, tick_y - 1.5, 24, "Medium", BLACK) + x + 14 + 10
        for label in ("Just starting", "Growing", "Established"):
            tx = checkbox(p, tx, tick_y, 9, label, 24) + 16
    return p


def sheet_side(k, optional):
    p, top, bottom = sheet_frame(k, "All session", "Heard something good? Write it here.", "SS")
    W = A1[0]
    gap = 16
    best_h = 170 if optional else 0
    col_h = bottom - top - (best_h + gap if optional else 0)
    cw = (W - 2 * M - 2 * gap) / 3
    for i, (t, h) in enumerate([("Quotes", "Exact words, no names"), ("Questions", "Things nobody could answer"),
                                ("Resources", "Links, books, people, tools")]):
        zone(p, k, M + i * (cw + gap), top, cw, col_h, t, h)
    if optional:
        zone(p, k, M, top + col_h + gap, W - 2 * M, best_h, "Best thing said today",
             "The table lead writes it in the last two minutes.", tint=True)
    return p


# the round-tables sheets, drawn by hand before sheets came from exercises ("print": {"renderer": "legacy"})
LEGACY_SHEETS = {"S1": sheet1, "S2": sheet2, "S3": sheet3, "SS": sheet_side}


# ---------------------------------------------------------------- sheets drawn from an exercise's boxes

def sheet_generic(k, e, optional):
    """A sheet laid out from its exercise: rows of boxes ("print": {"rows": [...]}), each row a fixed height in mm
    or "grow" (sharing what's left), each cell a box and its share of the width."""
    p, top, bottom = sheet_frame(k, e["label"], e["title"], e["code"])
    W = A1[0]
    boxes = {b["id"]: b for b in e["boxes"]}
    layout = e.get("print") or {}
    rows = layout.get("rows") or [{"height": "grow", "cells": [{"box": b["id"]}]} for b in e["boxes"]]
    rows = [r for r in rows if optional or not all(boxes[c["box"]].get("optional") for c in r["cells"])]
    gap = layout.get("gap", 18)
    fixed = sum(r["height"] for r in rows if r["height"] != "grow")
    grow = [r for r in rows if r["height"] == "grow"] or [None]
    free = bottom - top - fixed - gap * (len(rows) - 1)
    y = top
    for r in rows:
        h = r["height"] if r["height"] != "grow" else free / len(grow)
        shares = [c.get("share", 1) for c in r["cells"]]
        room = W - 2 * M - gap * (len(r["cells"]) - 1)
        x = M
        for c, share in zip(r["cells"], shares):
            w = room * share / sum(shares)
            draw_box(p, k, boxes[c["box"]], x, y, w, h, tint=c.get("tint", False))
            x += w + gap
        y += h + gap
    return p


def draw_box(p, k, b, x, y, w, h, tint=False):
    kind = b["type"]
    label, hint = b.get("label", ""), b.get("hint")
    if kind == "row":
        n = b.get("count", 3)
        gap = 18
        rh = (h - gap * (n - 1)) / n
        fields = b.get("fields", [])
        shares = [f.get("share", 1) for f in fields]
        for i in range(n):
            ry = y + i * (rh + gap)
            ty = zone(p, k, x, ry, w, rh, label.replace("{n}", str(i + 1)), tint=tint, box=b["id"], n=i + 1)
            # labelled parts, so the reader knows what each bit of writing is
            px = x + 14
            inner = w - 28 - 12 * (len(fields) - 1)
            for j, (f, share) in enumerate(zip(fields, shares)):
                pw = inner * share / sum(shares)
                p.text("art", f["label"], px, ty + 6, 24, "Medium", HINT)
                if j:
                    p.line("art", px - 6, ty - 2, px - 6, ry + rh - (46 if b.get("ticks") else 14), stroke=RULE, width=0.4)
                px += pw + 12
            if b.get("ticks"):
                t = b["ticks"]
                tick_y = ry + rh - 16
                tx = p.text("art", t.get("label", ""), x + 14, tick_y - 1.5, 24, "Medium", BLACK) + x + 14 + 10
                for o in t["options"]:
                    tx = checkbox(p, tx, tick_y, 9, o[1] if isinstance(o, list) else o, 24) + 16
        return
    ty = zone(p, k, x, y, w, h, label, hint, tint=tint, box=b["id"])
    if kind == "text":
        write_lines(p, x + 14, x + w - 14, ty + 30, b.get("lines", 3), 28)
    elif kind == "ranked":
        for i in range(b.get("count", 3)):
            ly = ty + 20 + i * 32
            p.text("art", f"{i + 1}.", x + 14, ly, 28, "SemiBold", BLACK)
            p.line("art", x + 34, ly + 1, x + w - 14, ly + 1, stroke=RULE, width=0.5)
    elif kind == "name":
        write_lines(p, x + 14, x + w - 14, ty + 24, 1, 28)
    elif kind == "tally":
        opts = b.get("options", [])
        bw = (w - 28 - (len(opts) - 1) * 6) / max(len(opts), 1)
        for i, o in enumerate(opts):
            bx = x + 14 + i * (bw + 6)
            p.text("art", o, bx + bw / 2, ty + 6, 22, "Medium", BLACK, align="center")
            p.rrect("art", bx, ty + 11, bw, 40, 4, stroke=RULE, width=0.6)
        if b.get("text_line"):
            cy = ty + 11 + 40 + 22
            lw = p.text("art", b["text_line"] + ":", x + 14, cy, 26, "Medium", BLACK)
            p.line("art", x + 14 + lw + 6, cy + 1, x + w - 14, cy + 1, stroke=RULE, width=0.5)
    elif kind == "list+votes":
        # numbered idea boxes in reading order, each with a strip at the bottom for dot votes
        n, cols = b.get("count", 8), b.get("columns", 4)
        rows = -(-n // cols)
        g = 10
        cw = (w - 28 - g * (cols - 1)) / cols
        ch = (y + h - 14 - ty - g * (rows - 1)) / rows
        for i in range(n):
            cx, cy = x + 14 + (i % cols) * (cw + g), ty + (i // cols) * (ch + g)
            p.rrect("art", cx, cy, cw, ch, 5, stroke=RULE, width=0.6)
            p.text("art", str(i + 1), cx + 7, cy + 10, 22, "SemiBold", HINT)
            strip = 22
            p.line("art", cx + 5, cy + ch - strip, cx + cw - 5, cy + ch - strip, stroke=RULE, width=0.4)
            p.text("art", b.get("votes_label", "Votes"), cx + 7, cy + ch - strip / 2 + 2.5, 20, "Medium", HINT)
            p.zones.append({"box": b["id"], "n": i + 1, "title": f"{b.get('item_label', label)} {i + 1}", "x": round(cx, 2), "y": round(cy, 2),
                            "w": round(cw, 2), "h": round(ch, 2), "write_from": round(cy + 14, 2), "votes_from": round(cy + ch - strip, 2)})


# ---------------------------------------------------------------- A5 commitment card

A5L = (210, 148)
CARD_LOGO_H = 11      # mm; 9 mm was too small to read at arm's length
CARD_LINES = 6        # write-on lines on each half, the same both sides


def qr(p, url, x, y, size):
    import segno
    q = segno.make(url, error="m", micro=False)
    matrix = q.matrix
    n = len(matrix)
    quiet = 4                            # the full quiet zone the QR spec asks for
    cell = size / (n + 2 * quiet)
    p.rect("art", x, y, size, size, fill=WHITE)
    ops = []
    for r, row in enumerate(matrix):
        for c, v in enumerate(row):
            if v:
                ops += p.rrect_ops(x + (c + quiet) * cell, y + (r + quiet) * cell, cell + 0.02, cell + 0.02, 0)
    p._paint("art", ops, fill=BLACK)


def commitment_card(k):
    p = Page(*A5L, BLEED)
    W, H = A5L
    half = W / 2
    p.rect("art", -BLEED, -BLEED, W + 2 * BLEED, H + 2 * BLEED, fill=k.highlight)
    # the perforation is a die line for the printer, never ink
    p.line("perf", half, -BLEED, half, H + BLEED, spot="CSPerf", stroke=True, width=0.25)
    pad = 9
    prompt = "One thing I will try, adapt or explore is…"
    bottom = H - pad                     # both halves' bottom blocks end here, so they line up across the perforation
    for side in (0, 1):
        x0 = side * half + pad
        w = half - 2 * pad
        logo(p, k, x0, pad, h=CARD_LOGO_H, max_w=w * 0.8, colour=k.card_prompt)
        y = p.para("art", prompt, x0, pad + CARD_LOGO_H + 11, 13, w, "Bold", k.card_prompt, leading=1.2)
        write_lines(p, x0, x0 + w, y + 7, CARD_LINES, 9)
        lines_end = y + 7 + (CARD_LINES - 1) * 9
        if side == 0:
            qs = 24
            qy = bottom - qs
            if k.qr_url:
                qr(p, k.qr_url, x0, qy, qs)
            else:
                # room for a QR code stuck on by hand, or a reprint once the playbook has an address
                p.rect("art", x0, qy, qs, qs, fill=WHITE)
                p.rect("art", x0, qy, qs, qs, stroke=BLACK, width=0.3, dash=(1, 0.8))
                ph, ph_pt = "Your QR code here", 7
                ph_lh = ph_pt / 2.835 * 1.25
                ph_n = len(p.wrap(ph, ph_pt, qs - 4, "Medium"))
                first = qy + qs / 2 - (ph_n - 1) * ph_lh / 2 + ph_pt / 2.835 * 0.7 / 2   # lines centred in the box
                p.para("art", ph, x0 + 2, first, ph_pt, qs - 4, "Medium", BLACK, leading=1.25, align="center")
            tx, tw = x0 + qs + 5, w - qs - 5
            ty = p.para("art", f"Scan for the {k.name}: what every table came up with.", tx, qy + 6,
                        8.5, tw, "Medium", k.card_ink, leading=1.3)
            if k.qr_text:
                # shrink a long address to fit beside the code rather than run into the perforation
                pt = 8.5
                while p.text_width(k.qr_text, pt, "SemiBold") > tw and pt > 6:
                    pt -= 0.25
                if p.text_width(k.qr_text, pt, "SemiBold") > tw:
                    raise SystemExit(f"The playbook address {k.qr_text!r} is too long to print on the card: use a shorter one.")
                p.text("art", k.qr_text, tx, ty + 1.5, pt, "SemiBold", k.card_prompt)
                ty += pt / 2.835 * 1.3
            assert ty <= bottom + 1, "the QR caption runs off the card: shorten playbook.name in the settings"
            block_top = qy
        else:
            # name, organisation and the consent line sit at the foot of the card, level with the QR block
            consent = "Add these only if you're happy for them to appear in the public playbook."
            c_lh = 8 / 2.835 * 1.3
            c_lines = len(p.wrap(consent, 8, w, "Regular"))
            cy = bottom - 1 - (c_lines - 1) * c_lh
            org_y = cy - 9
            name_y = org_y - 10
            for label, ly in (("Name (optional)", name_y), ("Organisation (optional)", org_y)):
                lw = p.text("art", label, x0, ly, 8.5, "Medium", k.card_ink)
                p.line("art", x0 + lw + 2, ly + 0.8, x0 + w, ly + 0.8, stroke=RULE, width=0.3)
            p.para("art", consent, x0, cy, 8, w, "Regular", k.card_ink, leading=1.3)
            block_top = name_y - 8.5 / 2.835 * 0.75
        assert block_top - lines_end >= 8, f"side {side}: bottom block crowds the write-on lines"
    return p


# ---------------------------------------------------------------- table cards: A4 folded to an A5 tent

A4P = (210, 297)
FACE = (210, 148.5)        # each half of the A4 sheet, one face of the tent
TENT_LOGO_H = 16           # mm; big enough to read from the next table


def tent_front(k, n):
    W, H = FACE
    f = Page(W, H)
    f.text("art", "Table", W / 2, 38, 48, "SemiBold", k.accent_text, align="center")
    f.text("art", str(n), W / 2, 110, 230, "Bold", k.accent_text, align="center")
    logo(f, k, 14, H - 14 - TENT_LOGO_H, h=TENT_LOGO_H, max_w=120)
    return f


def tent_back(k, n):
    W, H = FACE
    f = Page(W, H)
    f.text("art", "We're tackling:", 16, 36, 36, "SemiBold", k.accent_text)
    # the table number again, small, so people on this side of the room can see which table it is
    f.text("art", f"Table {n}", W - 16, 36, 20, "SemiBold", k.accent_text, align="right")
    write_lines(f, 16, W - 16, 64, 3, 19)
    logo(f, k, 14, H - 14 - TENT_LOGO_H, h=TENT_LOGO_H, max_w=120)
    return f


def table_card(k, n):
    """One A4 portrait page, printed on one side: the front on the bottom half, the back on the top half
    turned upside down, so both faces read the right way up once it's folded into a tent."""
    page = Page(*A4P, BLEED)
    b = BLEED * MM
    fw, fh = FACE[0] * MM, FACE[1] * MM
    placements = [
        (tent_front(k, n), f"1 0 0 1 {b:.3f} {b:.3f} cm"),                     # bottom half, upright
        (tent_back(k, n), f"-1 0 0 -1 {b + fw:.3f} {b + 2 * fh:.3f} cm"),      # top half, rotated 180°
    ]
    for face, matrix in placements:
        page.ops("art").extend(["q", matrix] + face.layers.get("art", []) + ["Q"])
    # fold marks at the edges, for scoring by hand; short so they all but vanish on the fold itself
    for x0, x1 in ((0, 7), (A4P[0] - 7, A4P[0])):
        page.line("art", x0, FACE[1], x1, FACE[1], stroke=RULE, width=0.3)
    return page


def overview(out, tables, codes=("S1", "S2", "S3", "SS"), made=()):
    """One image of every piece, for a quick look on screen (not for printing)."""
    import subprocess, tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shots = []
        for name, res in [(SHEET_PDF.format(code=c), 18) for c in codes] + \
                         [(f, r) for f, r in ((CARD_PDF, 70), (TABLES_PDF.format(n=tables), 50)) if f in {Path(m).name for m in made}]:
            subprocess.run(["pdftoppm", "-r", str(res), "-png", "-f", "1", "-l", "1", str(OUT / name), str(tmp / name)], check=True)
            shots.append(Image.open(next(tmp.glob(name + "*.png"))).convert("RGB"))
    g = 24
    sheets, rest = shots[:len(codes)], shots[len(codes):] or [Image.new("RGB", (1, 1), (232, 230, 236))]
    W = max(sum(i.width for i in sheets), sum(i.width for i in rest)) + g * 5
    H = g * 3 + max(i.height for i in sheets) + max(i.height for i in rest)
    c = Image.new("RGB", (W, H), (232, 230, 236))
    x = g
    for i in sheets:
        c.paste(i, (x, g)); x += i.width + g
    x, y = g, 2 * g + max(i.height for i in sheets)
    for i in rest:
        c.paste(i, (x, y)); x += i.width + g
    c.save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", help="settings file (default: playbook.config.json at the repo root, or $PLAYBOOK_CONFIG)")
    ap.add_argument("--tables", type=int, default=12, help="how many table cards (default 12)")
    ap.add_argument("--qr-url", help="address for the commitment card's QR code (default: playbook.url in the settings). "
                                     "Use an address you control, so it can forward anywhere later without a reprint")
    ap.add_argument("--no-qr", action="store_true", help="print the 'Your QR code here' box instead of a QR code")
    ap.add_argument("--no-optional", action="store_true", help="leave out the tally strip (S1) and best-thing box (SS)")
    a = ap.parse_args()
    if a.tables < 1:
        ap.error("--tables must be at least 1")
    if a.config and not Path(a.config).is_file():
        ap.error(f"no settings file at {a.config}")   # config.load would quietly fall back to the defaults
    cfg = config.load(a.config)
    pdfkit.use_fonts(cfg)
    url = "" if a.no_qr else (a.qr_url or cfg["playbook"]["url"] or "").strip()
    if url and "://" not in url:
        url = "https://" + url               # without a scheme, a phone reads the code as plain text, not a link
    W = formats.load(cfg)
    k = kit_settings(cfg, url or None, W)
    for w in k.warnings:
        print(f"  note: {w}")
    optional = not a.no_optional
    name = cfg["playbook"]["name"]
    OUT.mkdir(parents=True, exist_ok=True)
    made, codes = [], []
    for old in list(OUT.glob("sheet-*")) + list(OUT.glob("table-cards-*.pdf")) + list(OUT.glob(CARD_PDF)):
        old.unlink()                     # another workshop's sheets, or a run for a different number of tables
    for e in W.exercises:
        legacy = (e.get("print") or {}).get("renderer") == "legacy"
        if e["id"] == "commitment-card" and legacy:
            made.append(write([commitment_card(k)], OUT / CARD_PDF,
                              f"{name}: commitment card, A5 landscape, perforated down the middle (v{VERSION})"))
        elif e["id"] == "table-card" and legacy:
            made.append(write([table_card(k, n) for n in range(1, a.tables + 1)], OUT / TABLES_PDF.format(n=a.tables),
                              f"{name}: table cards 1 to {a.tables}, A4 portrait, one page per table, print one side, fold in half for an A5 tent (v{VERSION})"))
        elif e.get("per", "group") == "group" and e.get("boxes"):
            code = e["code"]
            page = LEGACY_SHEETS[code](k, optional) if legacy else sheet_generic(k, e, optional)
            made.append(write([page], OUT / SHEET_PDF.format(code=code), f"{name}: sheet {code}, A1 (v{VERSION})"))
            codes.append(code)
            # where each box is on the page (mm from the top left), for the handwriting tests and anything else
            # that needs to find a box in a photo of the sheet
            import json
            (OUT / SHEET_LAYOUT.format(code=code)).write_text(json.dumps(
                {"sheet": code, "exercise": e["id"], "page_mm": list(A1), "zones": page.zones}, indent=1) + "\n")
        else:
            raise SystemExit(f"The print kit can't draw {e['id']!r} yet: only sheets for groups, and the round-tables cards")
    overview(OUT.parent / "paper-kit-overview.png", a.tables, codes, made)
    import zipfile
    for old in OUT.parent.glob("paper-kit-print-files-v*.zip"):
        old.unlink()
    z = OUT.parent / ZIP.format(version=VERSION)
    # only this run's files: anything else in the folder may be left over from another kit
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in made:
            zf.write(f, f"paper-kit-v{VERSION}/{f.name}")
    print(f"Wrote {OUT} and {z.name}" + (f"  (QR: {k.qr_url})" if k.qr_url else "  (no QR code: the card has a 'Your QR code here' box)"))


if __name__ == "__main__":
    main()
