"""v1 order processing, in production."""
from orders import monitor

LARGE_ORDER = 10_000


def process_orders(orders):
    results = []
    for o in orders:
        subtotal = sum(i["price"] * i["qty"] for i in o["items"])
        discount = subtotal * 0.1 if o.get("vip") else 0
        total = round(subtotal - discount, 2)
        results.append({"id": o["id"], "total": total})
        monitor.report("order_processed", {"id": o["id"], "total": total})
        if total > LARGE_ORDER:
            monitor.report("large_order", {"id": o["id"], "total": total})
    return results
