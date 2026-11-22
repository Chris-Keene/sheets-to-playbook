# Raw transcription format and writing rules

Used by the sheets-to-playbook skill (.claude/skills/sheets-to-playbook/SKILL.md). Two stages, kept apart on purpose:

1. **Transcribe** (one reader per table, in parallel): copy what is on the paper (and in any voice note) into `runs/<run>/raw/T07.json`. No summarising, no tidying beyond what's described here.
2. **Write** (one writer, after all tables are in): turn every raw file into `runs/<run>/session.json` in the page's format, citing raw ids in `src`.

Splitting them means every line on the website can be traced back to a photo, and `ingest.py verify` can prove it.

This file holds the rules for every workshop. What's particular to the one being run comes from its format files:

- **The sheets, their boxes, the ids and the file's shape:** `python3 ingest/ingest.py brief` prints them for the workshop the settings name (`workshop` in playbook.config.json; round tables if it names none). Give each reader its output along with this file.
- **How to write the page:** `formats/workshops/<workshop>/recipe.md`.

---

## Stage 1: transcribing one table

### What you're given
- The table number, and the photos labelled for it: `view/P012.jpg` (whole sheet, downsized) and `tiles/P012-a1.jpg` to `-b2.jpg` (four overlapping quarters at higher resolution: a = top, b = bottom, 1 = left, 2 = right).
- Any voice note transcript for the table: `transcripts/A03.txt` (Whisper output, so expect mis-heard words). Voice notes are optional and usually absent.

### How to read
- Look at the whole sheet first to understand the layout, then read every zone in the tiles. Dense or small writing is only reliable in the tiles.
- When several photos show the same sheet (a whole shot plus close-ups), read them together and transcribe each item **once**.
- **Two different copies of the same sheet** for your table (different hands, tallies or wording: real tables have used the same number twice): transcribe both, carrying the numbering on (`challenge5` onwards for the second), and start `notes` with which ids came from which photo. `room` holds the first sheet's tally; copy the second's into `notes`. Don't add the two tallies together. A heading copied into an answer box ("The one we're tackling is…") is not an answer: leave the item out and quote it in `notes`.
- Each sheet has printed headings and a printed sheet code in the bottom corner (the brief lists them). The table number is **handwritten** by the lead, in the circle at the top right and again next to the sheet code (`S2 · Table 7`). Trust what's written on the sheet over the label you were given; if the two handwritten numbers or the label disagree, say so in `notes`.
- Some boxes are optional (the brief says which): if a sheet doesn't have one, an older print was used, so leave that field out.

### Transcription rules
- **Copy the words as written.** Fix nothing except obvious letter-level misspellings. Keep the writer's abbreviations, but expand an abbreviation in square brackets only if it is certain: `exec [executive]`.
- **Never guess silently.** A word you're not sure of goes in as `[?sponsor]` (your best reading after `?`). A word you can't read at all is `[illegible]`. Every item with either marker also goes in the `unclear` list with the photo id and what's wrong. A word you worked out from letter count or context rather than read is still a guess: mark it `[?word]` even if you're fairly sure. A note alone isn't a flag (round 3: a URL inferred from blobs of marker went only into `notes`).
- **Crossed-out text is left out.** Arrows and lines that join items: follow them, and note in `notes` if the meaning of a join is ambiguous.
- **Check every line for a single crossed-out word before you finish.** In thick marker one stroke through one word is easy to miss, and it's the one mistake that reaches the page unflagged (stress test: "not ever asked" with "ever" struck through was read as written). Look along each line in the tiles; leave the word out and say which word in `notes`.
- **Writing that runs off the sheet or out of the photo**: copy what's visible and mark the rest `[illegible]`. Don't finish a cut-off word, address or number from context, even as `[?…]`, unless you can see part of every letter.
- **Ticks**: any mark inside a box counts: a tick, a cross or a filled box. If one action mixes kinds of mark (a tick in one box, a cross in another), or a mark straddles two boxes, record your reading and add it to `unclear`.
- **Tallies**: count the marks in each box (a gate of four strokes with a fifth across is 5). Leave out boxes with no marks. A tally describes the table, not an item, so it has no id.
- **Rows** (a box with several labelled parts, like an action with what to try, what you need and how it sticks): one object per row, each part in its own field, ticked boxes as a list of their values (leave `[]` if none are ticked; don't infer).
- **The brief's notes for each box** add anything particular to that box (where a stray sector note goes, what a lead's pick is for).
- **Voice note** (only if there is one): pull out the specific points the lead makes that add something to the sheets, as `points`, each with an `excerpt` copied word for word from the transcript. Ignore filler. A point the sheets already cover doesn't need repeating.
- **Names**: transcribe names of people and organisations exactly as written. Removing them happens in stage 2; the reviewer needs to see what was really on the sheet.
- If a whole sheet is missing or unreadable, say so in `notes` and leave that section out. Don't reconstruct it from the other sheets or the voice note, even if the voice note mentions what the table picked (record that as a voice `point`).

### Ids
`T07.<sheet code>.<box><n>`: a two-digit table number, the sheet's code, and the box's name with a count from 1 in reading order (top to bottom, left to right), such as `T07.S1.challenge1`. A box that holds one thing has no number (`T07.S1.pick`). Voice note points are `T07.V.point1`. The brief lists every one for the workshop.

### Files
`raw/T07.json` holds one table: `table`, `photos`, `audio`, a section per sheet code (the brief shows the shape), and then:
```json
  "unclear": [{"id": "T07.S2.helped1", "photo": "P013", "note": "number before 'sponsors' could be 2 or 3"}],
  "notes": "Arrow from 'budget' to 'leadership' on S1; read as related, not merged."
```
Cards each person fills in (a commitment card) go in one file for the whole room, described in the brief.

Check your file with `python3 ingest/ingest.py verify`. It reports bad ids and empty items; a missing `session.json` at this stage is expected.

---

## Stage 2: writing the page

Write `runs/<run>/session.json` in the shape the workshop's recipe gives, with `meta.status` set to `"draft"`. The recipe (`formats/workshops/<workshop>/recipe.md`) says how to shape it; these rules hold for every workshop.

### Hard rules
- **Nothing that isn't in the raw files.** No examples, statistics, tools, names or advice from general knowledge, however helpful. If a section has no raw material, leave it empty; the draft shows an empty box and the published page hides it.
- **Every item carries `src`**: one raw id, or a list when you've merged the same point from several tables (`["T05.S3.action1", "T09.S3.action2"]`). Questions and lessons become objects `{"text": ..., "src": ...}`.
- **Quotes and commitments stay word for word.** Only fix spelling and add punctuation. `verify` compares them to the raw text and fails anything that drifts.
- **Anonymise.** Remove people's names and the names of employers and organisations from all text, including quotes (replace with a neutral phrase in square brackets: `[a regulator]`). Quotes carry no attribution unless a sector is written beside them on the sheet, in which case use `"Participant, <sector>"`. Public resources (W3C, GOV.UK) keep their names. **Exception:** a commitment's own `name` and `org` fields, filled in by that person on their card, are published as written.
- **Carry uncertainty forward.** If a line depends on a `[?word]` reading, keep the marker; `verify` lists it so the reviewer can check the photo.
