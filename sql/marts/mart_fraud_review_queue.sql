/*
  Mart: fraud-review queue — transaction grain with warehouse-native fields plus
        explicit placeholders for downstream ML scoring (populate when batch scores land).

  Join your scored table or load from Cloud Storage once `fraud_probability` /
  `risk_score` are materialized outside BigQuery — CAST(NULL ...) keeps the contract visible.
*/

SELECT
  p.Transaction_ID AS transaction_id,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', TIMESTAMP(p.Timestamp)) AS transaction_ts_label,
  DATE(TIMESTAMP(p.Timestamp)) AS transaction_date,
  p.User_ID AS user_id,
  ROUND(p.Amount, 2) AS amount,
  p.Status AS payment_status,
  p.Issuer_Bank AS issuer_bank,
  p.Card_Brand AS card_brand,
  -- Placeholders — replace with real score columns when integrated.
  CAST(NULL AS FLOAT64) AS fraud_probability,
  CAST(NULL AS FLOAT64) AS risk_score,
  CAST(NULL AS INT64) AS risk_flag,
  'pending_score_placeholder' AS score_source
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments` AS p
-- Example real join (uncomment when available):
-- LEFT JOIN `project-43c16c81-2fd4-4871-8ac.payment_optimization.fraud_scores_daily` AS s
--   ON p.Transaction_ID = s.transaction_id
ORDER BY TIMESTAMP(p.Timestamp) DESC
LIMIT 5000;
