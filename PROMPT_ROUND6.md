You are working in the `au-plans-scraper` repo (Python 3.12). Read NOTES.md
and README.md first for conventions and everything already covered/blocked/
dropped so far.

GOAL: this is "wave 1" of a larger provider expansion identified from real
2026 award/market data (Canstar Blue, Finder, WhistleOut) -- the biggest
gaps in current coverage. Unlike previous rounds, these have NOT been
pre-researched with live fetches -- you'll need to find the correct URL and
verify feasibility (static vs JS-rendered vs bot-blocked) for each yourself
before writing the parser, the same way earlier rounds' research was done.
If any of these turn out to be bot-blocked (like Belong/Optus/Southern
Phone/Woolworths Mobile already are), don't force it -- document it as
blocked in NOTES.md and move on, same as those.

Existing conventions to follow (look at scraper/providers/nbn/dodo.py,
scraper/providers/mobile/kogan.py, and scraper/providers/nbn/superloop.py or
scraper/providers/nbn/iinet.py for JS-rendered examples):
- Each provider module exposes PROVIDER, URL, REQUIRES_JS, and scrape() -> list[Plan]
- Use scraper/base.py's fetch_static() or fetch_js() -- never custom HTTP/browser code
- Build NbnPlan / MobilePlan pydantic models from scraper/schema.py
- Register each new module in run.py's PROVIDERS list
- Add a saved HTML fixture under tests/fixtures/ and a monkeypatched test in
  tests/test_providers.py for every new provider that's actually feasible
  (no live network calls in tests)
- Learn from rounds 3-5's bugs: watch for duplicate/responsive card markup
  needing dedup (key dedup on more than just one field if two distinct
  plans could share it), whitespace variations breaking price regexes
  (`\$\s*\d+` not `\$\d+`), and marketing-blurb text that could be
  mis-captured as a real price/promo -- scope your regex/context window to
  the specific card, not a fixed character radius or a page-wide search

===========================================================
WAVE 1 TARGETS (8 providers across 9 products -- NBN and/or mobile)
===========================================================

1. **TPG NBN** -- TPG's broadband/NBN plans (separate product from TPG
   mobile, which this project already scrapes at
   scraper/providers/mobile/tpg.py -- use that file as a reference for
   TPG's general site conventions, but this needs its own NBN page/module).
   TPG is Australia's 2nd-largest NBN retailer by market share and a
   repeat Canstar Blue value-award winner, so it's a high-value add.

2. **Vodafone NBN** -- likely at `https://www.vodafone.com.au/home-internet/nbn`
   (verify this is current/correct). Separate product from Vodafone mobile,
   already covered at scraper/providers/mobile/vodafone.py.

3. **SpinTel** -- NBN AND mobile, both notable: a named budget NBN pick
   (WhistleOut "Best Fast NBN Provider", often cheapest NBN 25 intro price)
   and Canstar's 2026 Outstanding Value SIM-Only Mobile winner. Implement
   both as separate provider modules if both product lines are scrapeable.

4. **Aussie Broadband Mobile** -- Aussie Broadband's mobile SIM plans
   (separate from their NBN plans, already covered at
   scraper/providers/nbn/aussie_broadband.py). Canstar's 2026 Most
   Satisfied Customers winner for postpaid SIM-only.

5. **Moose Mobile** -- appears to have BOTH an NBN product (2x Canstar
   Blue "Outstanding Value NBN Plan" winner) and a mobile SIM product.
   Verify both exist as real, separate offerings and implement whichever
   are feasible.

6. **Flip** -- NBN only. CONFIRMED real and currently operating at
   `flipconnect.com.au` (also reachable via flip.com.au) -- this project's
   own README/NOTES previously and incorrectly said Flip was "not a real
   ISP, a logistics company" and dropped it; that was wrong, reverse it.
   Offers unlimited NBN 25/50/100 plans ~$39-$109.90/mo with senior/
   pensioner/DVA discount variants (3-9% off) -- worth capturing the
   discount-tier plans distinctly if the schema allows, otherwise capture
   the standard tier and note the discount variants exist.

7. **Dodo Mobile** -- Dodo's mobile SIM plans (separate from Dodo NBN,
   already covered at scraper/providers/nbn/dodo.py). Runs on the Optus
   network (not Vodafone) -- confirm this when setting the `network` field.
   WhistleOut's pick for best 30GB+ SIM-only plan as of July 2026.

===========================================================
CONSTRAINTS
===========================================================

- For each target, first confirm the real plans-page URL and whether it's
  static or JS-rendered or bot-blocked -- don't guess a URL pattern and
  assume it's right (multiple earlier rounds hit wrong-URL issues, e.g.
  amaysim's /mobile-plans silently resolving to a checkout page instead of
  404ing)
- If a target turns out bot-blocked (decoy page, connection resets,
  timeouts, domain-wide 403/CAPTCHA), stop there for that one, add it to
  NOTES.md's "blocked" section with the same detail level as the existing
  Belong/Optus/Southern Phone/Woolworths Mobile entries, and move on --
  don't spend excessive effort forcing a JS/anti-bot workaround
- Don't touch any already-shipped provider or its tests
- Keep everything passing `pytest tests/`
- No new dependencies beyond requirements.txt unless clearly justified

DELIVERABLES: as many of the 8 wave-1 providers as turn out feasible, each
with module + fixture + test; NOTES.md updated with findings for both the
feasible ones (URL, structure notes) and any that turned out blocked;
README.md's provider list and held-back list updated to match; the Flip
"dropped, not a real ISP" note specifically corrected. Report back which of
the 8 shipped, which were blocked, and any that turned out to not actually
have a distinct product (e.g. if Moose Mobile turns out to be mobile-only
after all, despite the NBN award mention).
