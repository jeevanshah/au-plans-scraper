"""Vodafone NBN plans scraper.

Vodafone's NBN page embeds a Next.js `__NEXT_DATA__` JSON blob
(pageProps.plansResponseNbn.planListing.plans) with clean, already-labeled
fields per plan -- customPlanName, recurringCharge (regular price),
discountedRecurringCharge (promo price), maxConnectionSpeed (the real "NBN
X/Y" nominal tier label), and a promotions list with the intro-discount
duration. Parsing this directly is far more reliable than regexing the
rendered page text (no hardcoded Mbps->tier-name map, no risk of decoy
prices/text elsewhere on the page bleeding into extraction).

Each plan carries `isDuplicatePlan` / `isInterimPlan` / `isTrialPlan` flags
in the source data itself -- these are Vodafone's own signal for SKUs that
aren't real, currently-orderable branded tiers (e.g. a legacy "pre-fibre
interim" plan, or a duplicate listing of another tier), so they're skipped
rather than guessed at.
"""
import json
import re

from scraper.base import fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Vodafone"
URL = "https://www.vodafone.com.au/home-internet/nbn"
REQUIRES_JS = False

PROMO_MONTHS_RE = re.compile(r"for\s+(\d+)\s+months?", re.I)


def _plan_promo_months(plan: dict) -> int | None:
    """First promotion whose title states an explicit "for N months" duration.
    Plans can have zero, one, or several promotions (e.g. a permanent
    bundle discount alongside a time-limited intro discount) -- only a
    stated duration counts as promo_period_months."""
    for promo in plan.get("promotions", []):
        match = PROMO_MONTHS_RE.search(promo.get("title", ""))
        if match:
            return int(match.group(1))
    return None


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    script_tag = soup.find("script", id="__NEXT_DATA__")
    if script_tag is None or not script_tag.string:
        raise RuntimeError("scrape() could not find the __NEXT_DATA__ script tag")

    data = json.loads(script_tag.string)
    try:
        raw_plans = data["props"]["pageProps"]["plansResponseNbn"]["planListing"]["plans"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"scrape() could not locate plans in __NEXT_DATA__: {exc}")

    plans = []
    for p in raw_plans:
        if p.get("isDuplicatePlan") or p.get("isInterimPlan") or p.get("isTrialPlan"):
            continue

        regular = p.get("recurringCharge")
        discounted = p.get("discountedRecurringCharge")
        speed_tier = p.get("maxConnectionSpeed")
        plan_name = p.get("customPlanName") or p.get("planName")
        typical_evening = p.get("connectionSpeed")

        if regular is None or not speed_tier or not plan_name:
            continue

        has_promo = discounted is not None and discounted < regular

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name.replace("®", "").strip(),
                price_monthly=float(regular),
                promo_price=float(discounted) if has_promo else None,
                promo_period_months=_plan_promo_months(p) if has_promo else None,
                contract_length="Month-to-month",
                speed_tier=f"NBN {speed_tier}",
                typical_evening_speed_mbps=float(typical_evening) if typical_evening else None,
                tech_type=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
