"""Activ8me NBN plans scraper. Dynamic fetch via Playwright."""
import logging
import re

from bs4 import BeautifulSoup
from scraper.base import classify_tech_type, fetch_js, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

logger = logging.getLogger("scraper.activ8me_nbn")

PROVIDER = "Activ8me"
URL = "https://www.activ8me.net.au/internet/nbn-plans/"
DIRECT_URL = "https://www.activ8me.net.au/internet/nbn-plans/"
REQUIRES_JS = True

CARD_RE = re.compile(
    r"(?P<name>Premium \d+)\s*nbn[^\d]*(?P<speed>\d+/\d+)\s*Unlimited Data Allowance\*\s*\$(?P<price>[\d.]+)\s*/month"
    r"(?:.*?Anticipated Typical Evening[^\d]*(?P<evening>\d+)\s*Mbps)?",
    re.I | re.DOTALL,
)


def _parse_plans_from_soup(soup: BeautifulSoup, source_url: str) -> list[NbnPlan]:
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    for match in CARD_RE.finditer(text):
        name = match.group("name")
        speed_raw = match.group("speed")
        price_monthly = float(match.group("price"))
        evening_raw = match.group("evening")

        down, up = speed_raw.split("/")
        speed_tier, _, _ = normalize_nbn_speed_tier(down, up)

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        typical_evening = float(evening_raw) if evening_raw else float(down)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{speed_tier} ({name})",
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                promo_end_date=None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=typical_evening,
                tech_type=classify_tech_type(name),
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
    soup = fetch_js(target_url, wait_until="load", settle_ms=4000)
    plans = _parse_plans_from_soup(soup, target_url)
    if not plans:
        raise RuntimeError(f"Failed to extract Activ8me NBN plans from {target_url}")
    return plans
