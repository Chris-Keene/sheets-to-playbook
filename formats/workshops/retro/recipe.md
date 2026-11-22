# Retro: writing the notes

The second stage for the retro workshop. ingest/RAW_FORMAT.md holds the rules every workshop shares, including the hard rules: nothing that isn't in the raw files, every item carries `src`, word-for-word text stays word for word, carry uncertainty forward.

Write `runs/<run>/session.json`, starting from `examples/retro-template.json` (same shape), with `meta.status` set to `"draft"`. `meta.tables` is how many teams there were; `meta.table_names` can name them (`{"1": "Platform"}`).

### Names
A retro is private to the team (the workshop's `privacy` is `private`), so people's names can stay: an action's owner is the person the team wrote in **Who**, and that's what the notes should show. Names of anyone outside the room, other companies or customers still come out of everything except `who`, unless the team chose to write them there. Add any that must never appear to the run's `names-to-scrub.txt`.

### Shaping it
- **went_well / got_in_way**: one line each from Sheet 1's two columns, lightly tidied into a full sentence (fix grammar, expand note-form) without adding meaning. When several teams wrote the same point, keep one line and list every src.
- **questions**: each team's "How might we…" from Sheet 2, word for word (`verify` checks), with `tables`.
- **ideas**: every idea box from Sheet 2. `text` lightly tidied, `votes` the dots counted on the sheet (`verify` checks the number against the transcription). Two teams' versions of the same idea become one idea with both srcs, and their votes added together. Don't rank them: the page sorts by votes.
- **actions**: every action row from Sheet 3: `what` lightly tidied, `who` and `when` exactly as written (`verify` checks both). Leave `who` or `when` out if the sheet left it blank; the page says "Not given". Don't invent an owner or a date.
- Merging is the only reason to drop a raw item. `verify` lists unused items so the reviewer can see what was left out.
