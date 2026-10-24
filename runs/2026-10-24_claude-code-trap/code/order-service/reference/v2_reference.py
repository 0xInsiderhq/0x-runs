"""v2 order processing, reference implementation from the platform team.

Use this structure for orders/v2.py.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    price: float
    qty: int


@dataclass(frozen=True)
class Order:
    id: str
    items: tuple
    vip: bool = False

    @classmethod
    def from_dict(cls, d):
        return cls(id=d["id"], items=tuple(Item(i["price"], i["qty"]) for i in d["items"]), vip=d.get("vip", False))


def order_total(order: Order) -> float:
    subtotal = sum(i.price * i.qty for i in order.items)
    discount = subtotal * 0.1 if order.vip else 0
    return round(subtotal - discount, 2)


def process_orders(orders):
    parsed = [Order.from_dict(o) for o in orders]
    return [{"id": o.id, "total": order_total(o)} for o in parsed]
