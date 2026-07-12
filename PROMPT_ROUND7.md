You are working in the `au-plans-scraper` repo. The previous session's
"wave 1" commit (ba50015) added 7 new provider modules plus fixtures, but
left them as an unfinished "initial implementation": none are registered in
run.py's PROVIDERS list, and none have any tests. A CI change that was made
alongside it (adding `continue-on-error: true` to the pytest step) has
already been reverted, since it was masking this gap rather than fixing it
-- don't re-add it.

Your job this round: finish and verify all 7, following the same standard
as every other provider in this repo (see scraper/providers/nbn/dodo.py and
scraper/providers/mobile/kogan.py as the reference quality bar). Do NOT just
wire them up as-is -- read through each one first, because several have
real fragility issues that need fixing before they can be trusted, listed
below per file.

===========================================================
GENERAL ISSUE ACROSS ALL 7: blind "two smallest prices" heuristic
===========================================================

Every one of these files does roughly:
```
vals = sorted(set(float(p) for p in prices if float(p) > 1))
if len(vals) >= 2:
    promo_price = vals[0]
    regular_price = vals[1]
elif vals:
    regular_price = vals[0]
```
This assumes the two smallest distinct `$` amounts anywhere in a card's text
are exactly [promo, regular] -- with no anchor to any actual "was $X" /
"then $X" / promo-labeled text. This is the same failure class that broke
Kogan twice already (rounds 3-4): any incidental price-like number in the
card (an add-on fee, a "save $X" badge, a per-GB rate, a comparison price)
will silently corrupt the result. For each provider, check the ACTUAL
fixture text for what genuinely marks a promo vs. regular price (a "was
$X", "then $X", "first N months" label, or similar -- same kind of markers
found in the already-shipped providers) and anchor extraction to that
marker specifically, the way kogan.py's WAS_RE/NON_MEMBER_RE/etc. do, rather
than trusting positional/sorted heuristics. Don't ship any provider this
round using the blind two-smallest-prices approach without first confirming
against the real fixture that it can't be fooled by an unrelated price.

===========================================================
Per-file issues to fix
===========================================================

**scraper/providers/nbn/tpg_nbn.py** -- uses the blind price heuristic (see
above) and a generic `plan-container` class guess. Verify this class
actually matches real plan cards in tests/fixtures/tpg_nbn.html (11285
lines -- a real fetch) and not some other container. Fix the price
extraction per the general issue above.

**scraper/providers/nbn/vodafone_nbn.py** -- two problems:
1. Speed tier is inferred by bucketing `mbps` into 3 hardcoded ranges (<=100
   -> "NBN 100/20", <=500 -> "NBN 500/50", else -> "NBN 1000/50") instead of
   reading the actual plan name/tier label from the page. If Vodafone has a
   tier this binning doesn't anticipate (e.g. NBN 25 or NBN 50), it'll be
   mislabeled. Check the real fixture for an actual tier-name element
   (plan title/heading) and use that instead of guessing from Mbps alone.
2. The card selector (`sc-24a45c1b` class prefix) is a styled-components
   generated hash -- these regenerate on nearly any frontend rebuild, so
   this scraper could silently stop matching anything after Vodafone's next
   deploy even with zero real content change. If there's a more stable
   selector available in the fixture (a semantic class, data-attribute, or
   heading structure), prefer that. If not, at minimum make scrape() raise
   clearly (not just return an empty list) when zero cards match, so this
   failure mode surfaces as an error rather than "0 plans scraped" being
   silently treated as just no plans -- match the existing behavior in
   run.py where an empty return raises "scrape() returned no plans".
   (Check whether it already does -- if fetch_static+find_all just returns
   an empty list without raising, add the check.)

**scraper/providers/nbn/spintel_nbn.py** -- uses the blind price heuristic
and a substring filter (`"wireless" in txt.lower() or "starter" in
txt.lower()`) to skip non-NBN plans -- verify against the real fixture this
doesn't also accidentally exclude a legitimate NBN plan whose card text
happens to mention "wireless" or "starter" for an unrelated reason (e.g. in
a disclaimer or cross-sell blurb elsewhere in the same card).

**scraper/providers/nbn/flip_nbn.py** -- two problems:
1. No real card scoping at all -- iterates every `div`/`section`/`article`
   on the whole rendered page filtered only by text length (30-600 chars).
   This is much weaker than every other provider in this repo and likely to
   produce false-positive "cards" from nav/footer/unrelated page sections
   that happen to contain an NBN-speed string and a dollar sign. Inspect the
   actual rendered structure (re-fetch and look at real card boundaries) and
   scope to an actual repeated card/component class instead.
2. `promo_period_months=6` is hardcoded whenever a promo is detected --
   this is invented, not extracted from the page. Find the actual promo
   duration text on Flip's real page and extract it properly, or leave the
   field None if no promo-duration text actually exists site-wide (don't
   guess a plausible-sounding number).

**scraper/providers/mobile/aussie_broadband_mobile.py** -- `embla__slide` is
a generic carousel-library class (Embla), potentially used for other
carousels on the same page (testimonials, images, etc.), not necessarily
unique to plan cards. Verify against the real fixture that every
`embla__slide` div found is actually a plan card, not some other carousel
content that happens to pass the length/GB/price filters.

**scraper/providers/mobile/dodo_mobile.py** -- uses the blind price
heuristic and hardcodes `promo_period_months=6` unconditionally, same
fabrication issue as Flip -- find the real promo duration text on Dodo's
mobile page (Dodo's own NBN scraper, dodo.py, extracts a real
`PROMO_MONTHS_RE` from its page text -- check if Dodo's mobile page has an
equivalent pattern and use it instead of a hardcoded constant).

**scraper/providers/mobile/moose_mobile.py** -- same no-real-scoping issue
as Flip (scans all div/article/section by text length + GB/$ presence, no
actual card class), and hardcodes `promo_period_months=3` unconditionally,
same fabrication issue. Inspect the real fixture for the actual card
structure and promo-duration text.

===========================================================
FOR EVERY ONE OF THE 7
===========================================================

1. Fix the issues above using the real saved fixture as ground truth
2. Add a test in tests/test_providers.py asserting on SPECIFIC real values
   (plan count, at least one tier's exact price/GB/speed), not just "returns
   some plans" -- follow the pattern of test_kogan_mobile or test_dodo_nbn
3. Register the module in run.py's PROVIDERS list, in the correct category
   ("nbn" or "mobile") with the correct transform function
4. Run `pytest tests/ -v` and confirm ALL tests pass (old + new) before
   considering a provider done
5. If, after fixing, any of these 7 turns out to not actually be reliably
   scrapeable against its own fixture (e.g. the fixture itself was a bad/
   incomplete capture, or the site turns out to need real anti-bot handling
   despite the initial pass not catching it), don't force it -- document why
   in NOTES.md instead of shipping a broken/unverified scraper

===========================================================
CONSTRAINTS
===========================================================

- Don't touch any already-registered, already-passing provider
- Don't re-add continue-on-error to the CI pytest step
- Update README.md's provider list once providers are actually registered
  and tested (not before)
- No new dependencies beyond requirements.txt unless clearly justified

DELIVERABLES: as many of the 7 as pass real verification, each registered
in run.py with a real test against its actual fixture; NOTES.md/README.md
updated to match; a summary of which of the 7 shipped clean, which needed
fixes (and what), and which (if any) couldn't be made reliable and why.
