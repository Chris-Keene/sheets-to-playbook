"""Who the playbook belongs to and how it looks: one settings file read by every builder.

The settings live in playbook.config.json at the repo root. Point at another file with --config <path> or the
PLAYBOOK_CONFIG environment variable (examples/can/playbook.config.json is a full worked example).

A brand gives two colours, an accent and a highlight. Every other shade, for light and dark mode, is worked out
here and checked against WCAG 2.2 contrast (4.5:1 for text, 3:1 for borders and focus rings), so a rebrand can't
quietly make the site harder to read. A brand that wants exact colours can list them in brand.palette instead.
"""
import copy, json, math, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT = {
    "org": {
        "short": "",                     # e.g. "CAN": used in "tell CAN", "About CAN"
        "name": "",                      # e.g. "Champions of Accessibility Network"
        "forum": "community forum",      # the session's name in sentences: "created during the <forum> at <event>"
        "team": "the organisers",        # "<team> photographed every sheet"
        "about": "",                     # one or two sentences for the About page and the closing band
        "join": None,                    # {"label": "Join us on LinkedIn", "url": "https://..."}
    },
    "playbook": {
        "name": "Community Playbook",    # page titles, sheet footers, the card's QR caption
        "url": "",                       # where the playbook will live: the commitment card's QR code points here
        "searchable": False,             # true lets search engines list the final playbook (drafts never are)
        "file_name": "",                 # what "Download this playbook" saves as; default: the playbook's name, e.g. community-playbook.html
        "share": None,                   # link previews once it's online: {"image": "share.jpg", "image_alt": "..."}; needs url
    },
    "brand": {
        "accent": "#24508c",             # buttons, links, headings, the header band
        "highlight": "#ffd166",          # small labels on the band, the main button
        "logo": {},                      # {"primary": "brand/primary.svg", "secondary": ..., "mark": ...}, paths relative to this file
        "palette": None,                 # optional exact colours: {"light": {"--accent": "#..."}, "dark": {...}}
        "cmyk": None,                    # optional proofed print colours: {"accent": [c, m, y, k], "highlight": [...]}
        # the typeface for every page, sheet and slide. Give static (not variable) woff2 files, one per weight: the
        # print kit draws its lettering from them too. Paths are relative to this file.
        "font": {
            "family": "Poppins",
            "files": {"Regular": "assets/fonts/poppins-Regular.woff2", "Medium": "assets/fonts/poppins-Medium.woff2",
                      "SemiBold": "assets/fonts/poppins-SemiBold.woff2", "Bold": "assets/fonts/poppins-Bold.woff2"},
        },
    },
    "kit": {
        # shown on the playbook's "Run your own" page. The kit is CC BY 4.0, so passing it on means crediting it:
        # keep the credit if you adapt this line, and add your own alongside
        "licence": "Free to use and adapt under CC BY 4.0: please credit the sheets-to-playbook kit by Chris Keene.",
        # where the tools live, linked from the "Run your own" page ("" to leave the link out)
        "source": "https://github.com/Chris-Keene/sheets-to-playbook",
    },
    # the small "Built with" line at the foot of every playbook. Switch it off with "show": false.
    "credit": {
        "show": True,
        "text": "Built with sheets-to-playbook by Chris Keene",
        "url": "https://chriskeene.me",
        "logo": "assets/credit/ck.png",          # light backgrounds
        "logo_dark": "assets/credit/ck-white.png",  # dark mode
    },
}


def _merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def load(path=None):
    """The settings, with defaults for anything left out. `_dir` is where relative logo paths resolve from."""
    p = Path(path or os.environ.get("PLAYBOOK_CONFIG") or ROOT / "playbook.config.json")
    cfg = _merge(DEFAULT, json.loads(p.read_text()) if p.exists() else {})
    cfg["_dir"] = str(p.parent if p.exists() else ROOT)
    return cfg


# ---------------------------------------------------------------- colour

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexs(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):
    """t of the way from colour a to colour b."""
    a, b = rgb(a), rgb(b)
    return hexs(tuple(x + (y - x) * t for x, y in zip(a, b)))


def luminance(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def toward(c, target, against, need, step=0.02):
    """Move colour c toward target until it has `need` contrast against `against`."""
    t = 0.0
    while contrast(mix(c, target, t), against) < need and t < 1:
        t += step
    return mix(c, target, min(t, 1))


def hex_to_cmyk(h):
    """A naive conversion for the print files. A printer's proof is still the real check."""
    r, g, b = (v / 255 for v in rgb(h))
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0, 0, 0, 1)
    return tuple(round(x, 3) for x in ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k))


def palette(cfg):
    """{"light": {css var: colour}, "dark": {...}} worked out from the accent and highlight, then contrast-checked."""
    b = cfg["brand"]
    if b.get("palette"):
        return b["palette"]
    acc, hi = b["accent"], b["highlight"]
    L = {}
    L["--bg"] = mix(acc, "#ffffff", 0.97)
    L["--surface"] = "#ffffff"
    L["--tint"] = mix(acc, "#ffffff", 0.93)
    L["--ink"] = mix(acc, "#000000", 0.8)
    L["--muted"] = toward(mix(acc, "#555555", 0.7), "#000000", L["--bg"], 4.6)
    L["--accent"] = toward(acc, "#000000", L["--bg"], 4.6)
    L["--on-accent"] = "#ffffff" if contrast("#ffffff", L["--accent"]) >= 4.5 else L["--ink"]
    L["--logo"] = L["--accent"]
    L["--yellow"] = hi
    L["--on-yellow"] = max((L["--ink"], "#000000", "#ffffff"), key=lambda c: contrast(c, hi))   # dark or light text, whichever reads
    L["--band"] = L["--accent"]
    L["--on-band"] = L["--on-accent"]
    L["--band-accent"] = hi if contrast(hi, L["--band"]) >= 4.5 else L["--on-band"]
    L["--line"] = mix(acc, "#ffffff", 0.85)
    L["--ring-on"] = L["--accent"]
    L["--ring-off"] = mix(acc, "#ffffff", 0.8)
    L["--focus"] = L["--accent"]
    L["--dash"] = toward(mix(acc, "#ffffff", 0.45), "#000000", L["--bg"], 3.1)
    D = {}
    D["--bg"] = mix(acc, "#000000", 0.88)
    D["--surface"] = mix(acc, "#000000", 0.8)
    D["--tint"] = mix(acc, "#000000", 0.74)
    D["--ink"] = mix(acc, "#ffffff", 0.94)
    D["--muted"] = toward(mix(acc, "#ffffff", 0.7), "#ffffff", D["--tint"], 4.6)
    D["--accent"] = toward(mix(acc, "#ffffff", 0.55), "#ffffff", D["--tint"], 4.6)
    D["--on-accent"] = D["--bg"]
    D["--logo"] = D["--ink"]
    D["--band"] = toward(mix(acc, "#000000", 0.45), "#000000", "#ffffff", 4.6)
    D["--line"] = mix(acc, "#000000", 0.62)
    D["--ring-on"] = D["--accent"]
    D["--ring-off"] = D["--line"]
    D["--focus"] = hi if contrast(hi, D["--bg"]) >= 3 else D["--accent"]
    D["--dash"] = toward(mix(acc, "#ffffff", 0.45), "#ffffff", D["--bg"], 3.1)
    return {"light": L, "dark": D}


def adjustments(cfg, p):
    """Where the generated palette had to move the brand's own colours to stay readable: worth telling the user."""
    b = cfg["brand"]
    if b.get("palette"):
        return []
    out = []
    if p["light"]["--accent"].lower() != b["accent"].lower():
        out.append(f"accent {b['accent']} is too light for text on a white page, so {p['light']['--accent']} is used for text and buttons")
    if p["light"]["--band-accent"].lower() != b["highlight"].lower():
        out.append(f"highlight {b['highlight']} doesn't read on the accent band, so labels on the band use {p['light']['--band-accent']}")
    return out


def check_palette(p):
    """Pairs the playbook actually puts together. Returns a list of failures (empty is good)."""
    out = []
    for mode, need in (("light", [("--ink", "--bg", 4.5), ("--muted", "--bg", 4.5), ("--muted", "--tint", 4.5), ("--accent", "--bg", 4.5),
                                  ("--on-accent", "--accent", 4.5), ("--on-yellow", "--yellow", 4.5), ("--band-accent", "--band", 4.5),
                                  ("--on-band", "--band", 4.5), ("--focus", "--bg", 3), ("--dash", "--bg", 3)]),
                       ("dark", [("--ink", "--bg", 4.5), ("--muted", "--surface", 4.5), ("--accent", "--surface", 4.5),
                                 ("--on-accent", "--accent", 4.5), ("--focus", "--bg", 3)])):
        v = dict(p["light"]) if mode == "light" else {**p["light"], **p["dark"]}
        for fg, bg, n in need:
            if fg in v and bg in v and contrast(v[fg], v[bg]) < n:
                out.append(f"{mode}: {fg} on {bg} is {contrast(v[fg], v[bg]):.2f}:1, needs {n}:1")
    return out


def apply_palette(html, p):
    """Swap the template's colour variables for the brand's: the light block first, then both dark blocks."""
    def sub_block(block, vals):
        for k, v in vals.items():
            block = re.sub(r"(" + re.escape(k) + r"\s*:\s*)[^;]+;", lambda m: m.group(1) + v + ";", block)
        return block
    blocks = list(re.finditer(r":root(?:\[data-theme=\"dark\"\]|:not\(\[data-theme=\"light\"\]\))?\{[^{}]*\}", html))
    for m in reversed(blocks):
        vals = p["light"] if m.group(0).startswith(":root{") else p["dark"]
        html = html[:m.start()] + sub_block(m.group(0), vals) + html[m.end():]
    return html


# ---------------------------------------------------------------- logo

def asset(cfg, f):
    """A file named in the settings: absolute, or relative to the settings file, or (for the defaults) to the repo."""
    if not f:
        return None
    p = Path(f)
    if p.is_absolute():
        return p if p.exists() else None
    for base in (Path(cfg["_dir"]), ROOT):
        if (base / p).exists():
            return base / p
    return None


def logo_path(cfg, which):
    return asset(cfg, (cfg["brand"].get("logo") or {}).get(which))


# ---------------------------------------------------------------- font

def font_file(cfg, weight):
    """The brand font's file for a weight (Regular, Medium, SemiBold, Bold)."""
    files = cfg["brand"]["font"]["files"]
    f = asset(cfg, files.get(weight))
    if not f:
        raise SystemExit(f"brand.font.files.{weight} is missing or not found: {files.get(weight)!r}")
    return f



_BOLD = {}


def text_width(text, size, cfg=None):
    """How wide `text` sets in the brand font's Bold at `size`, measured from the font's own advance widths."""
    try:
        f = str(font_file(cfg or load(), "Bold"))
        if f not in _BOLD:
            from fontTools.ttLib import TTFont   # woff2 also needs the brotli package
            t = TTFont(f)
            _BOLD[f] = (t.getBestCmap(), t["hmtx"], t["head"].unitsPerEm)
        cmap, hmtx, upm = _BOLD[f]
        return sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in text) * size / upm
    except Exception:
        return len(text) * size * 0.78   # no fontTools: generous enough for capitals in a wide font


def wordmark(cfg, label, cls=""):
    """No logo file: the playbook's name, set in the brand font, standing in for one. geometricPrecision stops Chromium
    swapping the text to a fallback font when a scaled-down page puts it below a pixel threshold."""
    import html
    text = cfg["org"]["short"] or cfg["playbook"]["name"]
    w = max(60, math.ceil(text_width(text, 30, cfg)) + 4)
    family = html.escape(cfg["brand"]["font"]["family"])
    c = f' class="{html.escape(cls)}"' if cls else ""
    return (f'<svg{c} viewBox="0 0 {w} 40" role="img" aria-label="{html.escape(label)}" focusable="false">'
            f'<text x="0" y="30" font-family="{family}, Arial, sans-serif" font-weight="700" font-size="30" fill="currentColor" text-rendering="geometricPrecision">{html.escape(text)}</text></svg>')
