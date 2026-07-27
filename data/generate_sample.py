#!/usr/bin/env python3
"""
Synthetic DMRC ATS transaction generator.

WHY THIS EXISTS
---------------
The dashboard in this repository was built at DMRC against live Automatic
Ticketing System data under an NDA. That data cannot be redistributed and
is not present anywhere in this repository.

What can be shared is the *shape* of it. This script emits a dataset with
the same structure and statistical properties as the real extract, so the
schema, the SQL and the Power BI report can be rebuilt and run end to end
by anyone who clones the repo.

Every transaction produced here is synthetic. No DMRC record, passenger or
operational figure is reproduced. Station and line names are public
information (they are printed on the network map) and are used purely as
readable labels.

OUTPUT (three files, a proper star schema)
------------------------------------------
    sample_data.csv    fact table  - one row per transaction
    dim_stations.csv   dimension   - station_id -> name, line
    dim_lines.csv      dimension   - line_id -> name, colour code

DISTRIBUTIONS REPRODUCED
------------------------
  * revenue share by line          (Yellow Line dominant at ~51%)
  * mean ticket value              (~Rs 39.53, drawn from real fare slabs)
  * passenger type mix             (legacy-dominant, QR second, NCMC small)
  * bimodal weekday commute peaks  (~09:00 and ~18:00)
  * weekend footfall depression    (~0.78x weekday)
  * long-tailed station footfall   (interchanges carry the network)

USAGE
-----
    python generate_sample.py                      # 200,000 rows
    python generate_sample.py --rows 500000
    python generate_sample.py --rows 1000 --seed 7

Standard library only. No dependencies.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
from pathlib import Path

# ---------------------------------------------------------------------
# Public DMRC station names, used as readable labels only.
# ---------------------------------------------------------------------
NETWORK = {
    "Yellow Line": ("YL", 51.16, 1.00, [
        "Samaypur Badli", "Rohini Sector 18-19", "Haiderpur Badli Mor", "Jahangirpuri",
        "Adarsh Nagar", "Azadpur", "Model Town", "Guru Tegh Bahadur Nagar",
        "Vishwavidyalaya", "Vidhan Sabha", "Civil Lines", "Kashmere Gate",
        "Chandni Chowk", "Chawri Bazar", "New Delhi", "Rajiv Chowk", "Patel Chowk",
        "Central Secretariat", "Udyog Bhawan", "Lok Kalyan Marg", "Jor Bagh", "INA",
        "AIIMS", "Green Park", "Hauz Khas", "Malviya Nagar", "Saket", "Qutab Minar",
        "Chhatarpur", "Sultanpur", "Ghitorni", "Arjan Garh", "Guru Dronacharya",
        "Sikanderpur", "MG Road", "IFFCO Chowk", "HUDA City Centre",
    ]),
    "Blue Line (N)": ("BLN", 14.83, 1.05, [
        "Dwarka Sector 21", "Dwarka Sector 8", "Dwarka Sector 9", "Dwarka Sector 10",
        "Dwarka Sector 11", "Dwarka Sector 12", "Dwarka Sector 13", "Dwarka Sector 14",
        "Dwarka", "Dwarka Mor", "Nawada", "Uttam Nagar West", "Uttam Nagar East",
        "Janakpuri West", "Janakpuri East", "Tilak Nagar", "Subhash Nagar",
        "Tagore Garden", "Rajouri Garden", "Ramesh Nagar", "Moti Nagar", "Kirti Nagar",
        "Shadipur", "Patel Nagar", "Rajendra Place", "Karol Bagh", "Jhandewalan",
        "RK Ashram Marg", "Barakhamba Road", "Mandi House", "Supreme Court",
        "Indraprastha", "Yamuna Bank", "Akshardham", "Mayur Vihar-I",
        "Mayur Vihar Extension", "New Ashok Nagar", "Noida Sector 15",
        "Noida Sector 16", "Noida Sector 18", "Botanical Garden", "Golf Course",
        "Noida City Centre", "Noida Sector 34", "Noida Sector 52", "Noida Sector 61",
        "Noida Sector 59", "Noida Sector 62", "Noida Electronic City",
    ]),
    "Red Line": ("RL", 14.63, 0.92, [
        "Rithala", "Rohini West", "Rohini East", "Pitampura", "Kohat Enclave",
        "Netaji Subhash Place", "Keshav Puram", "Kanhaiya Nagar", "Inderlok",
        "Shastri Nagar", "Pratap Nagar", "Pulbangash", "Tis Hazari", "Shastri Park",
        "Seelampur", "Welcome", "Shahdara", "Mansarovar Park", "Jhilmil",
        "Dilshad Garden", "Shaheed Nagar", "Raj Bagh", "Rajendra Nagar", "Shyam Park",
        "Mohan Nagar", "Arthala", "Hindon River", "Shaheed Sthal",
    ]),
    "Blue Line (V)": ("BLV", 9.42, 0.95, [
        "Laxmi Nagar", "Nirman Vihar", "Preet Vihar", "Karkarduma", "Anand Vihar",
        "Kaushambi", "Vaishali",
    ]),
    "Green Line": ("GL", 7.47, 0.88, [
        "Ashok Park Main", "Punjabi Bagh", "Shivaji Park", "Madipur",
        "Paschim Vihar East", "Paschim Vihar West", "Peera Garhi", "Udyog Nagar",
        "Maharaja Surajmal Stadium", "Nangloi", "Nangloi Railway Station",
        "Rajdhani Park", "Mundka", "Mundka Industrial Area", "Ghevra", "Tikri Kalan",
        "Tikri Border", "Pandit Shree Ram Sharma", "Bahadurgarh City",
        "Brigadier Hoshiar Singh", "Satguru Ram Singh Marg",
    ]),
    "Violet Line": ("VL", 2.49, 1.02, [
        "Lal Qila", "Jama Masjid", "Delhi Gate", "ITO", "Janpath", "Khan Market",
        "Jawaharlal Nehru Stadium", "Jangpura", "Lajpat Nagar", "Moolchand",
        "Kailash Colony", "Nehru Place", "Kalkaji Mandir", "Govind Puri",
        "Harkesh Nagar Okhla", "Jasola Apollo", "Sarita Vihar", "Mohan Estate",
        "Tughlakabad", "Badarpur Border", "Sarai", "NHPC Chowk", "Mewala Maharajpur",
        "Sector 28 Faridabad", "Badkal Mor", "Old Faridabad", "Neelam Chowk Ajronda",
        "Bata Chowk", "Escorts Mujesar", "Sant Surdas Sihi", "Raja Nahar Singh",
    ]),
}

# Stations that carry disproportionate traffic (major interchanges / hubs).
HUB_STATIONS = {
    "Rajiv Chowk", "Kashmere Gate", "New Delhi", "Central Secretariat",
    "Hauz Khas", "INA", "Mandi House", "Botanical Garden", "Yamuna Bank",
    "Netaji Subhash Place", "Lajpat Nagar", "Welcome", "Inderlok",
    "Janakpuri West", "Dwarka", "HUDA City Centre", "Anand Vihar",
}

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


def build_dimensions(rng: random.Random):
    """Build line and station dimensions with long-tailed footfall weights.

    Real metro footfall is heavily skewed: a handful of interchanges carry a
    disproportionate share. A Pareto draw reproduces that far better than a
    uniform one, and it matters -- a uniform network makes the 'Revenue by
    Station' visual flat and tells the viewer nothing.
    """
    lines, stations = [], []
    line_id = 1
    station_id = 1

    for line_name, (cc, share, fare_bias, names) in NETWORK.items():
        lines.append({
            "line_id": line_id,
            "line_name": line_name,
            "line_colour_cc": cc,
            "revenue_share_target_pct": share,
        })
        for name in names:
            weight = rng.paretovariate(1.6)
            is_hub = name in HUB_STATIONS
            if is_hub:
                weight *= 4.0
            stations.append({
                "station_id": station_id,
                "station_name": name,
                "line_id": line_id,
                "line_name": line_name,
                "is_interchange": "TRUE" if is_hub else "FALSE",
                "_weight": weight,
                "_fare_bias": fare_bias,
            })
            station_id += 1
        line_id += 1

    return lines, stations


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


def generate(rows: int, out_dir: Path, seed: int) -> Path:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines, stations = build_dimensions(rng)
    days, day_weights = build_day_weights(rng)

    # ---- dimension files ---------------------------------------------
    with (out_dir / "dim_lines.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "line_id", "line_name", "line_colour_cc", "revenue_share_target_pct"])
        w.writeheader()
        w.writerows(lines)

    with (out_dir / "dim_stations.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "station_id", "station_name", "line_id", "line_name", "is_interchange"])
        w.writeheader()
        w.writerows({k: v for k, v in s.items() if not k.startswith("_")} for s in stations)

    # ---- weighted sampling setup -------------------------------------
    # Station weight is scaled so each line's *revenue* share comes out at
    # its observed value, independent of how many stations it has.
    line_share = {l["line_name"]: l["revenue_share_target_pct"] for l in lines}
    line_totals = {}
    for s in stations:
        line_totals[s["line_name"]] = line_totals.get(s["line_name"], 0.0) + s["_weight"]
    station_weights = [
        s["_weight"] / line_totals[s["line_name"]] * line_share[s["line_name"]]
        for s in stations
    ]

    by_line = {}
    for s in stations:
        by_line.setdefault(s["line_name"], []).append(s)

    line_cc = {l["line_name"]: l["line_colour_cc"] for l in lines}

    # ---- fact file ----------------------------------------------------
    fact_path = out_dir / "sample_data.csv"
    with fact_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "transaction_id", "Sta", "station_name", "Dest", "dest_station_name",
            "Line", "LineCC", "PrType", "TxT", "FarT", "Value",
            "TrxDetail", "InsertionDateTime",
        ])

        chosen_days = rng.choices(days, weights=day_weights, k=rows)
        origins = rng.choices(stations, weights=station_weights, k=rows)
        ptypes = rng.choices(PASSENGER_TYPES, weights=PASSENGER_WEIGHTS, k=rows)

        for i in range(rows):
            origin = origins[i]
            # ~92% of journeys stay on one line; the rest are interchanges.
            pool = by_line[origin["line_name"]] if rng.random() < 0.92 else stations
            dest = rng.choice(pool)
            while dest["station_id"] == origin["station_id"] and len(pool) > 1:
                dest = rng.choice(pool)

            ts = pick_timestamp(rng, chosen_days[i])
            fare = pick_fare(rng, origin["_fare_bias"])
            ptype = ptypes[i]

            writer.writerow([
                i + 1,
                origin["station_id"], origin["station_name"],
                dest["station_id"], dest["station_name"],
                origin["line_name"], line_cc[origin["line_name"]],
                ptype,
                rng.choice(TXN_TYPES),
                rng.choice(FARE_TYPES),
                f"{fare:.2f}",
                f"{ptype[:2].upper()}-{ts:%Y%m%d}-{rng.randrange(10**6):06d}",
                ts.strftime("%Y-%m-%d %H:%M:%S"),
            ])

    print(f"  sample_data.csv    {rows:,} transactions")
    print(f"  dim_stations.csv   {len(stations)} stations")
    print(f"  dim_lines.csv      {len(lines)} lines")
    return fact_path


def summarise(path: Path) -> None:
    """Print the distributions so they can be checked against the real ones."""
    import collections

    rev_by_line = collections.Counter()
    cnt_by_type = collections.Counter()
    rev_by_day = collections.Counter()
    total_rev = 0.0
    n = 0

    targets = {name: cfg[1] for name, cfg in NETWORK.items()}

    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            v = float(row["Value"])
            rev_by_line[row["Line"]] += v
            cnt_by_type[row["PrType"]] += 1
            rev_by_day[row["InsertionDateTime"][:10]] += v
            total_rev += v
            n += 1

    print(f"\n  transactions        {n:,}")
    print(f"  total revenue       Rs {total_rev:,.2f}")
    print(f"  avg ticket value    Rs {total_rev / n:,.2f}   (target 39.53)")
    print(f"  days covered        {len(rev_by_day)}")
    print(f"  daily avg revenue   Rs {total_rev / len(rev_by_day):,.0f}")
    print("\n  revenue share by line")
    for line, rev in rev_by_line.most_common():
        print(f"    {line:<16} {100 * rev / total_rev:6.2f}%   (target {targets[line]:5.2f}%)")
    print("\n  passenger type mix")
    for t, c in cnt_by_type.most_common():
        print(f"    {t:<16} {100 * c / n:6.2f}%")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).parent)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-summary", action="store_true")
    args = ap.parse_args()

    fact = generate(args.rows, args.out_dir, args.seed)
    if not args.no_summary:
        summarise(fact)
