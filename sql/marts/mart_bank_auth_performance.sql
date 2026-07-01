/*
  Mart: issuer bank authorization performance.
  Compares approval rate, failed value concentration, and dominant decline reason
  by issuer bank for payment operations prioritization.
*/
WITH base AS (
  SELECT
    Issuer_Bank AS issuer_bank,
    Status,
    Amount,
    Transaction_ID
  FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
),
bank_kpis AS (
  SELECT
    issuer_bank,
    COUNT(*) AS total_txns,
    COUNTIF(Status = '00: Success') AS success_txns,
    COUNTIF(Status != '00: Success') AS failed_txns,
    ROUND(SAFE_DIVIDE(COUNTIF(Status = '00: Success'), COUNT(*)) * 100, 2)
      AS auth_rate_pct,
    ROUND(SAFE_DIVIDE(COUNTIF(Status != '00: Success'), COUNT(*)) * 100, 2)
      AS failure_rate_pct,
    ROUND(SUM(Amount), 2) AS total_amount,
    ROUND(SUM(IF(Status != '00: Success', Amount, 0)), 2) AS failed_amount_pool
  FROM base
  GROUP BY issuer_bank
),
decline_rank AS (
  SELECT
    issuer_bank,
    Status AS top_decline_reason,
    COUNT(*) AS top_decline_txns,
    ROW_NUMBER() OVER (
      PARTITION BY issuer_bank
      ORDER BY COUNT(*) DESC, SUM(Amount) DESC
    ) AS rn
  FROM base
  WHERE Status != '00: Success'
  GROUP BY issuer_bank, Status
)
SELECT
  k.*,
  d.top_decline_reason,
  d.top_decline_txns
FROM bank_kpis AS k
LEFT JOIN decline_rank AS d
  ON k.issuer_bank = d.issuer_bank
  AND d.rn = 1
ORDER BY failed_amount_pool DESC;
