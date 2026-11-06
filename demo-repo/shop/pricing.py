"""Pricing rules. All prices are integer cents."""

#: (minimum quantity, percent off): 10+ items get 5%, 50+ get 10%, 100+ get 15%.
BULK_TIERS = [(10, 5), (50, 10), (100, 15)]


def bulk_discount_percent(quantity: int) -> int:
    """Percent off for buying `quantity` of one item."""
    percent = 0
    for min_qty, off in BULK_TIERS:
        if quantity > min_qty:
            percent = off
    return percent


def apply_discount(price_cents: int, percent: float) -> int:
    """Price after taking `percent` off, rounded to the nearest cent."""
    return int(price_cents * (1 - percent / 100))
