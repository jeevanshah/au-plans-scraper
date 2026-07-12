You are working in the `au-plans-scraper` repo. This is urgent -- the
previous round's commit broke the entire scraper orchestrator, and it also
left two "fixes" that were claimed as real but are actually superficial.
Fix all of this before anything else.

===========================================================
P0 -- CRITICAL: run.py cannot run at all, blocks every provider
===========================================================

`run.py` currently has:
```
from scraper.providers.mobile import aussie_broadband as mobile_aussiebb
```
But the actual file is `scraper/providers/mobile/aussie_broadband_mobile.py`,
not `aussie_broadband.py`. This is a module-level import that fails
immediately:
```
ImportError: cannot import name 'aussie_broadband' from 'scraper.providers.mobile'
```
This means `python run.py` cannot execute AT ALL right now -- not "one
provider fails," the entire script crashes before scraping a single
provider. This went undetected because `pytest tests/` imports provider
modules directly and never actually imports/exercises `run.py` itself, so
the test suite passing gave false confidence.

Fix: correct the import to match the real filename. Then, critically,
VERIFY BY ACTUALLY RUNNING `python run.py` end-to-end against live sites (or
at minimum `python -c "import run"` to confirm the module loads cleanly) --
do not consider this done just because `pytest tests/` passes. Passing
tests and a working run.py are two different things, and this exact gap is
what caused this bug to ship. Report the real `python run.py` output
(provider-by-provider scrape results) as evidence, not just a test count.

===========================================================
P1: Dodo Mobile's promo fix is still the old blind heuristic underneath
===========================================================

File: scraper/providers/mobile/dodo_mobile.py

The current code gates on a real `PROMO_BANNER_RE` ("N% OFF FOR FIRST N
MONTHS") before touching prices -- good, that part is real. But once
gated, it still does `max(vals[0], vals[1])` / `min(...)` on the first two
dollar amounts found in the card text to decide regular vs. promo price.
This is the same blind heuristic as before, just conditioned on the banner
existing rather than genuinely reading which specific number in the text is
labeled as the "was"/regular price vs. the promo price.

Fix: find the actual textual structure that distinguishes the regular price
from the promo price on Dodo's mobile page (e.g. is the regular price
struck-through, prefixed with "was", presented before/after the banner text
in a specific consistent order, or in a distinct HTML element/class from the
promo price?). Anchor extraction to that specific structure, not to
"whichever of the first two numbers is bigger/smaller." Verify against the
real fixture with a card that might have a misleading number (an add-on
price, a per-GB rate, etc.) if one exists, to prove the anchor actually
discriminates correctly rather than coincidentally working on today's data.

===========================================================
P1: Vodafone NBN's tier-naming fix is fake, and promo_months is now wrong for all but one tier
===========================================================

File: scraper/providers/nbn/vodafone_nbn.py

Two problems:

1. `MBPS_TO_TIER = {98: "NBN 100/20", 500: "NBN 500/50", 740: "NBN 1000/50"}`
   is NOT a fix -- it's the exact same hardcoded Mbps-bucketing approach
   from before, just moved into a dict literal instead of if/elif ranges.
   It still doesn't read any real tier name/label from the page. Find the
   actual plan-name/heading text associated with each tier on Vodafone's
   real NBN page and extract that directly, so a tier this project hasn't
   seen before (e.g. if Vodafone adds an NBN 25 or NBN 50 plan) doesn't
   silently get mapped to the wrong label or dropped.

2. The scraper now does ONE page-wide `PROMO_MONTHS_RE.search(text)` and
   reuses that single match's value for every tier in the loop, regardless
   of which specific plan that promo text actually belongs to. Since the
   scraper moved from card-scoped selectors to whole-page regex (to avoid
   the fragile styled-components hash class -- that part of the change was
   fine), it introduced this new bug: if different tiers have different
   promo durations, or if only one tier has a promo, every returned plan
   will incorrectly show the same promo_period_months. Fix this by scoping
   the promo-months extraction to each specific price/tier match's local
   context (e.g. the text between this tier's price and the next tier's
   price/heading in the page's linear text), not a single whole-page match
   applied everywhere.

Verify both fixes against the real fixture (tests/fixtures/vodafone_nbn.html)
and update/add test assertions that would have caught these two problems
specifically (e.g. assert each tier's promo_period_months independently, and
assert a tier name that isn't just re-deriving the Mbps value).

===========================================================
P2: Documentation gap
===========================================================

Neither README.md nor NOTES.md were updated in the round-7 commit to
reflect that Dodo Mobile, Aussie Broadband Mobile, Vodafone NBN, and
SpinTel NBN actually shipped. Update README.md's provider list to include
these 4 (Dodo and Vodafone already have NBN-only entries -- note these are
their separate mobile/NBN product lines, not duplicates), and add a NOTES.md
entry documenting: TPG NBN, Flip NBN, and Moose Mobile remain unshipped and
why (per round 7's findings -- no stable card anchor / fixture didn't
capture real plan data), so this isn't re-investigated from scratch later.

===========================================================
CONSTRAINTS
===========================================================

- Fix P0 first -- nothing else matters if run.py can't execute
- Don't touch SpinTel or Aussie Broadband Mobile -- those two were verified
  as genuinely fixed already, leave them alone
- Don't touch TPG NBN, Flip NBN, or Moose Mobile -- still correctly unshipped
- Run BOTH `pytest tests/ -v` AND an actual `python run.py` invocation (or
  at minimum confirm `python -c "import run"` succeeds) before reporting
  this done. A green pytest run alone is not sufficient evidence this time.

DELIVERABLES: working run.py (proven by actually running it, not just
importing provider modules in tests), genuinely-anchored Dodo Mobile promo
extraction, genuinely-fixed Vodafone tier-naming and per-tier promo-months,
README.md/NOTES.md updated, and a report confirming each fix was verified
against real fixture/live data, not just re-asserted.
