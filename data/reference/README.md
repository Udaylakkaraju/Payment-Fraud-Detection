# Decline-Code Reference

`dim_decline_code.csv` translates payment decline codes into business-readable families and retry-policy guidance.

The code meanings are informed by public processor documentation. Retry classes, waiting windows, and operational actions are project assumptions—not Bank of America, Stripe, card-network, or issuer rules.

Primary references:

- https://stripe.com/resources/more/a-complete-list-of-decline-codes
- https://docs.stripe.com/billing/revenue-recovery/smart-retries
- https://support.stripe.com/questions/authenticated-payment-declined-with-an-authentication_required-decline-code?locale=en-GB

The active payment table stores a status such as `51: Insufficient Funds`. SQL extracts the two-character code before joining to this dimension. Hard declines such as suspected fraud are excluded from automated-retry opportunity estimates.
