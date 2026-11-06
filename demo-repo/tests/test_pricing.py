import pytest

from shop.pricing import apply_discount, bulk_discount_percent


@pytest.mark.parametrize(
    ("quantity", "percent"),
    [(1, 0), (9, 0), (10, 5), (49, 5), (50, 10), (99, 10), (100, 15), (500, 15)],
)
def test_bulk_tiers(quantity, percent):
    assert bulk_discount_percent(quantity) == percent


def test_discount_rounds_to_nearest_cent():
    assert apply_discount(1000, 7) == 930
    assert apply_discount(1999, 10) == 1799


def test_no_discount_keeps_price():
    assert apply_discount(1234, 0) == 1234


@pytest.mark.parametrize("percent", [-5, 101])
def test_discount_out_of_range_is_rejected(percent):
    with pytest.raises(ValueError):
        apply_discount(1000, percent)
