 /* SKILL: Densification (Cross Join + Aggregation in one step) */
WITH Hourly_Buckets AS (
    -- 1. Calculate the Status for every single hour (Raw Data)
    SELECT 
        Issuer_Bank,
        CASE 
            WHEN COUNTIF(Status = '00: Success') / COUNT(*) < 0.70 THEN 'Critical Outage (<70%)'
            WHEN COUNTIF(Status = '00: Success') / COUNT(*) < 0.85 THEN 'Warning (70-85%)'
            ELSE 'Healthy (>85%)'
        END as Bucket
    FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
    GROUP BY Issuer_Bank, FORMAT_DATE('%Y%m%d%H', Timestamp)
),
Grid AS (
    -- 2. Create the perfect 15-row grid (5 Banks * 3 Buckets)
    SELECT DISTINCT Issuer_Bank, Bucket_Name
    FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`
    CROSS JOIN (
        SELECT 'Critical Outage (<70%)' as Bucket_Name 
        UNION ALL SELECT 'Warning (70-85%)' 
        UNION ALL SELECT 'Healthy (>85%)'
    )
)
-- 3. The Final Join & Count
SELECT 
    g.Issuer_Bank,
    g.Bucket_Name as Performance_Bucket,
    COUNT(h.Bucket) as Hours_Count,
    -- Recalculate % (Handle the zeros gracefully)
    ROUND(COUNT(h.Bucket) * 100.0 / SUM(COUNT(h.Bucket)) OVER (PARTITION BY g.Issuer_Bank), 1) as Pct_of_Total_Hours
FROM Grid g
LEFT JOIN Hourly_Buckets h ON g.Issuer_Bank = h.Issuer_Bank AND g.Bucket_Name = h.Bucket
GROUP BY 1, 2
ORDER BY 1, 2;