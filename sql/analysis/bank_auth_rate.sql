 /* GOAL: The Ultimate Concise Summary - Overall Auth Rate by Partner Bank */
SELECT 
    Issuer_Bank,
    COUNT(*) as Total_Txns_Processed,
    ROUND(COUNTIF(Status = '00: Success') / COUNT(*) * 100, 2) as Overall_Auth_Rate_Pct
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
GROUP BY 1
ORDER BY 3 DESC;