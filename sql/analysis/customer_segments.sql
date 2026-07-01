 /* Aggregating Segmentation Logic */
WITH RFM_Base AS (
    SELECT 
        User_ID,
        -- Calculate Scores per user
        NTILE(4) OVER (ORDER BY MAX(TIMESTAMP(Timestamp)) ASC) + 
        NTILE(4) OVER (ORDER BY COUNT(*) ASC) + 
        NTILE(4) OVER (ORDER BY SUM(Amount) ASC) as Total_Score
    FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
    WHERE Status = '00: Success'
    GROUP BY 1
)
SELECT 
    CASE 
        WHEN Total_Score >= 11 THEN 'Champion'
        WHEN Total_Score BETWEEN 8 AND 10 THEN 'Loyal'
        WHEN Total_Score BETWEEN 5 AND 7 THEN 'Potential Loyalist'
        ELSE 'At Risk'
    END as Customer_Segment,
    COUNT(User_ID) as User_Count,
    -- Calculate Percentage of Total Base
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM RFM_Base) * 100, 1) as Pct_of_Total
FROM RFM_Base
GROUP BY 1
ORDER BY User_Count DESC;