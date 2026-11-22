"""Tiny vector-PDF writer for print artwork: CMYK fills, named spot colours, layers, outlined text.

Why not Chrome's print-to-PDF: it only writes RGB and can't make the spot colours printers use for
cut lines and raised braille. Everything here is drawn in millimetres from the top-left corner of
the page (y down, like the SVGs), and converted to PDF points on output.
"""
import re
from pathlib import Path

import pikepdf
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont
from pikepdf import Array, Dictionary, Name

MM = 72 / 25.4
ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"   # the same Poppins files the web pages inline (fontTools reads woff2 via brotli)
FONT_FILES = {}                      # weight -> file, from the settings' brand.font (use_fonts); Poppins if unset
FAMILY = ["Poppins"]


def use_fonts(cfg):
    """Draw lettering in the settings' brand font (static files, one per weight) instead of Poppins."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "build"))
    import config as _config
    FONT_FILES.clear()
    for weight in ("Regular", "Medium", "SemiBold", "Bold"):
        FONT_FILES[weight] = _config.font_file(cfg, weight)
    FAMILY[0] = cfg["brand"]["font"]["family"]
    _fonts.clear()


def cap_height(weight="Bold"):
    """The font's capital height as a share of its size (from the OS/2 table; 0.7 if the font doesn't say)."""
    f = font_obj(weight)
    cap = getattr(f["OS/2"], "sCapHeight", 0) if "OS/2" in f else 0
    return cap / f["head"].unitsPerEm if cap else 0.7

# Brand colours aren't set here: the builders work them out from the settings file (build/config.py).
BLACK = (0, 0, 0, 1)
WHITE = (0, 0, 0, 0)                 # no ink: knocks out to the paper or vinyl
GREY = (0, 0, 0, 0.55)               # light printed rules and hints; 0.55 K keeps hint text readable


class _Pen(BasePen):
    """Turns pen calls into PDF path operators, mapping each point through `xf` (mm in, points out)."""

    def __init__(self, xf, glyphset=None):
        super().__init__(glyphset)   # TrueType accents are composites, so the pen needs the glyph set
        self.xf, self.ops = xf, []

    def _pt(self, p):
        x, y = self.xf(p)
        return f"{x:.3f} {y:.3f}"

    def _moveTo(self, p):
        self.ops.append(self._pt(p) + " m")

    def _lineTo(self, p):
        self.ops.append(self._pt(p) + " l")

    def _curveToOne(self, a, b, c):
        self.ops.append(f"{self._pt(a)} {self._pt(b)} {self._pt(c)} c")

    def _closePath(self):
        self.ops.append("h")


class Page:
    """One PDF page. `layers` maps a layer key to its list of content operators."""

    def __init__(self, w_mm, h_mm, bleed_mm=0.0):
        self.w, self.h, self.bleed = w_mm + 2 * bleed_mm, h_mm + 2 * bleed_mm, bleed_mm
        self.trim = (w_mm, h_mm)
        self.layers = {}

    # -- coordinates: callers use trim coordinates (0,0 = top-left of the finished size)
    def pt(self, x, y):
        return ((x + self.bleed) * MM, (self.h - (y + self.bleed)) * MM)

    def ops(self, layer):
        return self.layers.setdefault(layer, [])

    # -- primitives
    def _paint(self, layer, path_ops, fill=None, stroke=None, width=0.25, spot=None, dash=None):
        out = self.ops(layer)
        out.append("q")
        if spot:
            out.append(f"/GSop gs /{spot} {'CS' if stroke else 'cs'} 1 {'SCN' if stroke else 'scn'}")
        else:
            if fill:
                out.append("%.4f %.4f %.4f %.4f k" % fill)
            if stroke:
                out.append("%.4f %.4f %.4f %.4f K" % stroke)
        if stroke or (spot and stroke is not None):
            out.append(f"{width * MM:.3f} w")
        if dash:
            out.append("[%s] 0 d" % " ".join(f"{d * MM:.3f}" for d in dash))
        out.extend(path_ops)
        out.append("S" if stroke else "f")
        out.append("Q")

    def circle_ops(self, cx, cy, r):
        k = 0.5522847498 * r
        pts = lambda *xy: " ".join("%.3f %.3f" % self.pt(*p) for p in xy)
        return [pts((cx + r, cy)) + " m",
                pts((cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)) + " c",
                pts((cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)) + " c",
                pts((cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)) + " c",
                pts((cx + k, cy - r), (cx + r, cy - k), (cx + r, cy)) + " c", "h"]

    def rrect_ops(self, x, y, w, h, r):
        r = min(r, w / 2, h / 2)
        k = 0.5522847498 * r
        P = lambda *xy: " ".join("%.3f %.3f" % self.pt(*p) for p in xy)
        return [P((x + r, y)) + " m", P((x + w - r, y)) + " l",
                P((x + w - r + k, y), (x + w, y + r - k), (x + w, y + r)) + " c",
                P((x + w, y + h - r)) + " l",
                P((x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h)) + " c",
                P((x + r, y + h)) + " l",
                P((x + r - k, y + h), (x, y + h - r + k), (x, y + h - r)) + " c",
                P((x, y + r)) + " l",
                P((x, y + r - k), (x + r - k, y), (x + r, y)) + " c", "h"]

    def line_ops(self, x1, y1, x2, y2):
        return ["%.3f %.3f m" % self.pt(x1, y1), "%.3f %.3f l" % self.pt(x2, y2)]

    def circle(self, layer, cx, cy, r, **kw):
        self._paint(layer, self.circle_ops(cx, cy, r), **kw)

    def rrect(self, layer, x, y, w, h, r, **kw):
        self._paint(layer, self.rrect_ops(x, y, w, h, r), **kw)

    def rect(self, layer, x, y, w, h, **kw):
        self._paint(layer, self.rrect_ops(x, y, w, h, 0), **kw)

    def line(self, layer, x1, y1, x2, y2, **kw):
        self._paint(layer, self.line_ops(x1, y1, x2, y2), **kw)

    # -- artwork from files
    def svg(self, layer, svg, x, y, w=None, h=None, fill=BLACK, paths=None, colours=None):
        """Draw an SVG file's <path> shapes into a box at (x, y), with any transforms applied. They're drawn in one
        colour (`fill`), unless `colours` is given: a function from a hex colour to CMYK, used to keep each shape's
        own fill (for a logo in its own colours). Other SVG elements (circles, text, gradients) aren't drawn."""
        vb, ds = svg_paths(svg)
        fills = svg_fills(svg)
        if paths is not None:
            ds, fills = [ds[i] for i in paths], [fills[i] for i in paths]
            vb = bbox_of(ds)
        vx, vy, vw, vh = vb
        s = (w / vw) if w else (h / vh)
        to_page = lambda p: self.pt(x + (p[0] - vx) * s, y + (p[1] - vy) * s)
        if colours is None:
            pen = _Pen(to_page)
            for d in ds:
                parse_path(d, pen)
            self._paint(layer, pen.ops, fill=fill)
        else:
            for d, own in zip(ds, fills):
                if own == "none":
                    continue
                pen = _Pen(to_page)
                parse_path(d, pen)
                self._paint(layer, pen.ops, fill=colours(own) if own else fill)
        return vw * s, vh * s

    def text(self, layer, s, x, y, size_pt, font="SemiBold", fill=BLACK, align="left", tracking=0.0):
        """Outlined text: glyphs become paths, so the printer needs no fonts. (x, y) is the baseline."""
        f = font_obj(font)
        upm = f["head"].unitsPerEm
        scale = size_pt / MM / upm           # font units to mm
        cmap, gs, hmtx = f.getBestCmap(), f.getGlyphSet(), f["hmtx"]
        missing = sorted({ch for ch in s if ord(ch) not in cmap})
        if missing:
            # a missing glyph would print as an empty box; fail loudly instead
            raise ValueError(f"{FAMILY[0]} {font} has no glyph for {missing!r} in {s!r}")
        names = [cmap[ord(ch)] for ch in s]
        advance = sum(hmtx[n][0] for n in names) * scale + tracking * max(len(names) - 1, 0)
        if align == "center":
            x -= advance / 2
        elif align == "right":
            x -= advance
        pen = None
        cursor = x
        all_ops = []
        for n in names:
            pen = _Pen(lambda p, cx=cursor: self.pt(cx + p[0] * scale, y - p[1] * scale), gs)
            gs[n].draw(pen)
            all_ops.extend(pen.ops)
            cursor += hmtx[n][0] * scale + tracking
        if all_ops:
            self._paint(layer, all_ops, fill=fill)
        return advance

    def text_width(self, s, size_pt, font="SemiBold"):
        f = font_obj(font)
        cmap, hmtx = f.getBestCmap(), f["hmtx"]
        return sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in s) * size_pt / MM / f["head"].unitsPerEm

    def wrap(self, s, size_pt, width_mm, font="Regular"):
        words, lines, cur = s.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if self.text_width(t, size_pt, font) <= width_mm or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def para(self, layer, s, x, y, size_pt, width_mm, font="Regular", fill=BLACK, leading=1.35, align="left"):
        """Wrapped text; returns the y just below the last line."""
        lh = size_pt / MM * leading
        for i, ln in enumerate(self.wrap(s, size_pt, width_mm, font)):
            self.text(layer, ln, x if align == "left" else x + width_mm / 2, y + i * lh, size_pt, font, fill,
                      align="left" if align == "left" else "center")
        return y + len(self.wrap(s, size_pt, width_mm, font)) * lh


_fonts, _svgs = {}, {}


def font_obj(weight):
    if weight not in _fonts:
        _fonts[weight] = TTFont(FONT_FILES.get(weight) or FONTS / f"poppins-{weight}.woff2")
    return _fonts[weight]


def svg_paths(path):
    """(viewBox, [path data]) for an SVG file, with each path's own and its groups' transforms applied, so a logo
    exported with nested groups draws where it should. Raises ValueError if it has no <path> to draw."""
    return _svg(path)[:2]


def svg_fills(path):
    """Each path's fill colour, in the same order as svg_paths: "#rrggbb", "none", or "" when it doesn't say."""
    return _svg(path)[2]


def _svg(path):
    key = str(path)
    if key not in _svgs:
        import xml.etree.ElementTree as ET
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        root = ET.fromstring(Path(path).read_text())
        ds, fills = [], []

        def walk(el, m, fill):
            m = _compose(m, _transform(el.get("transform")))
            fill = _fill_of(el) or fill
            if el.tag.rsplit("}", 1)[-1] == "path" and el.get("d"):
                d = el.get("d")
                if m != _IDENTITY:
                    out = SVGPathPen(None)
                    parse_path(d, TransformPen(out, m))
                    d = out.getCommands()
                ds.append(d)
                fills.append(fill)
            for child in el:
                walk(child, m, fill)

        walk(root, _IDENTITY, "")
        if not ds:
            raise ValueError(f"{path} has no <path> shapes to draw")
        m = re.search(r"""viewBox=(["'])([^"']+)\1""", Path(path).read_text())
        vb = tuple(float(v) for v in re.split(r"[\s,]+", m.group(2).strip())) if m else bbox_of(ds)
        _svgs[key] = (vb, ds, fills)
    return _svgs[key]


_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _compose(a, b):
    """Apply b inside a (the SVG nesting order): the matrix for a parent's transform a and a child's b."""
    a1, b1, c1, d1, e1, f1 = a
    a2, b2, c2, d2, e2, f2 = b
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _transform(attr):
    """An SVG transform attribute as a matrix: translate, scale, rotate and matrix(), in sequence."""
    import math
    m = _IDENTITY
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", attr or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:
                t = _compose(_compose((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "matrix" and len(v) == 6:
            t = tuple(v)
        else:
            continue
        m = _compose(m, t)
    return m


def _fill_of(el):
    """An element's own fill as "#rrggbb" or "none" ("" if it doesn't set one), from the attribute or its style."""
    f = el.get("fill") or ""
    m = re.search(r"fill\s*:\s*([^;]+)", el.get("style") or "")
    if m:
        f = m.group(1).strip()
    f = f.strip().lower()
    if f == "none" or f.startswith("rgba(") and f.replace(" ", "").endswith(",0)"):
        return "none"
    if re.fullmatch(r"#[0-9a-f]{3}", f):
        f = "#" + "".join(ch * 2 for ch in f[1:])
    return f if re.fullmatch(r"#[0-9a-f]{6}", f) else ""


def bbox_of(ds):
    from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(None)
    for d in ds:
        parse_path(d, bp)
    x0, y0, x1, y1 = bp.bounds
    return (x0, y0, x1 - x0, y1 - y0)


def path_bbox(d):
    return bbox_of([d])


# ---------------------------------------------------------------- writing

SPOTS = {
    # name in the PDF: (printer-facing separation name, alternate CMYK so it shows on screen)
    "CSCut": ("CutContour", (0, 1, 0, 0)),
    "CSBraille": ("Braille", (1, 0, 1, 0)),
    "CSPerf": ("Perforation", (0, 1, 0, 0)),
}

LAYER_NAMES = {
    "art": "Artwork (CMYK)",
    "braille": "Braille: raised clear dots (spot 'Braille')",
    "cut": "Cut line (spot 'CutContour')",
    "perf": "Perforation (spot 'Perforation')",
    "guide": "Guides (do not print)",
}


def write(pages, out, title, layer_order=("art", "braille", "cut", "perf", "guide")):
    """pages: list of Page. Each layer becomes an optional-content group, so the printer can toggle them."""
    pdf = pikepdf.new()
    pdf.docinfo["/Title"] = title
    pdf.docinfo["/Creator"] = "Playbook print kit (print/pdfkit.py)"
    used = [k for k in layer_order if any(k in p.layers for p in pages)]
    ocgs = {}
    for k in used:
        d = Dictionary(Type=Name.OCG, Name=LAYER_NAMES[k])
        if k == "guide":
            d.Usage = Dictionary(Print=Dictionary(PrintState=Name.OFF), Export=Dictionary(ExportState=Name.OFF))
        ocgs[k] = pdf.make_indirect(d)
    if ocgs:
        pdf.Root.OCProperties = Dictionary(
            OCGs=Array(list(ocgs.values())),
            D=Dictionary(Name="Layers", Order=Array(list(ocgs.values())), ON=Array(list(ocgs.values())),
                         AS=Array([Dictionary(Event=Name.Print, Category=Array([Name.Print]),
                                              OCGs=Array(list(ocgs.values())))])))
    colorspaces = Dictionary()
    # declare only the spot colours actually drawn, so a printer's separations list shows no empty plates
    drawn = "\n".join("\n".join(ops) for p in pages for ops in p.layers.values())
    for key, (sep, alt) in SPOTS.items():
        if f"/{key} " not in drawn:
            continue
        fn = Dictionary(FunctionType=2, Domain=Array([0, 1]), C0=Array([0, 0, 0, 0]), C1=Array(list(alt)), N=1)
        colorspaces["/" + key] = Array([Name.Separation, Name("/" + sep), Name.DeviceCMYK, pdf.make_indirect(fn)])
    gs = Dictionary(GSop=Dictionary(Type=Name.ExtGState, OP=True, op=True, OPM=1))
    for p in pages:
        content = []
        for k in used:
            if k in p.layers:
                content += [f"/OC /oc_{k} BDC"] + p.layers[k] + ["EMC"]
        W, H = p.w * MM, p.h * MM
        b = p.bleed * MM
        page = pikepdf.Page(Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, W, H]), BleedBox=Array([0, 0, W, H]),
            TrimBox=Array([b, b, W - b, H - b]),
            Resources=Dictionary(ColorSpace=colorspaces, ExtGState=gs,
                                 Properties=Dictionary({f"/oc_{k}": v for k, v in ocgs.items()})),
            Contents=pdf.make_stream("\n".join(content).encode())))
        pdf.pages.append(page)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(out)
    return out
