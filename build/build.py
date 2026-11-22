#!/usr/bin/env python3
"""Build the playbook website (and its holding page) into self-contained HTML.

    python3 build/build.py                                        # the example and the blank template, in playbook/
    python3 build/build.py runs/<run>/session.json --out playbook/index.html     # your session
    python3 build/build.py --holding --out site/                  # a "coming soon" page for the playbook's address
    add --config <file> to use settings other than playbook.config.json (examples/can/playbook.config.json is one)

meta.status in the data decides the mode: example (a banner), template or draft (dashed boxes show what's still
empty, plus source tags on every line), final (empty sections hide, and the build refuses gaps that matter).

The brand (names, colours, logo, the playbook's address) comes from the settings file: see build/config.py.
The colours are checked for WCAG 2.2 contrast every build, and the build stops if a pairing fails.
The font (Poppins, OFL, unless the settings name another) and the logo are inlined, so each output is one portable file.
"""
import argparse, base64, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import formats  # noqa: E402

WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
LOGO_NAMES = {"primary": "primary", "secondary": "secondary", "logomark": "mark", "mark": "mark"}


MIME = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf"}
FONT_FORMAT = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}


def data_uri(f):
    f = Path(f)
    return f"data:{MIME[f.suffix.lower()]};base64," + base64.b64encode(f.read_bytes()).decode()


def font_css(cfg=None):
    """@font-face rules for the brand font, with the files inlined."""
    cfg = cfg or config.load()
    family = cfg["brand"]["font"]["family"]
    out = []
    for name, weight in WEIGHTS.items():
        f = config.font_file(cfg, name)
        out.append(
            "@font-face{font-family:\"%s\";font-style:normal;font-weight:%d;font-display:swap;"
            "src:url(%s) format(\"%s\")}" % (family, weight, data_uri(f), FONT_FORMAT[f.suffix.lower()])
        )
    return "\n".join(out)


def with_font(html, cfg):
    """Swap the default typeface's name for the brand font's wherever a page's CSS names it."""
    family = cfg["brand"]["font"]["family"]
    if family == "Poppins":
        return html
    return html.replace('"Poppins"', f'"{family}"').replace("Poppins,", f'"{family}",')


def logo(name, label, cls="", cfg=None, on="auto"):
    """The brand's logo (name: primary, secondary or mark), or the wordmark if there's no logo file.
    Other builders (sheets, slides) call this too: pass the settings you loaded, or the default file is used.

    An SVG logo is recoloured to the page's logo colour (so it follows dark mode) unless brand.logo.keep_colours is
    set. A logo in its own colours, or a PNG, can have a second file for dark backgrounds, named <name>_dark
    (e.g. "secondary_dark"). `on` says what it sits on: "light", "dark", or "auto" (both, swapped by the page's theme,
    which must style .brand-light and .brand-dark)."""
    cfg = cfg or config.load()
    key = LOGO_NAMES.get(name, name)
    f = config.logo_path(cfg, key)
    if not f:
        return config.wordmark(cfg, label, cls)
    dark = config.logo_path(cfg, key + "_dark")
    keep = bool((cfg["brand"].get("logo") or {}).get("keep_colours")) or f.suffix.lower() != ".svg"
    if not keep:
        return _logo_file(f, label, cls, recolour=True)
    if on == "dark":
        return _logo_file(dark or f, label, cls)
    if on == "light" or not dark:
        return _logo_file(f, label, cls)
    return _logo_file(f, label, (cls + " brand-light").strip()) + _logo_file(dark, label, (cls + " brand-dark").strip())


def _logo_file(f, label, cls="", recolour=False):
    import html as h
    c = f' class="{h.escape(cls)}"' if cls else ""
    if f.suffix.lower() != ".svg":
        return f'<img{c} src="{data_uri(f)}" alt="{h.escape(label)}">'
    svg = f.read_text()
    attrs = f' role="img" aria-label="{h.escape(label)}"'
    if recolour:
        svg = re.sub(r"<defs>.*?</defs>", "", svg, flags=re.S)
        svg = re.sub(r'\s(id|data-name|class)="[^"]*"', "", svg)
        # currentColor lets the page theme the logo (and switch it to light in dark mode)
        attrs += ' fill="currentColor"'
    return svg.replace("<svg", "<svg" + attrs + ' focusable="false"' + c, 1)


def nav_html(W):
    """The header's links, from the workshop's pages ([id, label], in order)."""
    import html as h
    return "\n".join(f'        <li><a href="#{h.escape(i)}" data-nav="{h.escape(i)}">{h.escape(label)}</a></li>'
                     for i, label in W.data.get("pages", [["overview", "Playbook"]]))


def credit_html(cfg):
    """The small "Built with" line for the foot of the page, from the credit settings ("" when it's switched off)."""
    import html as h
    c = cfg.get("credit") or {}
    if not c.get("show") or not c.get("text"):
        return ""
    imgs = ""
    for key, cls in (("logo", "brand-light"), ("logo_dark", "brand-dark")):
        f = config.asset(cfg, c.get(key))
        if f:
            # decorative: the words beside it say the same thing
            imgs += f'<img class="credit-logo {cls}" src="{data_uri(f)}" alt="">'
    if imgs and "brand-dark" not in imgs:
        imgs = imgs.replace(" brand-light", "")
    inner = imgs + f'<span>{h.escape(c["text"])}</span>'
    if c.get("url"):
        return f'<a class="credit" href="{h.escape(c["url"])}">{inner}</a>'
    return f'<span class="credit">{inner}</span>'


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "playbook"


def share_tags(data, cfg, out_dir):
    """Link-preview tags (LinkedIn, Slack, Teams...) for a final playbook, when the settings give its address
    (playbook.url) and a preview picture (playbook.share.image). The picture has to be a real file at a full web
    address, so it's copied beside the page. The description's counts come from the data, so they can't drift."""
    import html as h
    m, pb = data["meta"], cfg["playbook"]
    share = pb.get("share") or {}
    if not pb.get("url") or m.get("status") != "final":
        return ""
    url = pb["url"].rstrip("/") + "/"
    acts = sum(len(c.get("actions", [])) for c in data["challenges"])
    desc = (f"What the people at the {cfg['org']['forum']}{' at ' + m['event'] if m.get('event') else ''} wrote down: "
            f"{len(data['challenges'])} challenges, {acts} actions to try and {len(data['commitments'])} commitments.")
    og = {"og:type": "website", "og:site_name": m["series"], "og:title": m.get("title") or m["series"], "og:description": desc, "og:url": url}
    card = "summary"
    picture = config.asset(cfg, share.get("image"))
    if picture:
        if not share.get("image_alt"):
            sys.exit("playbook.share.image needs image_alt: a sentence describing the picture")
        name = "share" + picture.suffix.lower()
        shutil.copy(picture, Path(out_dir) / name)
        og["og:image"] = url + name
        og["og:image:alt"] = share["image_alt"]
        try:
            from PIL import Image
            with Image.open(picture) as im:
                og["og:image:width"], og["og:image:height"] = str(im.width), str(im.height)
        except Exception:
            pass
        card = "summary_large_image"
    out = [f'<meta name="description" content="{h.escape(desc)}">']
    out += [f'<meta property="{k}" content="{h.escape(v)}">' for k, v in og.items()]
    out += [f'<meta name="twitter:card" content="{card}">']
    return "\n".join(out)


def header_logo(cfg):
    """The site header: the logo file, or the org's short name as a wordmark, or nothing (the name beside it is enough)."""
    if config.logo_path(cfg, "secondary") or cfg["org"]["short"]:
        return logo("secondary", brand_label(cfg), cfg=cfg)
    return ""


def header_name(cfg, series):
    """The words beside the logo: the playbook's name without the org's own name in front ("CAN Community Playbook" -> "Community<br>Playbook")."""
    import html as h
    short = cfg["org"]["short"]
    name = series[len(short):].strip() if short and series.startswith(short + " ") else series
    words = name.split()
    if len(words) >= 2:
        half = (len(words) + 1) // 2
        return h.escape(" ".join(words[:half])) + "<br>" + h.escape(" ".join(words[half:]))
    return h.escape(name)


def brand_label(cfg):
    o = cfg["org"]
    if o["name"] and o["short"] and o["name"] != o["short"]:
        return f"{o['name']} ({o['short']})"
    return o["name"] or o["short"] or cfg["playbook"]["name"]


def supporter_logos(data, cfg):
    """Inline each supporter's light and dark logo as data URIs, keyed by meta.supporters[].logo. Logo files go in a
    supporters/ folder beside the settings file, named <logo>-light.svg (or .png) and <logo>-dark.svg."""
    out = {}
    folder = Path(cfg["_dir"]) / "supporters"
    for sp in data["meta"].get("supporters", []):
        key = sp.get("logo")
        entry = {}
        for variant in ("light", "dark"):
            for ext, mime in (("svg", "image/svg+xml"), ("png", "image/png")):
                f = folder / f"{key}-{variant}.{ext}"
                if f.exists():
                    entry[variant] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
                    break
        if "light" in entry:
            out[key] = entry
        elif key:
            print(f"  note: no logo file for supporter {sp.get('name')!r}; it will show as text")
    return json.dumps(out)


def json_for_script(data):
    # "</" would close the <script> element early
    return json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")


def check(data, W=None):
    """Catch the mistakes a hand-edit or an AI pass is most likely to make: the workshop's own rules (rules.py)."""
    W = W or formats.load(config.load())
    rules = W.rules()
    problems = rules.check(data) if rules and hasattr(rules, "check") else []
    if problems:
        sys.exit("Data problems:\n  " + "\n  ".join(problems))


# The kit offered on the playbook's "Run your own" page comes from the workshop (formats.Workshop.kit_files): each
# exercise lists its fill-in page and print file. They're copied into kit/ beside the built page, so the links work
# wherever the page goes. Patterns, because the builders name files after the brand.


def kit_files(dest, W):
    out = []
    for folder, pattern, title, note, group in W.kit_files():
        found = sorted((ROOT / folder).glob(pattern), key=lambda f: f.stat().st_mtime)
        if not found:
            continue
        f = found[-1]
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest / f.name)
        size = f.stat().st_size
        out.append({"href": f"{dest.name}/{f.name}", "title": title, "note": note, "group": group,
                    "kind": {".pdf": "PDF", ".zip": "zip", ".html": "web page"}[f.suffix],
                    "size": f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} KB"})
    return out


def themed(html, cfg):
    """The brand's colours in the page, checked for contrast first."""
    pal = config.palette(cfg)
    fails = config.check_palette(pal)
    if fails:
        sys.exit("These colours aren't readable enough (WCAG 2.2):\n  " + "\n  ".join(fails) +
                 "\nPick a different accent or highlight in the settings, or fix brand.palette.")
    for note in config.adjustments(cfg, pal):
        print(f"  note: {note}")
    return config.apply_palette(html, pal)


def build_playbook(data_path, out, cfg):
    data = json.loads(Path(data_path).read_text())
    W = formats.load(cfg)
    check(data, W)
    data["kit"] = kit_files(Path(out).parent / "kit", W)
    # who the playbook belongs to, for the page's wording: the settings fill any gaps in the session's meta
    data["org"] = {k: v for k, v in cfg["org"].items()}
    data["playbook"] = dict(cfg["playbook"])
    data["meta"].setdefault("series", cfg["playbook"]["name"])
    data["meta"].setdefault("kit_licence", cfg["kit"]["licence"])
    # the tools' home, for the "Run your own" page: the session can override the settings, and "" leaves it out
    links = data["meta"].setdefault("links", {}) if isinstance(data["meta"].get("links", {}), dict) else {}
    links.setdefault("source", cfg["kit"].get("source") or "")
    data["credit_html"] = credit_html(cfg)
    data["sheet_names"] = W.sheet_names()          # for the draft's source tags ("T07 · Sheet 2")
    data["card_prefixes"] = list(W.card_prefixes())
    data["file_name"] = (cfg["playbook"].get("file_name") or slug(data["meta"]["series"])).removesuffix(".html") + ".html"
    hero = data["meta"].get("hero") or {}
    if hero.get("file"):
        # a photo across the top of the homepage, inlined so the page stays one portable file
        f = Path(hero["file"]) if Path(hero["file"]).is_absolute() else Path(data_path).parent / hero["file"]
        if not f.exists():
            f = Path(cfg["_dir"]) / hero["file"]
        from PIL import Image
        with Image.open(f) as im:
            hero["width"], hero["height"] = im.size
        mime = {".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}[f.suffix.lower()]
        hero["src"] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
        if not hero.get("alt"):
            sys.exit("meta.hero needs alt text")
    html = (ROOT / "build" / "template-playbook.html").read_text()
    # the workshop's own views go into the shared page, and its pages into the navigation
    html = html.replace("/*VIEWS*/", W.views_js().rstrip(), 1)
    html = html.replace("<!--NAV-->", nav_html(W), 1)
    html = themed(html, cfg)
    if cfg["playbook"].get("searchable") and data["meta"].get("status") == "final":
        # search engines may list it: only a final playbook, and only when the settings say so (commitment cards
        # can carry names, so the default keeps every page out of search results)
        html = re.sub(r'\n?<meta name="robots" content="noindex">', "", html, count=1)
    import html as _h
    html = html.replace("<title>Community Playbook</title>", f"<title>{_h.escape(data['meta']['series'])}</title>", 1)
    html = html.replace("/*FONTS*/", font_css(cfg), 1)
    html = with_font(html, cfg)
    html = html.replace("<!--SHARE-->", share_tags(data, cfg, Path(out).parent), 1)
    html = html.replace("<!--LOGO-->", header_logo(cfg), 1)
    html = html.replace("<span>Community<br>Playbook</span>", f"<span>{header_name(cfg, data['meta']['series'])}</span>", 1)
    html = html.replace("/*DATA*/", json_for_script(data), 1)
    html = html.replace("/*SUPPORTER_LOGOS*/{}", supporter_logos(data, cfg), 1)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"{out}  {len(html.encode()) / 1024:.0f} KB  status={data['meta']['status']}")


def build_holding(out_dir, cfg, when="Coming soon"):
    """A page for the playbook's address (the QR code on the commitment card) until the playbook itself goes up."""
    import html as h
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    page = (ROOT / "build" / "template-holding.html").read_text()
    pal = config.palette(cfg)
    # the page's colours from the palette (light first, then the dark-mode block), whatever the template holds now
    keys = ["--bg", "--surface", "--ink", "--muted", "--accent", "--line", "--yellow", "--on-yellow", "--focus"]
    css = lambda mode: " ".join(f"{k}:{pal[mode][k]};" for k in keys if k in pal[mode])
    page = re.sub(r":root\{[^}]*\}", lambda m: ":root{ " + css("light") + " }", page, count=1)
    page = re.sub(r"(@media \(prefers-color-scheme: dark\)\{\s*):root\{[^}]*\}", lambda m: m.group(1) + ":root{ " + css("dark") + " }", page, count=1)
    join = cfg["org"].get("join")
    page = with_font(page, cfg)
    page = (page.replace("/*FONTS*/", font_css(cfg), 1)
                .replace("<!--CREDIT-->", credit_html(cfg), 1)
                .replace("<!--LOGO-->", logo("secondary", brand_label(cfg), "logo", cfg=cfg), 1)
                .replace("{{NAME}}", h.escape(cfg["playbook"]["name"]))
                .replace("{{WHEN}}", h.escape(when))
                .replace("{{FORUM}}", h.escape(cfg["org"]["forum"]))
                .replace("{{JOIN}}", f'<p class="muted">In the meantime, <a href="{h.escape(join["url"])}">{h.escape(join["label"])}</a>.</p>' if join else ""))
    (out / "index.html").write_text(page)
    # belt and braces with the meta tag: keep the placeholder out of search results until the real playbook lands
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex\n")
    print(f"{out / 'index.html'}  {len(page.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the playbook site from a session file.")
    ap.add_argument("data", nargs="?", help="a session.json (leave out to build the example and the blank template)")
    ap.add_argument("--out", help="the page to write (default playbook/index.html); with --holding, the folder to write into")
    ap.add_argument("--config", help="settings file (default: playbook.config.json)")
    ap.add_argument("--holding", action="store_true", help="build the coming-soon page instead")
    ap.add_argument("--when", default="Coming soon", help="the holding page's date line, e.g. \"Coming 19 November\"")
    a = ap.parse_args()
    cfg = config.load(a.config)
    if a.holding:
        build_holding(a.out or ROOT / "site", cfg, a.when)
    elif a.data:
        build_playbook(a.data, a.out or ROOT / "playbook" / "index.html", cfg)
    else:
        build_playbook(ROOT / "examples" / "example-playbook.json", ROOT / "playbook" / "index.html", cfg)
        build_playbook(ROOT / "examples" / "session-template.json", ROOT / "playbook" / "template.html", cfg)
