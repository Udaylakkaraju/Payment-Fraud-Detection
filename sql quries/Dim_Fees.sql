 /* STEP 1: CREATE the dim_fees reference table */
CREATE TABLE `project-43c16c81-2fd4-4871-8ac.payment_optimization.dim_fees` AS 
SELECT 'Amex' as Card_Brand, 0.029 as Pct_Fee, 0.30 as Fixed_Fee
UNION ALL
SELECT 'Visa', 0.015, 0.10
UNION ALL 
SELECT 'Mastercard', 0.015, 0.10;