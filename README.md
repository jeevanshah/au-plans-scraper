# au-plans-scraper

Scrapes NBN broadband and mobile phone plan pricing from major Australian
providers and publishes normalized JSON that a separate app/blog fetches
directly from this repo (via jsDelivr's GitHub CDN) -- no backend, no
hosting cost.

## Data

- [`data/nbn.json`](data/nbn.json) -- NBN broadband plans
- [`data/mobile.json`](data/mobile.json) -- mobile SIM-only plans
- [`data/meta.json`](data/meta.json) -- per-provider last-success timestamp and consecutive-failure count

Fetch from your app via:

```
https://cdn.jsdelivr.net/gh/<github-user>/au-plans-scraper@main/data/nbn.json
https://cdn.jsdelivr.net/gh/<github-user>/au-plans-scraper@main/data/mobile.json
```

(jsDelivr caches per branch and can lag up to ~12-24h behind the latest commit --
fine at the daily/weekly update cadence this scraper runs on.)

## Providers

**NBN:** Aussie Broadband, Tangerine, Telstra
**Mobile:** TPG, Telstra

Dropped: Circles.Life (exited the Australian market in 2025, acquired by amaysim).
Held back pending manual verification: Belong, Optus, amaysim, TPG's NBN plans (all four
either returned inconsistent responses during initial research or need Playwright +
careful rate-limiting -- see `scraper/providers/` for what's implemented so far).

## Running locally

```
pip install -r requirements.txt
playwright install chromium
python run.py
```

Writes/updates `data/nbn.json`, `data/mobile.json`, `data/meta.json`.

## Testing

```
pytest tests/
```

Runs each provider's parser against a saved HTML fixture in `tests/fixtures/` --
no live network calls, so it catches parser regressions cheaply. When a provider's
site changes layout, re-fetch its fixture and update the parser + test together.

## How a provider failing is handled

`run.py` never lets one provider's failure kill the run: it keeps that provider's
last-known-good plans (from the existing `data/*.json`) and increments
`consecutive_failures` in `data/meta.json`. After 3 consecutive failures, the
GitHub Actions workflow opens a `stale: <provider>` issue (and closes it once the
provider recovers) so staleness doesn't go unnoticed.

## Scheduling

The workflow (`.github/workflows/scrape.yml`) currently runs on `workflow_dispatch`
(manual trigger) only. Once the pilot providers have proven stable across a few
manual runs, uncomment the `schedule:` cron block to run it automatically (daily
recommended, given the low request volume).
