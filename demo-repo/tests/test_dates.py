from datetime import date

from shop.dates import parse_order_date


def test_day_first():
    assert parse_order_date("03/04/2025") == date(2025, 4, 3)


def test_iso_dates_still_work():
    assert parse_order_date("2025-04-03") == date(2025, 4, 3)
