# Paper kit

Everything a session needs on paper, built from the settings file so it carries your name, colours and logo.

| Builder | Makes | Where |
|---|---|---|
| `build_paper.py` | Print-ready PDFs: four A1 worksheets (S1, S2, S3 and the side sheet SS), an A5 commitment card perforated down the middle, A4 table cards that fold into A5 tents, an overview image and a zip of the PDFs | `print/out/paper/`, `print/out/` |
| `build_sheets_html.py` | The same six pieces as fill-in web pages: every box is a labelled text box, each page prints on one A4 sheet, and fonts and logo are inline so each file stands alone | `print/out/html/` |
| `pdfkit.py` | The small PDF writer `build_paper.py` uses: CMYK artwork, spot colours for the perforation, outlined text | (a library) |

## Run it

```sh
python3 print/build_paper.py                          # playbook.config.json at the repo root
python3 print/build_sheets_html.py
python3 print/build_paper.py --config path/to/playbook.config.json --tables 8
```

Both builders take `--config <file>` (or the `PLAYBOOK_CONFIG` environment variable) and `--tables N` (default 12).
`build_paper.py` also takes `--qr-url <address>` to override the settings, `--no-qr` for a "Your QR code here" box,
and `--no-optional` to leave out the sector tally (S1) and the "Best thing said today" box (SS).

Files written:

```
print/out/paper/sheet-S1-A1.pdf   sheet-S2-A1.pdf   sheet-S3-A1.pdf   sheet-SS-A1.pdf
print/out/paper/commitment-card-A5-perforated.pdf
print/out/paper/table-cards-A4-fold-to-A5-tables-1-to-<n>.pdf
print/out/paper-kit-print-files-v<version>.zip     print/out/paper-kit-overview.png
print/out/html/sheet-S1.html  sheet-S2.html  sheet-S3.html  sheet-SS.html  commitment-card.html  table-card.html
```

## What comes from the settings

See `build/config.py` for the whole file. The paper kit reads:

| Setting | Used for |
|---|---|
| `playbook.name` | Sheet footers ("All of this goes into the ..."), the card's QR caption, page and PDF titles, and the wordmark if `org.short` is empty |
| `playbook.url` | The commitment card's QR code and the address printed beside it; the HTML pages' link back to the kit. Leave it empty and the card gets a dashed "Your QR code here" box instead |
| `org.short`, `org.name` | The wordmark text, and the logo's accessible name on the web pages |
| `brand.accent`, `brand.highlight` | Header bands, headings and logo (accent); the commitment card (highlight) |
| `brand.logo.secondary` (or `.primary`) | The logo on every piece |
| `brand.palette` | The web pages' colours, if you list exact ones |
| `brand.cmyk` | Optional, print only: `{"accent": [c, m, y, k], "highlight": [c, m, y, k]}` with values from 0 to 1 |

### Colours

The web pages take their colours from the playbook's palette, which is checked for WCAG 2.2 contrast. Hints and
ruled lines stay fixed greys that pass on any brand's pale tint. Where a brand colour wouldn't read (a pale accent
as text, say), the builders darken that use of it just enough, and leave the brand colour itself alone everywhere
else.

The PDFs convert your hex colours to CMYK with a simple formula. That's fine for a proof, but it isn't a colour
profile: if your printer has already matched your brand colours, put their CMYK values in `brand.cmyk` and ask for
a printed proof before a full run.

### Logo

Point `brand.logo.secondary` (a wide, one-line version suits the footers best) at an SVG file. For print, the
logo is redrawn in the accent colour from its `<path>` shapes, so it works best as a flat, single-colour SVG of
filled paths: no transforms, strokes, text or embedded images. If there's no logo file, or it has nothing the kit
can draw, the organisation's short name (or the playbook's name) stands in, set in bold in the accent colour.

### The QR code

Point `playbook.url` at an address you control, so it can forward somewhere else later without a reprint. An
address without `https://` gets it added, so phones open it as a link.

## Needs

Python 3.9 or later with `pikepdf`, `fonttools` and `brotli` (to read the woff2 fonts), `segno` for QR codes and
`Pillow`; and Poppler's `pdftoppm` for the overview image. The font is Poppins (SIL Open Font License), from
`assets/fonts/`, so any name in your settings needs to use characters Poppins has; the builder stops and says so
if one doesn't.

## Checking your own build

The web pages were checked with both example settings (`playbook.config.json` and `examples/can/playbook.config.json`):
every control has an accessible name, headings run h1 then h2, text contrast is at least 4.5:1 and box edges at
least 3:1, nothing scrolls sideways at 375 px wide, and each page prints on exactly one A4 sheet. A very long
playbook name or unusual colours can still break that, so look at the pages (and print one) after changing your
settings. For the PDFs, open each one and check the colours against a printed proof.
