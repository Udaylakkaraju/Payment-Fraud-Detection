 /* Goal: Identify the top error codes driving the failures.
    Uses a window function for the total-failures denominator so the table
    is scanned once, instead of once for the GROUP BY and again in a
    correlated subquery.
*/
SELECT
    Status as Error_Reason,
    COUNT(*) as Failure_Count,
    -- Calculate % of Total Failures via a single-pass window function
    ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 2) as Pct_of_Failures
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
WHERE Status != '00: Success'
GROUP BY 1
ORDER BY 2 DESC;