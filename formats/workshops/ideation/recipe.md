# Ideation: writing the notes

The second stage for the ideation workshop. ingest/RAW_FORMAT.md holds the rules every workshop shares, including the hard rules: nothing that isn't in the raw files, every item carries `src`, word-for-word text stays word for word, carry uncertainty forward.

Start `runs/<run>/session.json` from `python3 ingest/ingest.py shape --out runs/<run>/session.json` (with this workshop's settings), set `meta.status` to `"draft"`, and fill in `meta`: `title`, `series` (the notes' name), `event`, `date`, and `tables`, how many teams there were (`meta.table_names` can name them: `{"1": "Platform"}`).

### Names
A ideation is private to the people in the room (the workshop's `privacy` is `private`), so people's names can stay where the sheets put them: an action's owner is the person written in **Who**. Names of anyone outside the room, other companies or customers come out of everything else. Add any that must never appear to the run's `names-to-scrub.txt`.

### Shaping it
- **questions**: each team's “How might we…”, word for word (`verify` checks), with `tables`.
- **ideas**: every idea box: `text` lightly tidied, `votes` the dots counted on the sheet (`verify` checks the number against the transcription). Two teams' versions of the same idea become one idea with both srcs and their votes added together. Don't rank them: the page sorts by votes.
- **actions**: every action row: `what` lightly tidied, `who` and `when` exactly as written (`verify` checks both). Leave `who` or `when` out if the sheet left it blank; the page says “Not given”. Don't invent an owner or a date.
- Every item carries `tables`: the teams it came from (the page shows them when there was more than one team).
- Merging is the only reason to drop a raw item. `verify` lists unused items so the reviewer can see what was left out.
