"""Orchestrator: runs every provider scraper, transforms output into the public
deal-card shape, and writes data/deals.json (+ data/meta.json).

A single provider failing never kills the run -- its last-known-good deals
(from the existing deals.json) are kept, and the failure is tracked in
meta.json so staleness is visible instead of silently rotting.
"""
import json
import logging
import random
import sys
import time
from pathlib import Path

from scraper.providers.mobile import aldimobile as mobile_aldi
from scraper.providers.mobile import amaysim as mobile_amaysim
from scraper.providers.mobile import aussie_broadband_mobile as mobile_aussiebb
from scraper.providers.mobile import boost as mobile_boost
from scraper.providers.mobile import dodo_mobile
from scraper.providers.mobile import felix as mobile_felix
from scraper.providers.mobile import kogan as mobile_kogan
from scraper.providers.mobile import moose_mobile
from scraper.providers.mobile import telstra as mobile_telstra
from scraper.providers.mobile import tpg as mobile_tpg
from scraper.providers.mobile import vodafone as mobile_vodafone
from scraper.providers.nbn import aussie_broadband, dodo, exetel, iinet, superloop, tangerine
from scraper.providers.nbn import spintel_nbn as nbn_spintel
from scraper.providers.nbn import telstra as nbn_telstra
from scraper.providers.nbn import tpg_nbn as nbn_tpg
from scraper.providers.nbn import flip_nbn as nbn_flip
from scraper.providers.nbn import swoop_nbn as nbn_swoop
from scraper.providers.nbn import vodafone_nbn as nbn_vodafone
from scraper.schema import now_iso
from scraper.transform import _make_id, mobile_plan_to_deal, nbn_plan_to_deal

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
    (iinet, "nbn", nbn_plan_to_deal),
    (mobile_tpg, "mobile", mobile_plan_to_deal),
    (mobile_telstra, "mobile", mobile_plan_to_deal),
    (mobile_amaysim, "mobile", mobile_plan_to_deal),
    (mobile_vodafone, "mobile", mobile_plan_to_deal),
    (mobile_kogan, "mobile", mobile_plan_to_deal),
    (mobile_felix, "mobile", mobile_plan_to_deal),
    (mobile_boost, "mobile", mobile_plan_to_deal),
    (mobile_aldi, "mobile", mobile_plan_to_deal),
    (dodo_mobile, "mobile", mobile_plan_to_deal),
    (mobile_aussiebb, "mobile", mobile_plan_to_deal),
    (nbn_vodafone, "nbn", nbn_plan_to_deal),
    (nbn_spintel, "nbn", nbn_plan_to_deal),
    (nbn_tpg, "nbn", nbn_plan_to_deal),
    (nbn_flip, "nbn", nbn_plan_to_deal),
    (moose_mobile, "mobile", mobile_plan_to_deal),
    (nbn_swoop, "nbn", nbn_plan_to_deal),
]

CONSECUTIVE_FAILURE_ISSUE_THRESHOLD = 3

# Politeness delay range in seconds between provider requests.
# Several providers (Belong, Optus -- see NOTES.md) show bot-mitigation
# behaviour; back-to-back requests from the same IP likely make it worse.
INTER_PROVIDER_DELAY_MIN = 1.0
INTER_PROVIDER_DELAY_MAX = 2.5

# Price-variance threshold: if a deal's promoPrice or regularPrice differs
# from the previous run's same provider+tier by more than this factor (in
# either direction), log a warning as potential parser drift.
PRICE_VARIANCE_WARN_FACTOR = 0.5


def _load_json(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sanity_check_deals(all_deals: list[dict], previous_deals: list[dict]):
    """Log warnings for suspect price swings or duplicate IDs.

    This is a best-effort check, not a hard gate -- it logs warnings so
    parser drift is visible in the CI log without blocking the data update.
    """

    # 1. Check promoPrice <= regularPrice when promo exists
    for deal in all_deals:
        promo = deal.get("promoPrice")
        regular = deal.get("regularPrice")
        has_promo = deal.get("promoMonths") is not None
        if has_promo and promo is not None and regular is not None:
            if promo > regular:
                logger.warning(
                    "Price sanity: %s (%s): promoPrice $%.2f > regularPrice $%.2f",
                    deal["id"],
                    deal["provider"],
                    promo,
                    regular,
                )

    # 2. Build an index of previous deals: (provider, serviceType, tier) -> dict
    prev_index: dict[tuple[str, str, str], dict] = {}
    for d in previous_deals:
        key = (d.get("provider", ""), d.get("serviceType", ""), d.get("tier", ""))
        prev_index[key] = d

    # 3. Check for large price swings vs previous run
    for deal in all_deals:
        key = (deal.get("provider", ""), deal.get("serviceType", ""), deal.get("tier", ""))
        prev = prev_index.get(key)
        if prev is None:
            continue  # first-time entry, nothing to compare

        for price_field in ("promoPrice", "regularPrice"):
            new_val = deal.get(price_field)
            old_val = prev.get(price_field)
            if new_val is None or old_val is None:
                continue
            if old_val == 0:
                continue
            delta = abs(new_val - old_val) / old_val
            if delta > PRICE_VARIANCE_WARN_FACTOR:
                logger.warning(
                    "Price drift: %s %s: $%.2f -> $%.2f (%.0f%% change) -- "
                    "may indicate parser issue or genuine price change",
                    deal["id"],
                    price_field,
                    old_val,
                    new_val,
                    delta * 100,
                )

    # 4. Uniqueness check on generated IDs
    seen_ids: set[str] = set()
    for deal in all_deals:
        deal_id = deal.get("id", "")
        if deal_id in seen_ids:
            logger.error(
                "Duplicate deal id '%s' -- provider=%s tier=%s. "
                "This indicates a collision in _make_id(), likely a "
                "provider slug change or two tiers normalizing to the same id.",
                deal_id,
                deal.get("provider"),
                deal.get("tier"),
            )
        seen_ids.add(deal_id)


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    meta = _load_json(DATA_DIR / "meta.json") or {}
    if isinstance(meta, list):  # defensive: meta.json should always be a dict
        meta = {}
    previous_deals = _load_json(DATA_DIR / "deals.json")

    all_deals = []

    for i, (module, category, transform) in enumerate(PROVIDERS):
        provider_name = module.PROVIDER
        meta_key = f"{provider_name} ({category})"
        previous_status = meta.get(meta_key, {})
        consecutive_failures = previous_status.get("consecutive_failures", 0)

        # Politeness delay between providers (skip before the first one)
        if i > 0:
            delay = INTER_PROVIDER_DELAY_MIN + random.random() * (
                INTER_PROVIDER_DELAY_MAX - INTER_PROVIDER_DELAY_MIN
            )
            logger.debug("Politeness delay: %.1fs before %s", delay, meta_key)
            time.sleep(delay)

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

    # Run sanity checks before writing
    _sanity_check_deals(all_deals, previous_deals)

    (DATA_DIR / "deals.json").write_text(json.dumps(all_deals, indent=2), encoding="utf-8")
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    any_stale = any(
        m.get("consecutive_failures", 0) >= CONSECUTIVE_FAILURE_ISSUE_THRESHOLD for m in meta.values()
    )
    return 1 if any_stale else 0


if __name__ == "__main__":
    sys.exit(main())
