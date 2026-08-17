"""Launtel NBN plans scraper.

Scrapes live residential NBN plans from Launtel's API:
https://future-portal-prod.launtel.io/api/plans/sellable/
Converts daily billing rates to standard monthly equivalents (daily * 30.4167).
"""
import requests

from scraper.base import normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Launtel"
URL = "https://www.launtel.net.au/residential"
API_BASE = "https://future-portal-prod.launtel.io/api/plans/sellable"
REQUIRES_JS = False

# Representative LOC IDs for nationwide FTTP & FTTB catalog coverage
DEFAULT_LOC_IDS = [
    ("LOC000086854569", "FTTP"),
    ("LOC000014513025", "FTTB"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DAYS_PER_MONTH = 30.4167


def scrape(raw_json: list[dict] | None = None) -> list[NbnPlan]:
    scraped_at = now_iso()
    items = []

    if raw_json is not None:
        items = raw_json
    else:
        seen_ids = set()
        for loc_id, tech in DEFAULT_LOC_IDS:
            ep = f"{API_BASE}/{loc_id}/{tech}"
            resp = requests.get(ep, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for item in data:
                item_id = item.get("id")
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    items.append(item)

    plans: list[NbnPlan] = []
    seen_tiers: set[str] = set()

    for item in items:
        down = int(item.get("downstream_speed", 0))
        up = int(item.get("upstream_speed", 0))

        # Skip non-broadband standby and IoT tiers (< 25 Mbps)
        if down < 25:
            continue

        speed_tier, _, _ = normalize_nbn_speed_tier(down, up)
        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        name = item.get("name", "").strip()
        peak_down = item.get("peak_downstream_speed")
        evening_speed = float(peak_down) if peak_down else float(down)

        reg_str = item.get("price", "$0").replace("$", "").strip()
        promo_str = item.get("discounted_price", "$0").replace("$", "").strip()
        reg_daily = float(reg_str)
        promo_daily = float(promo_str)

        reg_monthly = round(reg_daily * DAYS_PER_MONTH, 2)
        promo_monthly = round(promo_daily * DAYS_PER_MONTH, 2) if promo_daily < reg_daily else None
        promo_code = item.get("discount_code")

        title = f"{name} {speed_tier} (${reg_daily:.2f}/day)"
        if promo_code and promo_monthly:
            title = f"{name} {speed_tier} (${promo_daily:.2f}/day promo, code {promo_code})"

        tech_type = "Fibre" if down >= 250 else "Fibre and FTTN"

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=title,
                price_monthly=reg_monthly,
                promo_price=promo_monthly,
                promo_period_months=6 if promo_monthly else None,
                promo_end_date="2026-12-31" if promo_monthly else None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not extract any plans from Launtel API")
    return plans
