"""Orchestrator: runs every provider scraper, validates output, writes data/*.json.

A single provider failing never kills the run -- its last-known-good plans
(from the existing data file) are kept, and the failure is tracked in
data/meta.json so staleness is visible instead of silently rotting.
"""
import json
import logging
import sys
from pathlib import Path

from scraper.providers.mobile import telstra as mobile_telstra
from scraper.providers.mobile import tpg as mobile_tpg
from scraper.providers.nbn import aussie_broadband, tangerine
from scraper.providers.nbn import telstra as nbn_telstra
from scraper.schema import now_iso

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run")

DATA_DIR = Path(__file__).parent / "data"

NBN_PROVIDERS = [aussie_broadband, tangerine, nbn_telstra]
MOBILE_PROVIDERS = [mobile_tpg, mobile_telstra]

CONSECUTIVE_FAILURE_ISSUE_THRESHOLD = 3


def _load_json(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _run_category(providers, existing_plans_path: Path, meta: dict) -> tuple[list, dict]:
    previous_plans = _load_json(existing_plans_path)
    all_plans = []

    for module in providers:
        provider_name = module.PROVIDER
        previous_status = meta.get(provider_name, {})
        consecutive_failures = previous_status.get("consecutive_failures", 0)

        try:
            plans = module.scrape()
            if not plans:
                raise RuntimeError("scrape() returned no plans")
            all_plans.extend(p.model_dump() for p in plans)
            meta[provider_name] = {
                "status": "ok",
                "last_success": now_iso(),
                "consecutive_failures": 0,
                "plan_count": len(plans),
            }
            logger.info("%s: scraped %d plans", provider_name, len(plans))
        except Exception:
            logger.exception("%s: scrape failed, keeping last-known-good data", provider_name)
            kept = [p for p in previous_plans if p.get("provider") == provider_name]
            all_plans.extend(kept)
            consecutive_failures += 1
            meta[provider_name] = {
                "status": "error",
                "last_success": previous_status.get("last_success"),
                "consecutive_failures": consecutive_failures,
                "plan_count": len(kept),
            }
            if consecutive_failures >= CONSECUTIVE_FAILURE_ISSUE_THRESHOLD:
                logger.warning(
                    "%s: %d consecutive failures -- stale data, needs attention",
                    provider_name,
                    consecutive_failures,
                )

    return all_plans, meta


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    meta = _load_meta(DATA_DIR / "meta.json")

    nbn_plans, meta = _run_category(NBN_PROVIDERS, DATA_DIR / "nbn.json", meta)
    mobile_plans, meta = _run_category(MOBILE_PROVIDERS, DATA_DIR / "mobile.json", meta)

    (DATA_DIR / "nbn.json").write_text(json.dumps(nbn_plans, indent=2), encoding="utf-8")
    (DATA_DIR / "mobile.json").write_text(json.dumps(mobile_plans, indent=2), encoding="utf-8")
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    any_stale = any(
        m.get("consecutive_failures", 0) >= CONSECUTIVE_FAILURE_ISSUE_THRESHOLD for m in meta.values()
    )
    return 1 if any_stale else 0


if __name__ == "__main__":
    sys.exit(main())
