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
Fonts (Poppins, OFL) and the logo are inlined, so each output is one portable file.
"""
import argparse, base64, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402

WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
LOGO_NAMES = {"primary": "primary", "secondary": "secondary", "logomark": "mark", "mark": "mark"}


def font_css():
    out = []
    for name, weight in WEIGHTS.items():
        b64 = base64.b64encode((ASSETS / "fonts" / f"poppins-{name}.woff2").read_bytes()).decode()
        out.append(
            "@font-face{font-family:\"Poppins\";font-style:normal;font-weight:%d;font-display:swap;"
            "src:url(data:font/woff2;base64,%s) format(\"woff2\")}" % (weight, b64)
        )
    return "\n".join(out)


def logo(name, label, cls="", cfg=None):
    """The brand's logo as inline SVG (name: primary, secondary or mark), or the wordmark if there's no logo file.
    Other builders (sheets, slides) call this too: pass the settings you loaded, or the default file is used."""
    cfg = cfg or config.load()
    f = config.logo_path(cfg, LOGO_NAMES.get(name, name))
    if not f:
        return config.wordmark(cfg, label, cls)
    import html as h
    svg = f.read_text()
    svg = re.sub(r"<defs>.*?</defs>", "", svg, flags=re.S)
    svg = re.sub(r'\s(id|data-name|class)="[^"]*"', "", svg)
    # currentColor lets the page theme the logo (and switch it to light in dark mode)
    attrs = f' role="img" aria-label="{h.escape(label)}" fill="currentColor" focusable="false"'
    if cls:
        attrs += f' class="{cls}"'
    return svg.replace("<svg", "<svg" + attrs, 1)


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
    return f"{o['name']} ({o['short']})" if o["name"] and o["short"] else (o["name"] or o["short"] or cfg["playbook"]["name"])


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


def check(data):
    """Catch the mistakes a hand-edit or an AI pass is most likely to make."""
    ids = {c["id"] for c in data["challenges"]}
    themes = {t["id"] for t in data["themes"]}
    n = data["meta"]["tables"]
    status = data["meta"]["status"]
    problems = []
    if status not in ("example", "template", "draft", "final"):
        problems.append(f"meta.status must be example, template, draft or final, not {status!r}")
    if status == "final":
        # nothing half-filled goes live: these are the parts every challenge page leans on
        if not data["themes"]:
            problems.append("final: no themes")
        for c in data["challenges"]:
            for field in ("title", "summary", "theme"):
                if not c.get(field):
                    problems.append(f'final: {c["id"]} has no {field}')
            if not c["actions"]:
                problems.append(f'final: {c["id"]} has no actions')
        if len(ids) != len(data["challenges"]):
            problems.append("duplicate challenge ids")
    for c in data["challenges"]:
        if c["theme"] and c["theme"] not in themes:
            problems.append(f'{c["id"]}: unknown theme {c["theme"]}')
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", c["id"]):
            problems.append(f'{c["id"]}: id must be lowercase letters, digits and hyphens (used as the URL #anchor)')
        if c["id"] in ("overview", "commitments", "resources", "about", "kit"):
            problems.append(f'{c["id"]}: id clashes with a page name')
        for a in c["actions"]:
            bad = set(a.get("stages", [])) - {"starting", "growing", "established"}
            if bad:
                problems.append(f'{c["id"]}: unknown stage {bad}')
    for t in data["themes"] + data["challenges"]:
        out = [x for x in t["tables"] if not 1 <= x <= n]
        if out:
            problems.append(f'{t.get("id")}: table numbers outside 1-{n}: {out}')
    for q in data.get("quotes", []):
        if q.get("challenge") and q["challenge"] not in ids:
            problems.append(f'quote links unknown challenge {q["challenge"]}')
        out = [x for x in q.get("tables", []) if not 1 <= x <= n]
        if out:
            problems.append(f'quote "{q.get("text", "")[:40]}": table numbers outside 1-{n}: {out}')
    for k in data["meta"].get("table_names") or {}:
        if not (str(k).isdigit() and 1 <= int(k) <= n):
            problems.append(f"meta.table_names: {k!r} isn't a table number from 1 to {n}")
    for m in data["commitments"]:
        if m.get("challenge") and m["challenge"] not in ids:
            problems.append(f'commitment links unknown challenge {m["challenge"]}')
    if problems:
        sys.exit("Data problems:\n  " + "\n  ".join(problems))


# The paper kit offered on the playbook's "Run your own" page. Copied into kit/ beside the built page,
# so the links work wherever the page goes (the draft in a run folder, playbook/, the hosting folder).
# The kit offered on the playbook's "Run your own" page. Copied into kit/ beside the built page, so the links work
# wherever the page goes. Patterns, because the builders name files after the brand.
KIT_FILES = [   # (folder, file pattern, title, note, group)
    ("slides/out", "*.html", "The slides", "Opens in any browser and works offline. Arrow keys move, T starts each question\u2019s timer, N shows the facilitator notes.", "slides"),
    ("slides/out", "*.pdf", "The slides as a PDF", "One slide per page, without the notes.", "slides"),
    ("print/out/html", "*sheet-S1*.html", "Sheet 1: Where does support get stuck?", "Type into it, or print it on A4.", "html"),
    ("print/out/html", "*sheet-S2*.html", "Sheet 2: What has helped, or not?", "Type into it, or print it on A4.", "html"),
    ("print/out/html", "*sheet-S3*.html", "Sheet 3: What could people try now, and how does it stick?", "Type into it, or print it on A4.", "html"),
    ("print/out/html", "*sheet-SS*.html", "Side sheet: Heard something good?", "Type into it, or print it on A4.", "html"),
    ("print/out/html", "*commitment-card*.html", "Commitment card", "Both halves, with the QR code and the name and organisation lines.", "html"),
    ("print/out/html", "*table-card*.html", "Table card", "The table number on one side, \u201cWe\u2019re tackling\u201d on the other.", "html"),
    ("print/out/paper", "*sheet-S1*.pdf", "Sheet 1: Where does support get stuck?", "A1 poster, one per table.", "print"),
    ("print/out/paper", "*sheet-S2*.pdf", "Sheet 2: What has helped, or not?", "A1 poster, one per table.", "print"),
    ("print/out/paper", "*sheet-S3*.pdf", "Sheet 3: What could people try now, and how does it stick?", "A1 poster, one per table.", "print"),
    ("print/out/paper", "*sheet-SS*.pdf", "Side sheet: Heard something good?", "A1 poster, one per table, out all session.", "print"),
    ("print/out/paper", "*commitment-card*.pdf", "Commitment card", "A5, perforated down the middle. One per person.", "print"),
    ("print/out/paper", "*table-cards*.pdf", "Table cards", "A4, folding to an A5 tent: the table number on one side, \u201cWe\u2019re tackling\u201d on the other.", "print"),
    ("print/out", "*.zip", "The whole paper kit", "All the print files in one zip.", "print"),
]


def kit_files(dest):
    out = []
    for folder, pattern, title, note, group in KIT_FILES:
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
    check(data)
    data["kit"] = kit_files(Path(out).parent / "kit")
    # who the playbook belongs to, for the page's wording: the settings fill any gaps in the session's meta
    data["org"] = {k: v for k, v in cfg["org"].items()}
    data["playbook"] = dict(cfg["playbook"])
    data["meta"].setdefault("series", cfg["playbook"]["name"])
    data["meta"].setdefault("kit_licence", cfg["kit"]["licence"])
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
    html = themed(html, cfg)
    if cfg["playbook"].get("searchable") and data["meta"].get("status") == "final":
        # search engines may list it: only a final playbook, and only when the settings say so (commitment cards
        # can carry names, so the default keeps every page out of search results)
        html = re.sub(r'\n?<meta name="robots" content="noindex">', "", html, count=1)
    import html as _h
    html = html.replace("<title>Community Playbook</title>", f"<title>{_h.escape(data['meta']['series'])}</title>", 1)
    html = html.replace("/*FONTS*/", font_css(), 1)
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
    page = re.sub(r"--accent:#57258c", "--accent:" + pal["light"]["--accent"], page)
    page = re.sub(r"--yellow:#ffd35d", "--yellow:" + pal["light"]["--yellow"], page)
    page = re.sub(r"--focus:#57258c", "--focus:" + pal["light"]["--focus"], page)
    page = re.sub(r"--accent:#c4a6ee", "--accent:" + pal["dark"]["--accent"], page)
    join = cfg["org"].get("join")
    page = (page.replace("/*FONTS*/", font_css(), 1)
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
