"""Orchestrator: runs every provider scraper, transforms output into the public
deal-card shape, and writes data/deals.json (+ data/meta.json).

A single provider failing never kills the run -- its last-known-good deals
(from the existing deals.json) are kept, and the failure is tracked in
meta.json so staleness is visible instead of silently rotting.
"""
import json
import logging
import sys
from pathlib import Path

from scraper.providers.mobile import telstra as mobile_telstra
from scraper.providers.mobile import tpg as mobile_tpg
from scraper.providers.nbn import aussie_broadband, dodo, exetel, superloop, tangerine
from scraper.providers.nbn import telstra as nbn_telstra
from scraper.schema import now_iso
from scraper.transform import mobile_plan_to_deal, nbn_plan_to_deal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run")

DATA_DIR = Path(__file__).parent / "data"

# (module, category, transform_fn) -- category distinguishes same-name providers
# (e.g. "Telstra" appears in both NBN and mobile) when retaining last-known-good data.
PROVIDERS = [
    (aussie_broadband, "nbn", nbn_plan_to_deal),
    (tangerine, "nbn", nbn_plan_to_deal),
    (nbn_telstra, "nbn", nbn_plan_to_deal),
    (dodo, "nbn", nbn_plan_to_deal),
    (superloop, "nbn", nbn_plan_to_deal),
    (exetel, "nbn", nbn_plan_to_deal),
    (mobile_tpg, "mobile", mobile_plan_to_deal),
    (mobile_telstra, "mobile", mobile_plan_to_deal),
]

CONSECUTIVE_FAILURE_ISSUE_THRESHOLD = 3


def _load_json(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    meta = _load_json(DATA_DIR / "meta.json") or {}
    if isinstance(meta, list):  # defensive: meta.json should always be a dict
        meta = {}
    previous_deals = _load_json(DATA_DIR / "deals.json")

    all_deals = []

    for module, category, transform in PROVIDERS:
        provider_name = module.PROVIDER
        meta_key = f"{provider_name} ({category})"
        previous_status = meta.get(meta_key, {})
        consecutive_failures = previous_status.get("consecutive_failures", 0)

        try:
            plans = module.scrape()
            if not plans:
                raise RuntimeError("scrape() returned no plans")
            deals = [transform(p) for p in plans]
            all_deals.extend(deals)
            meta[meta_key] = {
                "status": "ok",
                "last_success": now_iso(),
                "consecutive_failures": 0,
                "plan_count": len(deals),
            }
            logger.info("%s: scraped %d plans", meta_key, len(deals))
        except Exception:
            logger.exception("%s: scrape failed, keeping last-known-good data", meta_key)
            kept = [
                d for d in previous_deals
                if d.get("provider") == provider_name and d.get("serviceType") == category
            ]
            all_deals.extend(kept)
            consecutive_failures += 1
            meta[meta_key] = {
                "status": "error",
                "last_success": previous_status.get("last_success"),
                "consecutive_failures": consecutive_failures,
                "plan_count": len(kept),
            }
            if consecutive_failures >= CONSECUTIVE_FAILURE_ISSUE_THRESHOLD:
                logger.warning(
                    "%s: %d consecutive failures -- stale data, needs attention",
                    meta_key,
                    consecutive_failures,
                )

    (DATA_DIR / "deals.json").write_text(json.dumps(all_deals, indent=2), encoding="utf-8")
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    any_stale = any(
        m.get("consecutive_failures", 0) >= CONSECUTIVE_FAILURE_ISSUE_THRESHOLD for m in meta.values()
    )
    return 1 if any_stale else 0


if __name__ == "__main__":
    sys.exit(main())
