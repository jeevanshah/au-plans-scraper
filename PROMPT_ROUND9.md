You are working in the `au-plans-scraper` repo. Before anything else, read
this carefully: the last round's summary claimed a fix to
scraper/providers/mobile/dodo_mobile.py that, on verification, was never
actually applied -- `git diff` between that round's starting and ending
commit shows the file completely unchanged. Whatever happened, the reported
work and the actual file state didn't match. This round, prove every claim
with evidence, not just a description of what you intended to do:

- For every file you change, be able to show the actual diff/before-after
  content as part of your report
- Run the specific test/command that demonstrates the fix works, and
  include its real output
- Don't describe a fix in prose without having actually written and saved
  the code change

Good news first: the P0 run.py import fix from last round is confirmed
genuinely working -- `python run.py` runs end-to-end successfully, all 19
registered providers scrape without error. Don't touch run.py's imports,
they're fine now.

===========================================================
FIX 1 (for real this time): Dodo Mobile's blind price heuristic
===========================================================

File: scraper/providers/mobile/dodo_mobile.py

Current code (confirmed unchanged from the ORIGINAL wave-1 version):
```
price_monthly = max(vals[0], vals[1])
promo_price = min(vals[0], vals[1])
```
This picks regular/promo price by raw numeric comparison, not by reading
which number is actually labeled as the regular vs. promo price in the
page's real text/markup. Fetch the live Dodo mobile page (or re-examine
tests/fixtures/dodo_mobile.html closely) and find the actual textual
structure that distinguishes them -- e.g. is there a "was $X" string, a
distinct HTML element/class for the pre-discount price vs. the discounted
price, or a consistent ordering tied to specific label text (not just
"whichever appears first in extracted text")? Anchor extraction to that
real structure.

Verify this isn't just "assume order" in a different disguise: find (or
construct) a test case where the SMALLER of the two numbers is actually the
REGULAR price and the LARGER is the promo price (unusual, but possible if a
card has some unrelated smaller dollar figure like a per-GB rate or add-on
fee) -- if your fix still can't handle that because it's secretly still
doing numeric min/max, it's not actually fixed. If Dodo's real page has no
such case and price/promo really is always distinguishable by explicit
label text (not just number size), use that label text as the anchor
regardless.

Update the test for Dodo Mobile to assert against the specific labeled
values from the real fixture, and show the diff of dodo_mobile.py in your
report as proof the file was actually modified.

===========================================================
FIX 2 (for real this time): Vodafone NBN's tier names still aren't from the page
===========================================================

File: scraper/providers/nbn/vodafone_nbn.py

Current code:
```
TIER_MAP = {98: ("NBN 100/20", "Home Fast"), 500: (...), 740: (...)}
```
This is a hardcoded dict keyed by Mbps value with plan names typed in by
hand -- it is NOT reading "Home Fast" / "Home Superfast" / "Home Ultrafast"
from the actual page, despite the file's docstring claiming it does. Fetch
the live Vodafone NBN page (or examine tests/fixtures/vodafone_nbn.html
closely) and find the actual heading/label element or text pattern that
names each tier, then extract that directly per-match instead of looking it
up in a static dict. If, after real investigation, the page genuinely has
NO extractable tier-name text anywhere near the price/speed data (unlikely,
but possible), say so explicitly and explain why a hardcoded map is the
only option -- don't just leave the same dict in place and claim it's fixed
without that justification.

Also: the per-tier promo_months window fix from last round is real and can
stay, but it's currently unproven because all 3 tiers in the fixture happen
to share the same 12-month promo value. If you can find or construct a
case (in the real fixture, or a live re-fetch) where two tiers actually
have different promo durations, add a test that proves per-tier scoping
produces DIFFERENT values for different tiers -- not just three assertions
that all happen to equal 12.

Show the diff of vodafone_nbn.py in your report as proof of what changed.

===========================================================
FIX 3: Documentation (still outstanding from round 7)
===========================================================

Update README.md's provider list to include Dodo Mobile, Aussie Broadband
Mobile, Vodafone NBN, and SpinTel NBN (all 4 actually shipped and registered
in run.py). Add a NOTES.md entry noting TPG NBN, Flip NBN, and Moose Mobile
remain unshipped, with the reason from round 7's findings, so they aren't
re-investigated from scratch.

===========================================================
CONSTRAINTS
===========================================================

- Don't touch run.py, SpinTel, or Aussie Broadband Mobile -- all three
  confirmed working already
- Don't touch TPG NBN, Flip NBN, or Moose Mobile
- Run `pytest tests/ -v` AND `python run.py` end-to-end, report both real
  outputs
- For Fix 1 and Fix 2 specifically, include the actual git diff (or
  before/after file content) in your report -- a prose description without
  a verifiable diff will not be trusted this round, given what happened
  last time

DELIVERABLES: a real, diff-verifiable fix to dodo_mobile.py anchored to
actual page structure (not numeric min/max); a real, diff-verifiable fix to
vodafone_nbn.py's tier-naming (reading from the page, not a hardcoded map)
or a documented justification for why that's not possible; README.md/
NOTES.md updated; both pytest and a live run.py execution's real output
included as evidence.
