"""Build the static site into dist/.

    python scripts/build.py            validate the data and build dist/
    python scripts/build.py --check    validate only
    python scripts/build.py --serve    build, then serve dist/ on localhost:8000
    python scripts/build.py --serve --lan   same, reachable from a phone on the same Wi-Fi

Output: dist/index.html (data embedded), dist/data.json, dist/ics/<id>.ics
for each venue and dist/ics/all.ics, and dist/<id>/index.html, one plain page
per conference for search engines.
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
import urllib.parse
from html import escape as h

from venues import BADGE_RANKS, PHASE_LABELS, ROOT, load_all, resolve

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
                item["local"] = f"{e['at']:%Y-%m-%d %H:%M} {e['tz']}"  # with the year, for the Claude connector
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
            if "abstracts" in rolling:
                rolling["abstracts"] = [d and ms(d) for d in rolling["abstracts"]]
        out.append({**{k: v[k] for k in ("id", "name", "full_name", "area", "area_label", "rank", "url", "notes")},
                    "editions": editions, "events": events, "rolling": rolling})
    return {"generated": now.isoformat(timespec="minutes"), "repo": REPO_URL, "venues": out}


# ----------------------------------------------------------- static text

def _fmt_range(start: dt.date, end: dt.date) -> str:
    if start.month == end.month:
        return f"{start:%b} {start.day}–{end.day}, {end.year}"
    return f"{start:%b} {start.day} – {end:%b} {end.day}, {end.year}"


def static_html(venues: list[dict], now: dt.datetime) -> str:
    """A plain list of the same data, rendered into the page at build time.
    Search engines and readers without JavaScript see it; app.js replaces it."""
    rows = []
    for v in venues:
        subs = sorted((e for e in v["events"] if e["type"] in ("abstract", "paper") and e["at"] > now),
                      key=lambda e: e["at"])
        conf = next((e for e in sorted((e for e in v["events"] if e["type"] == "conference"),
                                       key=lambda e: e["start"]) if e["end"] >= now.date()), None)
        parts = []
        for e in subs[:2]:
            label = f"{e['round']} {PHASE_LABELS[e['type']].lower()}" if e["round"] else PHASE_LABELS[e["type"]].lower()
            est = " (estimated)" if e["estimated"] else ""
            parts.append(f"{label} {e['at']:%b} {e['at'].day}, {e['at'].year} {e['tz']}{est}")
        if v["rolling"]:
            parts.append(v["rolling"]["label"].lower())
        if conf:
            where = f", {conf['location']}" if conf["location"] else ""
            parts.append(f"conference {_fmt_range(conf['start'], conf['end'])}{where}")
        year = subs[0]["edition"] if subs else (conf["edition"] if conf else v["editions"][-1]["year"])
        rank = f"{v['rank']}, " if v["rank"] in BADGE_RANKS else ""
        rows.append((subs[0]["at"] if subs else now + dt.timedelta(days=4000),
                     f"<li><a href=\"{v['id']}/\">{v['name']} {year}</a> ({rank}{v['area_label']}): "
                     f"{'; '.join(parts) or 'dates not announced'}.</li>"))
    items = "\n".join(html for _, html in sorted(rows, key=lambda r: r[0]))
    return ('<noscript><p>This page uses JavaScript for the timeline and the countdowns. '
            'The dates below are the same data.</p></noscript>\n'
            f'<ul class="static-list">\n{items}\n</ul>')


# ------------------------------------------------------ conference pages
# One page per conference, at <id>/, with every date as plain text. People search for
# "CVPR 2027 deadline", and these pages give search engines (and Claude's web search) a
# page that answers exactly that.

PAGE_PHASES = {"abstract": "Abstract deadline", "paper": "Paper deadline", "rebuttal": "Rebuttal",
               "commitment": "ARR commitment deadline", "notification": "Notification",
               "camera_ready": "Camera-ready deadline"}
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@600;700;800'
         '&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">')
GOATCOUNTER = '<script data-goatcounter="https://ml-deadlines.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>'
# "in 12 days" is filled in by the reader's browser, so the page never shows a stale count
DAYS_LEFT = ('<script>for(const el of document.querySelectorAll("[data-t]")){const d=(+el.dataset.t-Date.now())/864e5;'
             'el.textContent=d<0?"passed":d<1?"less than a day":"in "+Math.ceil(d)+" days";}</script>')


def _rank_text(v: dict) -> str:
    return f"ICORE 2026 rank {v['rank']}" if v["rank"] != "unranked" else "not ranked by ICORE 2026"


def _deadline_text(e: dict) -> str:
    at = e["at"]
    return f"{at:%a}, {at:%b} {at.day}, {at.year}, {at:%H:%M} {e['tz']}"


def _page_editions(v: dict, now: dt.datetime) -> list[dict]:
    """The editions a page shows: those not over yet (the next one is often an estimate)."""
    today = now.date()
    def upcoming(ed):
        if ed["end"]:
            return ed["end"] >= today
        return any(e["edition"] == ed["year"] and "at" in e and e["at"] > now for e in v["events"])
    return sorted((ed for ed in v["editions"] if upcoming(ed)), key=lambda ed: ed["year"]) or [v["editions"][-1]]


def _edition_section(v: dict, ed: dict, now: dt.datetime) -> str:
    name = f"{v['name']} {ed['year']}"
    when = _fmt_range(ed["start"], ed["end"]) if ed["start"] else "Dates not announced"
    meta = f"{when} · {ed['location'] or 'location not announced'}" + (f" · {ed['format']}" if ed.get("format") else "")
    events = sorted((e for e in v["events"] if e["edition"] == ed["year"] and e["type"] != "conference"),
                    key=lambda e: e["at"] if "at" in e else dt.datetime.combine(e["start"], dt.time(), dt.timezone.utc))
    rows = []
    for e in events:
        label = PAGE_PHASES[e["type"]] + (f" ({e['round']})" if e["round"] else "")
        est = ' <span class="est">estimated</span>' if e["estimated"] and not ed["estimated"] else ""
        note = f'<span class="note">{h(e["note"])}</span>' if e.get("note") and e["type"] in ("paper", "abstract") else ""
        if "at" in e:
            past = e["at"] < now
            left = f'<td class="left" data-t="{int(e["at"].timestamp() * 1000)}">{"passed" if past else ""}</td>'
            date = h(_deadline_text(e))
        else:
            past = e["end"] < now.date()
            start_ms = int(dt.datetime.combine(e["start"], dt.time(), dt.timezone.utc).timestamp() * 1000)
            left = ('<td class="left">passed</td>' if past else '<td class="left">under way</td>' if e["start"] <= now.date()
                    else f'<td class="left" data-t="{start_ms}"></td>')
            date = h(_fmt_range(e["start"], e["end"]))
        rows.append(f'<tr{" class=past" if past else ""}><th>{h(label)}{est}{note}</th><td>{date}</td>{left}</tr>')
    if not rows:
        rows.append('<tr><th>Deadlines</th><td>Not announced yet</td><td class="left"></td></tr>')
    if ed["estimated"]:
        src = (f"Not announced yet. These dates are estimated from {h(v['name'])} {ed.get('based_on') or ed['year'] - 1}, "
               "shifted forward by a year, and will be replaced by the official ones.")
    else:
        checked = f", checked on {ed['last_verified']:%b} {ed['last_verified'].day}, {ed['last_verified'].year}" if ed["last_verified"] else ""
        src = f'Dates from the <a href="{h(ed["source"] or ed["url"] or v["url"])}">official {h(v["name"])} page</a>{checked}.'
        if ed.get("notes"):
            src += f" {h(ed['notes'])}"
    tag = ' <span class="est-tag">estimated</span>' if ed["estimated"] else ""
    return (f'<section class="ved" id="{ed["year"]}">\n<h2>{h(name)}{tag}</h2>\n<p class="meta">{h(meta)}</p>\n'
            f'<table class="dates"><tbody>\n' + "\n".join(rows) + f'\n</tbody></table>\n<p class="src">{src}</p>\n</section>')


def _rolling_section(v: dict, now: dt.datetime) -> str:
    """Monthly venues (VLDB) have a deadline rule instead of rounds."""
    r = v["rolling"]
    dates = [d for d in r["dates"] if d > now][:6]
    rows = "\n".join(f'<tr><th>Submission deadline</th><td>{h(f"{d:%a}, {d:%b} {d.day}, {d.year}, {d:%H:%M} {d.tzname()}")}</td>'
                     f'<td class="left" data-t="{int(d.timestamp() * 1000)}"></td></tr>' for d in dates)
    note = f'<p class="src">{h(r["note"])}</p>' if r.get("note") else ""
    return (f'<section class="ved">\n<h2>Rolling submissions</h2>\n<p class="meta">{h(r["label"])}</p>\n'
            f'<table class="dates"><tbody>\n{rows}\n</tbody></table>\n{note}\n</section>')


def venue_page(v: dict, venues: list[dict], now: dt.datetime, css_tag: str) -> str:
    eds = _page_editions(v, now)
    years = " and ".join(str(ed["year"]) for ed in eds[:2])
    url = f"{SITE_URL}{v['id']}/"
    title = f"{v['name']} {years} deadlines and dates | ML Deadlines"

    # the description names the dates people search for: the next paper deadline, the next decision,
    # the next conference, whichever editions they belong to
    shown = {ed["year"] for ed in eds}
    def upcoming(kind):
        return min((e for e in v["events"] if e["edition"] in shown and e["type"] == kind and "at" in e and e["at"] > now),
                   key=lambda e: e["at"], default=None)
    bits = []
    for kind, label in (("paper", "paper deadline"), ("notification", "notification")):
        e = upcoming(kind)
        if e:
            bits.append(f"{v['name']} {e['edition']} {label} {e['at']:%b} {e['at'].day}, {e['at'].year} {e['tz']}"
                        + (" (estimated)" if e["estimated"] else ""))
    main = next((ed for ed in eds if ed["start"]), eds[0])
    if v["rolling"] and "rounds" not in v["rolling"]:
        nxt = next((d for d in v["rolling"]["dates"] if d > now), None)
        if nxt:
            bits.insert(0, f"{v['name']} monthly submission deadline, next {nxt:%b} {nxt.day}, {nxt.year}")
    if main["start"]:
        bits.append(f"{v['name']} {main['year']} conference {_fmt_range(main['start'], main['end'])}"
                    + (f", {main['location']}" if main["location"] else "") + (" (estimated)" if main["estimated"] else ""))
    desc = ("; ".join(bits) + ". " if bits else f"{v['name']} {years}: dates not announced yet. ") + \
        f"Deadlines and review dates of the {v['full_name']} from its official pages, with estimates marked."

    sections = [_edition_section(v, ed, now) for ed in eds]
    if v["rolling"] and "rounds" not in v["rolling"]:
        sections.insert(0, _rolling_section(v, now))

    ics = f"{SITE_URL}ics/{v['id']}.ics"
    webcal = "webcal:" + ics.split(":", 1)[1]
    cal = (f'<section class="vsec">\n<h2>Add {h(v["name"])} to your calendar</h2>\n'
           f'<p><a href="https://calendar.google.com/calendar/r?cid={urllib.parse.quote(webcal, safe="")}">Google Calendar</a> · '
           f'<a href="{h(webcal)}">Apple Calendar or Outlook</a> · <a href="{h(ics)}" download>Download the .ics file</a></p>\n'
           '<p class="small">A subscription updates itself when dates change or are announced.</p>\n</section>')
    others = [o for o in venues if o["area"] == v["area"] and o["id"] != v["id"]]
    related = (f'<section class="vsec">\n<h2>Other {h(v["area_label"])} conferences</h2>\n<p>'
               + " · ".join(f'<a href="../{o["id"]}/">{h(o["name"])}</a>' for o in others)
               + '</p>\n<p>All 37 conferences on one timeline: <a href="../">ML Deadlines</a></p>\n</section>') if others else ""

    # schema.org events for announced editions with a known place, which search engines can read
    ld = []
    for ed in eds:
        if ed["estimated"] or not ed["start"] or not ed["location"]:
            continue
        item = {"@context": "https://schema.org", "@type": "Event", "name": f"{v['name']} {ed['year']}",
                "description": f"{v['full_name']} {ed['year']}", "startDate": ed["start"].isoformat(),
                "endDate": ed["end"].isoformat(), "eventStatus": "https://schema.org/EventScheduled",
                "location": {"@type": "Place", "name": ed["city"] or ed["location"], "address": ed["location"]}}
        if ed.get("url"):
            item["url"] = ed["url"]
        mode = {"in-person": "Offline", "hybrid": "Mixed", "virtual": "Online"}.get(ed.get("format") or "")
        if mode:
            item["eventAttendanceMode"] = f"https://schema.org/{mode}EventAttendanceMode"
        ld.append(item)
    ld_html = (f'<script type="application/ld+json">{json.dumps(ld if len(ld) > 1 else ld[0]).replace("</", "<\\/")}</script>\n'
               if ld else "")

    series = f" {h(v['notes'])}" if v.get("notes") else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
<link rel="canonical" href="{url}">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ML Deadlines">
<meta property="og:title" content="{h(v['name'])} {years} deadlines and dates">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE_URL}og.png">
<meta name="twitter:card" content="summary_large_image">
{FONTS}
<link rel="stylesheet" href="../style.css?v={css_tag}">
{ld_html}</head>
<body>
<div class="wrap vpage">
<nav class="crumbs"><a href="../">ML Deadlines</a> <span aria-hidden="true">›</span> {h(v['name'])}</nav>
<header class="vhead">
<h1>{h(v['name'])} {years} deadlines and dates</h1>
<p class="tagline">{h(v['full_name'])}. {h(v['area_label'])}, {h(_rank_text(v))}.{series}</p>
</header>
{chr(10).join(sections)}
{cal}
{related}
<footer><span>Every date comes from the conference's official page. Data updated {now:%b} {now.day}, {now.year}.</span>
<a href="{REPO_URL}/issues/new?template=update-dates.yml">Report a wrong date</a>
<a href="{REPO_URL}">Source on GitHub</a></footer>
</div>
{DAYS_LEFT}
{GOATCOUNTER}
</body>
</html>
"""


def conference_nav(venues: list[dict]) -> str:
    """Links to every conference page, at the bottom of the home page."""
    links = " ".join(f'<a href="{v["id"]}/">{h(v["name"])}</a>' for v in sorted(venues, key=lambda v: v["name"].lower()))
    return f'<nav class="confnav" aria-label="Conference pages"><span>Conference pages:</span> {links}</nav>'


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
    page = page.replace('<main id="view"></main>', f'<main id="view">\n{static_html(venues, now)}\n</main>')
    page = page.replace('<nav id="confnav"></nav>', conference_nav(venues))
    # version tags make browsers fetch changed assets instead of a cached copy
    tags = {asset: hashlib.sha1((SITE_DIR / asset).read_bytes()).hexdigest()[:8] for asset in ("style.css", "app.js")}
    for asset, tag in tags.items():
        page = page.replace(f'"{asset}"', f'"{asset}?v={tag}"')
    (DIST / "index.html").write_text(page)
    for v in venues:
        (DIST / v["id"]).mkdir()
        (DIST / v["id"] / "index.html").write_text(venue_page(v, venues, now, tags["style.css"]))
    for asset in ("style.css", "app.js", "favicon.svg", "og.png"):
        shutil.copy(SITE_DIR / asset, DIST / asset)
    (DIST / ".nojekyll").write_text("")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc><lastmod>{now:%Y-%m-%d}</lastmod></url>\n"
        + "".join(f"  <url><loc>{SITE_URL}{v['id']}/</loc><lastmod>{now:%Y-%m-%d}</lastmod></url>\n" for v in venues)
        + "</urlset>\n")

    n_est = sum(1 for v in venues for e in v["editions"] if e["estimated"])
    print(f"Built {len(venues)} venues ({n_est} estimated editions) and their pages into {DIST.relative_to(ROOT)}/")
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
