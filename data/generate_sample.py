#!/usr/bin/env python3
"""
Synthetic DMRC ATS transaction generator.

WHY THIS EXISTS
---------------
The dashboard in this repository was built against live DMRC Automatic
Ticketing System data under an NDA. That data cannot be redistributed and
is not present anywhere in this repository.

What can be shared is the *shape* of it. This script emits rows with the
same column names, types and statistical structure as the real extract,
so that the schema, the SQL and the Power BI model can be run end to end
by anyone who clones the repo.

Every value produced here is synthetic. No DMRC record, station name,
passenger or transaction is reproduced.

DISTRIBUTIONS REPRODUCED
------------------------
  * revenue share by line          (Yellow Line dominant at ~51%)
  * mean ticket value              (~Rs 39.53, drawn from real fare slabs)
  * passenger type mix             (legacy-dominant, QR second, NCMC small)
  * bimodal weekday commute peaks  (~09:00 and ~18:00)
  * weekend footfall depression    (~0.78x weekday)
  * long-tailed station footfall   (a few interchanges carry the network)

USAGE
-----
    python generate_sample.py                       # 50,000 rows -> sample_data.csv
    python generate_sample.py --rows 500000
    python generate_sample.py --rows 1000 --out tiny.csv --seed 7

Standard library only. No dependencies.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
from pathlib import Path

# ---------------------------------------------------------------------
# Observed structure of the real network. Percentages are revenue share.
# ---------------------------------------------------------------------
LINES = [
    # name,             colour code, revenue share %, station count, fare bias
    ("Yellow Line",     "YL",  51.16, 37,  1.00),
    ("Blue Line (N)",   "BLN", 14.83, 50,  1.05),
    ("Red Line",        "RL",  14.63, 29,  0.92),
    ("Blue Line (V)",   "BLV",  9.42, 16,  0.95),
    ("Green Line",      "GL",   7.47, 24,  0.88),
    ("Violet Line",     "VL",   2.49, 34,  1.02),
]

# DMRC fare slabs. Weights tuned so the mean lands on the observed
# average ticket value of Rs 39.53 rather than a flat midpoint.
FARE_SLABS   = [10, 20, 30, 40, 50, 60]
FARE_WEIGHTS = [0.056, 0.108, 0.188, 0.240, 0.232, 0.176]

# Passenger / product type mix. Legacy tokens and cards still dominate;
# QR is the growth segment; NCMC was newly rolled out in this period.
PASSENGER_TYPES   = ["Other", "QR Ticket", "NCMC"]
PASSENGER_WEIGHTS = [0.700, 0.280, 0.020]

TXN_TYPES  = ["Entry", "Exit"]
FARE_TYPES = ["Adult", "Adult", "Adult", "Adult", "Concession", "Student", "Senior Citizen"]

PERIOD_START = dt.date(2024, 4, 28)
PERIOD_END   = dt.date(2024, 8, 4)

# Relative footfall by hour of day. Two commute peaks, near-zero overnight.
HOURLY_WEIGHTS = {
    0: 0.2, 1: 0.05, 2: 0.0, 3: 0.0, 4: 0.1, 5: 0.8,
    6: 2.5, 7: 5.5, 8: 9.0, 9: 9.5, 10: 6.0, 11: 4.5,
    12: 4.2, 13: 4.0, 14: 4.0, 15: 4.5, 16: 5.5, 17: 8.0,
    18: 9.5, 19: 8.5, 20: 6.0, 21: 4.0, 22: 2.5, 23: 1.0,
}

WEEKEND_FACTOR = 0.78


def build_stations(rng: random.Random):
    """Assign station IDs to lines and give each a long-tailed footfall weight.

    Real metro footfall is heavily skewed: a handful of interchanges carry
    a disproportionate share. A Pareto draw reproduces that far better than
    a uniform one, and it matters -- a uniform network would make the
    'Revenue by Station' visual flat and uninformative.
    """
    stations = []
    station_id = 1
    for line_name, cc, _share, count, fare_bias in LINES:
        for i in range(count):
            weight = rng.paretovariate(1.6)
            is_interchange = i % 11 == 0
            if is_interchange:
                weight *= 3.0
            stations.append({
                "id": station_id,
                "line": line_name,
                "cc": cc,
                "fare_bias": fare_bias,
                "weight": weight,
            })
            station_id += 1
    return stations


def build_day_weights(rng: random.Random):
    """Per-day sampling weights: weekend dip plus mild random variation."""
    days, weights = [], []
    day = PERIOD_START
    while day <= PERIOD_END:
        w = WEEKEND_FACTOR if day.weekday() >= 5 else 1.0
        w *= rng.uniform(0.93, 1.07)          # ordinary day-to-day noise
        days.append(day)
        weights.append(w)
        day += dt.timedelta(days=1)
    return days, weights


def pick_fare(rng: random.Random, bias: float) -> int:
    """Draw a fare slab, nudged by the line's average trip length."""
    weights = [w * (bias ** (i - 2.5)) for i, w in enumerate(FARE_WEIGHTS)]
    return rng.choices(FARE_SLABS, weights=weights, k=1)[0]


def pick_timestamp(rng: random.Random, day: dt.date) -> dt.datetime:
    hour = rng.choices(list(HOURLY_WEIGHTS), weights=list(HOURLY_WEIGHTS.values()), k=1)[0]
    return dt.datetime(day.year, day.month, day.day,
                       hour, rng.randrange(60), rng.randrange(60))


def generate(rows: int, out_path: Path, seed: int) -> None:
    rng = random.Random(seed)

    stations = build_stations(rng)
    days, day_weights = build_day_weights(rng)

    # Station sampling is weighted both by its own footfall tail and by
    # its line's revenue share, so the line-level donut comes out right.
    line_share = {name: share for name, _cc, share, _n, _b in LINES}
    line_totals = {}
    for s in stations:
        line_totals[s["line"]] = line_totals.get(s["line"], 0.0) + s["weight"]
    station_weights = [
        s["weight"] / line_totals[s["line"]] * line_share[s["line"]] for s in stations
    ]

    by_line = {}
    for s in stations:
        by_line.setdefault(s["line"], []).append(s)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        # Header uses the ATS export's own abbreviated column names.
        writer.writerow([
            "Sta", "Dest", "Line", "LineCC", "PrType",
            "TxT", "FarT", "Value", "TrxDetail", "InsertionDateTime",
        ])

        chosen_days = rng.choices(days, weights=day_weights, k=rows)
        origins = rng.choices(stations, weights=station_weights, k=rows)
        ptypes = rng.choices(PASSENGER_TYPES, weights=PASSENGER_WEIGHTS, k=rows)

        for i in range(rows):
            origin = origins[i]
            # ~92% of journeys stay on one line; the rest are interchanges.
            if rng.random() < 0.92:
                pool = by_line[origin["line"]]
            else:
                pool = stations
            dest = rng.choice(pool)
            while dest["id"] == origin["id"] and len(pool) > 1:
                dest = rng.choice(pool)

            ts = pick_timestamp(rng, chosen_days[i])
            fare = pick_fare(rng, origin["fare_bias"])
            ptype = ptypes[i]

            writer.writerow([
                origin["id"],
                dest["id"],
                origin["line"],
                origin["cc"],
                ptype,
                rng.choice(TXN_TYPES),
                rng.choice(FARE_TYPES),
                f"{fare:.2f}",
                f"{ptype[:2].upper()}-{ts:%Y%m%d}-{rng.randrange(10**6):06d}",
                ts.strftime("%Y-%m-%d %H:%M:%S"),
            ])

    print(f"Wrote {rows:,} synthetic rows -> {out_path}")


def summarise(path: Path) -> None:
    """Print the distributions so they can be checked against the real ones."""
    import collections

    rev_by_line = collections.Counter()
    cnt_by_type = collections.Counter()
    total_rev = 0.0
    n = 0
    dates = set()

    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            v = float(row["Value"])
            rev_by_line[row["Line"]] += v
            cnt_by_type[row["PrType"]] += 1
            total_rev += v
            n += 1
            dates.add(row["InsertionDateTime"][:10])

    print(f"\n  rows                {n:,}")
    print(f"  total revenue       Rs {total_rev:,.2f}")
    print(f"  avg ticket value    Rs {total_rev / n:,.2f}   (target 39.53)")
    print(f"  days covered        {len(dates)}")
    print("\n  revenue share by line")
    for line, rev in rev_by_line.most_common():
        target = dict((nm, sh) for nm, _c, sh, _s, _b in LINES)[line]
        print(f"    {line:<16} {100 * rev / total_rev:6.2f}%   (target {target:5.2f}%)")
    print("\n  passenger type mix")
    for t, c in cnt_by_type.most_common():
        print(f"    {t:<16} {100 * c / n:6.2f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=50_000)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "sample_data.csv")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-summary", action="store_true")
    args = ap.parse_args()

    generate(args.rows, args.out, args.seed)
    if not args.no_summary:
        summarise(args.out)
