# ML conference deadlines web app: plan

Status: first version built on 2026-09-18. Decisions below were agreed that day. How to run and maintain it is in README.md and CLAUDE.md.

## Goal

A public website that lists the deadlines, dates and locations of the main A*/A AI and ML conferences. It differs from aideadlin.es and similar sites in three ways:

1. It shows the full deadline timeline (abstract, paper, rebuttal, notification, camera-ready, conference), not only the paper deadline.
2. Users can subscribe to deadlines in their calendar (`.ics`).
3. It has a better visualization: a timeline view and a list view, chosen with a toggle.

## Venues (26)

| Area | Venues |
|---|---|
| Core ML | NeurIPS, ICML, ICLR, AISTATS, UAI, COLT |
| General AI | AAAI, IJCAI, ECAI, AAMAS |
| Vision | CVPR, ICCV, ECCV |
| NLP | ACL, EMNLP, NAACL |
| Data mining / IR / web | KDD, ICDM, WSDM, SIGIR, WWW, CIKM, ECML-PKDD |
| Databases | SIGMOD, ICDE, VLDB |

Robotics venues are out of scope. Ranks must be checked against the CORE 2023 portal when the data is collected.

## Views and sorting

- Two views, switched with a toggle: Timeline (one row per venue across 12 months, phases as colored segments, a line for today) and List.
- Both views sort by the next upcoming submission deadline, nearest first.
- Venues with monthly rolling deadlines (VLDB) are not in the sort. They appear in a separate "Rolling submissions" strip that shows the next date. Venues with a few rounds per year (SIGMOD, ICDE) stay in the main sort, keyed on their next round.
- When a venue's deadline has passed, its sort key becomes next year's deadline. If that date is not announced, it is estimated from last year's date and shown as "estimated" (faded in the UI).
- The timeline covers 12 months starting from today. The conference bar is labeled with its dates and location, and venue names link to the official site.
- An "abstract" phase is recorded only when the venue requires an abstract before the paper deadline. Paper registration steps without an abstract (e.g. CVPR) are left out.
- Times are stored with their timezone (usually AoE, UTC-12) and shown in the user's local timezone.

## Data model (draft)

A venue series (e.g. NeurIPS) has one edition per year. Each edition stores:

- conference dates, city, country, coordinates, format (in person or hybrid)
- a list of rounds; each round has its own phases (abstract, paper, rebuttal, notification, camera-ready), each with a datetime and timezone
- for monthly venues, a recurrence rule (e.g. "1st of every month") that the build expands into concrete rounds, plus the edition each round feeds into
- links (website, CFP, OpenReview), area tags, CORE rank, page limit, past acceptance rates
- `estimated: true` when dates are extrapolated from the previous year
- `source_url` and `last_verified`

## Stack

A single Python build script (no framework, since Node is not installed): it validates the YAML, writes a static page, `data.json` and one `.ics` file per venue into `dist/`. GitHub Actions deploys `dist/` to GitHub Pages on every push and rebuilds it daily. No backend.

## Maintenance

- Adding a venue: `scripts/new_venue.py` creates a template, plus a GitHub issue form for public suggestions.
- Updating: run manually about every two weeks, by asking Claude to "update the data". `scripts/check_updates.py` compares the official pages with the previous snapshots and lists what changed. Claude then edits the YAML from the official pages. The full workflow is in CLAUDE.md.
- Sources: official conference pages only. Anything they do not state stays empty.
