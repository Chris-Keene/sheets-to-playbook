# Changelog

Versions follow [SemVer](https://semver.org/): a new feature or changed behaviour bumps the minor version, a fix the patch.

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
