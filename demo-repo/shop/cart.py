"""A shopping cart."""

from shop.pricing import apply_discount, bulk_discount_percent


class Cart:
    def __init__(self, items=[]):
        self.items = items

    def add(self, sku: str, price_cents: int, quantity: int = 1) -> None:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        self.items.append((sku, price_cents, quantity))

    def total_cents(self) -> int:
        total = 0
        for _sku, price, quantity in self.items:
            total += apply_discount(price * quantity, bulk_discount_percent(quantity))
        return total
