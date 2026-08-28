"""Belong NBN plans scraper. Static HTML parsing __NEXT_DATA__ JSON payload."""
import json
import logging
import time

import requests
from bs4 import BeautifulSoup
from scraper.base import DEFAULT_BACKOFF_SECONDS, DEFAULT_RETRIES, DEFAULT_TIMEOUT, classify_tech_type, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

logger = logging.getLogger("scraper.belong_nbn")

PROVIDER = "Belong"
URL = "https://www.belong.com.au/broadband/nbn"
DIRECT_URL = "https://www.belong.com.au/broadband/nbn"
REQUIRES_JS = False

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


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
            logger.warning("Belong fetch attempt %d/%d failed: %s", attempt, DEFAULT_RETRIES, exc)
            if attempt < DEFAULT_RETRIES:
                time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"Failed to fetch Belong NBN from {url}") from last_exc


def _parse_plans_from_soup(soup: BeautifulSoup, source_url: str) -> list[NbnPlan]:
    scraped_at = now_iso()
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise ValueError("Could not find __NEXT_DATA__ script in Belong HTML")

    data = json.loads(script.string)
    raw_plans = (
        data.get("props", {})
        .get("pageProps", {})
        .get("swrInitialCache", {})
        .get("nbnProducts", {})
        .get("plans", [])
    )

    plans = []
    seen_tiers = set()

    for p in raw_plans:
        if p.get("status") != "Active":
            continue

        down = p.get("downstreamSpeedMbps")
        up = p.get("upstreamSpeedMbps")
        if not down or not up:
            continue

        speed_tier, _, _ = normalize_nbn_speed_tier(str(down), str(up))
        if speed_tier in seen_tiers:
            continue

        base_price = float(p.get("basePrice") or p.get("price") or 0)
        current_price = float(p.get("price") or base_price)
        is_offer = p.get("isOfferProduct", False)

        has_promo = is_offer and current_price < base_price
        promo_price = current_price if has_promo else None
        regular_price = base_price if has_promo else current_price
        promo_months = int(p.get("promoDuration") or 6) if has_promo else None

        promo_end_raw = p.get("promoEndDate")
        promo_end_date = str(promo_end_raw)[:10] if promo_end_raw else None

        evening_speed = float(p.get("eveningDownstreamSpeedMbps") or down)
        display_label = p.get("displayLabel") or speed_tier

        seen_tiers.add(speed_tier)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{speed_tier} ({display_label})",
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                promo_end_date=promo_end_date,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=classify_tech_type(display_label),
                deal_channel="direct",
                deal_channel_label="Direct Public Offer",
                direct_public_promo_price=promo_price,
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
        raise RuntimeError(f"Failed to extract Belong NBN plans from {target_url}")
    return plans
