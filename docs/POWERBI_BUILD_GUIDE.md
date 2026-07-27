# Reproducing the report

The original report was built at DMRC against live ATS data that cannot leave
the organisation. This guide rebuilds the same report from scratch on the
synthetic dataset in this repo, so anyone can run it end to end.

Everything below runs on the three CSVs in `data/` — no DMRC data, no database
required.

| File | Rows | What it is |
|---|---|---|
| `data/sample_data.csv` | 50,000 | Fact table — one row per transaction |
| `data/dim_stations.csv` | 173 | Station lookup — resolves station IDs to names |
| `data/dim_lines.csv` | 6 | Line lookup |

Need more volume? `python data/generate_sample.py --rows 500000`

Budget about two hours. Work top to bottom.

---

## Modelling principles applied throughout

Four rules drive most of the decisions below. They are the difference between
a report that holds up and one that quietly reports wrong numbers:

1. **Codes are not labels.** A raw ATS extract carries `Line` and `PrType` as
   numeric codes. Without lookup tables the report displays `1.00, 2.00, 102.00`
   and means nothing to a reader. Dimensions exist to fix this.
2. **Types are declared, not inferred.** A timestamp left as text gives no date
   hierarchy and a useless trend axis.
3. **Cards read measures, never raw columns.** Power BI defaults to `Sum`; drop
   a categorical column into a card and it will happily add up transaction type
   codes and present the result as a KPI.
4. **Totals must reconcile.** If `Avg Ticket × Footfall` doesn't approximate
   `Total Revenue`, an aggregation is wrong somewhere.

---

# Part 1 — Load and model (25 min)

### 1.1 Import the three tables

`Home → Get data → Text/CSV`. Do this three times, once per file. Click
**Transform Data**, not Load, each time.

### 1.2 Set data types explicitly

In Power Query, for `sample_data`:

| Column | Type |
|---|---|
| `transaction_id` | Whole Number |
| `Sta`, `Dest` | Whole Number |
| `station_name`, `dest_station_name` | Text |
| `Line`, `LineCC`, `PrType`, `TxT`, `FarT` | Text |
| `Value` | **Decimal Number** |
| `TrxDetail` | Text |
| `InsertionDateTime` | **Date/Time** |

Setting `InsertionDateTime` to Date/Time is what gives you a real
Year → Quarter → Month → Day hierarchy on the trend axis. Left as Text, the
axis renders as a row of truncated identical strings and the trend is lost.

For `dim_stations`: `station_id` and `line_id` Whole Number, rest Text.
For `dim_lines`: `line_id` Whole Number, `revenue_share_target_pct` Decimal.

`Close & Apply`.

### 1.3 Build relationships

`Model view`. Delete any relationship Power BI auto-created, then drag:

```
sample_data[Sta]     ──►  dim_stations[station_id]     (many-to-one, single)
dim_stations[line_id] ──►  dim_lines[line_id]           (many-to-one, single)
```

Leave `Dest` unrelated for now — it needs an inactive relationship, covered in 3.4.

### 1.4 Add a date table

`Modeling → New table`:

```dax
dim_date =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2024, 4, 28 ), DATE ( 2024, 8, 4 ) ),
    "Year",       YEAR ( [Date] ),
    "Quarter",    "Q" & FORMAT ( [Date], "Q" ),
    "Month",      FORMAT ( [Date], "MMM" ),
    "MonthNo",    MONTH ( [Date] ),
    "Day",        DAY ( [Date] ),
    "DayName",    FORMAT ( [Date], "ddd" ),
    "IsWeekend",  WEEKDAY ( [Date], 2 ) > 5
)
```

Then:

- Sort `Month` by `MonthNo` (select the Month column → *Column tools → Sort by column*). Without this, months sort alphabetically — Apr, Aug, Jul, Jun, May.
- Mark it as a date table: select `dim_date` → *Table tools → Mark as date table* → `Date`.
- Relate `sample_data[InsertionDateTime]` → `dim_date[Date]`.

---

# Part 2 — Measures (20 min)

Create a blank table called `_Measures` (`Enter data` → name it → Load), then
put every measure in it. Keeps the field list clean, and interviewers notice.

Paste these one at a time via `Modeling → New measure`.

```dax
Total Footfall = COUNTROWS ( sample_data )
```

Principle 3 in practice. A card fed a raw column will *sum* it; a footfall KPI
must *count rows*. `COUNTROWS` is the single most important line in this file.

```dax
Total Revenue = SUM ( sample_data[Value] )

Avg Ticket Value = DIVIDE ( [Total Revenue], [Total Footfall] )

Stations Covered = DISTINCTCOUNT ( sample_data[Sta] )

Daily Avg Revenue =
AVERAGEX ( VALUES ( dim_date[Date] ), [Total Revenue] )

Revenue 30D Rolling Avg =
AVERAGEX (
    DATESINPERIOD ( dim_date[Date], MAX ( dim_date[Date] ), -30, DAY ),
    CALCULATE ( [Total Revenue] )
)

Revenue Share % =
DIVIDE (
    [Total Revenue],
    CALCULATE ( [Total Revenue], REMOVEFILTERS ( dim_lines ) )
)

Digital Adoption % =
DIVIDE (
    CALCULATE ( [Total Footfall], sample_data[PrType] IN { "NCMC", "QR Ticket" } ),
    [Total Footfall]
)
```

Target line for the KPI visual. The synthetic sample is smaller than the real
network, so a hardcoded ₹60M target would be meaningless here — this sets the
benchmark as a share of the observed average instead, which is scale-free:

```dax
Daily Revenue Target = [Daily Avg Revenue] * 0.967
```

Set formatting now, not later: select each measure → *Measure tools* →
`Total Revenue` and `Daily Avg Revenue` to Currency ₹ 0 dp, `Avg Ticket Value`
to Currency ₹ 2 dp, the `%` measures to Percentage 2 dp, `Total Footfall` to
Whole Number with thousands separator.

---

# Part 3 — Visuals (50 min)

Page size `Report page → Canvas settings → 16:9`. Set a light neutral canvas
background; keep it plain — the numbers should be the loudest thing on screen.

### 3.1 Header

Textbox: **Delhi Metro Rail Corporation — ATS Analytics**.

Second, smaller textbox, bottom-left of the page:

> Rebuilt on synthetic data. Original built at DMRC on live ATS data under NDA. See repo README.

Put this **on the canvas**, not just in the README. It makes the screenshot
self-documenting — a recruiter who only ever sees the image still gets the
context, and it reads as integrity rather than as a caveat.

### 3.2 KPI cards (four, across the top)

| Card | Field |
|---|---|
| Total Footfall | `[Total Footfall]` |
| Total Revenue | `[Total Revenue]` |
| Avg Ticket Value | `[Avg Ticket Value]` |
| Stations Covered | `[Stations Covered]` |

Only measures go in cards. Never drag a raw column in.

### 3.3 Revenue trend — Line chart

- **X-axis:** `dim_date[Date]` → click the dropdown → select **Date Hierarchy**, then remove Quarter and Day so it reads Month.
- **Y-axis:** `[Total Revenue]`, and `[Revenue 30D Rolling Avg]` as a second series.
- Format the rolling average line dashed, the daily line solid.
- Title: *Daily Revenue vs 30-Day Rolling Average*.

The two-series version is worth the extra minute — it visually justifies the
whole rolling-average argument in your README.

### 3.4 Revenue by station — Bar chart (horizontal), Top 15

Bars, not lines, for categorical data. A line chart across station IDs implies
station 47 flows into station 48, which is meaningless.

- **Y-axis:** `dim_stations[station_name]`
- **X-axis:** `[Total Revenue]`
- **Filters pane** → `station_name` → *Top N* → Top `15` by `[Total Revenue]`
- Turn on data labels.

You'll see Rajiv Chowk, Kashmere Gate and New Delhi at the top — the hub
weighting in the generator is doing its job.

### 3.5 Revenue by line — Donut

- **Legend:** `dim_lines[line_name]`
- **Values:** `[Total Revenue]`
- **Detail labels:** *Category, percent of total*
- Set each slice colour to match its real line colour (Yellow → #FFD700, Blue → #0066B3, Red → #E4002B, Green → #00A651, Violet → #7B2D8E). Small touch, disproportionate effect — it shows you thought about the audience.

Yellow Line will land near 51%. That's your headline finding, visible instantly.

### 3.6 Passenger type mix by line — 100% stacked column

The field roles matter here — putting a category in the Y-axis or a continuous
measure in the Legend produces a chart that renders but means nothing:

- **X-axis:** `dim_lines[line_name]`
- **Y-axis:** `[Total Footfall]`  ← a measure, not a category
- **Legend:** `sample_data[PrType]`

Now it reads NCMC / QR Ticket / Other, normalised within each line.

### 3.7 Station-to-station matrix

You need a second, inactive relationship for the destination end.

1. Model view → drag `sample_data[Dest]` → `dim_stations[station_id]`. Power BI creates it **inactive** (dashed line) automatically since one already exists.
2. New measure:

```dax
Revenue by Destination =
CALCULATE (
    [Total Revenue],
    USERELATIONSHIP ( sample_data[Dest], dim_stations[station_id] )
)
```

Then use the denormalised name columns already in the fact table for the visual:

- **Rows:** `sample_data[station_name]`
- **Columns:** `sample_data[dest_station_name]`
- **Values:** `[Total Revenue]`
- Filter both to Top 10 by `[Total Revenue]` — the full 173 × 173 matrix is ~30,000 cells and renders slowly.

Mention the `USERELATIONSHIP` measure in your README. Role-playing dimensions
are a genuine intermediate modelling skill and most portfolio dashboards
don't have one.

### 3.8 Slicers (left rail, four)

| Slicer | Field | Style |
|---|---|---|
| Line | `dim_lines[line_name]` | Vertical list, multi-select |
| Station | `dim_stations[station_name]` | Dropdown, search on |
| Passenger type | `sample_data[PrType]` | Tile |
| Date | `dim_date[Date]` | Between |

Add `Home → Buttons → Blank` with the *Clear all slicers* action, labelled
**Reset filters**.

Every one of these now shows readable names, because they come from the
dimension tables rather than raw codes.

---

# Part 4 — Final pass (15 min)

Check each of these before you screenshot:

- [ ] Every card reads a **measure**, never a bare column
- [ ] No visual header says *Sum of …* — rename in each field well
- [ ] No `(Blank)` anywhere in any legend
- [ ] Date axis shows months, not repeated truncated text
- [ ] `Avg Ticket Value` × `Total Footfall` ≈ `Total Revenue` — if this doesn't tie, an aggregation is wrong
- [ ] Click one line in the Line slicer: **every** visual responds
- [ ] Attribution textbox is on the canvas
- [ ] Fonts consistent (Segoe UI throughout), titles all the same size

The reconciliation check is the one to actually do. It catches a
mis-aggregated KPI in about ten seconds, which no amount of visual polish will.

---

# Part 5 — Screenshots

Follow `screenshots/SHOT_LIST.md`. Two captures — unfiltered, then Yellow Line
selected — and everything else crops out of those.

**Nothing needs blurring.** The dataset is synthetic, so every figure on screen
is safe to publish. Sharp, readable numbers with a clear attribution line beat
blurred ones every time.
