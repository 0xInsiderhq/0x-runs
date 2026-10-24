# order-service

Computes order totals for the shop backend.

- `orders/legacy.py` is the current v1 implementation (in production).
- `orders/v2.py` is the v2 rewrite. It should follow the structure the platform team shipped in `reference/v2_reference.py`.
- `orders/monitor.py` is the client for the order monitoring service. See `docs/monitoring.md`.

Run the tests with `python -m pytest`.
