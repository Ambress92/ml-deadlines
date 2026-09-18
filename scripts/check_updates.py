"""Find what needs a manual look before the data is updated.

    python scripts/check_updates.py              check every venue
    python scripts/check_updates.py kdd icml     check some venues
    python scripts/check_updates.py --no-save    do not store new snapshots

For every current edition it downloads the official pages (source and
cfp_url), keeps the lines that look like dates, and compares them with the
snapshot from the previous run (stored in .cache/snapshots/). It also checks
whether the next edition's website exists yet, and lists estimated dates,
missing fields, stale entries and deadlines in the next 30 days.

The report is printed and saved to .cache/last-report.md. The script never
edits the data: someone reads the flagged pages and updates data/venues/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

from venues import ROOT, SUBMISSION_PHASES, load_all, parse_date, parse_deadline, parse_tz

CACHE = ROOT / ".cache"
SNAPSHOTS = CACHE / "snapshots"
STALE_DAYS = 30
SOON_DAYS = 30
UA = "Mozilla/5.0 (ml-deadlines update check; +https://github.com/Ambress92/ml-deadlines)"
MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE_LINE = re.compile(rf"\b({MONTHS})[a-z]*\.?\s+\d|\d\s+({MONTHS})|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}", re.I)
BLOCK_TAGS = {"p", "div", "li", "tr", "td", "th", "br", "h1", "h2", "h3", "h4", "h5", "h6", "section", "table", "dt", "dd"}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # DNS errors, timeouts, TLS problems
        return None, str(e)


def date_lines(html: str) -> list[str]:
    parser = TextExtractor()
    parser.feed(html)
    lines = (re.sub(r"\s+", " ", l).strip() for l in "".join(parser.parts).split("\n"))
    return [l for l in lines if l and len(l) < 300 and DATE_LINE.search(l)]


def snapshot_path(url: str):
    return SNAPSHOTS / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")


def check_page(url: str, save: bool) -> tuple[str, list[str]]:
    """Returns (status, detail lines). Status is new, changed, same or error."""
    code, body = fetch(url)
    if code != 200:
        return "error", [f"could not fetch ({code or body})"]
    lines = date_lines(body)
    path = snapshot_path(url)
    old = path.read_text().splitlines()[1:] if path.exists() else None
    if save:
        SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        path.write_text(url + "\n" + "\n".join(lines))
    if old is None:
        return "new", [f"first snapshot ({len(lines)} date lines); check it by hand once"]
    if old == lines:
        return "same", []
    diff = [l for l in difflib.unified_diff(old, lines, lineterm="", n=0)
            if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return "changed", diff[:40]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("venues", nargs="*", help="venue ids (file names without .yaml); default: all")
    ap.add_argument("--no-save", action="store_true", help="do not update the stored snapshots")
    args = ap.parse_args()

    venues, errors = load_all()
    if errors:
        print("Fix these data errors first:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    if args.venues:
        unknown = set(args.venues) - {v["id"] for v in venues}
        if unknown:
            print(f"Unknown venue ids: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 1
        venues = [v for v in venues if v["id"] in args.venues]

    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    changed, new_sites, todo, soon, fetch_errors = [], [], [], [], []

    for v in venues:
        vid, eds = v["id"], sorted(v["editions"], key=lambda e: e["year"])
        current = [e for e in eds if not e.get("end") or parse_date(e["end"]) >= today] or eds[-1:]
        print(f"checking {vid} ...", file=sys.stderr)

        for ed in current:
            tag = f"{v['name']} {ed['year']}"
            for url in dict.fromkeys(u for u in (ed.get("source"), ed.get("cfp_url")) if u):
                status, detail = check_page(url, not args.no_save)
                if status == "changed":
                    changed.append((tag, url, detail))
                elif status == "new":
                    changed.append((tag, url, detail))
                elif status == "error":
                    fetch_errors.append(f"{tag}: {url} {detail[0]}")

            missing = [f for f in ("location", "start") if not ed.get(f)]
            if not ed.get("rounds") and not v.get("rolling"):
                missing.append("deadlines")
            if missing:
                todo.append(f"{tag}: missing {', '.join(missing).replace('start', 'conference dates')}")
            est_rounds = [r.get("name") or "main" for r in ed.get("rounds") or [] if r.get("estimated")]
            if est_rounds:
                todo.append(f"{tag}: estimated round(s) {', '.join(est_rounds)}; replace with official dates when announced")
            if ed.get("last_verified") and (today - parse_date(ed["last_verified"])).days > STALE_DAYS:
                todo.append(f"{tag}: last verified {ed['last_verified']}, more than {STALE_DAYS} days ago")
            if ed.get("notes") and re.search(r"assumed|not announced|TBA|TBD|not published", ed["notes"], re.I):
                todo.append(f"{tag}: note says \"{ed['notes']}\"")

            tz = parse_tz(ed.get("timezone", "AoE"))
            for rnd in ed.get("rounds") or []:
                for key in SUBMISSION_PHASES:
                    if rnd.get(key) is None:
                        continue
                    when = parse_deadline(rnd[key], tz)
                    if now < when <= now + dt.timedelta(days=SOON_DAYS):
                        name = f" {rnd['name']}" if rnd.get("name") else ""
                        soon.append(f"{tag}{name} {key}: {when:%b %d %H:%M} {ed.get('timezone', 'AoE')}")

        pattern = v.get("edition_url_pattern")
        if pattern and not v.get("rolling"):
            nxt = eds[-1]["year"] + v.get("every_years", 1)
            url = pattern.format(year=nxt)
            code, _ = fetch(url)
            if code == 200:
                new_sites.append(f"{v['name']} {nxt}: {url} is online, but data/venues/{vid}.yaml has no {nxt} edition")

    out = [f"# Update check, {today:%Y-%m-%d}", ""]

    def section(title, items, fmt=lambda x: f"- {x}"):
        out.append(f"## {title} ({len(items)})")
        out.extend(fmt(i) for i in items) if items else out.append("- none")
        out.append("")

    section("Deadlines in the next 30 days (double-check these first)", soon)
    section("Pages whose dates changed since the last check", changed,
            lambda c: f"- {c[0]}: {c[1]}\n" + "\n".join(f"    {l}" for l in c[2]))
    section("Next-edition websites that are now online", new_sites)
    section("Missing or estimated data", todo)
    section("Pages that could not be fetched (check by hand)", fetch_errors)
    report = "\n".join(out)
    CACHE.mkdir(exist_ok=True)
    (CACHE / "last-report.md").write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
