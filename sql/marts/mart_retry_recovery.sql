/*
  Mart: retry / recovery signal within 24h (1440 minutes) by initial decline.
  Same sessionizing pattern as Smart Retry Analysis (LEAD window).
*/
WITH User_Journey AS (
  SELECT
    Status AS Current_Status,
    LEAD(Status) OVER (PARTITION BY User_ID ORDER BY TIMESTAMP(Timestamp)) AS Next_Status,
    TIMESTAMP_DIFF(
      LEAD(TIMESTAMP(Timestamp)) OVER (PARTITION BY User_ID ORDER BY TIMESTAMP(Timestamp)),
      TIMESTAMP(Timestamp),
      MINUTE
    ) AS mins_to_next
  FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
)
SELECT
  Current_Status AS initial_decline_label,
  COUNT(*) AS total_failures,
  COUNTIF(Next_Status = '00: Success' AND mins_to_next IS NOT NULL AND mins_to_next <= 1440) AS recovered_within_24h_txns,
  ROUND(SAFE_DIVIDE(
    COUNTIF(Next_Status = '00: Success' AND mins_to_next IS NOT NULL AND mins_to_next <= 1440),
    NULLIF(COUNT(*), 0)
  ) * 100, 2) AS recovery_rate_pct_24h
FROM User_Journey
WHERE Current_Status != '00: Success'
GROUP BY 1
ORDER BY total_failures DESC;
