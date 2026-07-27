-- =====================================================================
-- 01 — Load raw ATS export into the modelled star schema
-- ---------------------------------------------------------------------
-- The mapping from the ATS's abbreviated columns to semantic names.
-- This file is the single place where "Sta" becomes origin_station_id
-- and "Value" becomes fare_amount. Everything downstream reads core.
-- =====================================================================

-- --- Dimensions are seeded from the distinct values present in raw ----

INSERT INTO core.dim_line (line_name, line_colour_cc)
SELECT DISTINCT "Line", "LineCC"
FROM   raw.ats_transactions
WHERE  "Line" IS NOT NULL
ON CONFLICT (line_name) DO NOTHING;

INSERT INTO core.dim_passenger_type (passenger_type, is_digital)
SELECT DISTINCT
       "PrType",
       "PrType" IN ('NCMC', 'QR Ticket')
FROM   raw.ats_transactions
WHERE  "PrType" IS NOT NULL
ON CONFLICT (passenger_type) DO NOTHING;

INSERT INTO core.dim_station (station_id, station_name, line_id)
SELECT DISTINCT
       r."Sta"::INTEGER,
       'Station ' || r."Sta",            -- station master was a separate DMRC reference table
       l.line_id
FROM   raw.ats_transactions r
JOIN   core.dim_line l ON l.line_name = r."Line"
WHERE  r."Sta" ~ '^[0-9]+$'
ON CONFLICT (station_id) DO NOTHING;

-- Date dimension generated across the observed range rather than joined
-- from a calendar table, so gaps in trading days stay visible.
INSERT INTO core.dim_date (
    date_key, year, quarter, month, month_name,
    day_of_month, day_of_week, day_name, is_weekend
)
SELECT  d::DATE,
        EXTRACT(YEAR    FROM d)::SMALLINT,
        EXTRACT(QUARTER FROM d)::SMALLINT,
        EXTRACT(MONTH   FROM d)::SMALLINT,
        TO_CHAR(d, 'Mon'),
        EXTRACT(DAY FROM d)::SMALLINT,
        EXTRACT(ISODOW FROM d)::SMALLINT,
        TO_CHAR(d, 'Dy'),
        EXTRACT(ISODOW FROM d) IN (6, 7)
FROM generate_series(
        (SELECT MIN("InsertionDateTime"::TIMESTAMP)::DATE FROM raw.ats_transactions),
        (SELECT MAX("InsertionDateTime"::TIMESTAMP)::DATE FROM raw.ats_transactions),
        INTERVAL '1 day'
     ) AS d
ON CONFLICT (date_key) DO NOTHING;


-- --- Fact load --------------------------------------------------------
-- Rows failing coercion are dropped rather than defaulted. A NULL fare
-- silently becoming 0 would understate revenue, which is worse than a
-- row count that does not tie exactly.

INSERT INTO core.fact_transactions (
    txn_timestamp, txn_date, origin_station_id, dest_station_id,
    line_id, passenger_type_id, txn_type, fare_type, fare_amount, txn_detail
)
SELECT
    r."InsertionDateTime"::TIMESTAMP,
    r."InsertionDateTime"::TIMESTAMP::DATE,
    r."Sta"::INTEGER,
    NULLIF(r."Dest", '')::INTEGER,
    l.line_id,
    p.passenger_type_id,
    r."TxT",
    r."FarT",
    r."Value"::NUMERIC(10,2),
    r."TrxDetail"
FROM raw.ats_transactions r
JOIN core.dim_line            l ON l.line_name      = r."Line"
JOIN core.dim_passenger_type  p ON p.passenger_type = r."PrType"
WHERE r."Value" ~ '^[0-9]+(\.[0-9]+)?$'
  AND r."Sta"   ~ '^[0-9]+$';

ANALYZE core.fact_transactions;
