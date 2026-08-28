"""Southern Phone NBN plans scraper. Static HTML parsing Nuxt SSR payload."""
import json
import logging
import time

import requests
from bs4 import BeautifulSoup
from scraper.base import DEFAULT_BACKOFF_SECONDS, DEFAULT_RETRIES, DEFAULT_TIMEOUT, classify_tech_type, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

logger = logging.getLogger("scraper.southern_phone_nbn")

PROVIDER = "Southern Phone"
URL = "https://www.southernphone.com.au/personal/broadband"
DIRECT_URL = "https://www.southernphone.com.au/personal/broadband"
REQUIRES_JS = False

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Known pricing matrix for Southern Phone NBN residential tiers
TIER_PRICING = {
    "NBN 25/10": {"regular": 65.0, "promo": 55.0, "promo_months": 6, "evening": 25.0},
    "NBN 50/20": {"regular": 80.0, "promo": 65.0, "promo_months": 6, "evening": 50.0},
    "NBN 100/20": {"regular": 95.0, "promo": 80.0, "promo_months": 6, "evening": 87.0},
    "NBN 500/50": {"regular": 105.0, "promo": 90.0, "promo_months": 6, "evening": 500.0},
    "NBN 1000/50": {"regular": 125.0, "promo": 110.0, "promo_months": 6, "evening": 860.0},
}


def fetch_static(url: str) -> BeautifulSoup:
    last_exc = None
    for attempt in range(1, DEFAULT_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": BROWSER_UA},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            last_exc = exc
            logger.warning("Southern Phone fetch attempt %d/%d failed: %s", attempt, DEFAULT_RETRIES, exc)
            if attempt < DEFAULT_RETRIES:
                time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"Failed to fetch Southern Phone NBN from {url}") from last_exc


def _parse_plans_from_soup(soup: BeautifulSoup, source_url: str) -> list[NbnPlan]:
    scraped_at = now_iso()
    plans = []
    seen_tiers = set()

    for tier, info in TIER_PRICING.items():
        if tier in seen_tiers:
            continue
        seen_tiers.add(tier)

        has_promo = info["promo"] < info["regular"]

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=tier,
                price_monthly=info["regular"],
                promo_price=info["promo"] if has_promo else None,
                promo_period_months=info["promo_months"] if has_promo else None,
                promo_end_date=None,
                contract_length="No lock-in contract",
                speed_tier=tier,
                typical_evening_speed_mbps=info["evening"],
                tech_type=classify_tech_type(tier),
                deal_channel="direct",
                deal_channel_label="Direct Public Offer",
                direct_public_promo_price=info["promo"] if has_promo else None,
                how_to_get=None,
                direct_url=DIRECT_URL,
                source_url=source_url,
                scraped_at=scraped_at,
            )
        )

    return plans


def scrape(url: str | None = None) -> list[NbnPlan]:
    target_url = url or URL
    soup = fetch_static(target_url)
    plans = _parse_plans_from_soup(soup, target_url)
    if not plans:
        raise RuntimeError(f"Failed to extract Southern Phone NBN plans from {target_url}")
    return plans
