# au-plans-scraper

Scrapes NBN broadband and mobile phone plan pricing from major Australian
providers and publishes normalized JSON that a separate app/blog fetches
directly from this repo (via jsDelivr's GitHub CDN) -- no backend, no
hosting cost.

## Data

- [`data/deals.json`](data/deals.json) -- merged NBN + mobile deal cards (see shape below)
- [`data/meta.json`](data/meta.json) -- per-provider last-success timestamp and consecutive-failure count
- [`data/changelog.json`](data/changelog.json) -- human-readable log of genuine changes each run
  (new providers, new tiers, real price changes) vs. the previous run, most recent first, capped
  at the last `CHANGELOG_MAX_ENTRIES` entries in `run.py`

Fetch from your app via:

```
https://cdn.jsdelivr.net/gh/<github-user>/au-plans-scraper@main/data/deals.json
```

(jsDelivr caches per branch and can lag up to ~12-24h behind the latest commit --
fine at the daily/weekly update cadence this scraper runs on.)

Each entry looks like:

```json
{
  "id": "dodo-nbn-50-20-2026-07",
  "provider": "Dodo",
  "title": "Value NBN 50/20",
  "category": "Utilities",
  "description": "NBN 50/20 plan discounted for the first 6 months for new customers. Unlimited data, no lock-in contract.",
  "promoPrice": 57.99,
  "regularPrice": 87.99,
  "promoMonths": 6,
  "validUntil": "2026-09-01",
  "url": "https://www.dodo.com/nbn",
  "serviceType": "nbn",
  "tier": "NBN 50/20",
  "techType": "Fibre and FTTN",
  "postedAt": "2026-07-10",
  "_source": "Dodo official site, verified 2026-07-10"
}
```

`validUntil` and `techType` are `null` when a provider's page doesn't state an explicit
calendar end-date or connection-tech eligibility for that plan -- see `scraper/transform.py`
for the mapping from internal scrape fields to this shape, and `scraper/base.py`'s
`classify_tech_type` / `parse_relative_end_date` / `parse_absolute_end_date` for how those
two fields get extracted per provider.

## Providers

**NBN:** Aussie Broadband, Tangerine, Telstra, Dodo, Superloop, Exetel, iiNet,
Vodafone, SpinTel, TPG, Flip, Swoop, Neptune Internet, More Telecom, Purple Connect,
Arctel, Optus, Leaptel
**Mobile:** TPG, Telstra, amaysim, Vodafone, Kogan Mobile, Felix, Boost Mobile,
ALDImobile, Dodo, Aussie Broadband, Moose Mobile

Note some providers appear in both lists under separate scraper modules for
their NBN and mobile product lines (e.g. Dodo NBN vs. Dodo Mobile, Vodafone
NBN vs. Vodafone Mobile) -- these are different pages/pricing, not duplicates.

Dropped: Circles.Life (exited the Australian market in 2025, acquired by amaysim);
MyRepublic (exited the AU NBN market in Dec 2022/Jan 2023, all URLs return HTTP 530 --
not a scraping gap, there is no product to scrape).

Correction: Flip was previously listed here as dropped ("not actually an
NBN/broadband provider -- a logistics company, unrelated"). That was wrong --
Flip (flipconnect.com.au) is a real, currently-operating budget NBN retailer
and is now scraped like any other provider.

Held back (needs real anti-bot/browser-fingerprint handling, not scrapeable with
`fetch_static`/`fetch_js` as-is): Belong, Southern Phone, Woolworths
Mobile/everyday -- see `scraper/providers/` for what's implemented so far.

Note: Neptune Internet's main plans page IS behind Cloudflare bot-management
(403 with `Cf-Mitigated`/`CF-RAY` headers via a plain HTTP client), but a
real Playwright browser context passes with no stealth patches needed --
it's scraped via its Critical Information Summary page instead (see
`scraper/providers/nbn/neptune_nbn.py`), which is address-independent and
lists every plan in one combined table. Not every Cloudflare-fronted site
needs proxy/fingerprint workarounds -- worth checking with a real browser
fetch before writing a provider off as blocked.

Note: Optus was previously listed as blocked (every plain fetch timed out or hit
ECONNRESET, worse than a 403). Retried and now shipped: plain HTTP actually works
fine for the raw page, but its plan cards are entirely client-rendered, and
Playwright's *bundled* Chromium gets connection-reset (`net::ERR_HTTP2_PROTOCOL_ERROR`)
by Optus's TLS/HTTP2-level bot mitigation on every URL, even the homepage. Getting a
clean response needed two changes together: a real Google Chrome binary via
Playwright's `channel="chrome"`, AND dropping this project's usual self-identifying
User-Agent for a plain browser UA -- real Chrome with the normal
`au-plans-scraper/1.0 (...)`-prefixed UA still gets reset. See
`scraper/providers/nbn/optus.py` and `scraper/base.py`'s `fetch_js()` for the
`channel`/`user_agent` kwargs this needed, and NOTES.md for the full 2x2 test.

## Running locally

```
pip install -r requirements.txt
playwright install chromium chrome
python run.py
```

(Optus needs the `chrome` channel specifically -- Playwright's bundled Chromium gets
connection-reset by its bot mitigation regardless of user-agent, see
`scraper/providers/nbn/optus.py`. Every other provider only needs `chromium`.)

Writes/updates `data/deals.json`, `data/meta.json`, `data/changelog.json`.

## Testing

```
pytest tests/
```

Runs each provider's parser against a saved HTML fixture in `tests/fixtures/` --
no live network calls, so it catches parser regressions cheaply. When a provider's
site changes layout, re-fetch its fixture and update the parser + test together.

## How a provider failing is handled

`run.py` never lets one provider's failure kill the run: it keeps that provider's
last-known-good deals (from the existing `data/deals.json`) and increments
`consecutive_failures` in `data/meta.json`. After 3 consecutive failures, the
GitHub Actions workflow opens a `stale: <provider>` issue (and closes it once the
provider recovers) so staleness doesn't go unnoticed.

## Scheduling

The workflow (`.github/workflows/scrape.yml`) runs daily at 12:00am AEST
(`cron: '0 14 * * *'`, UTC+10) in addition to `workflow_dispatch` for manual
runs. GitHub Actions cron is UTC-only and not DST-aware, so during AEDT
(UTC+11, roughly early Oct-early Apr) this fires at 1:00am local time
instead -- a 1-hour drift for about 5 months of the year, acceptable for a
daily data-freshness job.
