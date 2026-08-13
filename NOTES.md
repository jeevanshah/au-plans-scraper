# Project notes

Working notes on this scraper's purpose and provider research. Not user-facing
docs (see README.md for that) -- this is context for whoever picks up scraper
work next.

## Purpose & app integration

`au-plans-scraper` exists to feed **App Library Ledger** (Flutter app at
`C:\Users\Deep\Desktop\mobile-app\app_library_ledger`), a subscription-tracking
app ("Track. Save. Thrive.") where users log recurring subscriptions and get
shown cheaper alternative offers.

The app's "Offers" feature (`lib/screens/offers_screen.dart`,
`lib/models/offer.dart` `SavingsOffer`) has a data model that near-exactly
matches this scraper's deal-card JSON shape (`provider`, `title`,
`promoPrice`, `regularPrice`, `promoMonths`, `validUntil`, `serviceType`,
`tier`, `techType`, etc.) -- this scraper is meant to be the app's real
backing data source, replacing a placeholder feed.

**Integration gap (as of 2026-07-11):** `lib/services/offers_service.dart`
hardcodes `offersUrl` to
`https://raw.githubusercontent.com/jeevanshah/app-library-ledger/main/offers.json`
(a different repo/filename), NOT this scraper's jsDelivr URL
(`https://cdn.jsdelivr.net/gh/<user>/au-plans-scraper@main/data/deals.json`).
No wiring exists yet between the two repos. Since the data shapes already
match, connecting them should just require swapping that one constant -- no
app-side model changes needed.

Keep the two data contracts in sync going forward: changes to
`scraper/transform.py`'s output shape should stay compatible with
`SavingsOffer` in the app, and vice versa once integration happens.

## Held-back provider research (Belong / Optus / amaysim)

The README lists three providers "held back pending manual verification":
Belong, Optus, amaysim. Live WebFetch research done 2026-07-11 to scope
whether/how each could be scraped:

### amaysim (mobile only) -- SHIPPED (round 1, 2026-07-11)

- Working URL: `https://www.amaysim.com.au/sim-plans` (also mirrored at
  `/plans/mobile-plans`). Avoid `/mobile-plans` -- that path 200s but
  resolves to a checkout/cart page, not the plan list (this mismatch is
  almost certainly what the README's "inconsistent responses" note was
  about, not real bot-blocking).
- Fully static AEM-rendered HTML, no JS/Playwright needed, no anti-bot
  protection detected (plain `requests` + UA header works).
- 12 plans across 4 groups (28-day, long-expiry e.g. 240GB/365-day,
  data-only, 7-day). Each plan is an
  `<article class="product-card product-card-plan ... product-id-XXXXX" data-plan-id="XXXXX" data-base-price="..." data-base-data="...">`
  with `data-mp-data` (GB), `data-mp-price` (current/promo price),
  `data-mp-price-sub`/`data-mp-price-sub2` (savings text), and a free-text
  `data-mp-terms` field like *"Ongoing is $320 for 240GB/365 days. Ends 20th
  July."* -- regex `Ongoing is \$(\d+) for (\d+)GB/(\d+) days\. Ends (\d+\w+ \w+)`
  gets ongoing price/GB/renewal period/promo end date in one shot.
- Bonus: page also embeds a
  `window.dataLayer.push({"product_list":[{name, id, price, alias, plan_type}]})`
  JSON blob per section -- cleaner than card scraping, though marked
  "Deprecated" in an HTML comment so treat as a nice-to-have fallback, not
  the primary source.
- Runs on the Optus network (mentioned repeatedly in page text/T&Cs); no
  Circles.Life branding despite amaysim having absorbed those customers.

### Belong (NBN + mobile) -- blocked, needs a different approach

- Real plan URLs are `https://www.belong.com.au/go/internet` (NBN) and
  `https://www.belong.com.au/go/mobile` (mobile) -- NOT `/nbn-plans` or
  `/mobile-plans` (those don't exist).
- Every URL on the domain currently returns an identical, fully
  server-rendered decoy "Our website is offline right now... doing what we
  can to get it back up" page to non-browser HTTP clients -- no Cloudflare
  interstitial, no CAPTCHA, no 403, just a soft branded fake-outage wall.
  This is a WAF/bot-management pattern serving fake content to suspected
  bots rather than hard-blocking them.
- Confirmed via WebSearch + third-party comparators (WhistleOut,
  OzBroadbandReview, Reviews.org) that the real site is up and has current
  2026 pricing (NBN Starter ~$55/mo intro then $75/mo up to $110/mo; mobile
  SIM $30-~$60/mo across 25GB/100GB/160GB tiers) -- the block is
  specifically against automated fetching, not a real outage.
- No plan-card HTML structure could be observed at all (page has zero plan
  content). A working scraper here will need real browser session handling
  (Playwright with realistic fingerprint/cookies, possibly non-datacenter
  IP) before any parsing logic can even be designed -- plain `requests` or
  basic Playwright `fetch_js` (as used for Superloop/TPG) is unlikely to be
  enough. Treat as the hardest of the three; may not be worth the
  effort/risk for a low-value provider.

### Optus (NBN + mobile) -- worse than Belong, likely not worth pursuing

- Every fetch attempt to optus.com.au (7 URLs tried, homepage/NBN/mobile/even
  a static PDF) simply timed out (60s) or hit ECONNRESET -- no page content,
  no 403, no CAPTCHA HTML ever came back. A control fetch to
  telstra.com.au succeeded fine in the same session, ruling out a generic
  tool problem.
- This looks like connection-level throttling/silent-drop bot mitigation
  (Akamai/Cloudflare-style stalling of non-browser-fingerprinted requests),
  not a parseable challenge you can detect and retry around -- it just looks
  like a flaky/timeout failure in logs. Confirms the README's "inconsistent
  responses" note.
- Real plan URLs likely include `optus.com.au/internet/nbn` (NBN, "$69/month
  for 6 months" per search snippets) and `optus.com.au/broadband-nbn`, but no
  working mobile SIM-only URL was even confirmed. No HTML structure, class
  names, or plan tiers observed at all -- this is pure web-search-derived
  info, not fetched content.

### How to apply

Treat Belong and Optus both as stretch goals requiring real anti-bot handling
(residential IP / full browser fingerprint / session cookies) -- don't assume
either is scrapeable with the project's existing `fetch_static`/`fetch_js`
helpers as-is. Of the two, Optus looks even less tractable than Belong since
it doesn't even return a decoy page to inspect.

## Round 2 provider research (2026-07-11)

After round 1 shipped amaysim, the user asked to stop going one provider at a
time and batch-research the next tier of major AU NBN/mobile providers
instead. Findings from that batch:

### EASY -- static HTML, no anti-bot, ready to scrape now

- **Vodafone (mobile)** -- `https://www.vodafone.com.au/plans/sim-only`.
  3 tiers: Small 65GB/$58, Medium 220GB/$68, Large 420GB/$78/mth, all
  month-to-month, no lock-in. Tier markup repeats twice (desktop/mobile
  responsive blocks) -- dedupe by first match. Medium/Large add international
  minutes. One promo end-date string seen: "from 23/01/2025 to 31/08/2026"
  (student bonus offer). No dataLayer/JSON blob; plain regex works, e.g.
  `(\d+GB)\s*\$(\d+) per month`.
- **Kogan Mobile** -- `https://www.koganmobile.com.au/plans`. Two families:
  Monthly (15GB/$20, 60GB intro $12->$25, 80GB/$40 w/ 5G) and 365-Day
  (140GB/$179.90, 250GB/$159 member price w/ "Non-Member Price: $300" style
  comparison, 350GB/$179, 500GB/$205). Discount badges ("52% off", "was
  $190"). Explicit promo end-dates like "11:59PM AEST 12/07/2026" -- regex
  `11:59\s?[AP]M\s?AE[SD]T\s+\d{1,2}/\d{1,2}/\d{4}`. Clean semantic HTML, no
  JSON blob.
- **Felix Mobile** -- `https://www.felixmobile.com.au/plan` (singular --
  `/plans` 404s). 3 tiers: 25GB $25->$12.50/mth (50% off 2mo), 50GB
  $30->$15/mth (50% off 3mo), Unlimited(40Mbps) $40->$20/mth (50% off 3mo),
  all month-to-month. Next.js but server-rendered/SSG so plain HTML has the
  content; has a `__NEXT_DATA__` script tag worth checking first as a
  cleaner structured source before falling back to regex. No hard promo
  end-date text -- offers noted as "until withdrawn" (promo code "FELIX50").
- **Boost Mobile** -- `https://www.boost.com.au/plans` (not
  `/plans/sim-only-plans`, that 404s). 28-day tiers $14/8GB up to $74/160GB,
  plus long-expiry 186-day ($180/160GB) and 365-day ($300/295GB, $330/375GB)
  tiers. Promo text as plain strings: "sale ends 20 July", price-lock
  "until 10 August 2026". Consistent repeated plan-tile markup, same
  BeautifulSoup approach as TPG/amaysim.
- **ALDImobile** -- `https://www.aldimobile.com.au/plans/`. `.product` card
  class, price in `<h4>$XX</h4>`, data/features in sibling `<ul><li>`. Tiers:
  Mobile 30-day ($23/12GB up to $59/175GB), Family 30-day (2-6 services,
  $55-$125), data-only 365-day ($95-$365), Long Life 365-day ($289/300GB).
  "Price Promise" text locks pricing until a stated date if activated by a
  stated date -- a clean extractable promo-end-date phrasing. Speed caps
  (100/150/250 Mbps) also stated as plain text per plan. CIS PDFs linked per
  plan if cross-validation is ever needed.

### NEEDS_JS -- Playwright required, no bot protection otherwise

- **iiNet (NBN)** --
  `https://www.iinet.net.au/internet-product/broadband/nbn/plans/fibre`
  (there's also a Fixed Wireless variant at `.../plans/wireless`). No
  anti-bot blocking (200 OK, no Cloudflare/CAPTCHA), but plan tiers/prices
  are client-rendered -- only promo copy (e.g. "$20/mth off for 6 months" on
  NBN25/50, "$25/mth off for 6 months" on NBN100/500, "$30/mth off for 6
  months" on Superfast/Ultrafast) and tech-type mentions (FTTP, FTTN, FTTB,
  HFC, VDSL2, Fixed Wireless) are in the raw HTML. Same pattern as this
  project's existing Superloop/TPG scrapers (`fetch_js`).

### DROP -- no longer applicable, don't re-investigate

- **MyRepublic** -- exited the Australian NBN market Dec 2022/Jan 2023; every
  URL (including bare root) returns HTTP 530, corroborated by web search
  (customers migrated to Superloop, already covered here). Not a scraping
  problem -- there's no product to scrape.

### BLOCKED -- hard anti-bot, same tier as Belong/Optus

- **Southern Phone (NBN)** -- domain-wide HTTP 403 including the homepage
  itself (typical WAF/Cloudflare bot-fight signature, not a wrong-URL issue).
  Correct page is likely
  `https://www.southernphone.com.au/personal/broadband/nbn-broadband` per
  search, unverified. A Critical Information Summary PDF was found openly
  hosted outside the WAF (`southernphone-prod.dotcms.cloud/...CIS...pdf`) --
  untested as a fallback data source.
- **Woolworths Mobile** -- rebranded to "everyday"
  (`mobile.everyday.com.au`); every request gets `ECONNRESET` even on the
  bare root domain -- connection-level blocking (Akamai-style), same failure
  signature as Optus, not a JS-rendering issue.

### How to apply (round 2)

Implement the 5 EASY mobile providers (Vodafone, Kogan, Felix, Boost,
ALDImobile) plus iiNet NBN (needs `fetch_js`, same as Superloop/TPG) in one
batch. Skip Southern Phone and Woolworths Mobile/everyday for now -- same
"needs real anti-bot/browser-fingerprint work" category as Belong/Optus.
Don't re-investigate MyRepublic -- confirmed dead product in AU, not a
scraping gap.

## Wave 1 completion (2026-07-12): TPG NBN, Flip NBN, Moose Mobile

Round 7 shipped 4 of wave 1's 7 providers but left TPG NBN, Flip NBN, and
Moose Mobile unregistered -- their fixtures didn't capture real plan data.
All three are now genuinely fixed and shipped. Root causes and fixes, so
this isn't re-investigated from scratch:

- **TPG NBN** -- the real problem wasn't the fixture, it was that TPG's NBN
  page (`https://www.tpg.com.au/nbn`) is a legacy AngularJS app whose raw
  HTML is *un-rendered template source* (`{* ... *}` expressions) -- final
  pricing needs both JS evaluation and a real address entered for
  eligibility/tech-type detection. However, the literal price values for
  both branches of each promo ternary are embedded directly in the
  template source as string arguments, e.g. `promotion.hasSixMonthPromotion(...)
  ? getDollars('69.99') : getDollars('94.99')` -- so real prices can be
  read straight out of the raw HTML via `getDollars\('([\d.]*)'\)\s*:\s*getDollars\('([\d.]*)'\)`,
  no browser/address needed. Card container class is `planCards` (not
  `plan-container`, which never existed on this page). Each named tier
  (e.g. "NBN100") repeats once per possible connection tech (FTTN, FTTC,
  Fibre, FTTB, HFC, Wireless) via `ng-show`-gated duplicates -- dedupe by
  tier name, keep first-seen (FTTN, the most common TPG connection type).
  Genuine NBN bundle plans vs. wireless-alternative products (5G Plus/
  Premium, "FTTB Max"/FTTB25/FTTB100, Home Wireless Broadband) are
  distinguished by the card's `ng-show` promo SKU containing `_Bundle_` --
  a real signal, not a name-guess.

- **Flip NBN** -- the captured fixture was the *homepage*
  (`flipconnect.com.au/`), which only has a "$48/month" teaser, not real
  per-tier pricing. The actual plans page is
  `https://flipconnect.com.au/cheap-nbn-plans`. It's a Vue/Vuetify SPA;
  plan cards are the direct `.flex-shrink-0` children of the
  `.plans-scroll-inner` carousel container -- a precise DOM anchor, not a
  page-wide scan of every div/section/article by text length. Within each
  card: `.text-flipRed` holds the marketing tier name, `.text-price` holds
  the promo price, and the regular price + promo duration come from the
  card's own "For 6 months, then $65.90 ongoing*" text.

- **Moose Mobile** -- same homepage-fixture problem, plus the plan cards
  render a few seconds after the page's "load" event fires -- the original
  `settle_ms=5000` fetch captured the page before they existed at all;
  `settle_ms=8000` against `https://moosemobile.com.au/` (the plans ARE on
  the homepage, just slow to render) reveals them. Cards are Swiper.js
  carousel slides with the `card-mobile` class; GB is in
  `.card-mobile__header .h2`, price in `.card-mobile__section.price .h3`.
  All 4 tiers are flat monthly prices, no promo/regular split.

Also fixed while completing this: `transform.py`'s `_make_id()` collided
for two distinct plans sharing a data allowance but differing in contract
length (Boost's 160GB/28-day and 160GB/186-day tiers both produced
`boost-mobile-160gb-2026-07`) -- the id now incorporates `contract_length`
for mobile plans. Dodo Mobile's and Vodafone NBN's price/tier-naming
"fixes" from rounds 7-8 turned out to still be a blind heuristic and a
hardcoded map respectively (see the round-8/9 prompts for the full story);
both are now genuinely anchored -- Dodo scopes price extraction to the
GB-figure-to-"/mth" text window (ignoring decoy prices elsewhere in the
tile), and Vodafone parses the page's own embedded `__NEXT_DATA__` Next.js
JSON (`plansResponseNbn.planListing.plans`) directly for plan names,
prices, and nominal tier labels, filtering out `isDuplicatePlan`/
`isInterimPlan` SKUs using the page's own flags rather than guessing.
Scheduling is also now live: `.github/workflows/scrape.yml` runs daily at
12:00am AEST via cron, not just on manual `workflow_dispatch`.

## Swoop and Neptune Internet (both shipped) -- 2026-07-22 / 2026-08-14

Two more candidates: Swoop and Neptune Internet, both real NBN retailers.

- **Swoop** -- `https://www.swoop.com.au/nbn/`, fully static, no anti-bot.
  4 tiers (NBN 25/10, 50/20, 500/50, 1000/100). Genuinely clean, semantic
  markup: plan cards are `div.card--plan`, the regular price is marked
  `span.discount.strikethrough` and the promo price `span.discount-price`
  (a real distinguishing class, not a positional guess), tier label is in
  `.card__header .subheading`, and typical evening download/upload speeds
  are the two `.h2` figures in `.card__typical-speeds .speeds` -- note
  these can differ from the nominal tier (the "1000/100" tier's real
  evening download is 890Mbps, not 1000). Shipped and registered.

- **Neptune Internet** -- initially found blocked: `https://www.neptune.net.au/internet`
  and every URL variant tried via a plain HTTP client (or WebFetch) returns
  403 with `Cf-Mitigated`/`CF-RAY` response headers, a Cloudflare bot-
  management challenge. **Follow-up (2026-08-14) reversed this finding**:
  a real Playwright browser context (this project's existing `fetch_js()`,
  no stealth patches at all) passes fine -- Neptune's Cloudflare rule
  checks for genuine browser/JS capability, not a harder fingerprint/proxy
  check, so it's a materially different (and much easier) obstacle than
  Belong/Optus/Southern Phone/Woolworths, which stay genuinely blocked even
  through `fetch_js`. Lesson: don't assume every `Cf-Mitigated` 403 needs
  proxy/anti-bot infrastructure -- retry with a real headless browser
  before writing a provider off.

  The `/internet` page itself is address-gated (shows no pricing until a
  real connection address is entered), so it's scraped via
  `/critical-information-summary` instead -- Australian telcos are
  required to publish this as a regulatory disclosure, so it's guaranteed
  complete and address-independent. One combined `<table>` covers Standard
  (7 tiers), Fixed Wireless (4, excluded -- not fixed-line NBN, same
  convention as other providers), FTTP Only (5, included), and Business
  (5, excluded -- requires an ABN) plans, distinguished mostly by a
  "(Fixed Wireless)"/"(FTTP)"/"eSLA" suffix on the plan name -- except one
  FTTP-tier row that has no suffix at all, handled by tracking section
  membership as a state machine over row order (once a Fixed-Wireless row
  is seen, the next unmarked row starts the FTTP-only section) rather than
  a fixed row count/position, so it survives future tier additions.

## CI/scheduling: pytest sys.path bug (fixed) and cloud-IP blocking (open)

The daily cron went live 2026-07-14 (`0 14 * * *` UTC = 12:00am AEST). Two
issues surfaced once it started actually running unattended -- neither
showed up during local dev/testing:

1. **Fixed (`e8ef915`):** the "Run parser tests" step used bare
   `pytest tests/`, which does NOT add the current directory to
   `sys.path` -- so CI hit `ModuleNotFoundError: No module named 'scraper'`
   on every run, even though `python -m pytest tests/` (which DOES add cwd
   to sys.path) always worked fine locally. `scraper/` has `__init__.py`
   (real package) but `tests/` doesn't, which is exactly the condition that
   triggers this. Fixed by changing the workflow step to
   `python -m pytest tests/`. Side note: a `continue-on-error: true` flag
   that got added and then reverted earlier turned out to have been
   covering for this exact bug, not "masking passing tests for no reason"
   as first assessed -- reverting it was still right (a safeguard shouldn't
   silently swallow real failures), but removing a workaround can surface a
   real pre-existing bug that then needs its own fix.

2. **Open as of 2026-07-22, not yet root-caused:** Dodo (both NBN and
   mobile) and Vodafone (both NBN and mobile) have failed on every single
   scheduled run since the cron went live -- 6+ consecutive failures each.
   Confirmed by direct testing that all 4 URLs work completely fine from a
   normal/dev connection -- this is GitHub Actions' cloud/datacenter IP
   range getting blocked (403 for Dodo, 503 for Vodafone) in a way that
   never manifests from a residential/dev machine. Same category as the
   already-documented anti-bot-blocked providers, except worse: it only
   shows up in the actual production environment (CI), not during dev.
   Also found: `manage_stale_issues.py` never actually opened a
   `stale: <provider>` GitHub issue despite being well past the
   3-consecutive-failure threshold for days -- that automation isn't
   working and needs investigating (was mid-investigation when this note
   was written -- check for a resolution before re-investigating).

## Workflow note: Claude implements scraper code directly

This project originally had DeepSeek write all new scraper code (parsers,
fixtures, tests) to save Claude tokens, with Claude doing research/planning/
verification only. That changed 2026-07-12: DeepSeek's self-reported fixes
repeatedly turned out to be superficial or fabricated (e.g. claiming a file
was fixed when it was never touched), so the workflow shifted to Claude
implementing directly -- research the live site, write the parser, add a
fixture-based test, register it in `run.py`, verify with `pytest` AND a
live `python run.py` run (not just one or the other), then commit. Default
to this unless told otherwise.
