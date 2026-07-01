 -- Smooths the daily Auth Rate to identify underlying performance trends.
WITH Daily_Stats AS (
    SELECT 
        DATE(Timestamp) as Txn_Date,
        COUNTIF(Status = '00: Success') / COUNT(*) * 100 as Daily_Auth_Rate
    FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
    GROUP BY 1
)
SELECT 
    Txn_Date,
    Daily_Auth_Rate,
    -- Calculates the average of the current day and the two preceding days
    ROUND(
        AVG(Daily_Auth_Rate) OVER (
            ORDER BY Txn_Date 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 1
    ) as Rolling_3Day_Avg
FROM Daily_Stats
ORDER BY 1;