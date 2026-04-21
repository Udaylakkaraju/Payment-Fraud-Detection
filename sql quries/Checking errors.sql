/* Goal: Check for data pipeline errors. 
   If this returns ANY rows, we have a critical data engineering bug.
*/
SELECT 
    Transaction_ID, 
    COUNT(*) as Duplicate_Count
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
GROUP BY 1
HAVING COUNT(*) > 1;