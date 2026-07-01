/*
  Mart: retry timing windows.
  Measures how quickly a failed payment is followed by success for the same user,
  grouped into action-friendly retry windows.
*/
WITH ordered_payments AS (
  SELECT
    User_ID,
    TIMESTAMP(Timestamp) AS transaction_ts,
    Status,
    Amount,
    LEAD(Status) OVER (PARTITION BY User_ID ORDER BY TIMESTAMP(Timestamp)) AS next_status,
    LEAD(TIMESTAMP(Timestamp)) OVER (
      PARTITION BY User_ID ORDER BY TIMESTAMP(Timestamp)
    ) AS next_transaction_ts
  FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
),
failed_payments AS (
  SELECT
    Status AS decline_reason,
    Amount,
    next_status,
    TIMESTAMP_DIFF(next_transaction_ts, transaction_ts, MINUTE) AS minutes_to_next
  FROM ordered_payments
  WHERE Status != '00: Success'
),
bucketed AS (
  SELECT
    decline_reason,
    Amount,
    CASE
      WHEN next_status != '00: Success' OR minutes_to_next IS NULL THEN 'No observed next success'
      WHEN minutes_to_next BETWEEN 0 AND 5 THEN '00-05 minutes'
      WHEN minutes_to_next BETWEEN 6 AND 30 THEN '06-30 minutes'
      WHEN minutes_to_next BETWEEN 31 AND 120 THEN '31-120 minutes'
      WHEN minutes_to_next BETWEEN 121 AND 1440 THEN '02-24 hours'
      ELSE 'Over 24 hours'
    END AS retry_window
  FROM failed_payments
)
SELECT
  decline_reason,
  retry_window,
  COUNT(*) AS failed_txns,
  ROUND(SUM(Amount), 2) AS failed_amount,
  ROUND(SAFE_DIVIDE(COUNT(*), SUM(COUNT(*)) OVER (PARTITION BY decline_reason)) * 100, 2)
    AS pct_of_decline_reason
FROM bucketed
GROUP BY decline_reason, retry_window
ORDER BY decline_reason, failed_txns DESC;
