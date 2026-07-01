 /* SKILL: String Manipulation (SPLIT or REGEXP)
*/
SELECT 
    Status as Original_Raw_Text,
    -- Logic: Split by ': ' and take the second part (Offset 1)
    SPLIT(Status, ': ')[OFFSET(1)] as Clean_Error_Reason,
    COUNT(*) as Count
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
WHERE Status != '00: Success'
GROUP BY 1, 2
ORDER BY 3 DESC;