 SELECT
  Cohort_Month,
  COUNT(*) AS Total_Txns,
  ROUND(COUNTIF(Status != '00: Success') / COUNT(*) * 100, 1) AS Failure_Rate_Pct
FROM (
  -- Inner Layer: Calculate Cohort for every row first
  SELECT
    Status,
    FORMAT_DATE('%Y-%m', MIN(Timestamp) OVER (PARTITION BY User_ID)) AS Cohort_Month
  FROM
    `project-43c16c81-2fd4-4871-8ac`.payment_optimization.payments
)
GROUP BY 1 
ORDER BY 1;