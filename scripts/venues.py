"""Load, validate and resolve the venue files in data/venues/.

Each venue file describes one conference series and its editions. See
data/SCHEMA.md for the format. `load_all` returns validated venues;
`resolve` turns one venue into concrete timestamped events, adding an
estimated next edition when the latest one's deadlines have passed.
"""
from __future__ import annotations

import copy
import datetime as dt
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
VENUES_DIR = ROOT / "data" / "venues"

AREAS = {
    "ml": "Core ML",
    "ai": "General AI",
    "cv": "Vision",
    "nlp": "NLP",
    "dm": "Data mining & IR",
    "db": "Databases",
}
RANKS = ("A*", "A")
FORMATS = ("in-person", "hybrid", "virtual")
POINT_PHASES = ("abstract", "paper", "commitment", "notification", "camera_ready")
SUBMISSION_PHASES = ("abstract", "paper")
PHASE_LABELS = {
    "abstract": "Abstract",
    "paper": "Paper",
    "rebuttal": "Rebuttal",
    "commitment": "Commitment",
    "notification": "Notification",
    "camera_ready": "Camera-ready",
    "conference": "Conference",
}

VENUE_KEYS = {"name", "full_name", "area", "rank", "url", "every_years", "irregular",
              "edition_url_pattern", "rolling", "editions", "notes"}
EDITION_KEYS = {"year", "url", "cfp_url", "location", "format", "start", "end",
                "timezone", "estimated", "last_verified", "source", "rounds", "notes"}
ROUND_KEYS = {"name", "abstract", "paper", "rebuttal", "commitment", "notification",
              "camera_ready", "estimated", "note"}
ROLLING_KEYS = {"every", "day", "time", "timezone", "notification_days", "label", "note"}

AOE = dt.timezone(dt.timedelta(hours=-12), "AoE")


class ValidationError(Exception):
    pass


# ---------------------------------------------------------------- parsing

def parse_tz(name: str) -> dt.tzinfo:
    """Accepts "AoE", "UTC", "UTC+2", "UTC-07:00" or an IANA name."""
    if name == "AoE":
        return AOE
    m = re.fullmatch(r"UTC(?:([+-])(\d{1,2})(?::?(\d{2}))?)?", name)
    if m:
        if not m.group(1):
            return dt.timezone.utc
        off = dt.timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
        return dt.timezone(off if m.group(1) == "+" else -off, name)
    try:
        return ZoneInfo(name)
    except Exception:
        raise ValidationError(f"unknown timezone {name!r}") from None


def parse_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            pass
    raise ValidationError(f"expected a date like 2026-09-24, got {value!r}")


def parse_deadline(value, tz: dt.tzinfo) -> dt.datetime:
    """A bare date means 23:59 in the edition's time zone."""
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=tz)
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time(23, 59), tz)
    if isinstance(value, str):
        parts = value.split()
        if len(parts) == 3:
            tz = parse_tz(parts[2])
        if len(parts) in (2, 3):
            try:
                return dt.datetime.strptime(" ".join(parts[:2]), "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except ValueError:
                pass
    raise ValidationError(f"expected a date, 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM TZ', got {value!r}")


def tz_label(when: dt.datetime, tz_name: str) -> str:
    if tz_name == "AoE" or tz_name.startswith("UTC"):
        return tz_name
    return when.strftime("%Z")


# ------------------------------------------------------------- validation

def _check_keys(obj, allowed, where, errors):
    if not isinstance(obj, dict):
        errors.append(f"{where}: expected a mapping")
        return False
    for key in obj:
        if key not in allowed:
            errors.append(f"{where}: unknown field {key!r}")
    return True


def _check_url(value, where, errors):
    if value is not None and not (isinstance(value, str) and value.startswith(("http://", "https://"))):
        errors.append(f"{where}: expected an http(s) URL, got {value!r}")


def validate(venue_id: str, v: dict) -> list[str]:
    errors: list[str] = []
    if not re.fullmatch(r"[a-z0-9-]+", venue_id):
        errors.append(f"file name must be lowercase letters, digits and dashes: {venue_id!r}")
    if not _check_keys(v, VENUE_KEYS, venue_id, errors):
        return errors
    for key in ("name", "full_name", "area", "rank", "url", "editions"):
        if key not in v:
            errors.append(f"{venue_id}: missing required field {key!r}")
    if v.get("area") not in AREAS:
        errors.append(f"{venue_id}.area: must be one of {', '.join(AREAS)}")
    if v.get("rank") not in RANKS:
        errors.append(f"{venue_id}.rank: must be one of {', '.join(RANKS)} (CORE 2023)")
    _check_url(v.get("url"), f"{venue_id}.url", errors)
    if v.get("every_years", 1) not in (1, 2):
        errors.append(f"{venue_id}.every_years: must be 1 or 2")
    pattern = v.get("edition_url_pattern")
    if pattern is not None and "{year}" not in str(pattern):
        errors.append(f"{venue_id}.edition_url_pattern: must contain {{year}}")

    rolling = v.get("rolling")
    if rolling is not None and _check_keys(rolling, ROLLING_KEYS, f"{venue_id}.rolling", errors):
        if rolling.get("every") != "month":
            errors.append(f"{venue_id}.rolling.every: only 'month' is supported")
        if not isinstance(rolling.get("day"), int) or not 1 <= rolling["day"] <= 28:
            errors.append(f"{venue_id}.rolling.day: must be a day of the month from 1 to 28")
        if not re.fullmatch(r"\d{2}:\d{2}", str(rolling.get("time", "23:59"))):
            errors.append(f"{venue_id}.rolling.time: expected HH:MM")
        try:
            parse_tz(rolling.get("timezone", "AoE"))
        except ValidationError as e:
            errors.append(f"{venue_id}.rolling.timezone: {e}")

    editions = v.get("editions") or []
    if not isinstance(editions, list) or not editions:
        errors.append(f"{venue_id}.editions: must be a non-empty list")
        return errors
    years = [e.get("year") for e in editions if isinstance(e, dict)]
    if len(years) != len(set(years)):
        errors.append(f"{venue_id}.editions: duplicate years")
    for i, ed in enumerate(editions):
        errors += _validate_edition(ed, f"{venue_id}.editions[{i}]")
    return errors


def _validate_edition(ed, where) -> list[str]:
    errors: list[str] = []
    if not _check_keys(ed, EDITION_KEYS, where, errors):
        return errors
    if not isinstance(ed.get("year"), int):
        errors.append(f"{where}.year: required, an integer")
    where = f"{where} ({ed.get('year')})"
    _check_url(ed.get("url"), f"{where}.url", errors)
    _check_url(ed.get("cfp_url"), f"{where}.cfp_url", errors)
    _check_url(ed.get("source"), f"{where}.source", errors)
    if ed.get("format") is not None and ed["format"] not in FORMATS:
        errors.append(f"{where}.format: must be one of {', '.join(FORMATS)}")
    loc = ed.get("location")
    if loc is not None:
        places = loc if isinstance(loc, list) else [loc]
        for place in places:
            if not isinstance(place, dict) or set(place) - {"city", "country"} or not place.get("country"):
                errors.append(f"{where}.location: expected {{city, country}}, a list of them, or nothing")
    try:
        tz = parse_tz(ed.get("timezone", "AoE"))
    except ValidationError as e:
        errors.append(f"{where}.timezone: {e}")
        return errors
    estimated = ed.get("estimated", False)
    if not isinstance(estimated, bool):
        errors.append(f"{where}.estimated: must be true or false")
    if not estimated:
        if "last_verified" not in ed:
            errors.append(f"{where}.last_verified: required unless the edition is estimated")
        if "source" not in ed:
            errors.append(f"{where}.source: required unless the edition is estimated (the page the dates come from)")
    for key in ("last_verified",):
        if key in ed:
            try:
                parse_date(ed[key])
            except ValidationError as e:
                errors.append(f"{where}.{key}: {e}")

    start = end = None
    try:
        if ed.get("start") is not None:
            start = parse_date(ed["start"])
        if ed.get("end") is not None:
            end = parse_date(ed["end"])
    except ValidationError as e:
        errors.append(f"{where}: {e}")
    if (start is None) != (end is None):
        errors.append(f"{where}: give both start and end, or neither")
    elif start and end and not (0 <= (end - start).days <= 20):
        errors.append(f"{where}: end must be 0 to 20 days after start")

    rounds = ed.get("rounds") or []
    if not isinstance(rounds, list):
        errors.append(f"{where}.rounds: must be a list")
        return errors
    for j, rnd in enumerate(rounds):
        rw = f"{where}.rounds[{j}]"
        if not _check_keys(rnd, ROUND_KEYS, rw, errors):
            continue
        if len(rounds) > 1 and not rnd.get("name"):
            errors.append(f"{rw}.name: required when an edition has several rounds")
        seq = []
        try:
            for key in ("abstract", "paper"):
                if rnd.get(key) is not None:
                    seq.append((key, parse_deadline(rnd[key], tz)))
            if rnd.get("rebuttal") is not None:
                r = rnd["rebuttal"]
                if not (isinstance(r, list) and len(r) == 2):
                    raise ValidationError("rebuttal: expected [start date, end date]")
                r0, r1 = parse_date(r[0]), parse_date(r[1])
                seq.append(("rebuttal start", dt.datetime.combine(r0, dt.time(0, 0), tz)))
                seq.append(("rebuttal end", dt.datetime.combine(r1, dt.time(23, 59), tz)))
            for key in ("commitment", "notification", "camera_ready"):
                if rnd.get(key) is not None:
                    seq.append((key, parse_deadline(rnd[key], tz)))
        except ValidationError as e:
            errors.append(f"{rw}: {e}")
            continue
        if not seq:
            errors.append(f"{rw}: has no dates")
        for (k1, t1), (k2, t2) in zip(seq, seq[1:]):
            if t2 < t1:
                errors.append(f"{rw}: {k2} ({t2:%Y-%m-%d}) is before {k1} ({t1:%Y-%m-%d})")
        if start and seq and seq[-1][0] != "camera_ready" and seq[-1][1].date() > start:
            errors.append(f"{rw}: {seq[-1][0]} is after the conference starts")
    return errors


def load_all() -> tuple[list[dict], list[str]]:
    venues, errors = [], []
    for path in sorted(VENUES_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            errors.append(f"{path.name}: invalid YAML: {e}")
            continue
        venue_errors = validate(path.stem, raw)
        errors += [f"{path.name}: {e}" for e in venue_errors]
        if not venue_errors:
            raw["id"] = path.stem
            venues.append(raw)
    return venues, errors


# ------------------------------------------------------------- estimation

def _shift(value, delta: dt.timedelta, tz):
    if isinstance(value, list):
        return [_shift(x, delta, tz) for x in value]
    if isinstance(value, str) and " " in value:
        parts = value.split()
        shifted = (parse_deadline(value, tz) + delta).strftime("%Y-%m-%d %H:%M")
        return f"{shifted} {parts[2]}" if len(parts) == 3 else shifted
    if isinstance(value, dt.datetime):
        return value + delta
    return parse_date(value) + delta


def _submission_times(ed: dict) -> list[dt.datetime]:
    tz = parse_tz(ed.get("timezone", "AoE"))
    return [parse_deadline(r[k], tz) for r in ed.get("rounds") or []
            for k in SUBMISSION_PHASES if r.get(k) is not None]


def _shifted_rounds(src: dict, years: int) -> list[dict]:
    """The rounds of `src` moved forward by `years` (in whole weeks, so
    deadlines keep their weekday), each marked as estimated."""
    delta = dt.timedelta(weeks=52 * years)
    tz = parse_tz(src.get("timezone", "AoE"))
    rounds = copy.deepcopy(src.get("rounds") or [])
    for rnd in rounds:
        rnd.pop("note", None)
        rnd["estimated"] = True
        for key in ("abstract", "paper", "rebuttal", "commitment", "notification", "camera_ready"):
            if rnd.get(key) is not None:
                rnd[key] = _shift(rnd[key], delta, tz)
    return rounds


def with_estimate(v: dict, now: dt.datetime) -> list[dict]:
    """Editions of `v` with estimates filled in. An announced edition that
    has no rounds yet gets the previous edition's rounds, shifted. If every
    submission deadline of the latest edition has passed, an estimated next
    edition is added."""
    editions = [copy.deepcopy(e) for e in sorted(v["editions"], key=lambda e: e["year"])]
    if v.get("rolling"):
        return editions
    for i, ed in enumerate(editions):
        if ed.get("rounds") or i == 0:
            continue
        prev = next((p for p in reversed(editions[:i]) if p.get("rounds")), None)
        if prev:
            ed["rounds"] = _shifted_rounds(prev, ed["year"] - prev["year"])
            ed["timezone"] = prev.get("timezone", "AoE")
            ed["based_on"] = prev["year"]
    last = editions[-1]
    subs = _submission_times(last)
    if v.get("irregular") or not subs or max(subs) > now:
        return editions
    years = v.get("every_years", 1)
    est = {"year": last["year"] + years, "estimated": True, "location": None,
           "timezone": last.get("timezone", "AoE"),
           "rounds": _shifted_rounds(last, years), "based_on": last["year"]}
    pattern = v.get("edition_url_pattern")
    est["url"] = pattern.format(year=est["year"]) if pattern else None
    if last.get("start"):
        delta = dt.timedelta(weeks=52 * years)
        est["start"] = parse_date(last["start"]) + delta
        est["end"] = parse_date(last["end"]) + delta
    return editions + [est]


# ---------------------------------------------------------------- resolve

def location_text(loc, short: bool = False) -> str | None:
    """"Kyoto, Japan / Hengqin, China"; with short=True only the cities."""
    if not loc:
        return None
    places = loc if isinstance(loc, list) else [loc]
    if short:
        return " / ".join(p.get("city") or p["country"] for p in places)
    return " / ".join(", ".join(x for x in (p.get("city"), p.get("country")) if x) for p in places)


def rolling_dates(v: dict, now: dt.datetime, count: int = 14) -> list[dt.datetime]:
    r = v["rolling"]
    tz = parse_tz(r.get("timezone", "AoE"))
    hh, mm = map(int, str(r.get("time", "23:59")).split(":"))
    local = now.astimezone(tz)
    out, y, m = [], local.year, local.month
    while len(out) < count:
        when = dt.datetime(y, m, r["day"], hh, mm, tzinfo=tz)
        if when > now:
            out.append(when)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def resolve(v: dict, now: dt.datetime) -> dict:
    """One venue as concrete events. Deadlines carry an aware datetime in
    `at`; ranges (rebuttal, conference) carry `start` and `end` dates."""
    editions, events = [], []
    for ed in with_estimate(v, now):
        tz_name = ed.get("timezone", "AoE")
        tz = parse_tz(tz_name)
        est_ed = ed.get("estimated", False)
        loc = location_text(ed.get("location"))
        city = location_text(ed.get("location"), short=True)
        editions.append({
            "year": ed["year"],
            "url": ed.get("url"),
            "cfp_url": ed.get("cfp_url"),
            "location": loc,
            "city": city,
            "format": ed.get("format"),
            "start": ed.get("start") and parse_date(ed["start"]),
            "end": ed.get("end") and parse_date(ed["end"]),
            "estimated": est_ed,
            "based_on": ed.get("based_on"),
            "last_verified": ed.get("last_verified") and parse_date(ed["last_verified"]),
            "source": ed.get("source"),
            "notes": ed.get("notes"),
        })
        for rnd in ed.get("rounds") or []:
            est = est_ed or rnd.get("estimated", False)
            base = {"edition": ed["year"], "round": rnd.get("name"), "estimated": est, "note": rnd.get("note")}
            for key in POINT_PHASES:
                if rnd.get(key) is not None:
                    at = parse_deadline(rnd[key], tz)
                    events.append({**base, "type": key, "at": at, "tz": tz_label(at, tz_name)})
            if rnd.get("rebuttal"):
                events.append({**base, "type": "rebuttal",
                               "start": parse_date(rnd["rebuttal"][0]),
                               "end": parse_date(rnd["rebuttal"][1])})
        if ed.get("start"):
            events.append({"edition": ed["year"], "round": None, "estimated": est_ed, "note": None,
                           "type": "conference", "location": loc, "city": city,
                           "start": parse_date(ed["start"]), "end": parse_date(ed["end"])})
    out = {k: v.get(k) for k in ("id", "name", "full_name", "area", "rank", "url")}
    out["area_label"] = AREAS[v["area"]]
    out["editions"] = editions
    out["events"] = events
    out["rolling"] = None
    out["notes"] = v.get("notes")
    if v.get("rolling"):
        r = v["rolling"]
        out["rolling"] = {
            "label": r.get("label", "Monthly"),
            "note": r.get("note"),
            "notification_days": r.get("notification_days"),
            "tz": r.get("timezone", "AoE"),
            "dates": rolling_dates(v, now),
        }
    return out
