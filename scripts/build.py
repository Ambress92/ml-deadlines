"""Build the static site into dist/.

    python scripts/build.py            validate the data and build dist/
    python scripts/build.py --check    validate only
    python scripts/build.py --serve    build, then serve dist/ on localhost:8000
    python scripts/build.py --serve --lan   same, reachable from a phone on the same Wi-Fi

Output: dist/index.html (data embedded), dist/data.json, dist/ics/<id>.ics
for each venue and dist/ics/all.ics.
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import http.server
import json
import shutil
import sys

from venues import PHASE_LABELS, ROOT, load_all, resolve

SITE_DIR = ROOT / "site"
DIST = ROOT / "dist"
REPO_URL = "https://github.com/Ambress92/ml-deadlines"
SITE_URL = "https://ambress92.github.io/ml-deadlines/"
KEEP_PAST_DAYS = 120  # editions whose conference ended longer ago are dropped from the site


def ms(when: dt.datetime) -> int:
    return int(when.timestamp() * 1000)


# ------------------------------------------------------------------- json

def to_json(venues: list[dict], now: dt.datetime) -> dict:
    cutoff = now.date() - dt.timedelta(days=KEEP_PAST_DAYS)
    out = []
    for v in venues:
        keep = {e["year"] for e in v["editions"] if not e["end"] or e["end"] >= cutoff}
        if not keep:
            keep = {v["editions"][-1]["year"]}
        events = []
        for e in v["events"]:
            if e["edition"] not in keep:
                continue
            item = {k: e[k] for k in ("type", "edition", "round", "estimated")}
            if e["note"] and e["type"] in ("abstract", "paper"):
                item["note"] = e["note"]
            if "at" in e:
                item["t"] = ms(e["at"])
                item["when"] = f"{e['at']:%b} {e['at'].day}, {e['at']:%H:%M} {e['tz']}"
            else:
                item["start"], item["end"] = e["start"].isoformat(), e["end"].isoformat()
                if e["type"] == "conference":
                    item["location"], item["city"] = e["location"], e["city"]
            events.append(item)
        editions = [
            {**{k: e[k] for k in ("year", "url", "cfp_url", "location", "city", "format", "estimated", "based_on", "source", "notes")},
             "start": e["start"] and e["start"].isoformat(),
             "end": e["end"] and e["end"].isoformat(),
             "last_verified": e["last_verified"] and e["last_verified"].isoformat()}
            for e in v["editions"] if e["year"] in keep
        ]
        rolling = None
        if v["rolling"]:
            rolling = {**v["rolling"], "dates": [ms(d) for d in v["rolling"]["dates"]]}
        out.append({**{k: v[k] for k in ("id", "name", "full_name", "area", "area_label", "rank", "url", "notes")},
                    "editions": editions, "events": events, "rolling": rolling})
    return {"generated": now.isoformat(timespec="minutes"), "repo": REPO_URL, "venues": out}


# -------------------------------------------------------------------- ics

def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets continue with a leading space."""
    raw = line.encode()
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (75 if not parts else 74):
            parts.append(cur.decode())
            cur = b""
        cur += b
    parts.append(cur.decode())
    return "\r\n ".join(parts)


def _utc(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics_events(v: dict, stamp: str) -> list[list[str]]:
    eds = {e["year"]: e for e in v["editions"]}
    out = []
    for e in v["events"]:
        ed = eds[e["edition"]]
        est = " (estimated)" if e["estimated"] else ""
        rnd = f" {e['round']}" if e["round"] else ""
        name = f"{v['name']} {e['edition']}"
        uid = f"{v['id']}-{e['edition']}-{(e['round'] or 'main').lower().replace(' ', '-')}-{e['type']}@ml-deadlines"
        desc = [v["full_name"]]
        if e["estimated"]:
            base = ed.get("based_on") or e["edition"] - 1
            desc.append(f"Estimated from the {base} dates. Not announced yet.")
        if ed.get("url"):
            desc.append(ed["url"])
        lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}"]
        if "at" in e:
            lines += [f"DTSTART:{_utc(e['at'] - dt.timedelta(minutes=30))}", f"DTEND:{_utc(e['at'])}",
                      f"SUMMARY:{_esc(f'{name}{rnd} {PHASE_LABELS[e['type']].lower()} deadline{est}')}"]
            desc.insert(1, f"Deadline: {e['at']:%Y-%m-%d %H:%M} {e['tz']}")
        else:
            end = e["end"] + dt.timedelta(days=1)  # DTEND is exclusive for all-day events
            lines += [f"DTSTART;VALUE=DATE:{e['start']:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}",
                      "TRANSP:TRANSPARENT"]
            if e["type"] == "conference":
                lines.append(f"SUMMARY:{_esc(f'{name}{est}')}")
                if e.get("location"):
                    lines.append(f"LOCATION:{_esc(e['location'])}")
            else:
                lines.append(f"SUMMARY:{_esc(f'{name}{rnd} rebuttal period{est}')}")
        if ed.get("url"):
            lines.append(f"URL:{ed['url']}")
        lines += [f"DESCRIPTION:{_esc(chr(10).join(desc))}", "END:VEVENT"]
        out.append(lines)
    return out


def ics_calendar(name: str, events: list[list[str]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ml-deadlines//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(name)}", "X-PUBLISHED-TTL:PT12H",
             "REFRESH-INTERVAL;VALUE=DURATION:PT12H"]
    for ev in events:
        lines += ev
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


# ------------------------------------------------------------------ build

def build(now: dt.datetime) -> int:
    raw, errors = load_all()
    if errors:
        print("Data errors:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    venues = [resolve(v, now) for v in raw]
    data = to_json(venues, now)

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "ics").mkdir(parents=True)
    (DIST / "data.json").write_text(json.dumps(data, separators=(",", ":")))

    stamp = _utc(now)
    everything = []
    for v in venues:
        evs = ics_events(v, stamp)
        everything += evs
        (DIST / "ics" / f"{v['id']}.ics").write_text(ics_calendar(f"{v['name']} deadlines", evs), newline="")
    (DIST / "ics" / "all.ics").write_text(ics_calendar("ML conference deadlines", everything), newline="")

    page = (SITE_DIR / "index.html").read_text()
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = page.replace("/*__DATA__*/null", blob)
    # version tags make browsers fetch changed assets instead of a cached copy
    for asset in ("style.css", "app.js"):
        tag = hashlib.sha1((SITE_DIR / asset).read_bytes()).hexdigest()[:8]
        page = page.replace(f'"{asset}"', f'"{asset}?v={tag}"')
    (DIST / "index.html").write_text(page)
    for asset in ("style.css", "app.js", "favicon.svg", "og.png"):
        shutil.copy(SITE_DIR / asset, DIST / asset)
    (DIST / ".nojekyll").write_text("")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc><lastmod>{now:%Y-%m-%d}</lastmod></url>\n"
        "</urlset>\n")

    n_est = sum(1 for v in venues for e in v["editions"] if e["estimated"])
    print(f"Built {len(venues)} venues ({n_est} estimated editions) into {DIST.relative_to(ROOT)}/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate the data only")
    ap.add_argument("--serve", action="store_true", help="serve dist/ on localhost after building")
    ap.add_argument("--lan", action="store_true", help="with --serve: listen on the local network, not only localhost")
    ap.add_argument("--today", help="pretend it is this date (YYYY-MM-DD), for testing")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    if args.today:
        now = dt.datetime.combine(dt.date.fromisoformat(args.today), dt.time(12), dt.timezone.utc)
    if args.check:
        _, errors = load_all()
        if errors:
            print("Data errors:\n  " + "\n  ".join(errors), file=sys.stderr)
            return 1
        print("Data is valid.")
        return 0
    code = build(now)
    if code == 0 and args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        host = "0.0.0.0" if args.lan else "127.0.0.1"
        print(f"Serving on http://{'<this computer IP>' if args.lan else 'localhost'}:8000 (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer((host, 8000), handler).serve_forever()
    return code


if __name__ == "__main__":
    sys.exit(main())
