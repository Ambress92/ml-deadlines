# ML Deadlines

A static website listing deadlines, dates and locations of 26 A*/A conferences (CORE 2023) in ML, AI, NLP, vision, data mining/IR and databases. Public repo: https://github.com/Ambress92/ml-deadlines. The site is deployed to GitHub Pages on every push to `main`, and it is rebuilt every day.

## Layout

- `data/venues/<id>.yaml`: one file per conference series. The format is in `data/SCHEMA.md`.
- `scripts/venues.py`: loading, validation, time zones, and the automatic estimates.
- `scripts/build.py`: validates and builds `dist/` (page, `data.json`, `.ics` calendars). Use `--check` to validate only and `--serve` for a local preview.
- `scripts/check_updates.py`: fetches the official pages and reports what changed. It never edits data.
- `scripts/new_venue.py`: creates a template file for a new venue.
- `site/`: page template, `app.js`, `style.css`.
- Use the venv: `.venv/bin/python scripts/...` (it only needs PyYAML).

## Data rules

- Only official conference pages are sources. Never use aggregators (aideadlin.es, wikicfp, mldeadlines, paperpilot, and so on) or search-engine summaries. If an official page does not state something, leave the field empty. Never guess.
- Every non-estimated edition needs `source` (the page the dates come from) and `last_verified` (the date you checked it).
- Keep deadlines in the time zone that the official page uses. If the page states none, use AoE and say so in `notes`.
- Only record `abstract` if the venue requires an abstract before the paper deadline. Paper registration without an abstract (e.g. CVPR) goes in the round's `note`.
- Do not hand-write estimated editions. The build derives them from the previous edition. The one exception is an announced edition that is missing a round (e.g. KDD cycle 2): add the round with `estimated: true` and a note naming the source edition.

## Workflow: "update the data"

The user runs this manually, roughly every two weeks, by asking Claude to update the data.

1. Run `.venv/bin/python scripts/check_updates.py`.
2. For each item in the report, open the official page, read the dates, and edit the YAML. Work in this order: deadlines in the next 30 days, changed pages, next-edition sites now online, then missing or estimated data.
3. When a new edition is announced, add it as a new entry under `editions` (keep the old one; the build drops old editions from the site by itself). Remove `estimated` rounds once official dates exist.
4. Set `last_verified` to today on every edition you checked.
5. Run `.venv/bin/python scripts/build.py`. It must print no errors.
6. Show the user a short summary of what changed, then commit and push if they agree.

## Workflow: "add a conference"

1. Check the CORE 2023 rank at https://portal.core.edu.au/conf-ranks/ (the site covers A* and A only).
2. Run `.venv/bin/python scripts/new_venue.py <id> --name ... --full-name ... --area ... --rank ... --url ...`.
3. Fill in the file from the official pages, following the data rules above. Delete the fields that the pages do not state.
4. Run `build.py --check`, preview with `build.py --serve`, then commit.

GitHub issues from the "Suggest a conference" and "Report a wrong date" forms follow the same steps.
