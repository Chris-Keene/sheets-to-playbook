#!/usr/bin/env python3
"""Fetch the fonts the test generators draw with, each with its licence, from the google/fonts repository.

    python3 tests/hw/get_fonts.py            # fills tests/hw/fonts/ and tests/fixtures/fonts/ (both git-ignored)
    python3 tests/hw/get_fonts.py --force    # fetch everything again

The fonts aren't shipped with the repo, so it never has to track their licences: each one comes straight from
https://github.com/google/fonts with that family's own licence file beside it (in fonts/licences/).
  tests/hw/fonts        20 handwriting fonts for make_hw_tests.py and make_round3.py
                        (17 under the SIL Open Font License 1.1, 3 under the Apache License 2.0)
  tests/fixtures/fonts  Poppins Regular and SemiBold (SIL OFL 1.1), the printed text on make_fixtures.py's sheets
Fonts already there and valid are skipped, so it's safe to run again. Every download is opened with Pillow
before it's kept, so an error page or a half-finished file never ends up looking like a font.
Needs Python 3.9 or later and Pillow.
"""
import argparse, ast, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

try:
    from PIL import ImageFont
except ImportError:
    sys.exit("Pillow is needed to check the downloads: python3 -m pip install -r tests/requirements.txt")

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
RAW = "https://raw.githubusercontent.com/google/fonts/main"

# saved as: (licence folder, family folder, file name in google/fonts)
HANDWRITING = {
    "PatrickHand-Regular.ttf": ("ofl", "patrickhand", "PatrickHand-Regular.ttf"),
    "Kalam-Regular.ttf": ("ofl", "kalam", "Kalam-Regular.ttf"),
    "IndieFlower-Regular.ttf": ("ofl", "indieflower", "IndieFlower-Regular.ttf"),
    "ShadowsIntoLight.ttf": ("ofl", "shadowsintolight", "ShadowsIntoLight.ttf"),
    "GochiHand-Regular.ttf": ("ofl", "gochihand", "GochiHand-Regular.ttf"),
    "ArchitectsDaughter-Regular.ttf": ("ofl", "architectsdaughter", "ArchitectsDaughter-Regular.ttf"),
    "PermanentMarker-Regular.ttf": ("apache", "permanentmarker", "PermanentMarker-Regular.ttf"),
    "RockSalt-Regular.ttf": ("apache", "rocksalt", "RockSalt-Regular.ttf"),
    "ReenieBeanie.ttf": ("ofl", "reeniebeanie", "ReenieBeanie.ttf"),
    "NothingYouCouldDo.ttf": ("ofl", "nothingyoucoulddo", "NothingYouCouldDo.ttf"),
    "Zeyada.ttf": ("ofl", "zeyada", "Zeyada.ttf"),
    "HomemadeApple-Regular.ttf": ("apache", "homemadeapple", "HomemadeApple-Regular.ttf"),
    "LaBelleAurore.ttf": ("ofl", "labelleaurore", "LaBelleAurore.ttf"),
    "CoveredByYourGrace.ttf": ("ofl", "coveredbyyourgrace", "CoveredByYourGrace.ttf"),
    "JustMeAgainDownHere.ttf": ("ofl", "justmeagaindownhere", "JustMeAgainDownHere.ttf"),
    "SueEllenFrancisco-Regular.ttf": ("ofl", "sueellenfrancisco", "SueEllenFrancisco-Regular.ttf"),
    "WaitingfortheSunrise.ttf": ("ofl", "waitingforthesunrise", "WaitingfortheSunrise.ttf"),
    "GloriaHallelujah.ttf": ("ofl", "gloriahallelujah", "GloriaHallelujah.ttf"),
    "DawningofaNewDay.ttf": ("ofl", "dawningofanewday", "DawningofaNewDay.ttf"),
    # Caveat only exists as a variable font. Saved under the plain name make_hw_tests.py expects; Pillow draws
    # its default instance, which is the Regular weight.
    "Caveat.ttf": ("ofl", "caveat", "Caveat[wght].ttf"),
}
PRINT = {
    "Poppins-Regular.ttf": ("ofl", "poppins", "Poppins-Regular.ttf"),
    "Poppins-SemiBold.ttf": ("ofl", "poppins", "Poppins-SemiBold.ttf"),
}
SETS = [("Handwriting fonts", HANDWRITING, HERE / "fonts"), ("Fixture print font", PRINT, TESTS / "fixtures" / "fonts")]
LICENCE = {"ofl": ("OFL.txt", "SIL Open Font License 1.1", "SIL OPEN FONT LICENSE"),
           "apache": ("LICENSE.txt", "Apache License 2.0", "APACHE LICENSE")}


def rel(p):
    try:
        return p.relative_to(TESTS.parent)
    except ValueError:
        return p


def url_for(lic, family, name):
    return f"{RAW}/{lic}/{family}/{urllib.parse.quote(name)}"


def fetch(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sheets-to-playbook-tests"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == tries:
                raise
        except urllib.error.URLError as e:
            if attempt == tries:
                if "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
                    raise RuntimeError(f"{e.reason}. With a python.org install on macOS, run the 'Install "
                                       "Certificates.command' in its Applications folder, then try again") from e
                raise
        time.sleep(2 * attempt)


def is_font(path):
    try:
        f = ImageFont.truetype(str(path), 40)
        x0, y0, x1, y1 = f.getbbox("Hello")
        return x1 > x0 and y1 > y0
    except Exception:
        return False


def is_licence(path, lic):
    try:
        return LICENCE[lic][2] in path.read_text(errors="replace").upper()
    except OSError:
        return False


def check_coverage():
    """make_hw_tests.py's FONT_FILES and HANDWRITING above must list the same fonts. Read without importing it,
    so this script still runs before numpy and scipy are installed."""
    src = (HERE / "make_hw_tests.py").read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FONT_FILES" for t in node.targets):
            wanted = set(ast.literal_eval(node.value).values())
            unknown = sorted(wanted - set(HANDWRITING))
            if unknown:
                sys.exit(f"make_hw_tests.py uses {', '.join(unknown)}, but get_fonts.py doesn't know where to "
                         "fetch it: add it to HANDWRITING with its google/fonts folder and file name.")
            return
    print("note: couldn't find FONT_FILES in make_hw_tests.py to cross-check")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="fetch every font and licence again")
    a = ap.parse_args()
    check_coverage()
    fetched, had, failed = 0, 0, []
    for title, fonts, folder in SETS:
        print(f"{title} -> {rel(folder)}/")
        (folder / "licences").mkdir(parents=True, exist_ok=True)
        sources = []
        for saved, (lic, family, name) in fonts.items():
            target = folder / saved
            lic_file, lic_name, _ = LICENCE[lic]
            lic_target = folder / "licences" / f"{family}-{lic_file}"
            font_url, lic_url = url_for(lic, family, name), url_for(lic, family, lic_file)
            sources.append(f"{saved}\t{lic_name}\t{font_url}\tlicence: licences/{lic_target.name}")
            if not a.force and is_font(target) and is_licence(lic_target, lic):
                had += 1
                print(f"  have     {saved}")
                continue
            got = []
            try:
                if a.force or not is_font(target):
                    part = target.with_name(target.name + ".part")
                    part.write_bytes(fetch(font_url))
                    if not is_font(part):
                        part.unlink()
                        raise RuntimeError(f"{font_url} didn't download as a font Pillow can open")
                    part.replace(target)
                    got.append(f"{target.stat().st_size // 1024} KB")
                if a.force or not is_licence(lic_target, lic):
                    lic_target.write_bytes(fetch(lic_url))
                    if not is_licence(lic_target, lic):
                        lic_target.unlink()
                        raise RuntimeError(f"{lic_url} doesn't look like the {lic_name}")
                    got.append("licence")
            except Exception as e:
                failed.append(saved)
                print(f"  FAILED   {saved}: {e}")
                continue
            fetched += 1
            print(f"  fetched  {saved:32} {' + '.join(got):<16} {lic_name}  ({lic}/{family}/{name})")
        (folder / "SOURCES.txt").write_text(
            "Fetched by tests/hw/get_fonts.py from the google/fonts repository. Each family's licence is in licences/.\n"
            "file\tlicence\tsource\tlicence file\n" + "\n".join(sources) + "\n")
    total = sum(len(f) for _, f, _ in SETS)
    if failed:
        sys.exit(f"\n{len(failed)} of {total} fonts failed: {', '.join(failed)}. Check your connection and run it again.")
    print(f"\nAll {total} fonts ready: {fetched} fetched, {had} already here.")


if __name__ == "__main__":
    main()
