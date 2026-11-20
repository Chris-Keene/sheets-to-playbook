# On the day

A runbook for the person turning the sheets into a playbook. The session itself is in the slides (`slides/`), which carry the timings for each question.

## Words used here

- **Table lead:** the person at each table who holds the pen and writes the table number on every sheet.
- **Commitment card:** an A5 card, perforated down the middle. People write one thing they'll try on both halves, keep the half with the QR code, and hand in the other half, the **stub**.
- **Ingest:** turning the photos into a draft playbook. The **ingest lead** is the person running it on a laptop.
- **Run:** one ingest, kept in its own folder under `runs/`. `runs/latest` always points at the newest.
- **Contact sheets:** pages of small thumbnails of every photo, for spotting gaps and blur at a glance.
- **Readers:** Claude sub-agents, one per table, each transcribing that table's sheets in parallel.
- **Static host:** a service that serves plain files with no server code, such as Cloudflare Pages, GitHub Pages or Netlify.
- **Holding page:** a "coming soon" page at the playbook's address, so the QR code works before the playbook is ready.

## Before

- **Settings:** `playbook.config.json` has your names, colours and, most importantly, `playbook.url`: the commitment card's QR code points there, so it has to be fixed before you print. A free static host (Cloudflare Pages, GitHub Pages, Netlify) gives you an address in advance; build the holding page with `python3 build/build.py --holding --out <folder>` so the QR code lands somewhere until the playbook is ready.
- **Print:** `python3 print/build_paper.py --tables <n>`. One set of S1, S2, S3 and SS sheets per table (A1), a table card per table, and a commitment card per person plus spares.
- **Roles:** a lead at each table holds the pen; one or two people photograph every sheet at the end; one person runs the ingest. The person running the ingest needs a laptop with this repo, Claude Code, and a way to receive the photos (AirDrop, a shared folder).
- **Wi-Fi:** Claude needs the internet to read the handwriting, and venue Wi-Fi is unreliable. Keep a phone hotspot ready.
- **Practice:** run the ingest once on the test inbox (`tests/README.md`) so nothing is new on the day.

## Straight after the session

| When | What | Who |
| --- | --- | --- |
| As the session ends | Photograph every sheet: the whole sheet, then close-ups if the writing is small. Then the commitment card stubs, laid out flat. Send everything to the person running the ingest. | Photographers |
| +5 minutes | Photos into one folder. In Claude Code: *"build the playbook from this folder"*. Within about 5 minutes Claude reports any missing or blurred sheet. **Re-shoot those before the sheets come down.** | Ingest lead |
| Next hour or so | Claude reads every table in parallel, writes the draft, checks it, and builds the review pack. More photos (the cards, a retake) can join the same run. | Claude |
| When you have a quiet hour | Review with someone who was in the room: `runs/latest/review.html` puts every line next to its photo, and `runs/latest/playbook-draft.html` is the site as it stands. The review app handles uncertain words quickly (`tools/review/`). | Ingest lead, organiser |
| When you're both happy | Claude sets the status to final and runs `publish`. Deploy the `playbook/` folder. | Ingest lead |

The playbook doesn't have to go out the same day. A first edition that evening and a second, tidied edition a week later works well: people see it while the session is fresh, and late additions still have a home.

## Commands, if you're driving by hand

```bash
python3 ingest/ingest.py prepare <folder>               # new run in runs/, contact sheets in runs/latest/contact/
python3 ingest/ingest.py prepare <folder> --into <run>  # a second batch joins an existing run
python3 ingest/ingest.py transcribe                     # only if there are voice notes
python3 ingest/ingest.py status                         # after labels.json is filled in
python3 ingest/ingest.py verify --links
python3 ingest/ingest.py draft                          # runs/latest/playbook-draft.html
python3 ingest/ingest.py review                         # runs/latest/review.html
python3 ingest/ingest.py publish --links                # data/session.json and playbook/index.html
```

Optional: put `runs/<run>/names-to-scrub.txt` in the run, one name or organisation per line, and `verify` fails if any of them reach the page.

## If Claude isn't available

Everything except reading the handwriting still works. Run `prepare`, then label the photos in `labels.json` (the format is in the skill, `.claude/skills/sheets-to-playbook/SKILL.md`, section 2, "Label and check coverage"), and `review.html` lays the photos out per table. Copy `examples/session-template.json` to `runs/latest/session.json`, type the content in from the photos following `ingest/RAW_FORMAT.md`, "Stage 2: writing the playbook", then run `verify`, `draft` and `publish` as normal. It's slower, but the checks and the site are the same.

## Afterwards

Photos, and voice notes if you took any, may contain names and faces. Delete `runs/*/audio`, `runs/*/transcripts`, the photos and the original recordings once the final edition is out, or whenever you agreed with the people in the room.
