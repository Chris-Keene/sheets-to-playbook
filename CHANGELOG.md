# Changelog

Versions follow [SemVer](https://semver.org/): a new feature or changed behaviour bumps the minor version, a fix the patch.

## 2.0.0 (27 November 2026)

Many workshops, not one. The kit was built around the four round-table sheets; now each workshop is an agenda of exercises, and every part of the kit follows it. Round tables come out exactly as before (checked by the golden test: every page, PDF and slide unchanged).

### Added
- **Workshops and exercises** (`formats/`): an exercise is one sheet or card (its question and boxes, laid out in rows); a workshop is an agenda of exercises with timings and add-ons, what its page holds and how each part is checked (`output.json`), its own rules (`rules.py`), its page views (`views.js`, optional `views.css`) and how to write it (`recipe.md`). The settings pick one (`workshop`) and can add folders of formats (`formats`). `build/formats.py` reads them.
- **Retro**, the first new workshop: How did it go? (went well, got in the way), What could we try? (a "How might we" question and ideas with dot votes), What we'll do (actions with who and by when). Private to the team, so names are allowed and sheets don't say "No names, please".
- **Sheets, fill-in pages and slides drawn from an exercise's boxes**: text, list, ranked, tally, row, list+votes and name. Slides for a workshop come from its agenda: a welcome with the plan, how it works, one slide per question with its own timer, the sheet's boxes, a progress rail and facilitator notes, and a thank-you. Round tables keep their hand-made sheets and slides.
- **Box positions beside every sheet** (`sheet-<code>-A1.layout.json`), so tests and tools can find any box in a photo.
- `ingest.py brief`: each workshop's sheets, boxes, ids and file shape for the readers, generated from its exercises. `RAW_FORMAT.md` now holds only the rules every workshop shares; round tables' shaping rules are in its `recipe.md`.
- **A generic notes page** (`build/views-generic.js`) for any workshop without its own views: laid out from its `output.json` (lists side by side, ideas ranked by votes, cards with labelled parts and ticks, 1 to 5 score tables that can name a band for each score, quotes, lists), with header links to its sections and a "How it was made" page from the agenda.
- **Seven more exercises**: pains (how it works today, what gets in the way, top three), now-next-later, risks, stakeholders, success-criteria, scale and impact. Row boxes can be one table with printed row labels (a scale's areas) and single-choice ticks. An agenda can reword an exercise's boxes and slide.
- **Three more workshops**: ideation, pre-mortem and business-change, each with an example, a template and a recipe.
- Checks any workshop can declare: a sum that must match the sheets (dot votes), fields copied exactly (who, by when, a score, a likelihood), what a final page must have. `ingest.py shape` prints an empty session for a workshop.
- A workshop names what it makes ("these notes", "this recap"), so the download button and the no-JavaScript message say so.
- `tools/new_event.py`: list the workshops, and set up an event's settings from yours.
- `tests/hw/make_format_test.py` and `score_format.py`: synthetic handwriting photos and scoring for any workshop, from an answer bank. Banks for retro, business change and a sampler of the other new exercises. First rounds: retro 69 answers (68 right, 1 flagged), business change 90 (90 right), sampler 30 (29 right, 1 flagged); no silent errors in any.
- Print kit: SVG logos made of nested groups and transforms now print where they should, and `brand.logo.keep_colours` keeps each shape's own colour on paper.

### Changed
- `verify`, the review page, the review app and `apply_review` follow the workshop's page paths instead of naming round tables' sections. Private workshops allow names (personal details are warnings there).
- Editing a word-for-word line in the review app now updates its transcription wherever it was written (a quote written on Sheet 2 used to keep its old raw text, so `verify` then failed it).
- A challenge can no longer have the id `challenges`, which the page's address for the challenge list would have hidden.
- **The commitment card is white** in print, in its fill-in page and on the slide that shows it, so you can print it on whatever colour of card you like. Its prompt and logo keep the brand colours; the print file adds a light dashed guide on the perforation, for printing without one.
- The golden test covers seven settings: default, CAN, a branded test with a two-colour logo, retro, ideation, pre-mortem and business change.

## 1.1.0 (20 November 2026)

### Added
- **Your own typeface:** `brand.font` sets the family and one static file per weight, used by the playbook, the holding page, the fill-in sheets, the slides and the print kit (which draws its lettering from the same files). Poppins stays the default.
- **Logos in their own colours:** `brand.logo.keep_colours`, PNG logos on the web pages, and a second file for dark backgrounds (`secondary_dark` and so on), swapped by the page's theme. The slides use the dark-background file on their coloured band. The print kit still draws SVGs only, and uses the wordmark for a PNG.
- **A "Built with" credit** at the foot of every playbook and holding page, with a small logo: "Built with sheets-to-playbook by Chris Keene". `credit` in the settings changes or removes it (`{"show": false}`). It replaces the session's `meta.credit`, which still shows if the credit is switched off.
- **Link to the tools** on the "Run your own" page: a "Get the whole kit on GitHub" button and a paragraph on how the site was made. `kit.source` sets the address, or `""` leaves it out.
- **Link previews** (`playbook.share`): Open Graph and Twitter tags on a final playbook once `playbook.url` is set, with an optional picture copied beside the page.
- `playbook.file_name` names the file "Download this playbook" saves (it was always `can-community-playbook.html`).
- `tests/golden.py`: a snapshot test of everything the kit builds (the text of every PDF, the text and accessibility tree of every page, slide and playbook view, `verify`'s report on a fake run in `tests/fixtures/run-golden/`), plus pictures kept on your own machine. Run it before and after a change to see exactly what moved.

### Changed
- **The challenge cards say they open.** Each card's title is an underlined link and ends with an "Explore this challenge" button (decoration only: the title link is still the one thing a screen reader hears), and the card lifts slightly on hover. People at the first forum didn't realise the cards opened.
- **"What we learned" is one heading and a grid of short cards**, instead of a box per lesson that each repeated the heading.
- The holding page takes all its colours from the palette (it used to find them by their exact hex values, so a changed template could silently keep the old ones).

## 1.0.0 (20 November 2026)

First public release, generalised from the kit and pipeline first used at the CAN Community Forum on 19 November 2026.

### Added
- One settings file, `playbook.config.json`, read by every builder: organisation and playbook names, the playbook's web address (for the QR code), logos, and two brand colours. Every other shade, in light and dark mode, is worked out and checked against WCAG 2.2 contrast. `--config` or `PLAYBOOK_CONFIG` picks another file.
- `playbook.searchable`: lets search engines list a final playbook. Off by default.
- A neutral default look, with the CAN settings as a worked example in `examples/can/`.
- The Claude Code skill now lives in `.claude/skills/`, so it's available as soon as Claude Code opens the clone. `tools/install_skill.py` installs it for every session.
- Review app: works on any run (`--run`), compiles its text recognition tool on first use, and falls back to whole photos where Apple's Vision isn't available. Run-specific checks and calls come from `<run>/review/extra.json`. `apply_review.py` now writes readings into `session.json` as well as the raw files, and is safe to run twice.
- HEIC photos convert with `pillow-heif` where installed, so the ingest no longer needs macOS for iPhone photos.
- `LICENSE` (MIT, code) and `LICENSE-CONTENT.md` (CC BY 4.0, the workshop kit).

### Changed
- The playbook site, holding page, paper kit and slides no longer name any organisation unless the settings do.
- The example playbook and session template describe a fictional event.

### Removed
- Deployment scripts tied to the original event's hosting.

## Before 1.0.0

Developed privately for the CAN Community Forum between October and November 2026: the three-sheet table format, the commitment card, the photo-to-playbook ingest with sub-agent readers and `verify`, three rounds of handwriting stress tests, the review app, and the playbook site.
