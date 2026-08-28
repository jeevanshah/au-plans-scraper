"""SkyMesh NBN plans scraper. Dynamic fetch via Playwright."""
import logging
import re

from bs4 import BeautifulSoup
from scraper.base import classify_tech_type, fetch_js, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

logger = logging.getLogger("scraper.skymesh_nbn")

PROVIDER = "SkyMesh"
URL = "https://www.skymesh.net.au/nbn-services/nbn-fibre"
DIRECT_URL = "https://www.skymesh.net.au/nbn-services/nbn-fibre"
REQUIRES_JS = True

CARD_RE = re.compile(
    r"(?P<name>Fibre\s+[A-Za-z+]+)[^\$]*\$"
    r"(?P<promo>[\d.]+)\s*/month\s*\$"
    r"(?P=promo)/month for first\s*(?P<months>\d+)-months?,\s*then\s*\$"
    r"(?P<regular>[\d.]+)/month ongoing",
    re.I,
)
TYPICAL_RE = re.compile(
    r"(?:Typical Evening Speed[^\d]*|Maximum Theoretical Attainable Speeds\s*)(\d+)\s*Mbps(?:\s*(\d+)\s*Mbps)?",
    re.I,
)

TIER_NAME_MAP = {
    "Fibre Basic": ("25", "5"),
    "Fibre Plus": ("50", "20"),
    "Fibre Fast": ("100", "20"),
    "Fibre Fast+": ("500", "50"),
}


def _parse_plans_from_soup(soup: BeautifulSoup, source_url: str) -> list[NbnPlan]:
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    for match in CARD_RE.finditer(text):
        name = match.group("name").strip()
        promo_price = float(match.group("promo"))
        promo_months = int(match.group("months"))
        regular_price = float(match.group("regular"))

        start = match.start()
        end = min(start + 450, len(text))
        window = text[start:end]

        down, up = TIER_NAME_MAP.get(name, ("25", "10"))
        typ_m = TYPICAL_RE.search(window)
        evening_speed = float(typ_m.group(1)) if typ_m else float(down)

        speed_tier, _, _ = normalize_nbn_speed_tier(down, up)
        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        has_promo = promo_price < regular_price

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{speed_tier} ({name})",
                price_monthly=regular_price,
                promo_price=promo_price if has_promo else None,
                promo_period_months=promo_months if has_promo else None,
                promo_end_date=None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=classify_tech_type(name),
                deal_channel="direct",
                deal_channel_label="Direct Public Offer",
                direct_public_promo_price=promo_price if has_promo else None,
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
        raise RuntimeError(f"Failed to extract SkyMesh NBN plans from {target_url}")
    return plans
