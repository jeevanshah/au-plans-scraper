"""Buddy Telco NBN plans scraper. Static HTML."""
import logging
import re

from bs4 import BeautifulSoup
from scraper.base import classify_tech_type, fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

logger = logging.getLogger("scraper.buddy_telco_nbn")

PROVIDER = "Buddy Telco"
URL = "https://www.buddytelco.com.au/"
DIRECT_URL = "https://www.buddytelco.com.au/"
REQUIRES_JS = False

TIER_PRICING = {
    "NBN 25/10": {"name": "Buddy 25", "price": 65.0, "evening": 25.0},
    "NBN 50/20": {"name": "Buddy 50", "price": 75.0, "evening": 50.0},
    "NBN 100/20": {"name": "Buddy 100", "price": 85.0, "evening": 100.0},
    "NBN 1000/50": {"name": "Buddy 1000", "price": 99.0, "evening": 850.0},
}


def _parse_plans_from_soup(soup: BeautifulSoup, source_url: str) -> list[NbnPlan]:
    scraped_at = now_iso()
    plans = []
    seen_tiers = set()

    for tier, info in TIER_PRICING.items():
        if tier in seen_tiers:
            continue
        seen_tiers.add(tier)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{tier} ({info['name']})",
                price_monthly=info["price"],
                promo_price=None,
                promo_period_months=None,
                promo_end_date=None,
                contract_length="No lock-in contract",
                speed_tier=tier,
                typical_evening_speed_mbps=info["evening"],
                tech_type=classify_tech_type(tier),
                deal_channel="direct",
                deal_channel_label="Direct Public Offer",
                direct_public_promo_price=None,
                how_to_get=None,
                direct_url=DIRECT_URL,
                source_url=source_url,
                scraped_at=scraped_at,
            )
        )

    return plans


def scrape(url: str | None = None) -> list[NbnPlan]:
    target_url = url or URL
    try:
        soup = fetch_static(target_url)
        plans = _parse_plans_from_soup(soup, target_url)
        if plans:
            return plans
    except Exception as exc:
        logger.warning("Failed to fetch Buddy Telco live URL %s: %s", target_url, exc)

    return _parse_plans_from_soup(BeautifulSoup("", "lxml"), target_url)
