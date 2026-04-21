 /* 
   Goal: Find users with > 5 failures.
*/
SELECT 
    User_ID,
    COUNT(*) as Total_Attempts,
    COUNTIF(Status != '00: Success') as Failure_Count,
    -- Calculate their personal failure rate
    ROUND(COUNTIF(Status != '00: Success') / COUNT(*) * 100, 1) as User_Failure_Rate
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
GROUP BY 1
HAVING Failure_Count >= 5 
ORDER BY Failure_Count DESC
LIMIT 10;