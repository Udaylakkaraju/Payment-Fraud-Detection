 /* Goal: Identify the top error codes driving the failures.
*/
SELECT 
    Status as Error_Reason,
    COUNT(*) as Failure_Count,
    -- Calculate % of Total Failures
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments` WHERE Status != '00: Success') * 100, 2) as Pct_of_Failures
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
WHERE Status != '00: Success'
GROUP BY 1
ORDER BY 2 DESC;