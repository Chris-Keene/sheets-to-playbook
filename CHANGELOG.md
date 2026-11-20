# Changelog

Versions follow [SemVer](https://semver.org/): a new feature or changed behaviour bumps the minor version, a fix the patch.

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
