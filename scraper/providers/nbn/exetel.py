"""Exetel NBN plan scraper. Static HTML, no JS rendering needed.

Exetel sells exactly one flat-rate NBN plan (no tiers, no promo pricing --
that's their whole marketing angle), so this parser looks for that one plan
rather than iterating plan cards like the multi-tier providers.
"""
import re

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Exetel"
URL = "https://www.exetel.com.au/broadband/nbn"
REQUIRES_JS = False

PRICE_RE = re.compile(r"One Plan\.\s*\$(\d+)\.\s*(\d+)/(\d+)\s*Mbps")
TYPICAL_SPEED_RE = re.compile(r"Typical Evening Speed\s*(\d+)/(\d+)")


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    text = soup.get_text(" ", strip=True)

    price_match = PRICE_RE.search(text)
    if not price_match:
        return []

    price, down, up = price_match.groups()
    typical_match = TYPICAL_SPEED_RE.search(text)

    plan = NbnPlan(
        provider=PROVIDER,
        plan_name="The One Plan",
        price_monthly=parse_price(price),
        promo_price=None,
        promo_period_months=None,
        contract_length="No lock-in contract",
        speed_tier=f"NBN {down}/{up}",
        typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
        source_url=URL,
        scraped_at=now_iso(),
    )
    return [plan]
