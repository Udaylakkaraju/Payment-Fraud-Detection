 -- Prepares the data for the Heatmap visual (Auth Rate per Hour/Day/Bank).
SELECT 
    FORMAT_DATE('%A', Timestamp) as Day_Name, 
    EXTRACT(HOUR FROM Timestamp) as Hour_of_Day,
    Issuer_Bank,
    ROUND(COUNTIF(Status = '00: Success') / COUNT(*) * 100, 1) as Auth_Rate_Pct
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;