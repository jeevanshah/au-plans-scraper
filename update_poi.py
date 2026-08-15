"""Standalone runner for the Point-of-Interconnect (POI) footprint scrape.

Deliberately separate from run.py's daily plan scrape -- see scraper/poi.py's
module docstring. Intended for a monthly (not daily) schedule, e.g. a second
GitHub Actions cron job, since IX peering doesn't change often.

Writes data/poi.json: { generatedAt, providers: { <name>: {asn, viaWholesaler,
states, cities, exchangeCount, sourceUrl} } }. On a per-provider fetch/parse
failure, keeps that provider's last-known-good entry from the existing
poi.json (matching run.py's resilience convention for the plan scraper) rather
than dropping it or crashing the whole run.
"""
import json
import logging
import random
import sys
import time
from pathlib import Path

from scraper import poi

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("update_poi")

DATA_DIR = Path(__file__).parent / "data"

INTER_PROVIDER_DELAY_MIN = 1.0
INTER_PROVIDER_DELAY_MAX = 2.5


def _load_json(path: Path):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    previous = _load_json(DATA_DIR / "poi.json")
    previous_providers = previous.get("providers", {})

    providers_out = {}
    any_failure = False

    for i, provider in enumerate(poi.PROVIDER_ASN):
        if i > 0:
            delay = INTER_PROVIDER_DELAY_MIN + random.random() * (
                INTER_PROVIDER_DELAY_MAX - INTER_PROVIDER_DELAY_MIN
            )
            time.sleep(delay)
        try:
            footprint = poi.scrape_provider(provider)
            providers_out[provider] = footprint
            logger.info(
                "%s: AS%d, %d exchanges, states=%s",
                provider, footprint["asn"], footprint["exchangeCount"], footprint["states"],
            )
        except Exception:
            logger.exception("%s: POI scrape failed, keeping last-known-good data", provider)
            any_failure = True
            if provider in previous_providers:
                providers_out[provider] = previous_providers[provider]

    out = {
        "generatedAt": poi.now_iso(),
        "providers": providers_out,
    }
    (DATA_DIR / "poi.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    logger.info("Wrote data/poi.json (%d providers)", len(providers_out))

    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
