You are working in the `au-plans-scraper` repo. Round 2 added 6 new provider
scrapers; two of them have real parsing bugs that were masked by loosened
test assertions instead of being fixed. Fix the root cause in each, then
tighten the tests back to exact/correct counts -- don't just raise the `>=`
threshold.

===========================================================
BUG 1: Kogan Mobile drops plans whose price has a space after "$"
===========================================================

File: scraper/providers/mobile/kogan.py

`DOLLAR_RE = re.compile(r"\$(\d+\.?\d*)")` requires a digit immediately
after `$`. But `soup.get_text(" ", strip=True)` inserts a space between the
`$` node and the number node for several cards (e.g. renders as `"$ 20"`,
`"$ 40"` in the extracted text), so `DOLLAR_RE.findall(...)` returns nothing
for those cards and the whole plan gets skipped at the `if not prices:
continue` guard.

Confirmed impact against tests/fixtures/kogan_mobile.html: the fixture has
11 card divs covering 7 distinct plan tiers (15GB/60GB/80GB monthly +
140GB/250GB/350GB/500GB 365-day), but the parser currently returns only 5 --
silently dropping the 15GB and 80GB monthly plans entirely. The same bug
also breaks promo-price extraction on cards that DO get kept (e.g. a "$12
first month / $25 thereafter" card collapses to a bare $25 with
promo_price=None, losing the promo entirely).

Fix: update DOLLAR_RE to tolerate an optional space/whitespace between `$`
and the digits (e.g. `\$\s*(\d+\.?\d*)`), and re-verify against the fixture
that all 7 tiers now come through with correct promo vs. non-promo pricing
where applicable (member price vs "Non-Member Price:"/"Was $X" comparison
text).

Then update the test in tests/test_providers.py to assert the exact tier
count (7, not `>= 5`) and assert specific known values for the two
previously-dropped tiers (15GB/$20 monthly, 80GB/$40 monthly) plus confirm
the promo-price extraction works on the card that has both an intro and
ongoing price.

===========================================================
BUG 2: Boost Mobile drops every long-expiry (186/365-day) plan
===========================================================

File: scraper/providers/mobile/boost.py

The parser associates a GB figure with its expiry-period text using a
±300-character context window, but that window is too narrow to reach the
"Day Expiry" text for the long-expiry tiers -- so EXPIRY_RE never matches
for those cards and they get dropped entirely (per the module's own
docstring claiming "28-day tiers plus long-expiry 186/365-day tiers" -- the
365-day handling doesn't actually work).

Confirmed impact against tests/fixtures/boost_mobile.html: GB values like
240, 295, 365, 375 are present in the fixture text but every one is dropped
because no "Day Expiry" match falls inside the current window. Only the 14
short-expiry (7/14/28-day) tiers currently come through -- none of the
186-day or 365-day tiers do.

Fix: widen the context window enough to reliably reach the expiry text for
these cards (inspect the actual fixture HTML to find the real distance/DOM
structure -- don't just guess a bigger arbitrary number, find the card
boundary and search within that instead of a fixed character radius if
possible, since a card-scoped search is more robust than any fixed window
size). Re-verify all 3 long-expiry tiers (180/160GB 186-day, 300/295GB
365-day, 330/375GB 365-day) now parse correctly with the right price/GB/
expiry-period combination.

Then update the test in tests/test_providers.py to assert the exact total
tier count (currently checked with `>= 8` or similar -- fix to the real
total once both short- and long-expiry tiers are captured) and add specific
assertions for at least one long-expiry tier's price/GB/contract_length.

===========================================================
GENERAL INSTRUCTION FOR THIS ROUND
===========================================================

Don't loosen a test to make a bug pass invisibly again -- if a fixture
genuinely has N real plan cards, the test should assert N (or assert on the
specific named tiers), not a `>=` floor picked to match whatever the buggy
parser currently outputs. `>=` is fine ONLY when the live site itself might
add/remove plans over time in a way that's expected and not a parsing
concern -- it is not a substitute for verifying the parser correctly
handles every tier that's actually in the saved fixture right now.

After both fixes, run `pytest tests/ -v` and confirm all tests pass with the
corrected assertions (not just a higher pass count from weaker assertions).
Report the exact tier counts you found in each fixture and confirm they now
match what the parser returns.
