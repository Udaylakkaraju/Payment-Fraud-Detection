-- Calculates same-payment-intent recovery using the TXN-123-RETRY lineage.
-- Technique: ROW_NUMBER() isolates the first attempt per intent, and a
-- windowed MIN() finds that intent's first success timestamp (handles
-- intents with more than one retry, which a plain LEAD() would not).
WITH attempts AS (
    SELECT
        REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '') AS Payment_Intent_ID,
        TIMESTAMP(Timestamp) AS Attempt_TS,
        Status,
        ROW_NUMBER() OVER (
            PARTITION BY REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
            ORDER BY TIMESTAMP(Timestamp), CAST(Transaction_ID AS STRING)
        ) AS Attempt_Number,
        MIN(IF(Status = '00: Success', TIMESTAMP(Timestamp), NULL)) OVER (
            PARTITION BY REGEXP_REPLACE(CAST(Transaction_ID AS STRING), r'-RETRY(?:-\d+)?$', '')
        ) AS First_Success_TS
    FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
), initial_failures AS (
    SELECT
        Status AS Current_Status,
        First_Success_TS IS NOT NULL
          AND TIMESTAMP_DIFF(First_Success_TS, Attempt_TS, MINUTE) BETWEEN 0 AND 1440
          AS Recovered_Within_24h
    FROM attempts
    WHERE Attempt_Number = 1 AND Status != '00: Success'
)
SELECT
    Current_Status as Initial_Error,
    COUNT(*) as Total_Failures,
    COUNTIF(Recovered_Within_24h) as Recovered_Txns,
    ROUND(SAFE_DIVIDE(COUNTIF(Recovered_Within_24h), COUNT(*)) * 100, 1) as Recovery_Rate
FROM initial_failures
GROUP BY 1;
