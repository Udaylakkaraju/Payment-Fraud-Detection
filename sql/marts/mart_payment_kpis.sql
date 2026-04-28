/*
  Mart: payment KPIs aligned to stakeholder reporting — daily grain.
  Dataset: project-43c16c81-2fd4-4871-8ac.payment_optimization.payments

  TIMESTAMP `Timestamp` is cast for safe date labeling in BigQuery.
*/
WITH base AS (
  SELECT
    TIMESTAMP(Timestamp) AS ts,
    Status,
    Amount,
    Transaction_ID,
    User_ID
  FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
)
SELECT
  DATE(ts) AS report_date,
  FORMAT_DATE('%Y-%m-%d', DATE(ts)) AS report_date_label,
  COUNT(*) AS total_txns,
  COUNTIF(Status = '00: Success') AS success_txns,
  COUNTIF(Status != '00: Success') AS failed_txns,
  ROUND(SAFE_DIVIDE(
    COUNTIF(Status = '00: Success'),
    NULLIF(COUNT(*), 0)
  ) * 100, 2) AS auth_rate_pct,
  ROUND(SUM(Amount), 2) AS total_amount,
  ROUND(SUM(IF(Status != '00: Success', Amount, 0)), 2) AS failed_amount_pool
FROM base
GROUP BY 1, 2
ORDER BY report_date;
