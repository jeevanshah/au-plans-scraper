You are working in the `au-plans-scraper` repo (Python 3.12). Read NOTES.md
(especially the "Round 2 provider research" section) and README.md first --
all the site-structure research below is already done, don't re-fetch pages
to rediscover it.

GOAL: add 6 new providers in one batch, plus 3 small cleanup items left over
from round 1 (the amaysim scraper + resilience hardening already shipped and
is verified working -- don't touch it except where noted).

Existing conventions to follow (look at scraper/providers/nbn/dodo.py,
scraper/providers/mobile/amaysim.py, and scraper/providers/nbn/superloop.py
as reference implementations):
- Each provider module exposes PROVIDER, URL, REQUIRES_JS, and scrape() -> list[Plan]
- Use scraper/base.py's fetch_static() (requests+BS4) or fetch_js() (Playwright)
  helpers -- never write your own HTTP/browser code
- Build plans as NbnPlan / MobilePlan pydantic models from scraper/schema.py
- Register each new module in run.py's PROVIDERS list
- Add a saved HTML fixture under tests/fixtures/ and a monkeypatched test in
  tests/test_providers.py for every new provider, following the existing
  pattern (no live network calls in tests)

===========================================================
TASK 1-5: five new static mobile scrapers
===========================================================

New files: scraper/providers/mobile/{vodafone,kogan,felix,boost,aldimobile}.py
(pick sensible module names). All REQUIRES_JS = False.

1. Vodafone -- https://www.vodafone.com.au/plans/sim-only
   - 3 tiers: Small 65GB/$58, Medium 220GB/$68, Large 420GB/$78/mth,
     month-to-month, no lock-in
   - Tier markup repeats twice on the page (desktop/mobile responsive
     blocks) -- dedupe so each tier only produces one MobilePlan
   - Regex idea: `(\d+GB)\s*\$(\d+) per month`
   - One promo end-date string exists ("from 23/01/2025 to 31/08/2026" on a
     student bonus offer) -- capture it if present, don't fail if absent

2. Kogan Mobile -- https://www.koganmobile.com.au/plans
   - Two families: Monthly (15GB/$20 up to 80GB/$40) and 365-Day
     (140-500GB, $159-$205, with member-vs-non-member pricing shown --
     use the member/lower price as promo_price and the non-member price as
     price_monthly when both appear)
   - Promo end-dates like "11:59PM AEST 12/07/2026" -- regex
     `11:59\s?[AP]M\s?AE[SD]T\s+\d{1,2}/\d{1,2}/\d{4}`

3. Felix Mobile -- https://www.felixmobile.com.au/plan (singular URL,
   NOT /plans)
   - 3 tiers: 25GB $25->$12.50/mth (50% off 2mo), 50GB $30->$15/mth (50% off
     3mo), Unlimited(40Mbps) $40->$20/mth (50% off 3mo), month-to-month
   - Check the `__NEXT_DATA__` script tag first for structured plan JSON --
     prefer it over regex/card-scraping if it contains clean plan data;
     fall back to HTML parsing if it doesn't
   - No hard promo end-date exists (offers are "until withdrawn") --
     promo_end_date should be None for these plans, that's correct, not a bug

4. Boost Mobile -- https://www.boost.com.au/plans (NOT
   /plans/sim-only-plans, that 404s)
   - 28-day tiers: $14/8GB, $28/21GB, $39/80GB, $15/110GB promo ("was $49"),
     $59/125GB, $74/160GB
   - Long-expiry: $180/160GB (186-day), $300/295GB (365-day), $330/375GB
     (365-day, "was $365")
   - Promo/sale-end text as plain strings, e.g. "sale ends 20 July" or
     "until 10 August 2026" -- extract with a relative/absolute date parser
     similar to scraper/base.py's existing parse_relative_end_date /
     parse_absolute_end_date, adding a new regex variant if neither matches
     this phrasing exactly

5. ALDImobile -- https://www.aldimobile.com.au/plans/
   - `.product` card class, price in `<h4>$XX</h4>`, data/features in
     sibling `<ul><li>` elements
   - Tiers: Mobile 30-day ($23/12GB up to $59/175GB), Family 30-day (2-6
     services, $55-$125 -- SKIP these, they're multi-service bundles, not
     single SIM-only plans, out of scope for this schema), data-only 365-day
     ($95-$365 -- SKIP, data-only isn't a mobile voice+data plan), Long Life
     365-day ($289/300GB -- include this one)
   - "Price Promise" text locks pricing until a stated date if activated by
     a stated date -- extract the lock-until date as promo_end_date when
     present
   - Speed caps (100/150/250 Mbps) stated as plain text per plan -- no field
     for this in MobilePlan, ignore it

===========================================================
TASK 6: iiNet NBN scraper (needs Playwright)
===========================================================

New file: scraper/providers/nbn/iinet.py, REQUIRES_JS = True
- URL: https://www.iinet.net.au/internet-product/broadband/nbn/plans/fibre
- Use fetch_js() like scraper/providers/nbn/superloop.py does -- plan
  tiers/prices are client-rendered, only promo copy is in raw HTML
- Promo text seen: "$20/mth off for 6 months" (NBN25/50 tiers), "$25/mth off
  for 6 months" (NBN100/500), "$30/mth off for 6 months"
  (Superfast/Ultrafast) -- use these to build promo_period_months
- Tech-type text present: FTTP, FTTN, FTTB, HFC, VDSL2, Fixed Wireless --
  feed through classify_tech_type() from scraper/base.py where applicable
- If the plan cards don't render even with fetch_js's default wait_until, add
  a wait_selector or settle_ms like Superloop's scraper does for its
  Gatsby+React hydration delay -- inspect the actual rendered page first to
  find the right card selector before hardcoding one

===========================================================
TASK 7: round-1 cleanup (small, do these too)
===========================================================

7.1 -- Fix README.md's "Providers" / held-back section:
   - amaysim is no longer held back (it shipped in round 1) -- move it to
     the main provider list
   - Add the 6 new providers from this round to the main list once they're
     implemented and passing tests
   - Update "held back" to list Belong, Optus, Southern Phone, and
     Woolworths Mobile (rebranded "everyday") -- all confirmed to need real
     anti-bot/browser-fingerprint handling this project doesn't have yet
   - Add a one-line note that MyRepublic was investigated and dropped
     (exited the AU NBN market entirely, not a scraping gap) so it isn't
     mistaken for an unresearched provider in the future

7.2 -- Restore run.py's trailing newline (round 1 left the file without one
   -- `git diff` shows "No newline at end of file"). Purely cosmetic, no
   logic change.

7.3 -- Leave `_sanity_check_deals()` as-is (soft/logging-only, never
   hard-fails). This is intentional -- real price changes are legitimate and
   shouldn't break a scrape run. Don't change its behavior.

===========================================================
CONSTRAINTS
===========================================================

- Don't touch amaysim.py or any other already-shipped/passing provider
  scrapers -- only add new ones and do the 3 cleanup items above
- Don't attempt Belong, Optus, Southern Phone, Woolworths Mobile/everyday, or
  MyRepublic -- all explicitly out of scope this round (see NOTES.md for why)
- Keep everything passing `pytest tests/` -- fetch each new provider's live
  page once to save a fixture, write a monkeypatched test asserting on real
  values (plan count, provider name, network, specific tier prices), same
  pattern as existing tests
- No new dependencies beyond what's in requirements.txt unless clearly
  justified

DELIVERABLES: 6 new provider modules + fixtures + tests, run.py updated
(PROVIDERS list + trailing newline restored), README.md updated per 7.1, and
a short summary of what was implemented vs. anything that turned out
trickier than expected (e.g. if iiNet's JS rendering needs a different
wait strategy than assumed, or if a provider's live page has changed since
this research was done).
