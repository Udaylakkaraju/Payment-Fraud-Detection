 -- Calculates the revenue recovery rate for failed payments (The Sessionizing logic).
WITH User_Journey AS (
    SELECT 
        Status as Current_Status,
        LEAD(Status) OVER (PARTITION BY User_ID ORDER BY Timestamp) as Next_Status,
        TIMESTAMP_DIFF(LEAD(Timestamp) OVER (PARTITION BY User_ID ORDER BY Timestamp), Timestamp, MINUTE) as Mins_To_Next
    FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
)
SELECT 
    Current_Status as Initial_Error,
    COUNT(*) as Total_Failures,
    COUNTIF(Next_Status = '00: Success' AND Mins_To_Next <= 1440) as Recovered_Txns,
    ROUND(COUNTIF(Next_Status = '00: Success' AND Mins_To_Next <= 1440) / COUNT(*) * 100, 1) as Recovery_Rate
FROM User_Journey
WHERE Current_Status != '00: Success'
GROUP BY 1;