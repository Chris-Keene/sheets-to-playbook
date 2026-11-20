#!/usr/bin/env python3
"""Make a fake 'end of session' inbox to test the ingest end to end.

    python3 tests/hw/get_fonts.py                # once: fetches the Poppins print font into tests/fixtures/fonts/
    python3 tests/fixtures/make_fixtures.py      # writes tests/fixtures/inbox/
    python3 tests/check_fixture.py <run>         # after the ingest has read the inbox: scores its transcriptions

Three tables (2, 5 and 9) photographed the way facilitators will on the day, plus card stubs,
a stray room photo and three voice notes. Built-in traps the pipeline should catch:
  - T09 Sheet 1 was never photographed (coverage gap)
  - one T02 Sheet 1 shot is badly blurred (blur check), the other is fine
  - T05 Sheet 2 is an iPhone HEIC; T09 Sheet 3 is stored sideways with an EXIF rotate flag
  - the '2k' in T05 Sheet 2's '(local gov, 2k)' is half scribbled out (should come back as [?word] / unclear)
  - T05 and T09 tackled the same challenge in different words (should merge)
  - the T09 voice note names a person and an organisation (must be anonymised)
  - a notes.txt that should be ignored
Built for macOS, where it uses three system handwriting fonts, sips for the HEIC and say for the voice notes.
Elsewhere it still runs: handwriting fonts from tests/hw/fonts stand in, the HEIC needs pillow-heif (or becomes a
JPEG), and voice notes are skipped if say or ffmpeg is missing (the ingest treats voice notes as optional).
It says when it does any of this.
ALL CONTENT HERE IS SYNTHETIC TEST DATA. The voices are macOS text-to-speech, for local testing only.
"""
import random, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "inbox"
SUPP = Path("/System/Library/Fonts/Supplemental")
ACCENT, HIGHLIGHT, INK = (36, 80, 140), (255, 209, 102), (24, 22, 34)   # the neutral default brand
W, H = 2000, 2828   # A1 portrait at a workable resolution

PRINT = str(HERE / "fonts" / "Poppins-SemiBold.ttf")
PRINT_REG = str(HERE / "fonts" / "Poppins-Regular.ttf")
HANDS = {2: (str(SUPP / "Bradley Hand Bold.ttf"), 0), 5: ("/System/Library/Fonts/Noteworthy.ttc", 1),
         9: ("/System/Library/Fonts/MarkerFelt.ttc", 0)}
# off macOS: the nearest of the test handwriting fonts (from tests/hw/get_fonts.py)
HW_FONTS = HERE.parent / "hw" / "fonts"
HANDS_ELSEWHERE = {2: (str(HW_FONTS / "PatrickHand-Regular.ttf"), 0), 5: (str(HW_FONTS / "Kalam-Regular.ttf"), 0),
                   9: (str(HW_FONTS / "PermanentMarker-Regular.ttf"), 0)}

QUESTIONS = {"S1": ("Question 1", "Where does support get stuck?"),
             "S2": ("Question 2", "What has helped, or not?"),
             "S3": ("Question 3", "What could people try now, and how does it stick?"),
             "SS": ("All session", "Heard something good? Write it here.")}

TABLES = {
    2: {
        "S1": {"challenges": ["Champions drift away after 6 months", "No time in the day job",
                              "Leaders only care at audit time", "Can't prove impact", "Champions don't know what to do"],
               "top3": ["Champions drift away", "No time in day job", "Can't prove impact"],
               "pick": "Keeping champions engaged after the launch"},
        "S2": {"helped": [("Monthly fix-it Friday with snacks", "retail, 3k staff"),
                          ("Giving champions a real task each month", "bank, 20k")],
               "hindered": [("Newsletter nobody read", "insurance"), ("Meetings at 8am", "NHS trust")],
               "lesson": "Ask champions what they want before planning"},
        "S3": [("Monthly 30 min fix-it session", "a room, list of small bugs, a host", "same day every month, rotate the host", ["starting", "growing"]),
               ("Champion of the month shout out", "exec to send the email", "link it to performance reviews", ["growing"])],
        "SS": {"quotes": [("Champions need a job, not a badge", "retail")],
               "questions": ["How many champions is enough?"],
               "resources": ["W3C planning & managing - w3.org/WAI/planning-and-managing"]},
    },
    5: {
        "S1": {"challenges": ["Only get money after complaints", "Budget sits with IT not product",
                              "Leadership support fades", "Seen as just compliance"],
               "top3": ["Only get money after complaints", "Budget sits with IT", "Seen as compliance"],
               "pick": "Getting budget before something goes wrong"},
        "S2": {"helped": [("Showed cost of fixing late vs early", "local gov, 2k"),
                          ("Piggybacked on the design system budget", "university")],
               "hindered": [("Asked for a big programme all at once", "charity")],
               "lesson": "Small asks that repeat beat one big ask"},
        "S3": [("Cost two real late fixes", "time from a delivery lead", "update the numbers every year", ["starting", "growing"]),
               ("Ask for a small recurring line in an existing budget", "a friendly budget owner", "it rolls over each year", ["starting"])],
        "SS": {"quotes": [("Small and recurring beats big and one-off", "local government")],
               "questions": ["Who owns the budget - IT or product?"],
               "resources": []},
    },
    9: {
        "S2": {"helped": [("Linking it to complaints data", "utility")],
               "hindered": [("Waiting for legal to push it", "telco")],
               "lesson": None},
        "S3": [("Find one complaint that cost money and share it", "a contact in customer services", "share a new one every quarter", ["growing", "established"])],
        "SS": {"quotes": [("Money follows risk, so show the risk", "telecoms")],
               "questions": [],
               "resources": ["Business case - w3.org/WAI/business-case"]},
    },
}

STUBS = ["Cost one late fix this month", "Run a fix-it Friday in January", "Ask finance who owns the budget",
         "Send my exec one win a month", "Talk to our design system lead", "Share this playbook with my team"]

VOICE = {
    5: ("Daniel", "Lead T5.m4a",
        "Table five. The best thing that wasn't on the paper was someone from a council who said they bid for accessibility "
        "as part of the design system refresh, so it was never a separate ask. Everyone wrote that down afterwards."),
    9: ("Moira", "New Recording 3.mp3",
        "Table nine. We went for budget, getting money before there's a crisis. Our first sheet got taken down early, sorry. "
        "The best thing not on paper was Sarah from Fernhollow Telecom saying their regulator now asks about accessibility in every review, "
        "so the risk argument is getting stronger."),
    2: ("Karen", "PTT-20260305-WA0004.opus",
        "Table two. We talked a lot about champions feeling invisible. One person said they ask champions to present their "
        "fix at the all hands meeting, and that made other people want to join."),
}


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def dashed_box(d, box, label, f_label):
    x0, y0, x1, y1 = box
    dash, gap = 26, 16
    for x in range(x0, x1, dash + gap):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=(120, 105, 140), width=4)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=(120, 105, 140), width=4)
    for y in range(y0, y1, dash + gap):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=(120, 105, 140), width=4)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=(120, 105, 140), width=4)
    if label:
        d.text((x0 + 26, y0 + 18), label, font=f_label, fill=ACCENT)


def hand(img, xy, text, hand_font, size, width, rng):
    """Write wrapped text like a marker pen: each line slightly tilted and wobbling."""
    path, idx = hand_font
    f = font(path, size, idx)
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if f.getlength(test) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    lines.append(cur)
    x, y = xy
    for line in lines:
        layer = Image.new("RGBA", (int(f.getlength(line)) + 40, size * 2), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((10, 4), line, font=f, fill=INK + (255,))
        layer = layer.rotate(rng.uniform(-1.6, 1.6), resample=Image.BICUBIC, expand=True)
        img.paste(layer, (int(x + rng.uniform(-6, 6)), int(y + rng.uniform(-4, 4))), layer)
        y += int(size * 1.25)
    return y


def sheet(table, code, rng):
    img = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(img)
    f_q, f_h, f_label, f_small = font(PRINT, 64), font(PRINT, 44), font(PRINT, 40), font(PRINT_REG, 34)
    eyebrow, q = QUESTIONS[code]
    d.rounded_rectangle((60, 60, 1640, 300), 14, fill=ACCENT)
    d.text((100, 88), eyebrow, font=f_h, fill=HIGHLIGHT)
    y = 150
    for line in wrap(q, f_q, 1500):
        d.text((100, y), line, font=f_q, fill="white"); y += 76
    d.ellipse((1700, 60, 1940, 300), outline=ACCENT, width=10)
    d.text((1820, 140), "Table", font=f_h, fill=ACCENT, anchor="mm")
    d.text((1820, 210), str(table), font=font(PRINT, 80), fill=ACCENT, anchor="mm")
    corner = f"T{table:02d} · {code}"
    for (x, y, a) in [(60, 2790, "ls"), (1940, 2790, "rs")]:
        d.text((x, y), corner, font=f_small, fill=(110, 95, 130), anchor=a)
    d.text((1940, 330), corner, font=f_small, fill=(110, 95, 130), anchor="ra")
    content = TABLES[table][code]
    hf = HANDS[table]
    if code == "S1":
        dashed_box(d, (60, 380, 1940, 1640), "Every challenge at this table", f_label)
        y = 470
        for c in content["challenges"]:
            y = hand(img, (110, y), "- " + c, hf, 66, 1760, rng) + 18
        dashed_box(d, (60, 1690, 1940, 2210), "Our top three", f_label)
        y = 1780
        for i, c in enumerate(content["top3"], 1):
            d.text((110, y + 12), f"{i}.", font=f_label, fill=ACCENT)
            y = hand(img, (170, y), c, hf, 62, 1700, rng) + 16
        dashed_box(d, (60, 2260, 1940, 2720), "The one we're tackling", f_label)
        hand(img, (110, 2360), content["pick"], hf, 72, 1760, rng)
    elif code == "S2":
        dashed_box(d, (60, 380, 985, 2150), "Helped", f_label)
        dashed_box(d, (1015, 380, 1940, 2150), "Got in the way", f_label)
        d.text((86, 440), "Who was it for? Add sector and size.", font=f_small, fill=(110, 95, 130))
        d.text((1041, 440), "Who was it for? Add sector and size.", font=f_small, fill=(110, 95, 130))
        for col, key in ((0, "helped"), (1, "hindered")):
            y = 540
            for text, who in content[key]:
                y = hand(img, (100 + col * 955, y), text, hf, 60, 820, rng)
                y = hand(img, (130 + col * 955, y), f"({who})", hf, 46, 780, rng) + 40
        dashed_box(d, (60, 2200, 1940, 2720), "If we did it again, we'd...", f_label)
        if content["lesson"]:
            hand(img, (110, 2300), content["lesson"], hf, 64, 1760, rng)
    elif code == "S3":
        boxes = [(60, 380, 1940, 1150), (60, 1190, 1940, 1960), (60, 2000, 1940, 2770)]
        for k, box in enumerate(boxes):
            dashed_box(d, box, "Action", f_label)
            x0, y0 = box[0], box[1]
            d.text((x0 + 26, y0 + 300), "What you need", font=f_small, fill=ACCENT)
            d.text((x0 + 26, y0 + 450), "How it sticks", font=f_small, fill=ACCENT)
            d.text((x0 + 26, y0 + 650), "Good for:", font=f_small, fill=ACCENT)
            ticks = ["Just starting", "Growing", "Established"]
            tx = x0 + 230
            positions = {}
            for t in ticks:
                d.rectangle((tx, y0 + 652, tx + 34, y0 + 686), outline=ACCENT, width=4)
                d.text((tx + 50, y0 + 650), t, font=f_small, fill=ACCENT)
                positions[t] = tx
                tx += 90 + int(f_small.getlength(t))
            if k < len(content):
                action, needs, sticks, stages = content[k]
                hand(img, (x0 + 60, y0 + 90), action, hf, 64, 1760, rng)
                hand(img, (x0 + 60, y0 + 345), needs, hf, 54, 1760, rng)
                hand(img, (x0 + 60, y0 + 495), sticks, hf, 54, 1760, rng)
                names = {"starting": "Just starting", "growing": "Growing", "established": "Established"}
                for s in stages:
                    px = positions[names[s]]
                    d.line([(px - 4, y0 + 668), (px + 14, y0 + 694), (px + 48, y0 + 630)], fill=INK, width=9)
    elif code == "SS":
        cols = [("Quotes", "Exact words, no names"), ("Questions", "Things nobody could answer"), ("Resources", "Links, books, people, tools")]
        for k, (title, hint) in enumerate(cols):
            x0 = 60 + k * 633
            dashed_box(d, (x0, 380, x0 + 607, 2720), title, f_label)
            d.text((x0 + 26, 440), hint, font=f_small, fill=(110, 95, 130))
        y = 560
        for text, who in content["quotes"]:
            y = hand(img, (90, y), f'"{text}"', hf, 56, 540, rng)
            y = hand(img, (110, y), f"({who})", hf, 44, 520, rng) + 40
        y = 560
        for qn in content["questions"]:
            y = hand(img, (723, y), qn, hf, 56, 540, rng) + 40
        y = 560
        for r in content["resources"]:
            y = hand(img, (1356, y), r, hf, 50, 540, rng) + 40
    return img


def wrap(text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    return lines + [cur]


def photograph(img, rng, wall=(196, 192, 184)):
    """Pin the sheet to a wall and take a slightly wonky phone photo of it."""
    bw, bh = 3024, 4032
    scale = rng.uniform(0.8, 0.88)
    sw, sh = int(bw * scale), int(bw * scale * H / W)
    sheet_img = img.resize((sw, sh), Image.LANCZOS)
    j = lambda: rng.uniform(-0.035, 0.035) * sw
    quad = (j(), j(), j(), sh + j(), sw + j(), sh + j(), sw + j(), j())   # keystone from a hand-held shot
    sheet_img = sheet_img.transform((sw, sh), Image.QUAD, quad, Image.BICUBIC, fillcolor=wall)
    bg = Image.new("RGB", (bw, bh), wall)
    ox, oy = (bw - sw) // 2 + int(rng.uniform(-60, 60)), (bh - sh) // 2 + int(rng.uniform(-80, 80))
    shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 70)).filter(ImageFilter.GaussianBlur(18))
    bg.paste(shadow, (ox + 18, oy + 22), shadow)
    bg.paste(sheet_img, (ox, oy))
    bg = bg.rotate(rng.uniform(-2.5, 2.5), resample=Image.BICUBIC, fillcolor=wall)
    a = np.asarray(bg).astype(np.float32)
    yy, xx = np.mgrid[0:bh, 0:bw]
    light = 0.86 + 0.18 * (1 - ((xx - bw * rng.uniform(0.3, 0.7)) ** 2 + (yy - bh * 0.35) ** 2) / (bw ** 2 + bh ** 2))
    a = a * light[..., None] + rng.normal(0, 4.5, a.shape)
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    return out


def stubs_photo(rng):
    bg = Image.new("RGB", (4032, 3024), (120, 88, 60))   # a wooden table
    for i, text in enumerate(STUBS):
        card = Image.new("RGB", (1100, 760), HIGHLIGHT)
        d = ImageDraw.Draw(card)
        d.text((50, 40), "One thing I will try, adapt or explore is...", font=font(PRINT, 38), fill=INK)
        for y in range(240, 700, 90):
            d.line([(50, y), (1050, y)], fill=(160, 130, 60), width=3)
        hand(card, (60, 170), text, HANDS[[2, 5, 9][i % 3]], 74, 980, rng)
        card = card.rotate(rng.uniform(-6, 6), expand=True, fillcolor=(120, 88, 60))
        bg.paste(card, (150 + (i % 3) * 1300, 250 + (i // 3) * 1350))
    a = np.asarray(bg).astype(np.float32) + rng.normal(0, 4, (3024, 4032, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def preflight():
    """Stop early, with the fix, if the fonts aren't there; swap in stand-ins for macOS-only parts."""
    missing = [Path(f).name for f in (PRINT, PRINT_REG) if not Path(f).exists()]
    if missing:
        sys.exit(f"The print font is missing from tests/fixtures/fonts/ ({', '.join(missing)}).\n"
                 "Run python3 tests/hw/get_fonts.py first.")
    if not all(Path(f).exists() for f, _ in HANDS.values()):
        if not all(Path(f).exists() for f, _ in HANDS_ELSEWHERE.values()):
            sys.exit("The macOS handwriting fonts aren't here, and nor are the stand-ins in tests/hw/fonts/.\n"
                     "Run python3 tests/hw/get_fonts.py first.")
        HANDS.update(HANDS_ELSEWHERE)
        print("note: macOS handwriting fonts not found, using Patrick Hand, Kalam and Permanent Marker instead")


def main():
    preflight()
    rng = np.random.default_rng(2026)   # fixed seeds: every run makes the same inbox
    random.seed(2026)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shots = []   # (filename, PIL image, special)
    n = 4400
    for t in (2, 5, 9):
        for code in ("S1", "S2", "S3", "SS"):
            if code not in TABLES[t]:
                continue   # T09 Sheet 1 was never photographed
            img = sheet(t, code, rng)
            if (t, code) == (5, "S2"):
                # half-scribble over the '2k' of '(local gov, 2k)' so the reader has to flag it
                d = ImageDraw.Draw(img)
                for k in range(14):
                    d.line([(330 + k * 9, 740), (380 + k * 9, 700)], fill=INK, width=5)
            n += 2
            photo = photograph(img, rng)
            shots.append((f"IMG_{n}.JPG", photo, "heic" if (t, code) == (5, "S2") else "sideways" if (t, code) == (9, "S3") else None))
            if (t, code) == (2, "S1"):
                n += 1
                shots.append((f"IMG_{n}.JPG", photo.filter(ImageFilter.GaussianBlur(9)), None))   # shaky duplicate
            if (t, code) == (9, "SS"):
                n += 1
                w, h = photo.size
                shots.append((f"IMG_{n}.JPG", photo.crop((0, int(h * 0.15), w, int(h * 0.6))).resize((w, int(h * 0.45) * w // w)), None))
    n += 3
    shots.append((f"IMG_{n}.JPG", stubs_photo(rng), None))
    room = Image.new("RGB", (4032, 3024), (210, 205, 215))
    rd = ImageDraw.Draw(room)
    for k in range(6):
        rd.ellipse((300 + k * 600, 1700, 800 + k * 600, 2100), fill=(240, 240, 240), outline=(150, 150, 150), width=6)
    shots.append((f"IMG_{n + 1}.JPG", room, None))
    random.shuffle(shots)   # the inbox arrives in no particular order
    for name, im, special in shots:
        if special == "heic" and save_heic(im, OUT / name.replace(".JPG", ".HEIC")):
            pass
        elif special == "sideways":
            exif = Image.Exif()
            exif[0x0112] = 6   # "rotate 90 clockwise to display", as phones store portrait shots
            im.rotate(90, expand=True).save(OUT / name, quality=88, exif=exif)
        else:
            im.save(OUT / name, quality=88)
    voices = installed_voices()
    for t, (voice, fname, text) in VOICE.items():
        target = OUT / fname
        needs_ffmpeg = fname.endswith((".opus", ".mp3")) or not shutil.which("afconvert")
        lacking = [t for t in ["say"] + (["ffmpeg"] if needs_ffmpeg else []) if not shutil.which(t)]
        if lacking:
            print(f"note: voice note {fname} skipped: no {' or '.join(lacking)} on this machine")
            continue
        aiff = OUT / f"t{t}.aiff"
        subprocess.run(["say"] + (["-v", voice] if voice in voices else []) + ["-o", str(aiff), text], check=True)
        if fname.endswith(".opus"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", str(target)], check=True)
        elif fname.endswith(".mp3"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-c:a", "libmp3lame", "-b:a", "64k", str(target)], check=True)
        elif shutil.which("afconvert"):
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(target)], check=True)
        else:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-c:a", "aac", "-b:a", "64k", str(target)], check=True)
        aiff.unlink()
    (OUT / "notes.txt").write_text("Remember to bring blu tack\n")
    print(f"{len(list(OUT.iterdir()))} files in {OUT.relative_to(HERE.parent.parent)}/")


def save_heic(im, target):
    """Save as an iPhone would, with macOS's sips or the pillow-heif package. False if neither is here."""
    if shutil.which("sips"):
        tmp = target.with_suffix(".tmp.jpg")
        im.save(tmp, quality=90)
        subprocess.run(["sips", "-s", "format", "heic", str(tmp), "--out", str(target)], check=True, capture_output=True)
        tmp.unlink()
        return True
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        im.save(target, format="HEIF", quality=90)
        return True
    except Exception:          # not installed, or no HEIF encoder in this build
        target.unlink(missing_ok=True)
        print(f"note: can't write HEIC here (needs macOS or pip install pillow-heif), so {target.stem}.JPG is a JPEG "
              "and the HEIC trap is skipped")
        return False


def installed_voices():
    """Names of the text-to-speech voices on this Mac, or None without say. A missing voice falls back to the default."""
    if not shutil.which("say"):
        return None
    listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    return {line.split("  ")[0].strip() for line in listing.splitlines() if line.strip()}


if __name__ == "__main__":
    main()
