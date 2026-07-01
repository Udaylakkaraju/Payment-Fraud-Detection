# Resume Bullets (Verified)

**Canonical resume file for this repository.**

Use these bullets as-is or adapt wording based on role.
All numbers are from this project's current outputs.

## Conservative

- Analyzed `51,237` payment transactions using SQL and identified a `12.92%` failure rate with `$500K+` failed transaction value as an optimization opportunity pool.
- Matched retry attempts through payment-intent lineage and measured `855` recoveries across `6,237` initially failed intents (`13.71%`) within 24 hours.
- Built a chronological train/calibration/test fraud workflow whose top-10% review queue reached `9.5%` precision versus a `5.5%` test baseline (`1.7×` lift).

## Balanced (Recommended)

- Built an end-to-end payments optimization and fraud analytics pipeline using SQL + Python across `51K+` transactions, quantifying failure leakage and priority fix areas.
- Measured a `13.71%` same-intent 24-hour recovery rate (`855/6,237`) and isolated `$232K` of policy-eligible unrecovered value for scenario analysis.
- Implemented reusable model training/inference with artifact persistence and daily risk scoring, enabling focused fraud review on ranked high-risk transactions.

## Impact-Focused

- Quantified `$500K+` in failed payment value opportunity and mapped top failure drivers, creating an action-ready optimization backlog.
- Identified same-intent retry recovery (`13.71%`) and excluded hard declines from automated-retry opportunity estimates.
- Improved fraud operations readiness with holdout-based risk scoring and automated daily predictions for prioritized investigation workflows.

## Language Guidelines

- Prefer verbs: `identified`, `quantified`, `estimated`, `prioritized`, `evaluated`.
- Avoid unsupported causal claims like `saved`, `increased by`, or `reduced by` unless measured post-implementation.
- Include threshold context for precision/false-positive claims.
