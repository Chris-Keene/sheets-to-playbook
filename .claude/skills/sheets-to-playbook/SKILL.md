---
name: sheets-to-playbook
description: Turn a folder of photos of the paper worksheets from a workshop or community session (plus any photos of commitment card stubs, and optional voice notes) into a draft playbook website, check every line against the photos, and publish it. Use when someone says "ingest these photos", "build the playbook from this folder", "turn the worksheets into a playbook", "photo check", "/sheets-to-playbook <folder>", or hands over a folder of photographed worksheets made with this repo's paper kit.
---

# Sheets to playbook

Repo: the folder holding `ingest/ingest.py` (the current project, if Claude Code was opened in the clone). All paths below are relative to it. Read `ingest/RAW_FORMAT.md` before stage 3: it holds the transcription rules and the hard rules for writing the page that every workshop shares.

**Which workshop:** the settings' `workshop` (round tables unless they name another; `formats/workshops/` lists them). Its sheets, boxes and ids come from `python3 ingest/ingest.py brief`, and how to write its page from `formats/workshops/<workshop>/recipe.md`. Read both before stage 3.

The goal is speed on the day **without inventing anything**. Every line on the website must trace to a photo or a voice note; `ingest.py verify` enforces it.

Tell the user what you're doing at each stage in a line or two. The stage timings below are rough guides for about a dozen tables.

**Before the day**, `playbook.config.json` should name the organisers and give the playbook's web address (the commitment card's QR code points there). If it still has the neutral defaults, say so, but carry on: the settings only change names and colours, never content. `--config <file>` on `verify`, `draft` and `publish` picks a different settings file.

## 1. Prepare (1 to 2 minutes)
```bash
python3 ingest/ingest.py prepare "<folder>"
python3 ingest/ingest.py transcribe      # only if the folder has voice notes; run it in the background
```
`prepare` makes a new run under `runs/` (and points `runs/latest` at it): photos rotated upright, HEIC converted, a sharpness score per photo, 2x2 tiles for close reading, contact sheets in `contact/`, and voice notes converted to 16 kHz WAV. `transcribe` uses local Whisper (`small.en`, offline once downloaded) and guesses each note's table from "Table seven…" at the start.

**A second batch** (more photos, or the cards, after the first half is under way): `python3 ingest/ingest.py prepare "<folder>" --into <run>` adds them to the same run. New ids carry on from the last one (P022…), labels and raw files are kept, and files already in the run are skipped. Then label only the new ids.

## 2. Label and check coverage (about 5 minutes; do this first, it's time-critical)
Look at every contact sheet (`contact/sheet-*.jpg`) and, where a thumbnail is unclear, the photo in `view/`. Write `labels.json` in the run folder:
```json
{"photos": {"P001": {"table": 7, "sheet": "S2"}, "P014": {"kind": "stubs"}, "P020": {"kind": "other", "note": "photo of the room"}},
 "audio":  {"A01": {"table": 7, "by": "speech"}}}
```
- Each sheet carries a printed code in the bottom corner (S1, S2, S3, SS) and printed headings; the table number is handwritten by the table lead, in the top-right circle and next to the code (`S2 · Table 7`). The kit's default headings: S1 "Where does support get stuck?", S2 "What has helped, or not?", S3 "What could people try now, and how does it stick?", SS the side sheet "Heard something good? Write it here." (Quotes · Questions · Resources). If the organisers changed the questions, go by the printed code. When the circle and the corner disagree, pen colour and content settle it: check the table's other sheets.
- Keep any audio labels `transcribe` already filled in, after checking them against the transcript's first line.
- **Two different sheets with the same code and table number** (`status` lists any sheet with more than one photo: check those): if the countries and content overlap, it's one table that used two copies; label both with the number and the reader transcribes both. If they're clearly two tables, give the second a spare number from 91 upwards, add `"note": "wrote 22; second table"`, and tell the user. Either table can be "the second": pick one, and describe both in the notes (sector, pen colour) so the review can tell them apart.
- **A close-up with no table number in shot** (just the tally box, say): label it with the sheet it matches and add `"note": "table inferred from <what matched>"`.
- **Two sheets in one photo** (pinned side by side): label it `"sheet": ["S2", "S3"]` so `status` counts it for both, and say so in a `note` so the reader knows which half is which.
- `prepare` can't turn a photo that is upside down in the frame (there's no rotate flag to read). Readers cope, but say so in a `note`. Card photos score lower for sharpness than sheets (plain card, thin pen), so check a BLURRY? card in `view/` before asking for a retake.

Then run `python3 ingest/ingest.py status` (add `--tables <n>` if there weren't 12 tables) and **tell the user straight away** about any MISSING or BLURRY sheet. The contact sheets also tag LOW-RES (forwarded over a messaging app: fine if the writing is big) and DARK (usually reads fine): mention them, but they aren't retakes. Ideally this check happens while the sheets are still on the wall and can be photographed again.

## 3. Transcribe each table (parallel, about 5 to 10 minutes)
Spawn one sub-agent per table (Agent tool, `general-purpose`, in the background, all in one message), plus one for card stubs if there are any. Don't downgrade the model: handwriting accuracy is where it matters. Each prompt must stand alone and include:
- The absolute repo path, the run folder, the table number, its photo ids (`view/<id>.jpg` and the tiles listed in `manifest.json`), and its voice transcript path if any.
- The output of `python3 ingest/ingest.py brief --table <nn>` (the workshop's sheets, ids and file shape), pasted in full.
- "Read `ingest/RAW_FORMAT.md`, stage 1, and follow it exactly, with the sheet brief above. Write `raw/T<nn>.json` in the run folder, then run `python3 ingest/ingest.py verify --run <run>` and fix any error it reports about your file. Reply with a short summary: items per sheet, every `unclear` entry, and every crossed-out word you left out."
- For stubs: write the card file the brief describes (`raw/commitments.json` for round tables), including the card's optional Name and Organisation lines exactly as written, and following the card rules there (untorn cards, sign-offs, one card in two photos).

While they run, read the voice transcripts yourself (if any) so you know the room before writing.

## 4. Write the playbook (about 10 to 15 minutes)
Follow `RAW_FORMAT.md` stage 2 and the workshop's `recipe.md`. Write `<run>/session.json` with `meta.status: "draft"`. Start `meta` from the session template the recipe names (`examples/session-template.json` for round tables) and fill in the event's own details (event name, date, venue) from what the user tells you; set `people` to the real headcount if they know it. Never guess these: leave a field as the template has it and list it for the user.

## 5. Verify, fix, build the review pack
```bash
python3 ingest/ingest.py verify --links
python3 ingest/ingest.py draft            # <run>/playbook-draft.html: dashed boxes = gaps, tags = sources
python3 ingest/ingest.py review           # <run>/review.html: every item next to its photos
```
Fix every **error** (an untraceable line, a quote that drifted, a name left in) and re-run until verify passes. **Warnings** are for the human review: report them, don't paper over them.

Then give the user the review summary: the challenges and which tables merged, every `unclear` reading with its photo id, every crossed-out word a reader left out, unused raw items, link problems, and anything you weren't sure how to group. `review.html` shows each reader's notes and the "Who's at this table?" tally under each table. Open `review.html` and `playbook-draft.html` for them.

**Lots of uncertain words?** The review app is faster than reading `review.html` top to bottom: `python3 tools/review/make_review.py --run <run>` builds `<run>/review/index.html`, one card per uncertain reading with a close-up of the handwriting. The user confirms or corrects each one, saves a decisions file, and `python3 tools/review/apply_review.py --run <run> <decisions.json>` writes the readings back into the raw files and `session.json`. Re-run `verify` and `draft` afterwards. Questions that aren't an uncertain word (a tick that might be a crossing-out, whether to merge two tables, whether to name a resource) go in `<run>/review/extra.json` as checks and calls before you build the app; `apply_review.py` lists the answers in `<run>/review/to-action.md` for you to act on. See `tools/review/README.md`.

## 6. Publish (after a human has checked the draft)
Apply the reviewers' fixes to `session.json`, set `meta.status` to `"final"`, then:
```bash
python3 ingest/ingest.py publish --links  # refuses if anything is untraceable or a section is empty
```
This writes `data/session.json` and `playbook/index.html`. The `playbook/` folder is a static site: deploying it anywhere is a separate step, so ask first. Every link in the page is handled in script, so it also works opened straight from disk.

## Never
- Add content from general knowledge, even "helpful" context. Empty is better than invented.
- Guess a word silently: use `[?word]` or `[illegible]` and list it.
- Put a person's or employer's name on the published page, except a commitment's own name and organisation that the person wrote on their card (`verify` checks those against the card).
- Publish without `verify` passing and a human having read the draft.

## Afterwards
Photos and voice notes may contain names and faces. Once the playbook is final, remind the user to delete `runs/*/audio`, the source photos and voice notes, and anything else the organisers agreed not to keep.
