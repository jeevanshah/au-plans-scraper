---
name: add-provider
description: Add a new NBN or mobile provider scraper to this repo end-to-end (research the live site, implement the parser, write a fixture-based test, register it in run.py, verify live, document, commit). Use whenever the user asks to add/support/scrape a new provider, or asks "can we do something about <provider>" in the context of the held-back/requested-providers list.
---

# Adding a new provider scraper

This repo's standing convention: Claude implements scraper code directly (no
delegating implementation to another model) and every new provider goes
through the same pipeline before it's considered done. Follow these steps
in order; don't skip verification steps even under time pressure.

## 1. Confirm it's real and scrapeable

- Check `README.md`'s Providers/Held-back/Dropped sections and `NOTES.md`
  for prior research on this provider -- it may already have been
  investigated and rejected (anti-bot, market exit, wrong business type).
- WebSearch to confirm the provider is a real, currently-operating AU
  NBN/mobile retailer if you're not certain.
- Find the live plans page and try `fetch_static()` first (see
  `scraper/base.py`). If it 403s/times out/resets, retry with `fetch_js()`
  (Playwright) before writing the provider off as blocked -- bundled
  Chromium is enough most of the time (Neptune, Leaptel). Only reach for
  `channel="chrome"` + a plain non-self-identifying User-Agent if bundled
  Chromium itself gets connection-reset at the TLS/HTTP2 level (this was
  needed for Optus specifically, not the general case).

## 2. Inspect the real DOM before writing the parser

Fetch the live page once (a scratch script, not inline bash `-c` strings
with regex -- backslash-dollar sequences get mangled; write a `.py` file
in the scratchpad dir instead) and print/save the actual HTML. Do not
guess selectors from memory of "typical" markup. Specifically watch for:

- **Double-rendered DOM**: some JS frameworks (Alpine.js on WordPress, for
  one) render a real hidden SSR fallback block alongside the live
  interactive version. Both exist in the DOM regardless of CSS
  `display:none`, so `get_text()`/`find_all()` will double-count unless
  you scope to one specific container. Leaptel needed this
  (`wp-block-leaptel-plan-list__ssr`).
- **BeautifulSoup class_ substring gotcha**: `class_=lambda c: c and "x"
  in c` matches once per individual class token AND once with the full
  joined string -- a substring check therefore ALSO matches nested
  descendant elements sharing a class prefix (e.g. `wp-block-leaptel-card`
  substring-matches `wp-block-leaptel-card__heading`). Always use exact
  token equality (`c == "x"`) when the container is a specific class, not
  a prefix family. This exact bug has bitten Flip NBN and Leaptel.
- Per-tier eligibility/tech-type disclosures, promo pricing shape ("$X/mo,
  $Y off for N months, then $Z ongoing"), and whether "typical evening
  speed" differs from the nominal speed tier (common pattern: Swoop, More
  Telecom, Arctel, Leaptel).

## 3. Implement the scraper module

- New file at `scraper/providers/nbn/<provider>.py` or
  `scraper/providers/mobile/<provider>.py`.
- Module docstring should record: which fetch method and why, any
  DOM gotchas discovered in step 2 (cite prior providers with the same
  bug, e.g. "same gotcha as Flip NBN"), and the promo/tech-type parsing
  conventions used.
- Use `classify_tech_type()` from `scraper/base.py` for tech eligibility
  text -- never guess when no eligibility text is present, return `None`.
- Use `parse_relative_end_date`/`parse_absolute_end_date` from
  `scraper/base.py` for any stated promo end-dates.
- Only set `promo_price`/`promo_end_date` when there's an actual matched
  discount -- don't set an end-date on a plan that turned out to have no
  promo (this was the amaysim bug: `promo_end_date` was being set purely
  because surrounding terms text matched, independent of whether the
  promo price regex itself matched).
- `scrape()` should raise `RuntimeError` if it finds the expected
  container but zero valid plans -- silent empty-list success would mask
  a layout change as "0 plans, no error."

## 4. Add a fixture + test

- Save a live capture of the fetched page HTML to
  `tests/fixtures/<provider>_<nbn|mobile>.html`.
- Add a `test_<provider>_<nbn|mobile>` function in
  `tests/test_providers.py` that monkeypatches `fetch_static`/`fetch_js`
  to return the fixture, then asserts on tier count, tier names, at least
  one full set of fields (price, promo, tech_type, typical evening speed
  if applicable), and the `promo_price < price_monthly` invariant across
  all plans.
- When editing `test_providers.py`, re-read enough context around the
  insertion point first -- inserting mid-function (missing trailing
  assertions) causes `NameError` at collection time, not at the edit
  itself.

## 5. Register and verify

- Add the import + `(<module>, "<nbn|mobile>", <transform_fn>)` tuple to
  `run.py`'s `PROVIDERS` list.
- Run `python -m pytest` (not bare `pytest`) -- full suite must pass.
- Run a live `python run.py` end-to-end -- confirm the new provider
  succeeds with a plausible plan count and zero other providers regress.
- Check `data/changelog.json` shows an "Added <Provider> ... plans" entry.

## 6. Document and commit

- Update `README.md`'s NBN/Mobile provider list.
- Add a dated section to `NOTES.md` documenting what was discovered in
  step 2 (fetch method, DOM gotchas, tech/pricing patterns) so the next
  provider addition doesn't rediscover the same bugs from scratch.
- Commit with the per-repo git identity override (no global git config
  set on this machine):
  `git -c user.name="Jeevan Shah" -c user.email="jeevenrajshah@gmail.com" commit -m "..."`
  Avoid double-quoted phrases inside PowerShell here-string commit
  messages (`@'...'@`) -- they can cause git to mis-split the message
  into invalid pathspec args. Push only after confirming no remote
  divergence (`git fetch origin; git log --oneline HEAD..origin/main`).
