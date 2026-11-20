# Facilitator slides

One self-contained HTML slide deck for running the forum session, plus an optional PDF backup. The deck runs offline from any laptop: fonts, logo, QR code and photos are all inlined. Names, colours, the logo and the playbook's address come from the same settings file as the playbook website, so the slides and the site always match.

```sh
python3 slides/build_slides.py                                      # slides/out/slides.html
python3 slides/build_slides.py --config path/to/playbook.config.json
python3 slides/build_slides.py --pdf                                # also slides/out/slides.pdf, one slide per page
```

Without `--config`, the builder reads `playbook.config.json` at the repo root, or the file named in the `PLAYBOOK_CONFIG` environment variable. `examples/can/playbook.config.json` is a full worked example.

## What the deck reads from the settings

| Setting | Where it shows |
| --- | --- |
| `org.forum` | The title slide's heading when `slides.title` is empty, or the line above it when it isn't. Also the page title. |
| `org.short`, `org.name` | The logo's accessible name. `org.short` is the wordmark when there's no logo file. |
| `playbook.name` | The playbook slide's label, the thank-you slide, the wordmark when there's no `org.short`. |
| `playbook.url` | The QR code and address on the thank-you slide, the small QR on the commitment card drawing, the address bar in the playbook screenshot. Empty: no QR code, and the last slide's notes say "Add your playbook's address in playbook.config.json". |
| `org.join` | `{"label", "url"}`: a "stay in touch" line on the thank-you slide. Leave it out to drop the line. |
| `brand.accent`, `brand.highlight`, `brand.palette` | The colours (see below). |
| `brand.logo.primary` | The logo on the title and thank-you slides. Missing file: the wordmark. |
| `brand.logo.mark` | The small mark on the table card drawing. Missing file: the `org.short` wordmark, or nothing. |
| `slides` | The section below. |

## The `slides` section

Every key is optional, and so is the section.

```json
"slides": {
  "title": "Growing and sustaining support for accessibility",
  "welcome": "Welcome to the session. Great to have you here!",
  "facilitators": [
    {"name": "Sam Example", "role": "Head of Accessibility, Example Org", "photo": "people/sam.jpg"},
    {"name": "Alex Sample", "role": "Accessibility Lead"}
  ],
  "playbook_image": "brand/playbook-screenshot.png",
  "playbook_image_alt": "The playbook's front page: the heading Growing and sustaining support, and a button reading Go to the challenges."
}
```

| Key | Default | Notes |
| --- | --- | --- |
| `title` | the forum's name (`org.forum`, capitalised: "Community forum" with the default settings) | The title slide's big heading. When it differs from the forum's name, the forum's name sits above it as a label. |
| `welcome` | "Welcome to the session. Great to have you here!" | One line at the foot of the title slide. |
| `facilitators` | none | Each needs a `name`; `role` and `photo` are optional. With none, the facilitators slide is left out and the slide count adjusts. Up to four sit in two roomy rows, five or six in tighter rows, seven to nine in three columns. More than nine won't fit. |
| `photo` | none | Relative to the settings file. Any common image format: it's cropped to a square from the centre and shrunk, so a phone photo is fine. Missing photo: the person's initials. The photo is decorative, because the name sits beside it. |
| `playbook_image` | none | A screenshot of the playbook for its slide, relative to the settings file. A tall full-page screenshot shows its top, like a browser window. With none, the slide shows its words on their own (and the address, if there is one). |
| `playbook_image_alt` | "The (playbook name) website's front page." | Describe what the screenshot actually shows. |

Photos and screenshots are personal or event material: keep them beside your own settings file, not in the repo.

## The session the deck runs

Eleven slides with facilitators, ten without: welcome, facilitators, the playbook, how it gets made, Question 1 (sheet), Question 1 (table cards), Question 2, Question 3, Question 4 (commitment card), share-back, thank you.

The speaker notes (press N) time the hour in minutes from the start:

| Minutes | Part | Timer |
| --- | --- | --- |
| 0 to 10 | Welcome, up to Question 1 | |
| 10 to 22 | Question 1: about 7 minutes on the sheet, then 5 with the table cards | 12 minutes, one timer shared by both slides |
| 22 to 35 | Question 2 | 13 minutes |
| 35 to 50 | Question 3 | 15 minutes |
| 50 to 55 | Question 4, the commitment card | 5 minutes |
| 55 to 60 | Share-back and close (skip the share-back if you're running late) | |
| Afterwards | Photograph the sheets and collect the card halves: about 30 minutes | |

## Presenting

| Key | Does |
| --- | --- |
| Right arrow, Down arrow, Page Down, Space | Next slide (most clickers send Page Down) |
| Left arrow, Up arrow, Page Up | Previous slide |
| Home, End | First, last slide |
| T | Start or pause the timer on this slide. Question 1's timer keeps running from its sheet slide onto the table card slide. |
| R | Reset the timer on this slide |
| B or . | Blank the screen; any key brings it back |
| F or F5 | Full screen |
| N | Speaker notes |

The controls in the corner fade out when the mouse is still and come back on mouse movement or keyboard focus. Screen readers hear "Slide 3 of 10" and the slide's heading on each change, and "One minute left" and "Time's up" from the timer on screen.

## Colours

The slide background is the brand's accent, labels use its highlight, and the highlight also fills the timer when time is nearly up, the progress rail and the numbered steps. Everything is worked out from the playbook's palette (`build/config.py`), so the slides and the site change together, then checked against WCAG 2.2 every build: 4.5:1 for text, 3:1 for the timer ring and focus outlines. A pale accent is darkened until white text reads on it, and a highlight that doesn't read on the accent is swapped for white for labels. If an exact `brand.palette` you've set fails a check, the build stops and says which pairing failed.

The deck has no dark mode on purpose: it's always the brand colour, on screen and in print.

## The PDF

`--pdf` prints the deck one slide per page at 1920 by 1080, without the notes, as a tagged PDF. It needs Node.js and Playwright with its Chromium. Install Playwright once in a folder of its own, then point the `PW` environment variable at it when you build:

```sh
mkdir -p ~/playwright && cd ~/playwright && npm install playwright && npx playwright install chromium
cd <this repo> && PW=~/playwright/node_modules/playwright python3 slides/build_slides.py --pdf
```

## Changing the template

Edit `template-slides.html`, not the output. The builder fills these in:

| In the template | Becomes |
| --- | --- |
| `{{key}}` | A piece of text from the settings, escaped |
| `<!--LOGO-->`, `<!--MARK-->`, `<!--QR-->`, `<!--QR_MINI-->`, `<!--HERO-->`, `<!--PEOPLE-->` | Built HTML |
| `<!--IF:x-->` a `<!--ELSE:x-->` b `<!--END:x-->` | a or b depending on the settings (`people`, `image`, `url`, `join`, `kicker`); the ELSE part is optional |
| `/*FONTS*/`, `/*COLOURS*/`, `/*VERSION*/` | The inlined fonts, the brand's colours, the builder's version |

The build stops if a placeholder is left unfilled, or if the template's own words contain an em dash or a spaced en dash.
