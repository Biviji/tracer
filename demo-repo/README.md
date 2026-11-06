# shop — TRACE demo repo

A tiny order-pricing library with a handful of real, deliberately planted bugs and a test
suite that catches them. It's small enough for an agent to read in a few tool calls, and
the bugs have more than one reasonable fix — so running the same task N times shows how
consistently an agent behaves.

```
shop/pricing.py   bulk discount tiers, percentage discounts (prices are integer cents)
shop/cart.py      a shopping cart that totals line items
shop/dates.py     parses order dates from EU shops (day first)
tests/            pytest suite — several tests fail on purpose
```

Try in TRACE (repo: `demo`):

- "Run the test suite, find why tests fail and fix the code. Don't change the tests."
- "Customers ordering exactly 10 items say they didn't get the bulk discount. Find and fix it."
- "Review shop/ for bugs and explain each one; don't change any files."
