#!/usr/bin/env python3
"""Build the facilitator slides into one self-contained HTML file, plus a PDF backup.

    python3 slides/build_slides.py                                  # slides/out/slides.html
    python3 slides/build_slides.py --config examples/can/playbook.config.json
    python3 slides/build_slides.py --pdf                            # also slides/out/slides.pdf, one slide per page

Names, colours, the logo and the playbook's address come from the settings file (playbook.config.json at the repo
root, or --config, or the PLAYBOOK_CONFIG environment variable), plus an optional "slides" section: see
slides/README.md. Fonts, the logo, the QR code and any photos are inlined, so the HTML runs offline from any laptop.

The PDF needs Node and Playwright with its Chromium: set PW to the Playwright package folder
(.../node_modules/playwright), or install it where Node finds it (npm install playwright in the repo).

How the template is filled:
    {{key}}                                 a piece of text from the settings, HTML-escaped
    <!--KEY-->                              built HTML: the logo, QR codes, photos, the facilitator list
    <!--IF:x--> a <!--ELSE:x--> b <!--END:x-->   a or b, depending on the settings (the ELSE part is optional)
    /*FONTS*/  /*COLOURS*/  /*VERSION*/      the inlined fonts, the brand's colours and this script's version
"""
import argparse, base64, html, io, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import build as playbook  # noqa: E402  reuse the playbook's font and logo inlining, so the two never drift apart

VERSION = "2.0.0"
OUT = HERE / "out"

SLIDES_DEFAULT = {
    "title": "",               # the title slide's heading; empty means the forum's name ("Community forum" by default)
    "welcome": "Welcome to the session. Great to have you here!",
    "facilitators": [],        # [{"name", "role", "photo"}]: none leaves the facilitators slide out
    "playbook_image": "",      # a screenshot of the playbook for its slide: none shows the words on their own
    "playbook_image_alt": "",  # what the screenshot shows, for screen readers
}

MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".avif": "image/avif"}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def cap(s):
    return s[:1].upper() + s[1:]


def note(msg):
    print(f"  note: {msg}")


def slide_settings(cfg):
    s = {**SLIDES_DEFAULT, **(cfg.get("slides") or {})}
    people = s["facilitators"] or []
    if not isinstance(people, list) or not all(isinstance(p, dict) and str(p.get("name") or "").strip() for p in people):
        sys.exit('slides.facilitators must be a list like [{"name": "...", "role": "...", "photo": "people/sam.jpg"}], '
                 "and every entry needs a name")
    s["facilitators"] = people
    return s


def resolve(cfg, f):
    """A path from the settings: relative ones start from the settings file's folder."""
    p = Path(str(f)).expanduser()
    return p if p.is_absolute() else Path(cfg["_dir"]) / p


def display_url(url):
    """An address as people read it out: no https://, no www., no trailing slash."""
    return re.sub(r"^(https?://)?(www\.)?", "", (url or "").strip()).rstrip("/")


# ---------------------------------------------------------------- colours

def best_text(bg, *options):
    return max(options or ("#ffffff", "#000000"), key=lambda c: config.contrast(c, bg))


def deck_colours(cfg):
    """The deck's colours: the brand's accent as the slide background and its highlight for labels and fills.
    Worked out from the playbook's own palette, so the site and the slides change together."""
    C, mix, toward = config.contrast, config.mix, config.toward
    p = config.palette(cfg)["light"]
    v = {}
    v["--band"] = band = p.get("--band") or p.get("--accent") or cfg["brand"]["accent"]
    v["--on-band"] = on = p.get("--on-band") or p.get("--on-accent") or best_text(band)
    v["--fill"] = fill = p.get("--yellow") or cfg["brand"]["highlight"]
    v["--on-fill"] = p.get("--on-yellow") or best_text(fill, p.get("--ink", "#000000"), "#000000", "#ffffff")
    hi = p.get("--band-accent") or fill
    v["--hi"] = hi if C(hi, band) >= 4.5 else on
    if v["--hi"] != hi:
        note(f"the highlight {hi} doesn't read on the slide background {band}, so labels use {on}")
    # the timer ring and focus outlines only need 3:1, so the highlight can often stay
    v["--ring"] = fill if C(fill, band) >= 3 else v["--hi"]
    # the step cards: a shade lifted toward the text colour, or pushed the other way if that would cost contrast
    v["--panel"] = mix(band, on, 0.08)
    if C(on, v["--panel"]) < 4.6:
        v["--panel"] = mix(band, best_text(on, "#000000", "#ffffff"), 0.12)
    # secondary text sits on the slide and on the step cards, so it has to read on both
    v["--soft"] = toward(toward(mix(band, on, 0.9), on, band, 4.6), on, v["--panel"], 4.6)
    v["--dash"] = toward(mix(band, on, 0.62), on, band, 3.1)
    v["--chip-line"] = toward(mix(band, on, 0.55), on, band, 3.1)
    v["--paper"] = "#ffffff"
    ink = p.get("--ink") or "#1a1a1a"
    v["--paper-ink"] = ink if C(ink, "#ffffff") >= 4.5 else "#000000"
    v["--paper-line"] = mix(band, "#ffffff", 0.6)
    v["--browser-bar"] = p.get("--tint") or mix(band, "#ffffff", 0.9)
    v["--browser-dot"] = mix(band, "#ffffff", 0.7)
    v["--browser-edge"] = mix(band, on, 0.35)
    v["--fill-line"] = mix(fill, v["--on-fill"], 0.6)
    v["--fill-faint"] = mix(fill, v["--on-fill"], 0.4)
    # the presenter's controls and notes: a near-black version of the brand, so they never look like part of a slide
    v["--chrome"] = chrome = mix(band, "#000000", 0.7)
    v["--on-chrome"] = best_text(chrome)
    v["--chrome-soft"] = toward(mix(chrome, v["--on-chrome"], 0.8), v["--on-chrome"], chrome, 4.6)
    v["--chrome-hover"] = mix(chrome, v["--on-chrome"], 0.14)
    v["--chrome-hi"] = fill if C(fill, chrome) >= 4.5 else v["--on-chrome"]
    v["--chrome-focus"] = fill if C(fill, chrome) >= 3 else v["--on-chrome"]
    r, g, b = config.rgb(ink)
    v["--shadow"] = f"rgba({r},{g},{b},.45)"
    return v


# Every pairing the deck puts together: foreground, background, the WCAG 2.2 ratio it needs, and where it shows
NEEDS = [
    ("--on-band", "--band", 4.5, "slide text"),
    ("--soft", "--band", 4.5, "secondary slide text"),
    ("--hi", "--band", 4.5, "labels and the welcome line"),
    ("--on-band", "--panel", 4.5, "headings on the step cards"),
    ("--soft", "--panel", 4.5, "text on the step cards"),
    ("--on-fill", "--fill", 4.5, "text on highlight fills (timer, progress rail, numbers, cards)"),
    ("--fill", "--on-fill", 4.5, "the Keep and Hand in tags"),
    ("--paper-ink", "--paper", 4.5, "text on the white cards"),
    ("--on-chrome", "--chrome", 4.5, "presenter controls and notes"),
    ("--on-chrome", "--chrome-hover", 4.5, "a hovered control"),
    ("--chrome-soft", "--chrome", 4.5, "the key list in the notes"),
    ("--chrome-hi", "--chrome", 4.5, "the notes heading"),
    ("--ring", "--band", 3, "the timer ring"),
    ("--on-band", "--band", 3, "the focus outline on the slide"),
    ("--chrome-focus", "--chrome", 3, "the focus outline on the controls"),
    ("--dash", "--band", 3, "the write-in box outlines"),
]


def check_colours(v):
    return [f"{what}: {v[fg]} on {v[bg]} is {config.contrast(v[fg], v[bg]):.2f}:1, needs {need}:1"
            for fg, bg, need, what in NEEDS if config.contrast(v[fg], v[bg]) < need]


# ---------------------------------------------------------------- pictures

def inline_image(path, width, square=False, max_ratio=None):
    """(data URI, width, height) for an image, cut down to what the slide shows, so a phone photo doesn't add
    megabytes. SVGs, and everything if Pillow is missing, go in as they are (width and height None)."""
    path = Path(path)
    mime = MIME.get(path.suffix.lower())
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None
    if Image is None or path.suffix.lower() == ".svg":
        if not mime:
            sys.exit(f"{path}: use a .webp, .png, .jpg or .svg image")
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode(), None, None
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:  # Pillow raises several kinds for a file it can't read
        sys.exit(f"{path}: can't read this image ({e})")
    im = ImageOps.exif_transpose(im)   # phone photos are often stored sideways with a flag saying so
    if square:
        side = min(im.size)
        im = ImageOps.fit(im, (side, side))
    elif max_ratio and im.height > im.width * max_ratio:
        im = im.crop((0, 0, im.width, round(im.width * max_ratio)))   # keep the top, as a browser window would
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if im.mode in ("P", "LA", "PA") or "transparency" in im.info else "RGB")
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=82, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode(), im.width, im.height


def initials(name):
    words = [w for w in name.split() if w[:1].isalnum()]   # a double-barrelled surname counts once
    return "".join(w[0] for w in (words[:1] + words[1:][-1:])).upper()


def people_html(cfg, people):
    items = []
    for p in people:
        name = str(p["name"]).strip()
        face = esc(initials(name))
        if p.get("photo"):
            f = resolve(cfg, p["photo"])
            if f.is_file():
                uri, _, _ = inline_image(f, 368, square=True)
                # the name sits beside the photo, so the photo itself is decorative (its span is aria-hidden)
                face = f'<img src="{uri}" width="184" height="184" alt="">'
            else:
                note(f"no photo at {f}, so {name} gets their initials")
        role = f'<p class="role">{esc(p["role"])}</p>' if str(p.get("role") or "").strip() else ""
        items.append(f'<li class="person"><span class="avatar" aria-hidden="true">{face}</span>'
                     f'<div><p class="name">{esc(name)}</p>{role}</div></li>')
    if len(people) > 9:
        note(f"{len(people)} facilitators won't all fit on one slide: nine is the most that does")
    return "\n    ".join(items)


def people_class(n):
    return "people" + (" compact" if 5 <= n <= 6 else " three" if n >= 7 else "")


def hero_html(cfg, s):
    f = resolve(cfg, s["playbook_image"])
    if not f.is_file():
        note(f"no playbook screenshot at {f}, so its slide shows the words on their own")
        return ""
    uri, w, h = inline_image(f, 1720, max_ratio=0.9)
    alt = s["playbook_image_alt"] or f"The {cfg['playbook']['name']} website’s front page."
    dims = f' width="{w}" height="{h}"' if w else ""
    return f'<img src="{uri}"{dims} alt="{esc(alt)}">'


def qr_svg(url, label, dark):
    import segno
    svg = segno.make(url, error="m").svg_inline(scale=1, border=4, dark=dark, light="#ffffff", omitsize=True)
    a = f' role="img" aria-label="{esc(label)}"' if label else ' aria-hidden="true"'
    return svg.replace("<svg", f'<svg{a} focusable="false"', 1)


def hidden(svg):
    return svg.replace(' role="img" aria-label=""', ' aria-hidden="true"', 1)


def escaped(svg, wordmark):
    """build.logo and config.wordmark set names into the SVG as they are, so "A&B" would break the page. Unescaping
    before escaping keeps this right whether or not they start escaping themselves. A real logo's own text is left
    alone: it may hold tspans."""
    svg = re.sub(r'aria-label="([^"]*)"', lambda m: f'aria-label="{esc(html.unescape(m.group(1)))}"', svg, count=1)
    if wordmark:
        svg = re.sub(r"(<text\b[^>]*>)(.*?)(</text>)", lambda m: m.group(1) + esc(html.unescape(m.group(2))) + m.group(3), svg, flags=re.S)
    return svg


# ---------------------------------------------------------------- the template

def conditionals(text, flags):
    pat = re.compile(r"<!--IF:(\w+)-->(.*?)(?:<!--ELSE:\1-->(.*?))?<!--END:\1-->", re.S)
    while True:
        new = pat.sub(lambda m: m.group(2) if flags[m.group(1)] else (m.group(3) or ""), text)
        if new == text:
            return new
        text = new


def build(cfg):
    s = slide_settings(cfg)
    tpl = (HERE / "template-slides.html").read_text()
    # house style for the template's own words: no em dashes, and no spaced en dashes (they read as one)
    assert "\u2014" not in tpl and " \u2013 " not in tpl, "em dash or spaced en dash in template-slides.html"

    url = (cfg["playbook"]["url"] or "").strip()
    people = s["facilitators"]
    hero = hero_html(cfg, s) if s["playbook_image"] else ""
    join = cfg["org"].get("join") or {}
    forum = cap((cfg["org"]["forum"] or "").strip() or "community forum")
    title = str(s["title"] or "").strip() or forum
    kicker = title.lower() != forum.lower()   # a session title of its own gets the forum's name above it
    if not url:
        note("no playbook.url in the settings, so the slides have no QR code (the last slide's notes say where to add it)")

    out = conditionals(tpl, {"kicker": kicker, "people": bool(people), "image": bool(hero), "url": bool(url),
                             "join": bool(join.get("url"))})
    text = {
        "doc_title": f"{forum}: {title}" if kicker else title,
        "h1": f"{forum} slides: {title}" if kicker else f"{title} slides",
        "forum": forum, "title": title, "welcome": s["welcome"],
        "playbook": cfg["playbook"]["name"],
        "url": display_url(url), "bar": display_url(url) or cfg["playbook"]["name"],
        "join_label": join.get("label") or "Stay in touch", "join_url": display_url(join.get("url")),
        "people_class": people_class(len(people)),
        "book_cols": "cols" if hero else "cols solo",
        "slide_count": len(re.findall(r'<section class="slide ', out)),
    }
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: esc(text[m.group(1)]), out)

    colours = deck_colours(cfg)
    fails = check_colours(colours)
    if fails:
        sys.exit("These slide colours aren't readable enough (WCAG 2.2):\n  " + "\n  ".join(fails) +
                 "\nPick a different accent or highlight in the settings, or fix brand.palette.")
    for n in config.adjustments(cfg, config.palette(cfg)):
        note(n)

    has_logo = config.logo_path(cfg, "primary") is not None
    label = playbook.brand_label(cfg).replace('"', "'")
    logo = playbook.logo("primary", label, "logo" if has_logo else "logo wordmark", cfg=cfg)
    out = out.replace("<!--LOGO-->", escaped(logo, not has_logo))
    if config.logo_path(cfg, "mark"):
        mark = hidden(playbook.logo("mark", "", "mark", cfg=cfg))
    elif cfg["org"]["short"]:
        mark = escaped(hidden(config.wordmark(cfg, "", "mark wordmark")), True)
    else:
        mark = ""   # no logomark and no short name: the table card drawing goes without
    out = out.replace("<!--MARK-->", mark, 1)
    if url:
        out = out.replace("<!--QR-->", qr_svg(url, f"QR code for {display_url(url)}", colours["--paper-ink"]), 1)
        out = out.replace("<!--QR_MINI-->", qr_svg(url, "", colours["--paper-ink"]), 1)
    out = out.replace("<!--HERO-->", hero, 1)
    out = out.replace("<!--PEOPLE-->", people_html(cfg, people), 1)
    out = out.replace("/*VERSION*/", VERSION, 1)
    out = out.replace("/*COLOURS*/", "\n".join(f"  {k}:{c};" for k, c in colours.items()), 1)
    out = out.replace("/*FONTS*/", playbook.font_css(), 1)

    left = re.findall(r"<!--(?:[A-Z_]+|IF:\w+|ELSE:\w+|END:\w+)-->|\{\{\w+\}\}|/\*(?:FONTS|COLOURS|VERSION)\*/", out)
    assert not left, f"template placeholders left unfilled: {sorted(set(left))}"
    OUT.mkdir(exist_ok=True)
    dest = OUT / "slides.html"
    dest.write_text(out)
    print(f"wrote {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB, {text['slide_count']} slides, v{VERSION})")
    return dest


PDF_JS = r"""
const { chromium } = require(process.env.PW || 'playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + process.argv[2]);
  await p.emulateMedia({ media: 'print' });
  // every slide must have its fonts before printing, or weights only used on hidden slides fall back to Arial
  await p.evaluate(() => Promise.all([...document.fonts].map(f => f.load())));
  await p.evaluate(() => document.fonts.ready);
  // tagged is off by default in Playwright, which leaves the PDF with no headings, no /Lang and no structure at all
  await p.pdf({ path: process.argv[3], width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true, tagged: true, outline: true });
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
"""


def pdf(html_path):
    out = html_path.with_suffix(".pdf")
    js = html_path.parent / ".pdf.js"
    js.write_text(PDF_JS)
    try:
        subprocess.run(["node", str(js), str(html_path), str(out)], check=True)
    except FileNotFoundError:
        sys.exit("--pdf needs Node.js: install it so `node` is on the PATH")
    except subprocess.CalledProcessError:
        sys.exit("The PDF export failed. It needs Playwright and its Chromium: set PW to the Playwright folder "
                 "(.../node_modules/playwright), or run `npm install playwright && npx playwright install chromium`.")
    finally:
        js.unlink(missing_ok=True)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the facilitator slides from the settings file.")
    ap.add_argument("--config", help="the settings file (default: playbook.config.json at the repo root, or PLAYBOOK_CONFIG)")
    ap.add_argument("--pdf", action="store_true", help="also export a PDF backup, one slide per page")
    a = ap.parse_args()
    if a.config and not Path(a.config).is_file():
        sys.exit(f"No settings file at {a.config}")
    h = build(config.load(a.config))
    if a.pdf:
        pdf(h)
