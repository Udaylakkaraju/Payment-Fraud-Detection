 /* STEP 2: Calculate Net Profit using the JOINED dim_fees table */
SELECT 
    t.Card_Brand,
    SUM(t.Amount) as Gross_TPV,
    -- Join the Fee table to deduct costs
    ROUND(SUM(t.Amount * f.Pct_Fee + f.Fixed_Fee), 2) as Total_Fees,
    -- Net Profit: Gross Amount minus Fees
    ROUND(SUM(t.Amount - (t.Amount * f.Pct_Fee + f.Fixed_Fee)), 2) as Net_Profit,
    -- Calculate Margin %
    ROUND((SUM(t.Amount - (t.Amount * f.Pct_Fee + f.Fixed_Fee)) / SUM(t.Amount)) * 100, 2) as Margin_Pct
FROM `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments` t
LEFT JOIN `project-43c16c81-2fd4-4871-8ac.payment_optimization.dim_fees` f ON t.Card_Brand = f.Card_Brand
WHERE t.Status = '00: Success' -- Only count successful transactions
GROUP BY 1
ORDER BY 4 DESC;