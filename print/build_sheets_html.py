#!/usr/bin/env python3
"""HTML versions of the paper kit: the four sheets, the commitment card and the table card.

    python3 print/build_sheets_html.py                          # writes print/out/html/*.html
    python3 print/build_sheets_html.py --config my.config.json  # another settings file (see build/config.py)

Each page matches its printed sheet (same words, colours and layout), and every box is a labelled text box, so a page
can be filled in on screen (an online table, a screen reader user) or printed on A4. The wording is copied from
print/build_paper.py: change it there and here together. One self-contained file per sheet: fonts and logo inline.
Names, colours, logo and the playbook's address come from the settings file. v1.1.0
"""
import argparse, html, sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import build as playbook  # noqa: E402  fonts and logo, shared with the playbook so they never drift

OUT = ROOT / "print" / "out" / "html"
e = html.escape

# The PDFs each page links to: keep in step with the names in build_paper.py
SHEET_PDF = "sheet-{code}-A1.pdf"
CARD_PDF = "commitment-card-A5-perforated.pdf"
TABLES_PDF = "table-cards-A4-fold-to-A5-tables-1-to-{n}.pdf"

CSS = """
*{box-sizing:border-box}
html{background:var(--page)}
body{margin:0;font-family:Poppins,system-ui,sans-serif;color:var(--ink);line-height:1.4}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.vh{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.intro{background:var(--band);color:var(--on-band);padding:12px 20px;font-size:.9375rem}
.intro p{margin:0 auto;max-width:980px}
.intro a{color:var(--band-accent);font-weight:600}
.intro a:focus-visible{outline-color:currentColor}
.sheet{background:var(--paper);max-width:980px;margin:20px auto;padding:28px;border-radius:6px;box-shadow:0 1px 6px rgba(0,0,0,.12);display:flex;flex-direction:column;gap:16px}
.head{display:flex;gap:18px;align-items:stretch}
.band{flex:1;background:var(--band);color:var(--on-band);border-radius:12px;padding:18px 22px}
.band .label{color:var(--band-accent);font-weight:600;margin:0 0 4px;font-size:1.05rem}
.band h1{margin:0;font-size:clamp(1.5rem,3.4vw,2.3rem);line-height:1.15;font-weight:700}
.circle{flex:none;width:132px;height:132px;border:3px solid var(--accent);border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px}
.circle label{color:var(--accent);font-weight:600}
.circle input{width:70px;text-align:center;font:inherit;font-size:1.8rem;font-weight:600;border:0;border-bottom:2px solid var(--rule);background:transparent;color:var(--ink)}
.zone{border:2px dashed var(--rule);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:6px;min-width:0}
.zone.tint{background:var(--tint)}
.zone h2,.zone legend{margin:0;font-size:1.15rem;font-weight:600;padding:0}
.zone .hint{margin:0;color:var(--hint);font-size:.9rem}
textarea{width:100%;flex:1;font:inherit;color:var(--ink);border:0;resize:vertical;background:transparent;
  background-image:repeating-linear-gradient(transparent 0 31px,var(--rule) 31px 32px);line-height:32px;padding:0 4px;min-height:96px}
input[type=text],input[type=number]{font:inherit;color:var(--ink);border:0;border-bottom:1.5px solid var(--rule);background:transparent;padding:2px 4px;min-width:0}
.row{display:grid;gap:14px}
.tally{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media (min-width:720px){.tally{grid-template-columns:repeat(8,1fr)}}
.tally label{display:flex;flex-direction:column;gap:4px;font-size:.8125rem;font-weight:500}
.tally input{width:100%;height:46px;border:1.5px solid var(--rule);border-radius:6px;text-align:center;font-size:1.2rem;background:#fff}
.countries{display:flex;gap:8px;align-items:baseline;margin-top:6px}
.countries input{flex:1}
.top3 ol{margin:4px 0 0;padding-left:1.4em;display:grid;gap:10px}
.top3 li::marker{font-weight:600}
.top3 input{width:100%}
.actions{display:grid;gap:14px}
.action .cols{display:grid;gap:12px;grid-template-columns:1fr}
@media (min-width:720px){.action .cols{grid-template-columns:46fr 27fr 27fr}}
.action .col{display:flex;flex-direction:column;gap:2px}
.action .col label{color:var(--hint);font-weight:500;font-size:.9rem}
.goodfor{border:0;margin:6px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center}
.goodfor legend{float:left;font-weight:500;margin-right:6px;font-size:.95rem}
.goodfor label{display:flex;gap:6px;align-items:center;font-size:.95rem}
.goodfor input{width:20px;height:20px;accent-color:var(--accent)}
/* a wordmark standing in for a logo file is measured roughly, so let its last letter show rather than clip */
svg.logo{overflow:visible;max-width:100%}
.foot{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;justify-content:space-between;font-size:.85rem;color:var(--hint);margin-top:4px}
.foot .brand{display:flex;gap:4px 12px;align-items:center;flex:1 1 0;min-width:min(100%,240px)}
@media (max-width:719px){.foot .brand{flex-wrap:wrap}}
/* capped, so a long wordmark can't push the note onto a second line and the sheet onto a second page */
.foot svg{height:30px;width:auto;max-width:180px;flex:none;color:var(--accent)}
.foot .code{color:var(--ink);font-weight:600}
.foot .code span{display:inline-block;width:56px;border-bottom:1.5px solid var(--ink);margin-left:6px}
@media (min-width:720px){.two{grid-template-columns:1fr 1fr}.three{grid-template-columns:1fr 1fr 1fr}.s1-bottom{grid-template-columns:1fr 1fr}}
/* commitment card: two halves, torn apart along the perforation */
.card{display:grid;grid-template-columns:1fr;background:var(--highlight);color:var(--on-highlight);border-radius:6px;max-width:980px;margin:20px auto;box-shadow:0 1px 6px rgba(0,0,0,.12)}
@media (min-width:720px){.card{grid-template-columns:1fr 1fr}.card .half + .half{border-left:2px dashed var(--card-accent)}}
.card .half{padding:22px 24px;display:flex;flex-direction:column;gap:10px;min-width:0}
.card .half + .half{border-top:2px dashed var(--card-accent)}
@media (min-width:720px){.card .half + .half{border-top:0}}
.card svg.logo{height:34px;width:auto;color:var(--card-accent);align-self:flex-start}
.card .prompt{color:var(--card-accent);font-weight:700;font-size:1.3rem;line-height:1.2}
.card textarea{min-height:190px;background-image:repeating-linear-gradient(transparent 0 31px,var(--card-lines) 31px 32px)}
.card .qr{display:flex;gap:14px;align-items:center;margin-top:auto}
.card .qr svg{width:96px;height:96px;background:#fff;padding:4px;flex:none}
.card .qr-blank{width:96px;height:96px;flex:none;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:8px;background:#fff;color:var(--ink);border:2px dashed var(--ink);font-size:.8125rem;font-weight:500;line-height:1.25}
.card .qr p{margin:0;font-size:.9rem;min-width:0;overflow-wrap:anywhere}
.card .qr b{color:var(--card-accent)}
.card .who{display:grid;gap:8px;margin-top:auto}
.card .who label{display:flex;gap:8px;align-items:baseline;font-size:.95rem}
.card .who input{flex:1;border-bottom-color:var(--card-rule)}
.card .consent{font-size:.85rem;margin:0}
/* table card: a tent, the number on one side and the challenge on the other */
.tent{max-width:980px;margin:20px auto;display:grid;gap:0;box-shadow:0 1px 6px rgba(0,0,0,.12);border-radius:6px;overflow:hidden}
.tent .side{background:#fff;padding:26px;min-height:300px;display:flex;flex-direction:column;justify-content:center;gap:12px}
.tent .side + .side{border-top:2px dashed var(--rule)}
.tent .num{display:flex;align-items:center;justify-content:center;gap:14px;color:var(--accent);font-weight:700;font-size:3rem}
.tent .num input{width:140px;font-size:3rem;font-weight:700;text-align:center;color:var(--ink)}
.tent .tackle{font-weight:700;font-size:1.6rem;color:var(--accent)}
.tent .side svg{height:34px;width:auto;color:var(--accent);align-self:flex-start}
@media print{
  @page{size:A4;margin:9mm}
  html,body{background:#fff}
  .intro{display:none}
  .sheet,.card,.tent{box-shadow:none;margin:0;max-width:none;border-radius:0}
  .sheet{padding:0;gap:3mm;min-height:277mm}
  textarea{resize:none}
  .s1-challenges textarea{min-height:68mm}.s1-bottom textarea{min-height:24mm}
  .s2-cols textarea{min-height:120mm}.s2-lessons textarea{min-height:40mm}
  .action textarea{min-height:40mm}
  .ss-cols textarea{min-height:130mm}.ss-best textarea{min-height:36mm}
  .card .half{min-height:120mm}
  .tent .side{min-height:132mm}.tent .side:first-child{transform:rotate(180deg)}
}
@media print{.card{grid-template-columns:1fr 1fr}.card .half + .half{border-top:0;border-left:2px dashed var(--card-accent)}}
"""


# ---------------------------------------------------------------- settings

def readable(fg, bg, need=4.5):
    """fg if it reads on bg; otherwise fg pushed toward black or white (whichever bg suits) until it does."""
    if config.contrast(fg, bg) >= need:
        return fg
    target = "#000000" if config.contrast("#000000", bg) >= config.contrast("#ffffff", bg) else "#ffffff"
    return config.toward(fg, target, bg, need)


def colours(cfg):
    """The page's CSS variables. Brand colours come from the playbook's light palette (worked out from the accent and
    highlight, or the brand's own list); hints and rules stay the fixed greys that pass on every brand's tint."""
    worked_out = config.palette({**cfg, "brand": {**cfg["brand"], "palette": None}})["light"]
    L = {**worked_out, **((cfg["brand"].get("palette") or {}).get("light") or {})}
    return {
        "--page": config.mix(cfg["brand"]["accent"], "#ffffff", 0.9),   # light enough that the grey rules still pass 3:1 on it
        "--paper": "#ffffff",
        "--ink": L["--ink"],
        "--tint": L["--tint"],
        "--accent": L["--accent"],
        "--band": L["--band"],
        "--on-band": L["--on-band"],
        "--band-accent": L["--band-accent"],
        "--highlight": L["--yellow"],
        "--on-highlight": L["--on-yellow"],
        "--card-accent": readable(L["--accent"], L["--yellow"]),
        "--card-lines": readable("#7a6f80", L["--yellow"], 3),   # the card's own greys, darker than the sheet's to show on a highlight
        "--card-rule": readable("#5d5363", L["--yellow"], 3),
        "--hint": "#4d4655",
        "--rule": "#8a8291",
        "--focus": "#0b57d0",
    }


def settings(cfg, tables):
    o, pb = cfg["org"], cfg["playbook"]
    url = (pb.get("url") or "").strip()
    if url and "://" not in url:
        url = "https://" + url
    u = urlparse(url)
    return SimpleNamespace(
        cfg=cfg, tables=tables, name=pb["name"], url=url,
        address=(u.netloc + u.path).rstrip("/") if url else "",
        home=url.rstrip("/") + "/#kit" if url else "",
        # the logo's accessible name: the organisation's full name, or whatever the wordmark says
        label=f"{o['name']} ({o['short']})" if o["name"] and o["short"] else (o["name"] or o["short"] or pb["name"]),
        css=":root{color-scheme:light;" + "".join(f"{k}:{v};" for k, v in colours(cfg).items()) + "}",
    )


# ---------------------------------------------------------------- pages

def page(k, title, desc, pdf, body, extra_class=""):
    kit = f'<a href="{e(k.home)}">{e(k.name)} kit</a>' if k.home else f"{e(k.name)} kit"
    intro = (f'<div class="intro" role="note"><p>{e(desc)} Type into it on screen, or print it on A4. '
             f'From the {kit}' + (f' · <a href="{e(pdf)}">Print-ready PDF</a>' if pdf else "") + '.</p></div>')
    return (f'<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{e(title)} · {e(k.name)} kit</title>\n<style>{playbook.font_css(k.cfg)}{k.css}{playbook.with_font(CSS, k.cfg)}</style>\n</head>\n'
            f'<body class="{extra_class}">\n{intro}\n<main>\n{body}\n</main>\n</body>\n</html>\n')


def logo_svg(k, cls="logo"):
    return playbook.logo("secondary", e(k.label), cls, cfg=k.cfg, on="light")   # the sheets are light only


def frame(k, label, question, code, inner):
    head = (f'<div class="head"><div class="band"><p class="label">{e(label)}</p><h1>{e(question)}</h1></div>'
            f'<div class="circle"><label for="table-no">Table</label><input id="table-no" type="text" inputmode="numeric" autocomplete="off"></div></div>')
    foot = (f'<footer class="foot"><div class="brand">{logo_svg(k)}<span>{e(f"All of this goes into the {k.name}. No names, please.")}</span></div>'
            f'<div class="code" aria-hidden="true">{e(code)} · Table<span></span></div></footer>')
    return f'<div class="sheet">{head}{inner}{foot}</div>'


def zone(zid, title, hint="", cls="", tint=False):
    h = f'<p class="hint" id="{zid}-hint">{e(hint)}</p>' if hint else ""
    desc = f' aria-describedby="{zid}-hint"' if hint else ""
    return (f'<section class="zone {cls}{" tint" if tint else ""}" aria-labelledby="{zid}-h"><h2 id="{zid}-h">{e(title)}</h2>{h}'
            f'<textarea id="{zid}" aria-labelledby="{zid}-h"{desc}></textarea></section>')


def s1(k):
    sectors = ["Public sector", "Finance", "Retail", "Tech", "Education", "Charity", "Health", "Other"]
    tally = "".join(f'<label>{e(s)}<input type="number" min="0" inputmode="numeric" aria-label="{e(s)}: how many people"></label>' for s in sectors)
    who = ('<section class="zone tint" aria-labelledby="who-h"><h2 id="who-h">Who’s at this table?</h2>'
           '<p class="hint" id="who-hint">Everyone puts one tally mark against their sector, and writes their country.</p>'
           f'<div class="tally" role="group" aria-labelledby="who-h" aria-describedby="who-hint">{tally}</div>'
           '<div class="countries"><label for="countries">Countries:</label><input id="countries" type="text"></div></section>')
    top3 = ('<section class="zone top3" aria-labelledby="top3-h"><h2 id="top3-h">Our top three</h2><ol>' +
            "".join(f'<li><input type="text" aria-label="Top three, number {i}"></li>' for i in (1, 2, 3)) + '</ol></section>')
    inner = (who + zone("challenges", "Every challenge at this table", "Write them all down. Budget, leadership, burnout, proving impact…", "s1-challenges") +
             f'<div class="row s1-bottom">{top3}{zone("tackling", "The one we’re tackling", "Copy it onto your table card too.")}</div>')
    return frame(k, "Question 1", "Where does support get stuck?", "S1", inner)


def s2(k):
    inner = (f'<div class="row two s2-cols">{zone("helped", "Helped", "What happened, and why did it work?")}'
             f'{zone("hindered", "Got in the way", "What would you change or avoid?")}</div>' +
             zone("again", "If we did it again, we’d…", cls="s2-lessons"))
    return frame(k, "Question 2", "What has helped, or not?", "S2", inner)


def s3(k):
    acts = ""
    for i in (1, 2, 3):
        cols = "".join(f'<div class="col"><label for="a{i}-{c}">{e(t)}</label><textarea id="a{i}-{c}"></textarea></div>'
                       for c, t in (("try", "What to try"), ("need", "What you need"), ("sticks", "How it sticks")))
        ticks = "".join(f'<label><input type="checkbox" name="a{i}-good" value="{e(t)}"> {e(t)}</label>' for t in ("Just starting", "Growing", "Established"))
        acts += (f'<section class="zone action" aria-labelledby="a{i}-h"><h2 id="a{i}-h">Action {i}</h2><div class="cols">{cols}</div>'
                 f'<fieldset class="goodfor"><legend>Good for:</legend>{ticks}</fieldset></section>')
    return frame(k, "Question 3", "What could people try now, and how does it stick?", "S3", f'<div class="actions">{acts}</div>')


def ss(k):
    cols = "".join(zone(z, t, h) for z, t, h in (("quotes", "Quotes", "Exact words, no names"), ("questions", "Questions", "Things nobody could answer"),
                                                ("resources", "Resources", "Links, books, people, tools")))
    inner = (f'<div class="row three ss-cols">{cols}</div>' +
             zone("best", "Best thing said today", "The table lead writes it in the last two minutes.", "ss-best", tint=True))
    return frame(k, "All session", "Heard something good? Write it here.", "SS", inner)


def card(k):
    caption = e(f"Scan for the {k.name}: what every table came up with.")
    if k.url:
        import segno
        ink = colours(k.cfg)["--ink"]
        qr = segno.make(k.url, error="m").svg_inline(scale=1, border=2, dark=ink, light="#ffffff", omitsize=True)
        qr = qr.replace("<svg", f'<svg role="img" aria-label="QR code for {e(k.address)}" focusable="false"', 1)
        caption += f"<br><b>{e(k.address)}</b>"
    else:
        # no address in the settings yet: a box to stick a QR code in, not a picture of one
        qr = '<div class="qr-blank">Your QR code here</div>'
    prompt = "One thing I will try, adapt or explore is…"
    keep = (f'<section class="half" aria-label="The half you keep">{logo_svg(k)}<label class="prompt" for="keep-text">{e(prompt)}</label>'
            f'<textarea id="keep-text"></textarea><div class="qr">{qr}<p>{caption}</p></div></section>')
    leave = (f'<section class="half" aria-label="The half you leave on the table">{logo_svg(k)}<label class="prompt" for="leave-text">{e(prompt)}</label>'
             f'<textarea id="leave-text"></textarea><div class="who"><label>Name (optional) <input type="text" autocomplete="off"></label>'
             f'<label>Organisation (optional) <input type="text" autocomplete="off"></label>'
             f'<p class="consent">Add these only if you’re happy for them to appear in the public playbook.</p></div></section>')
    return f'<h1 class="vh">Commitment card</h1><div class="card">{keep}{leave}</div>'


def table_card(k):
    return ('<h1 class="vh">Table card</h1><div class="tent">'
            f'<section class="side" aria-label="Side one: the table number"><div class="num"><label for="tent-no">Table</label>'
            f'<input id="tent-no" type="text" inputmode="numeric" autocomplete="off"></div></section>'
            f'<section class="side" aria-label="Side two: the challenge"><label class="tackle" for="tent-what">We’re tackling:</label>'
            f'<textarea id="tent-what"></textarea>{logo_svg(k)}</section></div>')


def sheets(k):
    if k.url:
        card_desc = f"The commitment card: write on both halves, tear, keep the half with the QR code. The QR code points to {k.address}."
    else:
        card_desc = "The commitment card: write on both halves, tear, keep the half with the QR code. Print or stick your playbook’s QR code in the dashed box."
    return [
        ("sheet-S1.html", "Sheet 1: Where does support get stuck?", "Sheet 1 of the paper kit.", SHEET_PDF.format(code="S1"), s1, ""),
        ("sheet-S2.html", "Sheet 2: What has helped, or not?", "Sheet 2 of the paper kit.", SHEET_PDF.format(code="S2"), s2, ""),
        ("sheet-S3.html", "Sheet 3: What could people try now?", "Sheet 3 of the paper kit.", SHEET_PDF.format(code="S3"), s3, ""),
        ("sheet-SS.html", "Side sheet: Heard something good?", "The side sheet of the paper kit, out all session.", SHEET_PDF.format(code="SS"), ss, ""),
        ("commitment-card.html", "Commitment card", card_desc, CARD_PDF, card, "card-page"),
        ("table-card.html", "Table card", "The table card folds into a tent: the number on one side, the challenge on the other.",
         TABLES_PDF.format(n=k.tables), table_card, ""),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", help="settings file (default: playbook.config.json at the repo root, or $PLAYBOOK_CONFIG)")
    ap.add_argument("--tables", type=int, default=12, help="how many table cards the linked PDF holds (default 12)")
    a = ap.parse_args()
    if a.config and not Path(a.config).is_file():
        ap.error(f"no settings file at {a.config}")   # config.load would quietly fall back to the defaults
    if a.tables < 1:
        ap.error("--tables must be at least 1")
    k = settings(config.load(a.config), a.tables)
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, title, desc, pdf, fn, cls in sheets(k):
        out = page(k, title, desc, pdf, fn(k), cls)
        if "\u2014" in out or " \u2013 " in out:
            # house style avoids them; the only way in is through a name in the settings
            print(f"  note: {fname} has an em dash or spaced en dash, from the settings")
        (OUT / fname).write_text(out)
        print(f"wrote {(OUT / fname).relative_to(ROOT)} ({len(out.encode()) // 1024} KB)")


if __name__ == "__main__":
    main()
