# Tests

These tests check the hardest part of the toolkit: reading photographed handwriting. They make **synthetic** photos of filled-in worksheets, with a known answer key, so a run of the ingest can be scored item by item. Nothing here is real event data: every name, organisation and answer is invented.

The number that matters is **silent errors**: readings that are wrong *and* unflagged. Those are the ones that could reach a published playbook without anyone noticing.

## What each test is for

| File | What it's for |
|---|---|
| `hw/make_hw_tests.py` | **Rounds 1 and 2.** Fake handwriting on the real printed sheets: 10 tables, each pushing on one thing (messy hands, bad light, WhatsApp compression, dense biro, crossings-out, jargon, coloured pens, missing and duplicate photos), plus 16 commitment cards. 20 handwriting fonts. Writes 44 photos to `hw/inbox/` and the answer key to `hw/truth.json`. |
| `hw/make_round3.py` | **Round 3.** Traps that real people produced in a dry run: printed prompts copied into the answer boxes, yellow and highlighter pens, two tables writing the same number, two sheets in one photo, an upside-down photo, untorn cards, sign-offs, one card photographed twice. Writes 27 photos to `hw/round3/inbox/` and the answer key to `hw/round3/truth.json`. |
| `hw/score.py` | Scores an ingest run against an answer key (see [Reading the score](#reading-the-score)). |
| `hw/answer_labels.py` | Writes a run's `labels.json` from the answer key, so the readers can be scored on reading alone. |
| `hw/get_fonts.py` | Fetches the fonts the generators need (they aren't shipped). |
| `fixtures/make_fixtures.py` | A small fake inbox for an end-to-end smoke test: three tables on simplified sheets, card stubs, a stray room photo, three voice notes and a `notes.txt`, with planted problems (a missing sheet, a blurred duplicate, a HEIC, an EXIF-rotated photo, a half-scribbled word, a name in a voice note). Its answer key is the data at the top of the script. |
| `check_fixture.py` | Scores an ingest run of the fixture inbox. |
| `golden.py` | **Not a reading test: a "did anything change?" test.** Builds everything the kit makes (print files, fill-in sheets, slides, the playbook from three session files, and `verify` plus `draft` on the fake run in `fixtures/run-golden/`) and compares it with the snapshots in `golden/snapshots/`. Run it before and after a change: `PW=<.../node_modules/playwright> python3 tests/golden.py`, then `--update` once you've checked every difference is one you meant. Pictures of every page are compared too, but kept on your own machine (`golden/local/`), so a fresh clone runs `--update` once first. |
| `four-tables.json` | Not a test of the reader: the example playbook squeezed onto four tables, to check the design copes with a small room. `python3 build/build.py tests/four-tables.json --out <folder>/index.html` |

## Before you start (once)

1. **Python 3.9 or later**, the toolkit's packages and the test extras (scipy):
   ```bash
   pip install -r requirements.txt -r tests/requirements.txt
   ```
2. **poppler**, for `pdftoppm` (rasterises the printed sheets) and `pdfinfo`: `brew install poppler` on macOS, `sudo apt install poppler-utils` on Debian or Ubuntu.
3. **The fonts.** They come from Google Fonts rather than the repo, so the repo never has to track their licences:
   ```bash
   python3 tests/hw/get_fonts.py
   ```
   This downloads 20 handwriting fonts into `tests/hw/fonts/` (17 under the SIL Open Font License 1.1, 3 under the Apache License 2.0) and Poppins into `tests/fixtures/fonts/` (SIL OFL 1.1), each straight from the [google/fonts](https://github.com/google/fonts) repository with its licence in a `licences/` folder beside it and a `SOURCES.txt` listing where each came from. Both folders are git-ignored. It skips fonts already there, and checks every download opens as a font.
4. **The printed sheets.** The handwriting is drawn onto the real sheets, so build them first:
   ```bash
   python3 print/build_paper.py
   ```
   Use the default options: `--no-proposed` leaves out the tally and "best thing" boxes the tests write into.

The generators stop with a message saying which of these is missing. They run from any folder.

**macOS** is the reference platform. Elsewhere, `make_hw_tests.py` writes the HEIC photo through `pillow-heif` if it's installed (otherwise as a JPEG, skipping that trap), and `make_fixtures.py` also swaps in stand-in handwriting fonts and skips the voice notes if `say` or `ffmpeg` is missing. Each says when it does this.

## Running a test

The order is always: **fonts, print files, generate an inbox, run the ingest, score.**

```bash
# 1 and 2: once, as above
python3 tests/hw/get_fonts.py
python3 print/build_paper.py

# 3: generate an inbox and its answer key (about 40 seconds)
python3 tests/hw/make_round3.py

# 4: run the ingest on it
python3 ingest/ingest.py prepare tests/hw/round3/inbox          # makes a run under runs/; runs/latest points at it
python3 tests/hw/answer_labels.py runs/latest --truth tests/hw/round3/truth.json   # optional, see below
#    then, in Claude Code in this folder, run the transcription stage of the sheets-to-playbook skill:
#    one reader per table writes raw/T<nn>.json, and one writes raw/commitments.json for the cards

# 5: score it
python3 tests/hw/score.py runs/latest --truth tests/hw/round3/truth.json
```

For rounds 1 and 2, use `make_hw_tests.py` and `tests/hw/inbox`, and leave out `--truth` (`tests/hw/truth.json` is the default). Only stages 1 to 3 of the skill (prepare, label, transcribe) are scored; writing the playbook isn't.

**Labelling and reading are scored separately.** Labelling means working out which table and sheet each photo shows. `answer_labels.py` writes correct labels from the answer key, so a reading mistake can't hide behind a labelling one. To test a labeller too, have it write `labels-blind.json` in the run folder, in the same format as `labels.json`, without seeing the answer key, `labels.json` or the output of `ingest.py status` (status prints what's in `labels.json`, so run it only after the labeller has finished). `score.py` scores `labels-blind.json` when it finds one.

**The fixture** runs the same way, without an answer-label helper (label it with the skill as normal):

```bash
python3 tests/fixtures/make_fixtures.py
python3 ingest/ingest.py prepare tests/fixtures/inbox
#    label, transcribe (and, if you like, carry on to the draft playbook) with the skill
python3 tests/check_fixture.py runs/latest
```

The generated inboxes are git-ignored. Rounds 1 and 2 come to about 45 MB, so delete them when you're done.

## Reading the score

`score.py` pairs every item in the answer key with the closest transcribed item and sorts each one into:

| Kind | Meaning |
|---|---|
| **silent** | Wrong, with no `[?word]` or `[illegible]` marker and not listed in `unclear`. **This is the number that matters**: nothing tells the human reviewer to look, so it can reach the published playbook. The target is zero. |
| missed | On the sheet, not in the transcription. |
| extra | In the transcription, not on the sheet. A crossed-out item that crept back in counts here. |
| flagged | Wrong or unsure, but marked, so the review catches it. Costs reviewer time, not accuracy. |
| exact | Right, ignoring case, punctuation and `[expansions]`. |

It also prints word accuracy, how many correct readings were marked unsure anyway, and pass or fail checks: crossed-out text kept out, ticks, the tally and countries, the "best thing" box, card names and organisations (including blank ones staying blank), the noted table-number mismatch and arrow in rounds 1 and 2, and blind labelling if there is one. `--json report.json` saves the lot.

`check_fixture.py` is simpler: it counts items transcribed exactly and prints the misses for a person to judge.

## Last results, for context

The last full run was round 3: **0 silent errors in 135 items** (132 exact, 3 flagged, none missed, no extras), and every check passed. The readers were given correct labels. A blind photo labeller, scored separately, got **26 of 27 photos** right; the miss was the photo of two sheets side by side, which the label format couldn't express at the time (a label's `sheet` can now be a list).

All three flags came from the generator bug described below, not from hard handwriting.

A fresh run won't be pixel-identical to that one: the fonts are the same files, but the printed sheets have changed colour and wording since (not box positions), and one card's sign-off now uses a different invented name.

## Caveats

- **Fonts are kinder than real handwriting, so these scores are a ceiling.** Each "writer" is a handwriting font with random warping, slant, wobble and ink, but letterforms still repeat, nobody smudges, and nobody's writing is as bad as a rushed real hand. Before relying on the pipeline, photograph real people's handwriting on the printed sheets and check it. The human review is never optional.
- **Known generator bug: big hands can write over the line above.** `Sheet.write` spaces lines by the writer's nominal size, not the scaled size it actually draws at, so large handwriting sometimes overlaps the previous line (you can see it on some sheets). People rarely do that. It's left as is because fixing it changes every photo and makes new scores incomparable with old ones.
- **The handwriting positions are measured, not read from the PDFs.** `GEO` in `make_hw_tests.py` holds the box positions of v1.3.0 of the sheets, which v1.4.0 kept. If `print/build_paper.py` moves a box, update `GEO`. The generators print a note when the sheets are a version nobody has checked (`GEO_VERSIONS`); that's fine as long as no box has moved, so look at a photo or two, then add the version.
- **Some warnings are expected.** A line like `warning: table 3 S1.challenges runs 28 mm past its box` means a dense table overflowed a box, as real dense tables do.
- **The crossed-out check searches the whole raw file**, notes included, so a reader that quotes a whole crossed-out item in `notes` fails it. The ingest's format asks readers to leave crossed-out items out and name only single crossed-out words in `notes`.

## About the synthetic content

Everything the tests write is invented. Names and organisations appear on purpose ("Sam Patel", "Brightway Retail", "Priya at Halcyon Bank") because the ingest has to handle them: on a card's optional Name and Organisation lines, and inside commitments, quotes and voice notes, where `ingest.py verify` checks for personal details. Email addresses use the reserved `.example` domain. Real public resources (W3C, WebAIM, GOV.UK guidance) appear as written resources because that's what people write down.
