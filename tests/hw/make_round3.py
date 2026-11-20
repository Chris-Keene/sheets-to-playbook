#!/usr/bin/env python3
"""Round 3 of the handwriting stress test: what real people did in a dry run, aimed at S2, S3 and the side sheet.

    python3 tests/hw/make_round3.py      # writes tests/hw/round3/inbox/ and tests/hw/round3/truth.json
    python3 tests/hw/score.py <run> --truth tests/hw/round3/truth.json

Needs the same fonts and printed sheets as make_hw_tests.py (tests/hw/get_fonts.py, print/build_paper.py).
The first photos of real handwriting (a dry run, not shipped) only covered S1 and the cards, and turned up traps
the fonts never made: printed prompts copied into answer boxes, yellow pens, two tables writing the same number,
tallies in four pens, untorn cards with a different message on each half, sign-offs, and one card photographed
twice. Round 3 puts those traps on all four sheets, plus two photo habits likely on the day: two sheets in one
photo, and a photo upside down in the frame (no EXIF flag to fix it). Reuses make_hw_tests.py for the sheets,
hands and camera.
ALL CONTENT IS SYNTHETIC TEST DATA. Names and organisations in it are invented.
"""
import json, random, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))      # so the import works from any working directory
import make_hw_tests as m
OUT = HERE / "round3" / "inbox"
TRUTH = HERE / "round3" / "truth.json"
# pale inks people grabbed in the dry run: yellow marker, pink highlighter, orange
m.INKS.update(yellow=(238, 204, 46), highlighter=(246, 112, 176), orange=(238, 142, 36))

PROFILES = {
    3: "Copied prompts: the printed prompts written into the answer boxes, the pick box holds the copied heading, an S3 row of prompts only",
    5: "Pale pens: yellow marker, pink highlighter and orange on every sheet",
    22: "Two tables wrote 22 (this one): different people, countries and content",
    91: "Two tables wrote 22 (the other one): should get a spare number from 91",
    8: "Photo habits and a messy tally: S2 and S3 in one photo, the side sheet upside down, a tally close-up, four pens on the tally",
    12: "Names inside items on the side sheet, a URL and a handle, quotes in speech marks",
}
m.PROFILES.update(PROFILES)

T = {}
T[3] = dict(writers=[("kalam", 17, "black", "marker", 0.03), ("indie", 17, "blue", "marker", -0.04), ("gochi", 18, "black", "marker", 0.06)],
    tally={"Public sector": 3, "Charity": 1}, countries="UK, Ireland",
    S1=dict(challenges=[dict(text="Challenges we're facing are:", copied=True),
                        "Accessibility is always the last thing in the sprint", "No one owns the accessibility statement",
                        "Contractors leave and take the knowledge", "We only test with automated tools"],
            top3=["Last thing in the sprint", "Nobody owns the statement", "Only automated testing"],
            pick="The one we're tackling", pick_copied=True),
    S2=dict(helped=[dict(text="What happened, and why did it work?", copied=True),
                    "A champion in every squad with two hours a week", "Bug bash days with prizes"],
            hindered=[dict(text="What would you change or avoid?", copied=True),
                      "Champions chosen without asking them", "Prizes stopped after the first quarter"],
            lessons=["Ask people to volunteer, don't assign them"]),
    S3=[dict(action="Two hours a week for each champion", needs="Line managers to protect the time", sticks="Put it in their objectives", stages=["starting", "growing"]),
        dict(action="Something someone could start on Monday.", needs="What would make it happen?", sticks="What stops it fading after a month?", stages=[], copied=True)],
    SS=dict(quotes=["If it's everyone's job it's nobody's job"], questions=["How do you keep champions going after year one?"],
            resources=["A11y Project checklist"], best="Volunteers, not conscripts"))

T[5] = dict(writers=[("patrick", 17, "black", "marker", 0.02), ("caveat", 18, "orange", "marker", 0.05)],
    tally={"Retail": 2, "Tech": 2, "Other": 1}, countries="UK, Portugal",
    S1=dict(challenges=["Our app store reviews mention accessibility", "Design system has no accessible patterns",
                        dict(text="Product managers don't see the risk", ink="yellow"), "Testing devices are shared and always missing"],
            top3=["Design system", "PMs don't see the risk", "No devices"],
            pick="Getting product managers to see the risk"),
    S2=dict(helped=[dict(text="Playing a screen reader demo in sprint review", ink="highlighter"), "Adding accessibility bugs to the risk log",
                    dict(text="A shared device library", ink="yellow")],
            hindered=[dict(text="Demo felt like a lecture", ink="orange"), "Risk log owned by a different team"],
            lessons=[dict(text="Let the PM drive the screen reader themselves", ink="yellow")]),
    S3=[dict(action="PM drives a screen reader for ten minutes", needs="A quiet room and headphones", sticks="Do it at every new feature kickoff", stages=["starting"]),
        dict(action="Device library with a booking sheet", needs="Five old phones and a shelf", sticks="Someone checks it every Friday", stages=["growing"])],
    SS=dict(quotes=[dict(text="My PM went quiet after the screen reader demo", ink="highlighter")], questions=[dict(text="Who pays for test devices?", ink="yellow")],
            resources=["Apple Accessibility Inspector"], best="Let them drive it"))

T[22] = dict(writers=[("architect", 16, "black", "marker", 0.0), ("shadows", 18, "black", "marker", 0.07)],
    tally={"Finance": 4, "Tech": 1}, countries="UK, USA",
    S1=dict(challenges=["Regulators ask but nobody checks", "Old mainframe screens nobody will touch",
                        "Accessibility budget comes from the innovation pot", "Champions all leave for better jobs"],
            top3=["Regulators", "Mainframe screens", "Budget from innovation pot"],
            pick="Getting a permanent accessibility budget"),
    S2=dict(helped=["Linked it to the Consumer Duty", "Showed the cost of complaints"],
            hindered=["Budget cut every January", "Pilot projects with no owner after"],
            lessons=["Tie the budget to a regulation, not a project"]),
    S3=[dict(action="Write accessibility into the Consumer Duty plan", needs="Compliance to co-own it", sticks="Reported to the board each quarter", stages=["growing", "established"])],
    SS=dict(quotes=["Budget follows the regulator"], questions=["Does Consumer Duty cover apps?"],
            resources=["FCA Consumer Duty guidance"], best="Follow the regulator"))

T[91] = dict(writers=[("gloria", 13, "blue", "marker", 0.04), ("sueellen", 14, "black", "marker", -0.03)],
    number_circle=22, number_footer=22,
    tally={"Education": 2, "Health": 2, "Charity": 1}, countries="Scotland, Wales",
    S1=dict(challenges=["Staff think captions are only for deaf students", "PDF course handbooks",
                        "IT says the VLE is the supplier's problem", "Disabled students tired of asking"],
            top3=["Captions myth", "PDF handbooks", "Tired of asking"],
            pick="Stop students having to ask"),
    S2=dict(helped=["Students union ran the campaign", "Captions on by default in the lecture tool"],
            hindered=["Each faculty bought its own tools"], lessons=["Make the default the accessible one"]),
    S3=[dict(action="Captions on by default everywhere", needs="IT to change one setting", sticks="It's the default so nobody has to remember", stages=["starting"]),
        dict(action="HTML handbooks instead of PDF", needs="One template and a writer", sticks="New handbooks only in HTML", stages=["growing"])],
    SS=dict(quotes=["Default beats training"], questions=["Who checks supplier VPATs at a university?"],
            resources=["Jisc accessibility regulations guide"], best="Default beats training"))

T[8] = dict(writers=[("reenie", 16, "black", "marker", 0.1), ("homemade", 11, "black", "marker", 0.12), ("kalam", 16, "blue", "marker", 0.0)],
    tally={"Tech": 4, "Retail": 3, "Finance": 2, "Public sector": 1}, tally_inks=["black", "blue", "red", "green"],
    countries="UK, Germany, India",
    S1=dict(challenges=["Release trains leave no time to fix", "Accessibility tickets closed as won't fix",
                        "No screen reader users on the team", "Burnout after the EAA push"],
            top3=["No time to fix", "Won't fix tickets", "Burnout"],
            pick="Stopping accessibility tickets being closed as won't fix"),
    S2=dict(helped=["Severity agreed with customer support", "A weekly fifteen minute bug triage"],
            hindered=["Triage skipped in release weeks", "Support tickets never linked to bugs"],
            lessons=["Protect triage in release weeks"]),
    S3=[dict(action="Link every support ticket to its bug", needs="A field in Jira and Zendesk", sticks="Weekly report of linked tickets", stages=["starting", "growing"]),
        dict(action="No won't fix without a second opinion", needs="Two named reviewers", sticks="It's in the definition of done", stages=["growing"]),
        dict(action="Hire one screen reader user as a tester", needs="Budget for a contract role", sticks="Their findings go to sprint review", stages=["established"])],
    SS=dict(quotes=["Won't fix means won't use"], questions=["How do you link support data to bugs?"],
            resources=["Zendesk to Jira integration"], best="Protect triage"))

T[12] = dict(writers=[("caveat", 17, "black", "marker", 0.02), ("nothing", 12, "black", "marker", 0.15), ("grace", 14, "black", "marker", 0.0)],
    tally={"Health": 3, "Public sector": 2}, countries="UK",
    S1=dict(challenges=["Clinical systems we can't change", "Letters still sent as scanned PDFs", "No accessibility in the digital strategy"],
            top3=["Clinical systems", "Scanned letters", "Not in the strategy"],
            pick="Getting accessibility into the digital strategy"),
    S2=dict(helped=["Patient panel reviewed the new app", "Director of digital spoke at the launch"],
            hindered=["Panel only met once"], lessons=["Keep the panel meeting every month"]),
    S3=[dict(action="Monthly patient panel", needs="Expenses budget for panel members", sticks="Panel signs off every release", stages=["growing"])],
    SS=dict(quotes=["Priya said nothing about us without us", "If the letter is a scan, it's not a letter"],
            questions=["Ask Marcus about the panel budget?"],
            resources=["www.nhs.uk/accessibility", "@a11yNHS on LinkedIn"], best="Nothing about us without us"))

SHOTS = {3: {}, 5: dict(light=0.95), 22: {}, 91: dict(keystone=0.05), 8: {}, 12: dict(light=0.9)}

# Cards. `stub` is the half with the Name and Organisation lines (the commitment); `qr` the half people keep.
# `signoff` is written under the stub text: it is not part of the commitment. Truth follows RAW_FORMAT's card rules.
CARDS = [
    dict(key="A", torn=False, stub="Run a screen reader test on one journey", qr="Run a screen reader test on one journey",
         name="Ana Silva", org="Corbel Insurance", font="patrick"),
    dict(key="B", torn=False, stub="Set up a monthly champions call", qr="Learning from others", font="kalam"),
    dict(key="C", torn=False, stub="Book a disabled user to test our app", qr="", font="caveat"),
    dict(key="D", stub="Get accessibility into our sprint reviews", signoff="Thanks Sam :)", font="indie"),
    dict(key="E", stub="Write our first accessibility statement", signoff="Great session!", name="Dev", font="gochi"),
    dict(key="F", stub="Ask design for a contrast check in Figma", font="architect", ink="orange"),
    dict(key="G", half="qr", qr="Share the playbook with my team", font="shadows"),
    dict(key="H", stub="Pair with a developer on one bug a week", name="Tom", font="reenie", twice=True),
    dict(key="I", stub="Add alt text checks to our CMS workflow", org="Eastmoor Council", font="grace"),
    dict(key="J", stub="Find our accessibility statement and read it", font="justme", ink="biro", pen="biro", size=5),
]


def card_image(base, c, rng, i):
    """The whole card, or one half of it, written on. Card coordinates are mm at 2x PX (see make_cards)."""
    m.SIZE_BOOST = 1.15
    sheet = m.Sheet(base.copy())
    wr = m.Writer(c["font"], 2 * c.get("size", 6), c.get("ink", "black"), c.get("pen", "marker"), rng.uniform(-0.05, 0.12), seed=500 + i)
    lines = m.GEO["card"]["lines"]
    def write(text, x_mm):
        y = sheet.write(text, wr, x_mm * 2, lines[0][1] * 2 - 2, 2 * 85, line_gap=9 / (wr.size / 2))[0]
        return y
    if c.get("stub") is not None and c.get("half") != "qr":
        y = write(c["stub"], lines[0][0])
        if c.get("signoff"):
            sheet.write(c["signoff"], wr, lines[0][0] * 2 + 10, y + 4, 2 * 70, max_lines=1)
        if c.get("name"):
            sheet.write(c["name"], wr, m.GEO["card"]["name"][0] * 2, (m.GEO["card"]["name"][1] - 1) * 2, 2 * 55, max_lines=1)
        if c.get("org"):
            sheet.write(c["org"], wr, m.GEO["card"]["org"][0] * 2, (m.GEO["card"]["org"][1] - 1) * 2, 2 * 46, max_lines=1)
    if c.get("qr"):
        write(c["qr"], lines[0][0] - 105)
    im = sheet.img.convert("RGB")
    W, H = im.size
    if c.get("torn", True):   # torn along the perforation: keep the half that was handed in
        im = im.crop((0, 0, W // 2, H)) if c.get("half") == "qr" else im.crop((W // 2, 0, W, H))
    return im


def card_truth(c):
    if c.get("half") == "qr":
        return {"text": c["qr"], "note": "only the QR half came in: transcribe it, no name or org"}
    t = {"text": c["stub"]}
    for f in ("name", "org"):
        if c.get(f):
            t[f] = c[f]
    notes = []
    if c.get("torn") is False:
        notes.append(f"untorn; QR half says {c['qr']!r}" if c.get("qr") else "untorn; QR half blank")
    if c.get("signoff"):
        notes.append(f"sign-off {c['signoff']!r} left out of the text")
    if c.get("twice"):
        notes.append("photographed twice (second photo upside down): one card")
    if c.get("ink") == "orange":
        notes.append("orange highlighter: correct or flagged")
    if notes:
        t["note"] = "; ".join(notes)
    return t


def table_top(cards, rng, per_row, size=(4032, 3024)):
    wood = (128, 94, 64)
    top = Image.new("RGB", size, wood)
    cw = (size[0] - 120) // per_row
    for k, c in enumerate(cards):
        c = c.copy(); c.thumbnail((cw - 60, 1300))
        c = c.rotate(rng.uniform(-6, 6), expand=True, fillcolor=wood)
        top.paste(c, (60 + (k % per_row) * cw, 100 + (k // per_row) * 1450))
    a = np.asarray(top).astype(np.float32) + rng.normal(0, 4, (size[1], size[0], 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def side_by_side(a, b, gap=120, wall=(196, 192, 184)):
    """Two sheets pinned next to each other, so one photo catches both."""
    a, b = a.convert("RGB"), b.convert("RGB")
    out = Image.new("RGB", (a.width + b.width + gap, max(a.height, b.height)), wall)
    out.paste(a, (0, 0)); out.paste(b, (a.width + gap, 0))
    return out


def main():
    m.preflight()
    rng = np.random.default_rng(18112026)   # fixed seeds: every run makes the same photos and answer key
    random.seed(18112026)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    bases = m.base_sheets()
    truth = {"tables": {}, "cards": [], "photos": {}, "expect": {}, "profiles": PROFILES}
    shots = []
    for n, spec in T.items():
        sheets, tt = m.make_table(n, spec, bases, rng)
        truth["tables"][n] = tt
        cond = SHOTS[n]
        for code, sh in sheets.items():
            if n == 8 and code == "S3":
                continue                                  # it's in the S2 photo
            if n == 8 and code == "S2":
                both = side_by_side(sheets["S2"].img, sheets["S3"].img)
                shots.append(dict(im=m.photograph(both, rng, size=(4032, 3024), fill=0.9), table=n, sheet="S2+S3",
                                  kind="two sheets in one photo"))
                continue
            im = m.photograph(sh.img, rng, **cond)
            if n == 8 and code == "SS":
                im = im.rotate(180)                       # upside down in the frame, and no EXIF flag to say so
                shots.append(dict(im=im, table=n, sheet=code, kind="whole, upside down"))
                continue
            shots.append(dict(im=im, table=n, sheet=code, kind="whole"))
            if n == 8 and code == "S1":                   # a close-up of the tally and countries
                shots.append(dict(im=m.photograph(sh.img, rng, crop=(0, 0.2, 1, 0.48)), table=n, sheet=code, kind="close-up of the tally"))
    truth["expect"] = {
        "two_tables_wrote_22": "label one 22 and the other 91 (spare number), with a note; flag it for the review",
        "two_sheets_one_photo": "T08 S2 and S3 share one photo: label it so both sheets count, or note it",
        "upside_down": "T08 SS photo is upside down with no EXIF: note it",
        "copied": "T03 copied prompts are not items; the pick box holds the copied heading, so no pick",
        "same_card_twice": "card H is in two photos: one card",
    }
    imgs = {c["key"]: card_image(bases["card"], c, rng, i) for i, c in enumerate(CARDS)}
    truth["cards"] = [dict(card_truth(c), key=c["key"]) for c in CARDS]
    untorn = [imgs[k] for k in ("A", "B", "C")]
    halves = [imgs[k] for k in ("D", "E", "F", "G", "H", "I", "J")]
    shots.append(dict(im=table_top(untorn, rng, per_row=2, size=(4032, 3024)), table=None, sheet="stubs", kind="untorn cards A, B, C"))
    shots.append(dict(im=table_top(halves, rng, per_row=4), table=None, sheet="stubs", kind="halves D to J"))
    alone = table_top([imgs["H"]], rng, per_row=1, size=(2400, 1800)).rotate(180)
    shots.append(dict(im=alone, table=None, sheet="stubs", kind="card H again, upside down"))
    random.shuffle(shots)
    n_img = 8200
    for sh in shots:
        n_img += 1
        name = f"IMG_{n_img}.JPG"
        sh["im"].save(OUT / name, quality=86)
        truth["photos"][name] = {k: v for k, v in sh.items() if k in ("table", "sheet", "kind")}
    TRUTH.write_text(json.dumps(truth, indent=1, ensure_ascii=False))
    print(f"{len(shots)} photos in {OUT.relative_to(m.ROOT)}/, answer key in {TRUTH.relative_to(m.ROOT)}")


if __name__ == "__main__":
    main()
