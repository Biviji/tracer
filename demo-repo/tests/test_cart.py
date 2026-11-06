from shop.cart import Cart


def test_new_carts_start_empty():
    first = Cart()
    first.add("mug", 1200)
    assert Cart().items == []


def test_total_applies_bulk_discount():
    cart = Cart()
    cart.add("pen", 100, quantity=10)  # 10 items -> 5% off
    cart.add("mug", 1200)
    assert cart.total_cents() == 950 + 1200
