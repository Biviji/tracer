"""Order dates. Our shops are in the EU: '03/04/2025' means 3 April 2025."""

from datetime import date

from dateutil import parser


def parse_order_date(text: str) -> date:
    return parser.parse(text).date()
