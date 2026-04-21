# Resume Bullets (Verified)

Use these bullets as-is or adapt wording based on role.
All numbers are from this project's current outputs.

## Conservative

- Analyzed `51,237` payment transactions using SQL and identified a `12.92%` failure rate with `$500K+` failed transaction value as an optimization opportunity pool.
- Found that `1,554` of `6,619` failed payments (`23.5%`) later succeeded within 24 hours, indicating retry and routing optimization potential.
- Built a holdout-evaluated fraud scoring workflow (train/infer + daily scoring) and achieved `83.5%` recall with zero false positives on a holdout sample at a selected operating threshold.

## Balanced (Recommended)

- Built an end-to-end payments optimization and fraud analytics pipeline using SQL + Python across `51K+` transactions, quantifying failure leakage and priority fix areas.
- Measured retry recovery behavior and surfaced a `23.5%` post-failure success signal (`1,554/6,619`) to guide smarter retry timing strategy.
- Implemented reusable model training/inference with artifact persistence and daily risk scoring, enabling focused fraud review on ranked high-risk transactions.

## Impact-Focused

- Quantified `$500K+` in failed payment value opportunity and mapped top failure drivers, creating an action-ready optimization backlog.
- Identified meaningful retry opportunity (`23.5%` of failed transactions later succeeded within 24h), supporting potential approval uplift initiatives.
- Improved fraud operations readiness with holdout-based risk scoring and automated daily predictions for prioritized investigation workflows.

## Language Guidelines

- Prefer verbs: `identified`, `quantified`, `estimated`, `prioritized`, `evaluated`.
- Avoid unsupported causal claims like `saved`, `increased by`, or `reduced by` unless measured post-implementation.
- Include threshold context for precision/false-positive claims.
