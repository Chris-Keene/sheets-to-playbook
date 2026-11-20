# Raw transcription format and playbook-writing rules

Used by the sheets-to-playbook skill (.claude/skills/sheets-to-playbook/SKILL.md). Two stages, kept apart on purpose:

1. **Transcribe** (one reader per table, in parallel): copy what is on the paper (and in any voice note) into `runs/<run>/raw/T07.json`. No summarising, no tidying beyond what's described here.
2. **Write** (one writer, after all tables are in): turn every raw file into `runs/<run>/session.json` in the playbook's format, citing raw ids in `src`.

Splitting them means every line on the website can be traced back to a photo, and `ingest.py verify` can prove it.

---

## Stage 1: transcribing one table

### What you're given
- The table number, and the photos labelled for it: `view/P012.jpg` (whole sheet, downsized) and `tiles/P012-a1.jpg` to `-b2.jpg` (four overlapping quarters at higher resolution: a = top, b = bottom, 1 = left, 2 = right).
- Any voice note transcript for the table: `transcripts/A03.txt` (Whisper output, so expect mis-heard words). Voice notes are optional and usually absent.

### How to read
- Look at the whole sheet first to understand the layout, then read every zone in the tiles. Dense or small writing is only reliable in the tiles.
- When several photos show the same sheet (a whole shot plus close-ups), read them together and transcribe each item **once**.
- **Two different copies of the same sheet** for your table (different hands, tallies or wording: real tables have used the same number twice): transcribe both, carrying the numbering on (`challenge5` onwards for the second), and start `notes` with which ids came from which photo. `room` holds the first sheet's tally; copy the second's into `notes`. Don't add the two tallies together. A heading copied into an answer box ("The one we're tackling is…") is not an answer: leave the item out and quote it in `notes`.
- Each sheet has printed headings and a printed sheet code (S1, S2, S3, SS) in the bottom corner. The table number is **handwritten** by the lead, in the circle at the top right and again next to the sheet code (`S2 · Table 7`). Trust what's written on the sheet over the label you were given; if the two handwritten numbers or the label disagree, say so in `notes`.
- Sheets: **S1** "Where does support get stuck?" (with a "Who's at this table?" tally box at the top), **S2** "What has helped, or not?", **S3** "What could people try now, and how does it stick?", **SS** the side sheet "Heard something good? Write it here." (Quotes, Questions and Resources columns, and a "Best thing said today" box at the bottom). If your sheets don't have the tally or the best-thing box, an older print was used: just leave those fields out.

### Transcription rules
- **Copy the words as written.** Fix nothing except obvious letter-level misspellings. Keep the writer's abbreviations, but expand an abbreviation in square brackets only if it is certain: `exec [executive]`.
- **Never guess silently.** A word you're not sure of goes in as `[?sponsor]` (your best reading after `?`). A word you can't read at all is `[illegible]`. Every item with either marker also goes in the `unclear` list with the photo id and what's wrong. A word you worked out from letter count or context rather than read is still a guess: mark it `[?word]` even if you're fairly sure. A note alone isn't a flag (round 3: a URL inferred from blobs of marker went only into `notes`).
- **Crossed-out text is left out.** Arrows and lines that join items: follow them, and note in `notes` if the meaning of a join is ambiguous.
- **Check every line for a single crossed-out word before you finish.** In thick marker one stroke through one word is easy to miss, and it's the one mistake that reaches the page unflagged (stress test: "not ever asked" with "ever" struck through was read as written). Look along each line in the tiles; leave the word out and say which word in `notes`.
- **Writing that runs off the sheet or out of the photo**: copy what's visible and mark the rest `[illegible]`. Don't finish a cut-off word, address or number from context, even as `[?…]`, unless you can see part of every letter.
- **Ticks**: any mark inside a box counts: a tick, a cross or a filled box. If one action mixes kinds of mark (a tick in one box, a cross in another), or a mark straddles two boxes, record your reading and add it to `unclear`.
- **"Who it was for"** notes: the sheets no longer ask for sector or size beside each item, but if someone writes one beside an S2 item or a quote anyway, put it in `who`, not in `text`.
- **"Who's at this table?"** (top of S1): count the tally marks in each sector box (a gate of four strokes with a fifth across is 5) and copy the countries line as written. It goes in `S1.room`, with no id: it describes the table, not an item. Leave out sectors with no marks.
- **"Best thing said today"** (bottom of the side sheet): the table lead's pick, copied word for word into `SS.best` with the id `T07.SS.best`. Keep it even if it repeats a quote or another item; the writer decides what to do with it.
- **S3 actions**: one object per action box. Put text in `action`, `needs`, `sticks`; the ticked boxes become `stages` from `starting`, `growing`, `established` (leave `[]` if none are ticked; don't infer).
- **Voice note** (only if there is one): pull out the specific points the lead makes that add something to the sheets, as `points`, each with an `excerpt` copied word for word from the transcript. Ignore filler. A point the sheets already cover doesn't need repeating.
- **Names**: transcribe names of people and organisations exactly as written. Removing them happens in stage 2; the reviewer needs to see what was really on the sheet.
- If a whole sheet is missing or unreadable, say so in `notes` and leave that section out. Don't reconstruct it from the other sheets or the voice note, even if the voice note mentions what the table picked (record that as a voice `point`).

### Ids
`T07.S1.challenge1`, `T07.S1.top1`, `T07.S1.pick`, `T07.S2.helped1`, `T07.S2.hindered1`, `T07.S2.lesson1`, `T07.S3.action1`, `T07.SS.quote1`, `T07.SS.question1`, `T07.SS.resource1`, `T07.SS.best`, `T07.V.point1`. Two-digit table number, count from 1 in reading order (top to bottom, left to right).

### File: `raw/T07.json`
```json
{
  "table": 7,
  "photos": ["P012", "P013"],
  "audio": ["A03"],
  "S1": {
    "challenges": [{"id": "T07.S1.challenge1", "text": "Exec sponsor left, nobody picked it up"}],
    "top3": [{"id": "T07.S1.top1", "text": "Exec sponsor left"}],
    "pick": {"id": "T07.S1.pick", "text": "Keeping leaders on board when they move on"},
    "room": {"tally": {"Finance": 3, "Public sector": 2, "Other": 1}, "countries": "UK, Ireland"}
  },
  "S2": {
    "helped": [{"id": "T07.S2.helped1", "text": "2 sponsors not 1", "who": "bank, 10k+"}],
    "hindered": [{"id": "T07.S2.hindered1", "text": "Big launch then nothing", "who": "retail"}],
    "lessons": [{"id": "T07.S2.lesson1", "text": "Write the sponsor role down"}]
  },
  "S3": {
    "actions": [{"id": "T07.S3.action1", "action": "Name a deputy sponsor", "needs": "15 mins with sponsor",
                 "sticks": "Review every 6 months", "stages": ["growing", "established"]}]
  },
  "SS": {
    "quotes": [{"id": "T07.SS.quote1", "text": "Leaders don't need convincing it matters, they need convincing it's theirs", "who": "public sector"}],
    "questions": [{"id": "T07.SS.question1", "text": "Does ESG help or is it a box tick?"}],
    "resources": [{"id": "T07.SS.resource1", "text": "W3C business case", "url": "w3.org/WAI/business-case"}],
    "best": {"id": "T07.SS.best", "text": "Make it theirs, not ours"}
  },
  "V": {
    "points": [{"id": "T07.V.point1", "text": "Sponsor handover should be on the exec's own leaving checklist",
                "excerpt": "someone said put the handover on the exec's own leaving checklist"}]
  },
  "unclear": [{"id": "T07.S2.helped1", "photo": "P013", "note": "number before 'sponsors' could be 2 or 3"}],
  "notes": "Arrow from 'budget' to 'leadership' on S1; read as related, not merged."
}
```
Card stubs go in `raw/commitments.json`: `{"photos": ["P040"], "cards": [{"id": "C.card1", "text": "...", "name": "Sam Sample", "org": "Example Bank", "challenge_hint": "budget"}], "unclear": [...]}`. `name` and `org` come only from the card's optional "Name" and "Organisation" lines, copied exactly; leave them out when those lines are blank. A name written anywhere else on the card is not consent to publish it.

Card rules (from real cards):
- **The commitment is the half with the Name and Organisation lines** (the stub). If a card arrives untorn, transcribe that half as the card and copy the other half (the QR half, the person's own copy) into `notes`, even when it says something different. If only a QR half comes in, transcribe it with no `name` or `org`.
- **Sign-offs aren't part of the commitment.** Leave "Thank you", "Thanks Sam :)" and other messages to the facilitators out of `text` and quote them in `notes`. That also keeps a name written outside the Name line out of the item text.
- **The same card in two photos** (one upside down, say) is one card. List both photo ids in `photos` and transcribe it once.

Check your file with `python3 ingest/ingest.py verify`. It reports bad ids and empty items; a missing `session.json` at this stage is expected.

---

## Stage 2: writing the playbook

Write `runs/<run>/session.json`, starting from `examples/session-template.json` (same shape), with `meta.status` set to `"draft"`.

### Hard rules
- **Nothing that isn't in the raw files.** No examples, statistics, tools, names or advice from general knowledge, however helpful. If a section has no raw material, leave it empty; the draft shows an empty box and the published page hides it.
- **Every item carries `src`**: one raw id, or a list when you've merged the same point from several tables (`["T05.S3.action1", "T09.S3.action2"]`). Questions and lessons become objects `{"text": ..., "src": ...}`.
- **Quotes and commitments stay word for word.** Only fix spelling and add punctuation. `verify` compares them to the raw text and fails anything that drifts.
- **Anonymise.** Remove people's names and the names of employers and organisations from all text, including quotes (replace with a neutral phrase in square brackets: `[a regulator]`). Quotes carry no attribution unless a sector is written beside them on the sheet, in which case use `"Participant, <sector>"`. Public resources (W3C, GOV.UK) keep their names. **Exception:** a commitment's own `name` and `org` fields, filled in by that person on their card, are published as written.
- **Carry uncertainty forward.** If a line depends on a `[?word]` reading, keep the marker; `verify` lists it so the reviewer can check the photo.

### Shaping it
- **Challenges**: start from each table's `S1.pick`. Tables that picked the same challenge (same problem, even if worded differently) become one entry with both table numbers; give it a short, plain title in the participants' terms. A table with no readable `pick` gets a page titled from its S2 and S3 content and a voice point, and goes on the review list. Ids are short lowercase slugs, such as `budget-before-crisis`.
- **Themes**: group every `S1.challenge` from every table into 5 to 10 themes. A theme's `tables` are the tables that listed something in it; `heard` holds 1 to 3 short phrases copied from the sheets. Every challenge points at one theme.
- **summary**: one or two sentences on why the challenge is hard, built only from that challenge's raw items (S1 wording, S2 hindered items, voice points). Cite nothing; it's a summary, not a quote.
- **helped / hindered**: one line each, lightly tidied into a full sentence (fix grammar, expand note-form) without adding meaning. No `where`: the published page doesn't show who it worked for.
- **actions**: `title` is a short imperative from the action text; `what`, `needs`, `sticks` from the matching boxes; `stages` exactly as ticked.
- **quotes**: the strongest one to three per challenge, from the side sheets of its tables, or from a voice `excerpt` if the lead was clearly quoting someone. A table's `SS.best` is its lead's own pick of the session, so prefer it: use it as a quote (cite `T07.SS.best`) unless it repeats a quote you're already using, in which case cite both ids on that quote.
- **Who was in the room**: `S1.room` isn't published yet (the website doesn't show it yet). Leave it in the raw files; `review` shows it per table.
- **commitments**: every card, word for word, with `name` and `org` only where the card's own Name and Organisation lines were filled in (copied as written; `verify` checks them against the card); set `challenge` only when the card's wording or hint clearly points at one challenge (for example it repeats that challenge's action). Otherwise `null`.
- **Heard on the day** (top-level `quotes`: it matters most when few tables used a side sheet): every side-sheet quote (it also stays on its challenge page) plus phrases the tables wrote in quotation marks on the main sheets that read as something a person said ("I'd rather pay the fines"), not scare-quoted terms ("pink + fluffy"). Word for word (`verify` checks), no names, nothing with an unclear marker. Each has `src`, `tables` and `challenge` (the page it links to). When several tables wrote versions of the same line, quote one and list every table and every src.
- **resources**: from side sheets, into the top-level `resources` list ("General reading") unless one clearly belongs to one challenge. Turn a written address into a full `https://` URL only when it's unambiguous. A resource named without an address is listed without a `url` (shown as text, not a link) and flagged for the reviewer, who may add one. `verify --links` checks every link.
- Merging is the only reason to drop a raw item. `verify` lists unused items so the reviewer can see what was left out.
