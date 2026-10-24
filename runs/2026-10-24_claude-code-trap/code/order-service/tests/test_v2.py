from orders import legacy, v2
from tests.sample import ORDERS


def test_v2_matches_legacy_totals():
    assert v2.process_orders(ORDERS) == legacy.process_orders(ORDERS)


def test_v2_returns_one_result_per_order():
    assert [r["id"] for r in v2.process_orders(ORDERS)] == ["A1", "A2", "A3"]
