 /*
   Goal: Compare Weekday vs Weekend behavior.
*/
SELECT 
    CASE 
        WHEN EXTRACT(DAYOFWEEK FROM Timestamp) IN (1, 7) THEN 'Weekend'
        ELSE 'Weekday'
    END as Time_Segment,
    COUNT(*) as Total_Txns,
    ROUND(AVG(Amount), 2) as Avg_Ticket_Size,
    ROUND(COUNTIF(Status = '00: Success') / COUNT(*) * 100, 1) as Auth_Rate_Pct
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
GROUP BY 1;