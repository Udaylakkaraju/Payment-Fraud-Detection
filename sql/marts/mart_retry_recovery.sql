/*
  Mart: same-payment-intent retry recovery within 24h by initial decline.
  Retry IDs use the source convention TXN-123-RETRY.
*/
WITH attempts AS (
  SELECT
    REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
      AS payment_intent_id,
    TIMESTAMP(Timestamp) AS attempt_ts,
    Status,
    ROW_NUMBER() OVER (
      PARTITION BY REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
      ORDER BY TIMESTAMP(Timestamp), CAST(Transaction_ID AS STRING)
    ) AS attempt_number,
    MIN(IF(Status = '00: Success', TIMESTAMP(Timestamp), NULL)) OVER (
      PARTITION BY REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
    ) AS first_success_ts
  FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
),
initial_failures AS (
  SELECT
    Status AS initial_decline_label,
    first_success_ts IS NOT NULL
      AND TIMESTAMP_DIFF(first_success_ts, attempt_ts, MINUTE) BETWEEN 0 AND 1440
      AS recovered_within_24h
  FROM attempts
  WHERE attempt_number = 1 AND Status != '00: Success'
)
SELECT
  initial_decline_label,
  COUNT(*) AS total_failures,
  COUNTIF(recovered_within_24h) AS recovered_within_24h_txns,
  ROUND(SAFE_DIVIDE(COUNTIF(recovered_within_24h), COUNT(*)) * 100, 2)
    AS recovery_rate_pct_24h
FROM initial_failures
GROUP BY 1
ORDER BY total_failures DESC;
