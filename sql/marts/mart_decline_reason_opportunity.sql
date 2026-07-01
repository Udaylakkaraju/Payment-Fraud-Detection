/*
  Mart: decline reason opportunity.
  Ranks failed-payment reasons by failed value, observed 24h recovery, and
  scenario-ready unrecovered value pool.
*/
WITH attempts AS (
  SELECT
    REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
      AS payment_intent_id,
    TIMESTAMP(Timestamp) AS attempt_ts,
    Status,
    Amount,
    ROW_NUMBER() OVER (
      PARTITION BY REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
      ORDER BY TIMESTAMP(Timestamp), CAST(Transaction_ID AS STRING)
    ) AS attempt_number,
    MIN(IF(Status = '00: Success', TIMESTAMP(Timestamp), NULL)) OVER (
      PARTITION BY REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
    ) AS first_success_ts
  FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
),
failed_payments AS (
  SELECT
    Status AS decline_reason,
    Amount,
    REGEXP_EXTRACT(Status, r'^([0-9A-Z]{2}):') IN ('51', '91')
      AS automatic_retry_allowed,
    first_success_ts IS NOT NULL
      AND TIMESTAMP_DIFF(first_success_ts, attempt_ts, MINUTE) BETWEEN 0 AND 1440
      AS recovered_within_24h
  FROM attempts
  WHERE attempt_number = 1 AND Status != '00: Success'
)
SELECT
  decline_reason,
  COUNT(*) AS failed_txns,
  ROUND(SUM(Amount), 2) AS failed_amount_pool,
  COUNTIF(recovered_within_24h) AS recovered_within_24h_txns,
  ROUND(SUM(IF(recovered_within_24h, Amount, 0)), 2) AS recovered_amount_observed,
  ROUND(SAFE_DIVIDE(COUNTIF(recovered_within_24h), COUNT(*)) * 100, 2)
    AS observed_recovery_rate_pct,
  ROUND(SUM(IF(recovered_within_24h, 0, Amount)), 2) AS unrecovered_amount_pool,
  ROUND(SUM(IF(
    recovered_within_24h OR NOT automatic_retry_allowed,
    0,
    Amount
  )), 2) AS scenario_eligible_unrecovered_amount,
  ROUND(SUM(IF(
    recovered_within_24h OR NOT automatic_retry_allowed,
    0,
    Amount
  )) * 0.10, 2)
    AS scenario_10pct_incremental_recovery
FROM failed_payments
GROUP BY decline_reason
ORDER BY unrecovered_amount_pool DESC;
