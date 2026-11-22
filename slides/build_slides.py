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
import formats  # noqa: E402

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


def slide_credit(cfg):
    """The settings' "Built with" credit for the last slide: its dark-background logo (the slide is the band colour)."""
    c = cfg.get("credit") or {}
    if not c.get("show") or not c.get("text"):
        return ""
    f = config.asset(cfg, c.get("logo_dark") or c.get("logo"))
    img = f'<img src="{playbook.data_uri(f)}" alt="">' if f else ""
    inner = img + f"<span>{esc(c['text'])}</span>"
    return f'<a class="credit" href="{esc(c["url"])}">{inner}</a>' if c.get("url") else f'<p class="credit">{inner}</p>'


def agenda_slides(W, cfg):
    """The slides for a workshop laid out from its agenda: a welcome, how it works, one slide per question (its own
    timer, the sheet's boxes, a progress rail and facilitator notes) and a thank-you. Round tables keeps its own
    hand-written hour (workshop.json "slides": "legacy")."""
    group = W.group
    steps = [e for e in W.exercises[:len(W.data.get("agenda", []))]]
    welcome = W.data.get("welcome_minutes", 5)
    close = W.data.get("close_minutes", 5)
    plan, t = [f"0 to {welcome}: welcome"], welcome
    starts = []
    for e in steps:
        m = e.get("minutes", 10)
        starts.append((t, t + m))
        plan.append(f"{t} to {t + m}: {e['label']}, {e['title']} ({m} minutes)")
        t += m
    plan.append(f"{t} to {t + close}: what happens next, and close")
    total = t + close
    rail = [e.get("rail") or e["title"] for e in steps]
    out = [f"""<!-- Welcome ----------------------------------------------------------- -->
<section class="slide s-title" aria-roledescription="slide" aria-label="Welcome" tabindex="-1">
  <!--LOGO-->
  <div class="head">
    <!--IF:kicker--><p class="kicker">{{{{forum}}}}:</p><!--END:kicker-->
    <h2>{{{{title}}}}</h2>
  </div>
  <p class="welcome">{{{{welcome}}}}</p>
  <div class="slide-notes">
    <p>Minutes 0 to {welcome}: the welcome, up to {esc(steps[0]['label']) if steps else 'the first question'}.</p>
    <p>The session at a glance ({total} minutes), in minutes from the start:</p>
    <ul>{''.join(f'<li>{esc(x)}</li>' for x in plan)}</ul>
    <p>Afterwards, allow 10 minutes or so to photograph every sheet.</p>
  </div>
</section>

<!--IF:people-->
<section class="slide s-people" aria-roledescription="slide" aria-label="Your facilitators" tabindex="-1" hidden>
  <h2>Your facilitators:</h2>
  <ul class="{{{{people_class}}}}">
    <!--PEOPLE-->
  </ul>
  <div class="slide-notes"><p>Still the welcome.</p></div>
</section>
<!--END:people-->

<!-- How it works ------------------------------------------------------ -->
<section class="slide s-how" aria-roledescription="slide" aria-label="How the {{{{playbook}}}} gets made" tabindex="-1" hidden>
  <div class="top"><p class="label">How it works</p></div>
  <h2 class="q">From your sheets to the {{{{playbook}}}}</h2>
  <ol class="flow">
    <li><h3>Talk and write</h3><p>Each {esc(group)} fills in a sheet for each question. Anyone can speak; one person writes.</p></li>
    <li><h3>We photograph the sheets</h3><p>Sheets only, never people. Nothing is recorded.</p></li>
    <li><h3>AI reads, people check</h3><p>AI reads every sheet. People check each line against the photos before anything goes out.</p></li>
    <li><h3>The {{{{playbook}}}} arrives</h3><p>Soon after today. <!--IF:url-->It lives at {{{{url}}}}.<!--ELSE:url-->We’ll send it round.<!--END:url--></p></li>
  </ol>
  {'<p class="rule"><b>Names stay off the page.</b> Nothing said today is attributed to anyone.</p>' if W.privacy == "public" else ''}
  <div class="slide-notes">
    <p>The last of the welcome: {esc(steps[0]['label']) if steps else 'the first question'} starts at minute {welcome}.</p>
    <p>Thick black markers only, so the photos are readable.</p>
  </div>
</section>
"""]
    for i, e in enumerate(steps):
        boxes = {b["id"]: b for b in e["boxes"]}
        rows = (e.get("print") or {}).get("rows") or [{"height": "grow", "cells": [{"box": b["id"]}]} for b in e["boxes"]]
        rows = [r for r in rows if not all(boxes[c["box"]].get("optional") for c in r["cells"])]
        cells, heights = [], []
        for r in rows:
            heights.append("1fr" if r["height"] == "grow" else "auto")
            shares = [c.get("share", 1) for c in r["cells"]]
            spans = [max(1, round(12 * sh / sum(shares))) for sh in shares]
            spans[-1] = 12 - sum(spans[:-1])
            for c, span in zip(r["cells"], spans):
                b = boxes[c["box"]]
                if b["type"] == "row":
                    fs = b.get("fields", [])
                    fspans = [max(1, round(span * f.get("share", 1) / sum(x.get("share", 1) for x in fs))) for f in fs]
                    fspans[-1] = span - sum(fspans[:-1])
                    cells += [f'<div class="box" style="grid-column:span {fs_}"><h3>{esc(f["label"])}</h3></div>' for f, fs_ in zip(fs, fspans)]
                else:
                    hint = b.get("slide_hint", b.get("hint", ""))
                    cells.append(f'<div class="box" style="grid-column:span {span}"><h3>{esc(b.get("label", ""))}</h3>'
                                 + (f"<p>{esc(hint)}</p>" if hint else "") + "</div>")
        sl = e.get("slide") or {}
        m = e.get("minutes", 10)
        a, z = starts[i]
        here = ' aria-current="step"'
        rail_html = "".join(f'<li{here if j == i else ""}>{esc(x)}</li>' for j, x in enumerate(rail))
        notes = "".join(f"<p>{esc(n)}</p>" for n in sl.get("notes", []))
        out.append(f"""<!-- {esc(e['label'])} ------------------------------------------------------ -->
<section class="slide s-q" aria-roledescription="slide" aria-label="{esc(e['label'])}" tabindex="-1" hidden>
  <div class="top">
    <p class="label">{esc(e['label'])}<span class="sep" aria-hidden="true">·</span><span class="visually-hidden">, </span>{esc(e['short'])}</p>
    <button class="timer" type="button" data-minutes="{m}"><span class="t-time">{m}:00</span><span class="t-hint">Start timer</span></button>
  </div>
  <h2 class="q{' long' if len(e['title']) > 40 else ''}">{esc(e['title'])}</h2>
  <div class="grid" style="grid-template-columns:repeat(12,1fr);grid-template-rows:{' '.join(heights)}">
    {''.join(cells)}
  </div>
  {f'<p class="note"><b>{esc(e["label"])}</b><span>{esc(sl["prompt"])}</span></p>' if sl.get("prompt") else ''}
  <ol class="rail" aria-label="Where we are in the session">{rail_html}</ol>
  <div class="slide-notes">
    <p>Minutes {a} to {z}. Read the question out in full. {m} minutes.</p>
    {notes}
  </div>
</section>
""")
    out.append(f"""<!-- Thank you --------------------------------------------------------- -->
<section class="slide s-end" aria-roledescription="slide" aria-label="Thank you" tabindex="-1" hidden>
  <!--LOGO-->
  <div class="cols">
    <div>
      <h2>Thank you</h2>
      <p class="lede">{'The {{playbook}} goes live soon after today. Share it with anyone who couldn’t be here.' if W.privacy == 'public' else 'We’ll send the {{playbook}} round soon after today.'}</p>
      <!--IF:join--><p class="lede join">{{{{join_label}}}}<br><span class="hl">{{{{join_url}}}}</span></p><!--END:join-->
    </div>
    <!--IF:url--><div class="qr-col">
      <div class="qr-tile"><!--QR--></div>
      <p class="url">{{{{url}}}}</p>
    </div><!--END:url-->
  </div>
  <!--CREDIT-->
  <div class="slide-notes">
    <p>Minutes {t} to {total}: what happens next, and thank you.</p>
    <p>Afterwards, photograph every sheet before anyone takes them down.</p>
  </div>
</section>
""")
    return "\n".join(out)


def build(cfg):
    s = slide_settings(cfg)
    tpl = (HERE / "template-slides.html").read_text()
    W = formats.load(cfg)
    if W.data.get("slides") != "legacy":
        # every other workshop: the same deck design, its slides made from the agenda
        a, b = tpl.index('<main class="stage" id="stage">') + len('<main class="stage" id="stage">'), tpl.index("</main>")
        tpl = tpl[:a] + "\n\n" + agenda_slides(W, cfg) + "\n" + tpl[b:]
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
    logo = playbook.logo("primary", label, "logo" if has_logo else "logo wordmark", cfg=cfg, on="dark")   # it sits on the band
    out = out.replace("<!--LOGO-->", escaped(logo, not has_logo))
    if config.logo_path(cfg, "mark"):
        mark = hidden(playbook.logo("mark", "", "mark", cfg=cfg, on="light"))   # on the table card drawing
    elif cfg["org"]["short"]:
        mark = escaped(hidden(config.wordmark(cfg, "", "mark wordmark")), True)
    else:
        mark = ""   # no logomark and no short name: the table card drawing goes without
    out = out.replace("<!--MARK-->", mark, 1)
    if url:
        out = out.replace("<!--QR-->", qr_svg(url, f"QR code for {display_url(url)}", colours["--paper-ink"]), 1)
        out = out.replace("<!--QR_MINI-->", qr_svg(url, "", colours["--paper-ink"]), 1)
    out = out.replace("<!--HERO-->", hero, 1)
    out = out.replace("<!--CREDIT-->", slide_credit(cfg), 1)
    out = out.replace("<!--PEOPLE-->", people_html(cfg, people), 1)
    out = out.replace("/*VERSION*/", VERSION, 1)
    out = out.replace("/*COLOURS*/", "\n".join(f"  {k}:{c};" for k, c in colours.items()), 1)
    out = playbook.with_font(out, cfg)
    out = out.replace("/*FONTS*/", playbook.font_css(cfg), 1)

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
