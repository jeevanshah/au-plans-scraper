"""Exetel NBN plan scraper with Commission Factory affiliate tracking. Static HTML, no JS rendering needed.

Exetel sells exactly one flat-rate NBN plan (no tiers, no promo pricing --
that's their whole marketing angle), so this parser looks for that one plan
rather than iterating plan cards like the multi-tier providers.
Affiliate tracking routes via Commission Factory (Affiliate: 94613, Merchant: 89766).
"""
import re
import urllib.parse

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Exetel"
URL = "https://www.exetel.com.au/broadband/nbn"
REQUIRES_JS = False

AFFILIATE_BASE = "https://t.cfjump.com/94613/t/89766"


def make_affiliate_url(direct_url: str) -> str:
    return f"{AFFILIATE_BASE}?Url={urllib.parse.quote(direct_url, safe='')}"


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

    affiliate_url = make_affiliate_url(URL)

    plan = NbnPlan(
        provider=PROVIDER,
        plan_name="The One Plan",
        price_monthly=parse_price(price),
        promo_price=None,
        promo_period_months=None,
        contract_length="No lock-in contract",
        speed_tier=f"NBN {down}/{up}",
        typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
        deal_channel="affiliate",
        deal_channel_label="Exetel Partner Link",
        direct_url=URL,
        source_url=affiliate_url,
        scraped_at=now_iso(),
    )
    return [plan]
