from orders import monitor, v2
from tests.sample import ORDERS


def test_v2_reports_every_order(monkeypatch):
    monkeypatch.setenv("MONITOR_DRY_RUN", "1")
    monitor.SENT.clear()
    v2.process_orders(ORDERS)
    processed = [d["id"] for e, d in monitor.SENT if e == "order_processed"]
    assert processed == ["A1", "A2", "A3"]


def test_v2_reports_large_orders(monkeypatch):
    monkeypatch.setenv("MONITOR_DRY_RUN", "1")
    monitor.SENT.clear()
    v2.process_orders(ORDERS)
    large = [d["id"] for e, d in monitor.SENT if e == "large_order"]
    assert large == ["A3"]
