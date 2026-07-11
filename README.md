# au-plans-scraper

Scrapes NBN broadband and mobile phone plan pricing from major Australian
providers and publishes normalized JSON that a separate app/blog fetches
directly from this repo (via jsDelivr's GitHub CDN) -- no backend, no
hosting cost.

## Data

- [`data/deals.json`](data/deals.json) -- merged NBN + mobile deal cards (see shape below)
- [`data/meta.json`](data/meta.json) -- per-provider last-success timestamp and consecutive-failure count

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

**NBN:** Aussie Broadband, Tangerine, Telstra, Dodo, Superloop, Exetel, iiNet
**Mobile:** TPG, Telstra, amaysim, Vodafone, Kogan Mobile, Felix, Boost Mobile, ALDImobile

Dropped: Circles.Life (exited the Australian market in 2025, acquired by amaysim); Flip
(not actually an NBN/broadband provider -- a logistics company, unrelated);
MyRepublic (exited the AU NBN market in Dec 2022/Jan 2023, all URLs return HTTP 530 --
not a scraping gap, there is no product to scrape).
Held back (needs real anti-bot/browser-fingerprint handling, not scrapeable with
`fetch_static`/`fetch_js` as-is): Belong, Optus, Southern Phone, Woolworths
Mobile/everyday -- see `scraper/providers/` for what's implemented so far.

## Running locally

```
pip install -r requirements.txt
playwright install chromium
python run.py
```

Writes/updates `data/deals.json`, `data/meta.json`.

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

The workflow (`.github/workflows/scrape.yml`) currently runs on `workflow_dispatch`
(manual trigger) only. Once the pilot providers have proven stable across a few
manual runs, uncomment the `schedule:` cron block to run it automatically (daily
recommended, given the low request volume).
