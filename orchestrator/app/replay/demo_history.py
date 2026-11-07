"""History for the built-in demo ("demo" in replay mode): the shop library, built up commit by
commit, with four real bug fixes that each came with a test, plus commits that are not bug fixes.

Commit dates and authors are fixed, so the history (and every sha) is identical on every machine:
a scan and a later launch agree on the case ids. Lives in the orchestrator, not in demo-repo/,
because the sandboxes get demo-repo/ and must never see the fixed code.
"""

import os
import subprocess
import tempfile
import threading
from pathlib import Path

README = """# shop

A tiny order-pricing library: bulk discount tiers, percentage discounts (integer cents),
a shopping cart, and order-date parsing for EU shops.

Run the tests with `pytest -q`.
"""

README_TIERS = README + """
## Discount tiers

| Items of one product | Discount |
| -------------------- | -------- |
| 10+                  | 5%       |
| 50+                  | 10%      |
| 100+                 | 15%      |
"""

PYTEST_INI = "[pytest]\npythonpath = .\ntestpaths = tests\n"
REQUIREMENTS = "python-dateutil==2.9.0.post0\n"
INIT = '"""A tiny order-pricing library."""\n'

PRICING_V1 = '''"""Pricing rules. All prices are integer cents."""

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
'''
PRICING_V2 = PRICING_V1.replace("if quantity > min_qty:", "if quantity >= min_qty:")
PRICING_V3 = PRICING_V2.replace(
    '''    """Price after taking `percent` off, rounded to the nearest cent."""
    return int(price_cents * (1 - percent / 100))''',
    '''    """Price after taking `percent` off, rounded to the nearest cent."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(price_cents * (100 - percent) / 100)''',
)

CART_V1 = '''"""A shopping cart."""

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
'''
CART_V2 = CART_V1.replace(
    "    def __init__(self, items=[]):\n        self.items = items",
    "    def __init__(self, items=None):\n        self.items = list(items) if items else []",
)

DATES_V1 = '''"""Order dates. Our shops are in the EU: '03/04/2025' means 3 April 2025."""

from datetime import date

from dateutil import parser


def parse_order_date(text: str) -> date:
    return parser.parse(text).date()
'''
DATES_V2 = DATES_V1.replace(
    "def parse_order_date(text: str) -> date:\n    return parser.parse(text).date()",
    '''def parse_order_date(text: str) -> date:
    text = text.strip()
    try:
        return date.fromisoformat(text)  # 2025-04-03: unambiguous
    except ValueError:
        return parser.parse(text, dayfirst=True).date()''',
)

TEST_BASICS = '''from shop.cart import Cart
from shop.pricing import apply_discount, bulk_discount_percent


def test_small_orders_pay_full_price():
    assert bulk_discount_percent(1) == 0
    assert apply_discount(1234, 0) == 1234


def test_cart_adds_items():
    cart = Cart([])
    cart.add("mug", 1200, quantity=2)
    assert cart.total_cents() == 2400
'''
TEST_DATES_V1 = '''from datetime import date

from shop.dates import parse_order_date


def test_iso_dates():
    assert parse_order_date("2025-04-03") == date(2025, 4, 3)
'''
TEST_DATES_V2 = TEST_DATES_V1 + '''

def test_day_first():
    assert parse_order_date("03/04/2025") == date(2025, 4, 3)
    assert parse_order_date("25/12/2024") == date(2024, 12, 25)
'''
TEST_PRICING_V1 = '''import pytest

from shop.pricing import bulk_discount_percent


@pytest.mark.parametrize(
    ("quantity", "percent"),
    [(1, 0), (9, 0), (10, 5), (49, 5), (50, 10), (99, 10), (100, 15), (500, 15)],
)
def test_bulk_tiers(quantity, percent):
    assert bulk_discount_percent(quantity) == percent
'''
TEST_PRICING_V2 = TEST_PRICING_V1.replace(
    "from shop.pricing import bulk_discount_percent", "from shop.pricing import apply_discount, bulk_discount_percent"
) + '''

def test_discount_rounds_to_nearest_cent():
    assert apply_discount(1000, 7) == 930
    assert apply_discount(1999, 10) == 1799
    assert apply_discount(995, 5) == 945


@pytest.mark.parametrize("percent", [-5, 101])
def test_discount_out_of_range_is_rejected(percent):
    with pytest.raises(ValueError):
        apply_discount(1000, percent)
'''
TEST_CART = '''from shop.cart import Cart


def test_new_carts_start_empty():
    first = Cart()
    first.add("mug", 1200)
    assert Cart().items == []


def test_total_applies_bulk_discount():
    cart = Cart()
    cart.add("pen", 100, quantity=10)  # 10 items -> 5% off
    cart.add("mug", 1200)
    assert cart.total_cents() == 950 + 1200
'''

#: (message, files changed: path -> content). Oldest first.
COMMITS: list[tuple[str, dict[str, str]]] = [
    (
        "Add pricing rules and shopping cart",
        {
            "README.md": README,
            "pytest.ini": PYTEST_INI,
            "requirements.txt": REQUIREMENTS,
            "shop/__init__.py": INIT,
            "shop/pricing.py": PRICING_V1,
            "shop/cart.py": CART_V1,
            "tests/test_basics.py": TEST_BASICS,
        },
    ),
    (
        "Add order date parsing for EU shops",
        {"shop/dates.py": DATES_V1, "tests/test_dates.py": TEST_DATES_V1},
    ),
    (
        "Fix bulk discount not applied at exactly 10, 50 or 100 items (#12)\n\n"
        "Customers who order exactly 10 of a product are charged full price. Support says the\n"
        "same happens at 50 and 100: the discount only starts one item later than advertised.",
        {"shop/pricing.py": PRICING_V2, "tests/test_pricing.py": TEST_PRICING_V1},
    ),
    ("Document the discount tiers in the README", {"README.md": README_TIERS}),
    (
        "Fix EU order dates read month-first (#15)\n\n"
        "An order placed on 03/04/2025 shows up as 4 March instead of 3 April. Our shops are in\n"
        "the EU and always write the day first. ISO dates like 2025-04-03 must keep working.",
        {"shop/dates.py": DATES_V2, "tests/test_dates.py": TEST_DATES_V2},
    ),
    (
        "Fix discounted prices being a cent too low (#18)\n\n"
        "A 1000-cent item with 7% off should cost 930 cents but is charged 929: some prices come out\n"
        "one cent lower than the correctly rounded value. Invalid discounts (below 0% or above\n"
        "100%) are also silently accepted and should be an error.",
        {"shop/pricing.py": PRICING_V3, "tests/test_pricing.py": TEST_PRICING_V2},
    ),
    (
        "Fix new carts already containing items from other carts (#21)\n\n"
        "After one customer adds a mug, the next customer's brand-new cart already has that mug\n"
        "in it, and their total is wrong.",
        {"shop/cart.py": CART_V2, "tests/test_cart.py": TEST_CART},
    ),
]

_lock = threading.Lock()
_built: Path | None = None


def build(dest: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Shop Dev",
        "GIT_AUTHOR_EMAIL": "dev@shop.example",
        "GIT_COMMITTER_NAME": "Shop Dev",
        "GIT_COMMITTER_EMAIL": "dev@shop.example",
    }
    git = ["git", "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q", str(dest)], check=True, capture_output=True)
    for day, (message, files) in enumerate(COMMITS, start=1):
        for path, content in files.items():
            f = dest / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(content.encode())
        stamp = f"2025-0{1 + day // 4}-{10 + day:02d}T10:00:00+00:00"
        env_c = {**env, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        subprocess.run([*git, "add", "-A"], cwd=dest, check=True, capture_output=True)
        subprocess.run([*git, "commit", "-q", "-m", message], cwd=dest, check=True, capture_output=True, env=env_c)


def demo_history() -> Path:
    """Path to the demo history repo (its working tree), built once per process."""
    global _built
    with _lock:
        if _built is None or not (_built / ".git").is_dir():
            path = Path(tempfile.mkdtemp(prefix="trace-demo-history-")) / "shop"
            build(path)
            _built = path
        return _built
