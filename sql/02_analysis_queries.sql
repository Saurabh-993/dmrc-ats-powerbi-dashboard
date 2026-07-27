-- =====================================================================
-- 02 — Analytical queries behind each dashboard visual
-- ---------------------------------------------------------------------
-- Every visual on the report page maps to one of these. Power BI
-- imports the results rather than the fact table, which is why a
-- 66M-row dataset responds to slicers in under a second.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1. Headline KPI block  ->  the three cards at the top of the report
-- ---------------------------------------------------------------------
SELECT
    COUNT(*)                                 AS total_transactions,
    SUM(fare_amount)                         AS total_revenue,
    ROUND(AVG(fare_amount), 2)               AS avg_ticket_value,
    COUNT(DISTINCT origin_station_id)        AS stations_covered,
    MIN(txn_date)                            AS period_start,
    MAX(txn_date)                            AS period_end
FROM core.fact_transactions;


-- ---------------------------------------------------------------------
-- Q2. Daily revenue with 30-day rolling average  ->  "Revenue Trend Over Time"
--
-- The rolling window is the analytical core of the project. A raw daily
-- series on metro data is dominated by the weekday/weekend swing, which
-- makes it useless for spotting a genuine trend. A 30-day trailing mean
-- flattens the weekly cycle and is what the Rs 60M daily target was set
-- against.
-- ---------------------------------------------------------------------
SELECT
    txn_date,
    SUM(fare_amount) AS daily_revenue,
    AVG(SUM(fare_amount)) OVER (
        ORDER BY txn_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS revenue_30d_rolling_avg,
    CASE
        WHEN SUM(fare_amount) > AVG(SUM(fare_amount)) OVER (
                 ORDER BY txn_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
        THEN 'above_trend' ELSE 'below_trend'
    END AS trend_flag
FROM core.fact_transactions
GROUP BY txn_date
ORDER BY txn_date;


-- ---------------------------------------------------------------------
-- Q3. Revenue contribution by line  ->  donut + "Revenue by Metro Line"
--
-- SUM(SUM(...)) OVER () gives each line's share without a second pass
-- over the fact table. This is the query that surfaced the concentration
-- finding: one line carries just over half of network revenue.
-- ---------------------------------------------------------------------
SELECT
    l.line_name,
    COUNT(*)                                        AS footfall,
    SUM(f.fare_amount)                              AS revenue,
    ROUND(100.0 * SUM(f.fare_amount)
          / SUM(SUM(f.fare_amount)) OVER (), 2)     AS revenue_share_pct,
    RANK() OVER (ORDER BY SUM(f.fare_amount) DESC)  AS revenue_rank
FROM core.fact_transactions f
JOIN core.dim_line l USING (line_id)
GROUP BY l.line_name
ORDER BY revenue DESC;


-- ---------------------------------------------------------------------
-- Q4. Passenger type mix by line  ->  100% stacked column
--
-- Absolute counts hide the interesting signal here, because line volumes
-- differ by an order of magnitude. Normalising to within-line percentage
-- is what makes digital adoption comparable across the network.
-- ---------------------------------------------------------------------
SELECT
    l.line_name,
    p.passenger_type,
    COUNT(*) AS txn_count,
    ROUND(100.0 * COUNT(*)
          / SUM(COUNT(*)) OVER (PARTITION BY l.line_name), 2) AS pct_within_line
FROM core.fact_transactions f
JOIN core.dim_line           l USING (line_id)
JOIN core.dim_passenger_type p USING (passenger_type_id)
GROUP BY l.line_name, p.passenger_type
ORDER BY l.line_name, txn_count DESC;


-- ---------------------------------------------------------------------
-- Q5. Station-to-station revenue matrix  ->  the pivot table visual
--
-- Self-join on dim_station to resolve both ends of the journey. Capped
-- to the busiest pairs: the full origin-destination matrix across 200+
-- stations is ~40,000 cells, which no one reads and Power BI renders
-- slowly. Top-N by revenue is the version that gets used.
-- ---------------------------------------------------------------------
SELECT
    o.station_name AS origin_station,
    d.station_name AS destination_station,
    l.line_name,
    COUNT(*)                     AS journeys,
    SUM(f.fare_amount)           AS revenue,
    ROUND(AVG(f.fare_amount), 2) AS avg_fare
FROM core.fact_transactions f
JOIN core.dim_station o ON o.station_id = f.origin_station_id
JOIN core.dim_station d ON d.station_id = f.dest_station_id
JOIN core.dim_line    l ON l.line_id    = f.line_id
WHERE f.dest_station_id IS NOT NULL
GROUP BY o.station_name, d.station_name, l.line_name
HAVING COUNT(*) > 100
ORDER BY revenue DESC
LIMIT 500;


-- ---------------------------------------------------------------------
-- Q6. Station ranking  ->  "Revenue by Station", highest/lowest cards
-- ---------------------------------------------------------------------
WITH ranked AS (
    SELECT
        s.station_id,
        s.station_name,
        l.line_name,
        COUNT(*)           AS footfall,
        SUM(f.fare_amount) AS revenue,
        ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS busiest_rank,
        ROW_NUMBER() OVER (ORDER BY COUNT(*) ASC)  AS quietest_rank
    FROM core.fact_transactions f
    JOIN core.dim_station s ON s.station_id = f.origin_station_id
    JOIN core.dim_line    l ON l.line_id    = f.line_id
    GROUP BY s.station_id, s.station_name, l.line_name
)
SELECT *,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 3) AS network_revenue_pct
FROM ranked
ORDER BY revenue DESC;


-- ---------------------------------------------------------------------
-- Q7. Daily average vs target benchmark  ->  the KPI / gauge visual
-- ---------------------------------------------------------------------
WITH daily AS (
    SELECT txn_date, SUM(fare_amount) AS daily_revenue
    FROM core.fact_transactions
    GROUP BY txn_date
)
SELECT
    ROUND(AVG(daily_revenue), 2)                              AS actual_daily_avg,
    60000000                                                  AS target_daily_avg,
    ROUND(100.0 * (AVG(daily_revenue) - 60000000) / 60000000, 2) AS variance_pct,
    COUNT(*) FILTER (WHERE daily_revenue >= 60000000)         AS days_at_or_above_target,
    COUNT(*)                                                  AS days_measured
FROM daily;


-- ---------------------------------------------------------------------
-- Q8. Peak-hour profile  ->  used to justify the sampling strategy
--
-- Sampling uniformly across a metro dataset biases against peak hours,
-- where fare mix differs. Confirming the hourly profile survived the
-- 20% sample was the check that made the sample defensible.
-- ---------------------------------------------------------------------
SELECT
    EXTRACT(HOUR FROM txn_timestamp)::INT AS hour_of_day,
    COUNT(*)                              AS footfall,
    SUM(fare_amount)                      AS revenue,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_daily_footfall
FROM core.fact_transactions
GROUP BY hour_of_day
ORDER BY hour_of_day;
