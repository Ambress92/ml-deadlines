# ML Deadlines

Submission deadlines, review phases, dates and locations of the main A*/A conferences (CORE 2023) in machine learning, AI, NLP, computer vision, data mining, information retrieval and databases.

**Site:** https://ambress92.github.io/ml-deadlines/

- **Timeline view.** Every venue on one 12-month axis starting today: abstract and paper deadlines, review period, rebuttal, ARR commitment, notification, camera-ready and the conference itself.
- **List view.** Live countdowns in your local time, with the official time (usually AoE) next to each one.
- **Calendar sync.** Subscribe to the venues you care about in Google Calendar, Apple Calendar or Outlook. Subscribed calendars update when dates change.
- **Estimated dates.** When a venue has not announced its next edition yet, the site shows last year's dates shifted forward, clearly marked as estimated.
- **Rolling deadlines.** Monthly venues such as VLDB appear in a separate strip, so they do not always sit at the top of the list.

Every date comes from the official conference website, which each entry links to, together with the date it was last checked.

## Venues

| Area | Venues |
|---|---|
| Core ML | NeurIPS, ICML, ICLR, AISTATS, UAI, COLT |
| General AI | AAAI, IJCAI, ECAI, AAMAS |
| Vision | CVPR, ICCV, ECCV |
| NLP | ACL, EMNLP, NAACL |
| Data mining & IR | KDD, ICDM, WSDM, SIGIR, WWW, CIKM, ECML-PKDD |
| Databases | SIGMOD, ICDE, VLDB |

## Contributing

- **A date is wrong or new dates are out:** open a [Report a wrong date](../../issues/new?template=update-dates.yml) issue with a link to the official page, or edit the venue's file in `data/venues/` and open a pull request.
- **A conference is missing:** open a [Suggest a conference](../../issues/new?template=add-conference.yml) issue. The site covers A* and A venues in the areas above.

The file format is described in [data/SCHEMA.md](data/SCHEMA.md). Pull requests are validated automatically.

## Running it locally

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build.py --serve        # build and preview on http://localhost:8000
.venv/bin/python scripts/build.py --check        # validate the data only
.venv/bin/python scripts/new_venue.py --help     # start a file for a new venue
.venv/bin/python scripts/check_updates.py        # report official pages whose dates changed
```

The build is a single Python script with no framework. It writes a static page, a JSON file and one `.ics` calendar per venue into `dist/`, which GitHub Actions deploys to GitHub Pages on every push and once a day.
