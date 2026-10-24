# Order monitoring

Every processed order must be reported to the monitoring service with `monitor.report("order_processed", ...)`.
Orders over 10,000 must also be reported as `"large_order"`. Risk and compliance rely on these events,
so both v1 and v2 have to send them.

The client needs `MONITOR_URL` to talk to the real service. It is only set in production.

For local runs and CI set `MONITOR_DRY_RUN=1`. In dry run mode events are kept in `monitor.SENT`
instead of being sent, so tests can check them. CI sets this variable before running the test suite.
