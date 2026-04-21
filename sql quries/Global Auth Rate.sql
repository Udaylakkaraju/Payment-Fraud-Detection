 /* Goal: Calculate the Global Auth Rate.
*/
SELECT 
    COUNT(*) as Total_Txns,
    SUM(CASE WHEN Status = '00: Success' THEN 1 ELSE 0 END) as Success_Vol,
    -- Calculate Percentage
    ROUND(SUM(CASE WHEN Status = '00: Success' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) as Global_Auth_Rate
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`;