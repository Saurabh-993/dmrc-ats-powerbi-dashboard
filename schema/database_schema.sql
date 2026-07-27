-- =====================================================================
-- DMRC ATS Analytics — PostgreSQL schema
-- ---------------------------------------------------------------------
-- Two layers:
--   raw.*     mirrors the Automatic Ticketing System export as-is,
--             including its abbreviated column names. Nothing is
--             cleaned here — this is the landing zone.
--   core.*    the modelled star schema the Power BI report reads from.
--
-- No DMRC data is contained in or distributed with this repository.
-- Run data/generate_sample.py to populate these tables with synthetic
-- rows shaped to the same distributions.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;


-- =====================================================================
-- LAYER 1 — RAW LANDING
-- Column names are the ATS export's own. They are abbreviated and
-- untyped on arrival; every value lands as text and is coerced on the
-- way into core. Keeping the raw layer verbatim means a bad transform
-- is always replayable without re-requesting the extract.
-- =====================================================================

CREATE TABLE raw.ats_transactions (
    trx_id              BIGSERIAL PRIMARY KEY,
    "Sta"               TEXT,          -- origin / entry station code
    "Dest"              TEXT,          -- destination / exit station code
    "Line"              TEXT,          -- metro line name
    "LineCC"            TEXT,          -- line colour code
    "PrType"            TEXT,          -- passenger / product type (NCMC, QR, Other)
    "TxT"               TEXT,          -- transaction type
    "FarT"              TEXT,          -- fare type (adult, concession, ...)
    "Value"             TEXT,          -- fare amount, rupees
    "TrxDetail"         TEXT,          -- free-text transaction detail
    "InsertionDateTime" TEXT,          -- timestamp the record hit the ATS
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE raw.ats_transactions IS
    'Verbatim ATS export. Text-typed on purpose: coercion happens in the load to core.';


-- =====================================================================
-- LAYER 2 — DIMENSIONS
-- =====================================================================

CREATE TABLE core.dim_line (
    line_id        SMALLSERIAL PRIMARY KEY,
    line_name      TEXT NOT NULL UNIQUE,   -- 'Yellow Line', 'Blue Line (N)', ...
    line_colour_cc TEXT,                   -- from raw."LineCC"
    is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE core.dim_station (
    station_id   INTEGER PRIMARY KEY,      -- ATS station code, kept as natural key
    station_name TEXT NOT NULL,
    line_id      SMALLINT REFERENCES core.dim_line(line_id),
    is_interchange BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE core.dim_passenger_type (
    passenger_type_id SMALLSERIAL PRIMARY KEY,
    passenger_type    TEXT NOT NULL UNIQUE, -- 'NCMC', 'QR Ticket', 'Other'
    is_digital        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE core.dim_date (
    date_key     DATE PRIMARY KEY,
    year         SMALLINT NOT NULL,
    quarter      SMALLINT NOT NULL,
    month        SMALLINT NOT NULL,
    month_name   TEXT     NOT NULL,
    day_of_month SMALLINT NOT NULL,
    day_of_week  SMALLINT NOT NULL,        -- 1 = Monday
    day_name     TEXT     NOT NULL,
    is_weekend   BOOLEAN  NOT NULL
);


-- =====================================================================
-- LAYER 2 — FACT
-- One row per ticketing transaction. BIGSERIAL because the real table
-- runs to hundreds of millions of rows and INTEGER would have wrapped.
-- =====================================================================

CREATE TABLE core.fact_transactions (
    transaction_id      BIGSERIAL PRIMARY KEY,
    txn_timestamp       TIMESTAMP NOT NULL,
    txn_date            DATE      NOT NULL REFERENCES core.dim_date(date_key),
    origin_station_id   INTEGER   NOT NULL REFERENCES core.dim_station(station_id),
    dest_station_id     INTEGER            REFERENCES core.dim_station(station_id),
    line_id             SMALLINT  NOT NULL REFERENCES core.dim_line(line_id),
    passenger_type_id   SMALLINT  NOT NULL REFERENCES core.dim_passenger_type(passenger_type_id),
    txn_type            TEXT,             -- from raw."TxT"
    fare_type           TEXT,             -- from raw."FarT"
    fare_amount         NUMERIC(10,2) NOT NULL CHECK (fare_amount >= 0),
    txn_detail          TEXT
);

-- Indexes chosen from the actual filter and group-by patterns in the
-- report: every visual either slices by date, by station, by line, or
-- by passenger type. Without these, the station-to-station matrix was
-- the slowest visual on the page by an order of magnitude.
CREATE INDEX idx_fact_txn_date        ON core.fact_transactions (txn_date);
CREATE INDEX idx_fact_txn_timestamp   ON core.fact_transactions (txn_timestamp);
CREATE INDEX idx_fact_origin_station  ON core.fact_transactions (origin_station_id);
CREATE INDEX idx_fact_line            ON core.fact_transactions (line_id);
CREATE INDEX idx_fact_passenger_type  ON core.fact_transactions (passenger_type_id);

-- Composite index backing the origin -> destination revenue matrix.
CREATE INDEX idx_fact_od_pair
    ON core.fact_transactions (origin_station_id, dest_station_id)
    INCLUDE (fare_amount);


-- =====================================================================
-- LAYER 3 — SERVING VIEWS
-- Pre-aggregated so Power BI imports a few thousand rows instead of
-- tens of millions. The rolling average is computed here rather than
-- in DAX: PostgreSQL does it once at refresh, DAX would recompute it
-- on every slicer interaction.
-- =====================================================================

CREATE OR REPLACE VIEW core.vw_daily_revenue_trend AS
WITH daily AS (
    SELECT
        txn_date,
        SUM(fare_amount)   AS daily_revenue,
        COUNT(*)           AS daily_footfall,
        AVG(fare_amount)   AS avg_ticket_value
    FROM core.fact_transactions
    GROUP BY txn_date
)
SELECT
    txn_date,
    daily_revenue,
    daily_footfall,
    ROUND(avg_ticket_value, 2) AS avg_ticket_value,
    ROUND(AVG(daily_revenue) OVER (
        ORDER BY txn_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ), 2) AS revenue_30d_rolling_avg,
    ROUND(
        100.0 * (daily_revenue - LAG(daily_revenue) OVER (ORDER BY txn_date))
        / NULLIF(LAG(daily_revenue) OVER (ORDER BY txn_date), 0)
    , 2) AS revenue_dod_pct_change
FROM daily;

COMMENT ON VIEW core.vw_daily_revenue_trend IS
    'Daily revenue with a 30-day trailing average. The average is what the Rs 60M daily target benchmark was derived from.';


CREATE OR REPLACE VIEW core.vw_line_revenue_share AS
SELECT
    l.line_name,
    SUM(f.fare_amount)                                   AS total_revenue,
    COUNT(*)                                             AS total_footfall,
    ROUND(100.0 * SUM(f.fare_amount)
          / SUM(SUM(f.fare_amount)) OVER (), 2)          AS revenue_share_pct
FROM core.fact_transactions f
JOIN core.dim_line l USING (line_id)
GROUP BY l.line_name
ORDER BY total_revenue DESC;


CREATE OR REPLACE VIEW core.vw_station_performance AS
SELECT
    s.station_id,
    s.station_name,
    l.line_name,
    COUNT(*)                     AS footfall,
    SUM(f.fare_amount)           AS revenue,
    ROUND(AVG(f.fare_amount), 2) AS avg_ticket_value
FROM core.fact_transactions f
JOIN core.dim_station s ON s.station_id = f.origin_station_id
JOIN core.dim_line    l ON l.line_id    = f.line_id
GROUP BY s.station_id, s.station_name, l.line_name;
