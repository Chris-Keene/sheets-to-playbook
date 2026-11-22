#!/usr/bin/env python3
"""A synthetic handwriting test for any workshop: fill its printed sheets from an answer bank and photograph them.

    python3 tests/hw/make_format_test.py retro                      # bank tests/hw/banks/retro.json
    python3 tests/hw/make_format_test.py retro --config <settings>  # default: tests/golden/<workshop>.config.json

It builds the workshop's A1 sheets with print/build_paper.py (moving any print/out aside and putting it back), reads
where each box is from the layout file the builder writes beside each PDF, writes the bank's answers into the boxes
in fake handwriting (the fonts and effects from make_hw_tests.py, with the bank's traps), photographs every sheet,
and writes into tests/hw/<workshop>/:

    inbox/        the photos, shuffled, named like a phone's
    truth.json    the answer key: for each team, what a careful reader should transcribe, plus each photo's sheet
    PROFILE.md    what each team's sheets test

Then run the pipeline on inbox/ (ingest.py prepare, answer_labels.py --truth, one reader per team with the brief),
and score it with tests/hw/score_format.py.
"""
import argparse, json, os, random, shutil, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "build"))
import make_hw_tests as mh  # noqa: E402  the handwriting, the marks and the camera
import config  # noqa: E402
import formats  # noqa: E402

BLEED = 3


def build_sheets(cfg_file, work):
    """The workshop's A1 PDFs and layout files, built fresh into work/ without disturbing print/out."""
    out = ROOT / "print" / "out"
    saved = work / "_print_out"
    if out.exists():
        shutil.move(str(out), str(saved))
    try:
        subprocess.run([sys.executable, str(ROOT / "print" / "build_paper.py"), "--config", str(cfg_file), "--tables", "3"],
                       check=True, capture_output=True, text=True)
        shutil.copytree(out / "paper", work / "paper")
    finally:
        shutil.rmtree(out, ignore_errors=True)
        if saved.exists():
            shutil.move(str(saved), str(out))
    return work / "paper"


def base_image(pdf):
    im = mh.render_pdf(pdf, int((594 + 2 * BLEED) * mh.PX))
    b = int(BLEED * mh.PX)
    return im.crop((b, b, im.width - b, im.height - b))


def writers_for(hand, team):
    return [mh.Writer(f, hand.get("size", 15), hand.get("ink", "black"), hand.get("pen", "marker"),
                      slant=0.08 * (i % 2), wobble=1.0, seed=team * 10 + i) for i, f in enumerate(hand["fonts"])]


def write_item(sheet, it, wr, x, y, w, rng, team_truth, log, key, dash=True):
    """Write one item with its traps. Returns the y below it."""
    if it.get("ink"):
        wr = mh.Writer(wr.font_key, wr.size, it["ink"], wr.pen, wr.slant, wr.wobble, seed=int(rng.integers(1e6)))
    shown = it.get("raw", it["text"])
    if it.get("sticky"):
        sw = min(w - 10, 130)
        small = mh.Writer(wr.font_key, wr.size * 0.65, wr.ink, wr.pen, wr.slant, seed=int(rng.integers(1e6)))
        n_lines = int(small.font.getlength(shown) * 1.25 // ((sw - 12) * mh.PX)) + 1
        sh_h = max(60, n_lines * small.size * 1.28 + 22)
        sheet.sticky(x, y - 6, sw, sh_h, rng.uniform(-3, 3))
        yy, boxes = sheet.write(shown, small, x + 5, y + 12, sw - 12)
        log.append(f"{key}: on a sticky note '{it['text']}'")
        return max(yy, y - 6 + sh_h) + 10
    # line spacing that allows for the size boost, so lines never overlap by accident (crammed writing is a trap of its own)
    yy, boxes = sheet.write(("- " if dash else "") + shown, wr, x, y, w, line_gap=1.28 * mh.SIZE_BOOST)
    words = boxes[1:] if dash and boxes else boxes
    if "strike" in it and words:
        sheet.strike(words[it["strike"]][1], wr.ink)
        team_truth.setdefault("struck", []).append([it["text"], shown.split(" ")[it["strike"]]])
        log.append(f"{key}: word crossed out in '{shown}' (must be left out)")
    if "scribble" in it and words:
        sheet.scribble(words[it["scribble"]][1], wr.ink)
        team_truth["flag_ok"].append(it["text"])
        log.append(f"{key}: word half scribbled in '{it['text']}' (correct or flagged)")
    if it.get("ink") in ("faint", "pencil"):
        log.append(f"{key}: written in {it['ink']} '{it['text']}'")
    return yy + 5


def dots(sheet, n, x_mm, y_mm, w_mm, h_mm, rng):
    """n dot-vote stickers drawn in marker in a strip: rows of dots, slightly uneven, like real ones."""
    d = ImageDraw.Draw(sheet.img)
    r, step = 2.4 * mh.PX, 6.2
    per_row = max(1, int((w_mm - 4) // step))
    colours = [(196, 32, 40), (28, 52, 150), (24, 110, 60), (22, 20, 28)]
    for i in range(n):
        cx = (x_mm + 2 + (i % per_row) * step + rng.uniform(-0.8, 0.8)) * mh.PX + r
        cy = (y_mm + h_mm / 2 + (i // per_row - 0.5 * ((n - 1) // per_row)) * step + rng.uniform(-0.8, 0.8)) * mh.PX
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colours[int(rng.integers(len(colours)))] + (255,))


def fill_sheet(base, exercise, zones, bank, hand, team, rng, log):
    """One team's sheet, written in: returns (Sheet, what a reader should transcribe for it)."""
    sheet = mh.Sheet(base)
    wrs = writers_for(hand, team)
    mh.number(sheet, team, team, wrs[0])
    truth, tt = {}, {"flag_ok": [], "struck": []}
    boxes = {b["id"]: b for b in exercise["boxes"]}
    by_box = {}
    for z in zones:
        by_box.setdefault(z["box"], []).append(z)
    for bid, b in boxes.items():
        key, mine = b["key"], bank.get(b["key"])
        if mine is None:
            continue
        zs = by_box.get(bid, [])
        whole = next((z for z in zs if z["n"] is None), zs[0] if zs else None)
        if b["type"] in ("list", "ranked"):
            x, y, w = whole["x"] + 14, whole["write_from"] + 12, whole["w"] - 28
            for i, it in enumerate(mine):
                y = write_item(sheet, it, wrs[i % len(wrs)], x, y, w, rng, tt, log, f"{exercise['code']}.{key}")
            truth[key] = [it["text"] for it in mine]
        elif b["type"] == "text":
            write_item(sheet, mine, wrs[0], whole["x"] + 16, whole["write_from"] + 14, whole["w"] - 32, rng, tt, log,
                       f"{exercise['code']}.{key}", dash=False)
            truth[key] = mine["text"]
        elif b["type"] == "list+votes":
            cells = sorted((z for z in zs if z["n"]), key=lambda z: z["n"])
            for z, it in zip(cells, mine):
                w0 = wrs[z["n"] % len(wrs)]
                small = mh.Writer(w0.font_key, w0.size * 0.8, w0.ink, w0.pen, w0.slant, w0.wobble, seed=team * 100 + z["n"])
                write_item(sheet, it, small, z["x"] + 5, z["write_from"] + 12, z["w"] - 10, rng, tt, log,
                           f"{exercise['code']}.{key}", dash=False)
                # the dots go after the printed "Votes", as people put stickers in the space beside it
                dots(sheet, it.get("votes", 0), z["x"] + 31, z["votes_from"], z["w"] - 35, z["y"] + z["h"] - z["votes_from"], rng)
            truth[key] = [{"text": it["text"], "votes": it.get("votes", 0)} for it in mine]
        elif b["type"] == "row":
            rows = sorted((z for z in zs if z["n"]), key=lambda z: z["n"])
            fields = b.get("fields", [])
            shares = [f.get("share", 1) for f in fields]
            out = []
            for z, it in zip(rows, mine):
                px = z["x"] + 14
                inner = z["w"] - 28 - 12 * (len(fields) - 1)
                for j, (f, share) in enumerate(zip(fields, shares)):
                    pw = inner * share / sum(shares)
                    if it.get(f["key"]):
                        write_item(sheet, {"text": it[f["key"]]}, wrs[j % len(wrs)], px, z["write_from"] + 28, pw - 6, rng, tt, log,
                                   f"{exercise['code']}.{key}", dash=False)
                    px += pw + 12
                out.append({f["key"]: it.get(f["key"], "") for f in fields})
            truth[key] = out
    return sheet, truth, tt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("workshop")
    ap.add_argument("--config", help="settings naming the workshop (default tests/golden/<workshop>.config.json)")
    ap.add_argument("--bank", help="answer bank (default tests/hw/banks/<workshop>.json)")
    a = ap.parse_args()
    cfg_file = Path(a.config or ROOT / "tests" / "golden" / f"{a.workshop}.config.json")
    cfg = config.load(str(cfg_file))
    W = formats.load(cfg, a.workshop)
    bank = json.loads(Path(a.bank or HERE / "banks" / f"{a.workshop}.json").read_text())
    out = HERE / a.workshop
    shutil.rmtree(out / "inbox", ignore_errors=True)
    (out / "inbox").mkdir(parents=True)
    rng = np.random.default_rng(22112026)   # fixed: every run makes the same photos and answer key
    random.seed(22112026)
    mh.SIZE_BOOST = 1.45                    # A1 writing, as the round-table tests use
    with tempfile.TemporaryDirectory() as tmp:
        paper = build_sheets(cfg_file, Path(tmp))
        bases, layouts = {}, {}
        for e in W.per_group():
            bases[e["code"]] = base_image(paper / f"sheet-{e['code']}-A1.pdf")
            layouts[e["code"]] = json.loads((paper / f"sheet-{e['code']}-A1.layout.json").read_text())["zones"]
    truth = {"workshop": W.id, "teams": {}, "photos": {}}
    shots, log = [], []
    for t, spec in bank["teams"].items():
        team = int(t)
        tt = {"flag_ok": []}
        for e in W.per_group():
            code = e["code"]
            if code not in spec:
                continue
            sheet, answers, traps = fill_sheet(bases[code], e, layouts[code], spec[code], spec["hand"], team, rng, log)
            tt[code] = answers
            tt["flag_ok"] += traps["flag_ok"]
            tt.setdefault("struck", []).extend(traps["struck"])
            shots.append(dict(im=mh.photograph(sheet.img, rng, **spec.get("shot", {})), table=team, sheet=code, kind="whole"))
        truth["teams"][t] = tt
    random.shuffle(shots)
    n_img = 8200
    for sh in shots:
        n_img += 1
        name = f"IMG_{n_img}.JPG"
        sh["im"].save(out / "inbox" / name, quality=88)
        truth["photos"][name] = {k: sh[k] for k in ("table", "sheet", "kind")}
    (out / "truth.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False))
    (out / "PROFILE.md").write_text(f"# {W.name}: synthetic handwriting test\n\n" + "\n".join(f"- {x}" for x in log) + "\n")
    print(f"{len(shots)} photos in {(out / 'inbox').relative_to(ROOT)}/, answer key in {(out / 'truth.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
