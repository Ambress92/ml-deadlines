"""Create data/venues/<id>.yaml for a new conference, ready to fill in.

    python scripts/new_venue.py icra --name ICRA --area ai --rank A* \
        --full-name "IEEE International Conference on Robotics and Automation" \
        --url https://www.ieee-ras.org/conferences-workshops/fully-sponsored/icra --year 2027

Fill in the fields marked TODO from the official website, delete the ones
you do not know, then run `python scripts/build.py --check`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

from venues import AREAS, RANKS, VENUES_DIR

TEMPLATE = """\
name: {name}
full_name: {full_name}
area: {area}
rank: {rank}
url: {url}
# every_years: 2                 # for venues held every other year (ICCV, ECCV)
# edition_url_pattern: https://example.org/{{year}}/   # lets the update check find next year's site
editions:
  - year: {year}
    url: TODO                    # this edition's website
    cfp_url: TODO                # call for papers
    source: TODO                 # the official page the dates below come from
    last_verified: {today}
    location: {{city: TODO, country: TODO}}
    start: TODO                  # first day of the conference, YYYY-MM-DD
    end: TODO                    # last day, workshops included
    # timezone: AoE              # default; or UTC, UTC-7, America/Los_Angeles, ...
    rounds:
      - abstract: TODO           # YYYY-MM-DD means 23:59 in the time zone above
        paper: TODO              # or "YYYY-MM-DD HH:MM" for another time
        rebuttal: [TODO, TODO]   # first and last day
        notification: TODO
        camera_ready: TODO
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", help="short lowercase id, used as the file name (e.g. icra)")
    ap.add_argument("--name", required=True, help="short name shown on the site (e.g. ICRA)")
    ap.add_argument("--full-name", required=True)
    ap.add_argument("--area", required=True, choices=list(AREAS))
    ap.add_argument("--rank", required=True, choices=list(RANKS), help="CORE 2023 rank")
    ap.add_argument("--url", required=True, help="the series' main website")
    ap.add_argument("--year", type=int, default=dt.date.today().year + 1, help="first edition to add")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9-]+", args.id):
        print("The id must be lowercase letters, digits and dashes.", file=sys.stderr)
        return 1
    path = VENUES_DIR / f"{args.id}.yaml"
    if path.exists():
        print(f"{path.relative_to(VENUES_DIR.parent.parent)} already exists.", file=sys.stderr)
        return 1
    path.write_text(TEMPLATE.format(name=args.name, full_name=args.full_name, area=args.area,
                                    rank=args.rank, url=args.url, year=args.year, today=dt.date.today()))
    print(f"Created {path.relative_to(VENUES_DIR.parent.parent)}. Fill in the TODO fields, "
          f"then run: python scripts/build.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
