# Venue file format

Each file in `data/venues/` describes one conference series. The file name (without `.yaml`) is the venue id. Run `python scripts/build.py --check` after any edit. The validator reports unknown fields, bad dates and dates in the wrong order.

```yaml
name: KDD                      # short name shown on the site
full_name: ACM SIGKDD Conference on Knowledge Discovery and Data Mining
area: dm                       # ml | ai | cv | nlp | dm | db
rank: A*                       # CORE 2023: A* or A
url: https://kdd.org           # the series' main site
every_years: 1                 # 2 for biennial venues (ICCV, ECCV)
irregular: false               # true if not held on a fixed cycle (NAACL): no next-edition estimate
edition_url_pattern: https://kdd{year}.kdd.org/   # optional; the update check uses it to find next year's site
notes: optional text about the series
editions:
  - year: 2027
    url: https://kdd2027.kdd.org/
    cfp_url: https://kdd2027.kdd.org/research-track-call-for-papers/
    source: https://kdd2027.kdd.org/research-track-call-for-papers/   # required: where the dates come from
    last_verified: 2026-09-18                                           # required: when you checked
    location: {city: San Jose, country: USA}   # or a list of places, or leave it out
    format: in-person          # in-person | hybrid | virtual (optional)
    start: 2027-08-01          # conference days, workshops included
    end: 2027-08-05
    timezone: AoE              # default AoE; also UTC, UTC-7, or an IANA name like America/Los_Angeles
    notes: optional text
    rounds:
      - name: Cycle 1          # required only when there are several rounds
        abstract: 2026-07-19   # a bare date means 23:59 in the edition's time zone
        paper: 2026-07-26      # "2026-07-26 17:00" for another time, "2026-07-26 17:00 UTC" for another zone
        rebuttal: [2026-09-29, 2026-10-13]
        commitment: 2026-12-23 # ARR commitment deadline (ACL, EMNLP, NAACL)
        notification: 2026-11-14
        camera_ready: 2027-01-10
        estimated: false       # true for a round that is not announced yet
        note: optional text shown next to the deadline
```

## Rolling deadlines

Venues with a monthly deadline (VLDB) get a `rolling` block. They appear in their own strip at the top of the site and are left out of the "next deadline" sort.

```yaml
rolling:
  every: month
  day: 1
  time: "17:00"
  timezone: America/Los_Angeles
  notification_days: 45
  label: PVLDB Vol. 20, 1st of every month
  note: text shown on hover
```

## Estimates

The build fills gaps in two ways, and marks everything it fills as estimated on the site and in the calendars:

- If every submission deadline of the latest edition has passed, it adds the next edition (`every_years` later). Its rounds and conference dates are shifted by whole weeks, so deadlines keep their weekday, and the location is left empty.
- If an announced edition has no rounds yet, it copies the rounds of the previous edition, shifted in the same way.
